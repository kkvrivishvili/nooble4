import { createBrowserClient } from '@supabase/ssr'
import type { SignupCredentials, AuthResponse } from './authTypes'
import { isUserAllowed } from './restrictions'
import { trackActivity } from '@/lib/rbac/analytics'
import { InviteValidationSchema } from '@/middleware/schemas'

export async function signup({ 
  email, 
  password, 
  confirmPassword,
  inviteToken,
  orgSlug 
}: SignupCredentials): Promise<AuthResponse> {
  const supabase = createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  )
  
  // Client-side validation
  if (password !== confirmPassword) {
    return {
      data: null,
      error: new Error('Passwords do not match')
    }
  }

  // Check if email is allowed before creating account
  if (!isUserAllowed(email)) {
    return {
      data: null,
      error: new Error('This email domain is not authorized to create an account.'),
      metadata: {
        shouldRedirectToSignup: false,
        message: 'Please use an authorized email address or contact support.'
      }
    }
  }

  // Validate invite token if present
  if (inviteToken && orgSlug) {
    // Use our schema for validation
    const validatedData = InviteValidationSchema.parse({ 
      token: inviteToken,
      email 
    })

    const { data: invite, error } = await supabase
      .from('organization_invites')
      .select('email, expires_at, accepted_at')
      .eq('token', validatedData.token)
      .single()

    if (error || !invite) {
      return {
        data: null,
        error: new Error('Invalid invite'),
        metadata: { redirectTo: '/auth/login' }
      }
    }

    if (new Date(invite.expires_at) < new Date()) {
      return {
        data: null,
        error: new Error('Invite has expired'),
        metadata: { redirectTo: '/auth/login' }
      }
    }

    if (invite.accepted_at) {
      return {
        data: null,
        error: new Error('Invite has already been accepted'),
        metadata: { redirectTo: '/auth/login' }
      }
    }

    if (invite.email.toLowerCase() !== email.toLowerCase()) {
      return {
        data: null,
        error: new Error('Email does not match invite'),
        metadata: { redirectTo: '/auth/login' }
      }
    }
  }

  const { data: { user }, error } = await supabase.auth.signUp({
    email,
    password,
    options: {
      emailRedirectTo: `${window.location.origin}/auth/callback?${new URLSearchParams({
        ...(inviteToken && { invite_token: inviteToken }),
        ...(orgSlug && { org_slug: orgSlug })
      })}`
    }
  })

  if (error) {
    return {
      data: null,
      error,
      metadata: {
        shouldRedirectToSignup: false,
        message: error.message
      }
    }
  }

  // Double check restrictions after successful signup
  if (user?.email && !isUserAllowed(user.email)) {
    // Clean up by deleting the unauthorized user
    await supabase.auth.admin.deleteUser(user.id)
    return {
      data: null,
      error: new Error('This email domain is not authorized to create an account.'),
      metadata: {
        shouldRedirectToSignup: false,
        message: 'Please use an authorized email address or contact support.'
      }
    }
  }

  // Map Supabase User to our UserRow type
  if (user?.email) {
    await trackActivity({
      userId: user.id,
      actionType: 'signup',
      metadata: {
        timestamp: new Date().toISOString(),
        userAgent: window.navigator.userAgent,
        hasInvite: !!inviteToken
      }
    }).catch(console.error) // Non-blocking

    return {
      data: {
        id: user.id,
        email: user.email,
        created_at: user.created_at,
        updated_at: user.last_sign_in_at || user.created_at
      },
      error: null,
      metadata: {
        message: inviteToken 
          ? 'Please check your email to verify your account. After verification, you can accept the organization invitation.'
          : 'Please check your email to verify your account.',
        redirectTo: inviteToken ? `/auth/verify-email?invite=${inviteToken}&org=${orgSlug}` : undefined
      }
    }
  }

  return {
    data: null,
    error: new Error('Account creation failed')
  }
}
