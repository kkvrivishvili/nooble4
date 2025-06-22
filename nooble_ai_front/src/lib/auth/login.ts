import { createBrowserClient } from '@supabase/ssr'
import type { LoginCredentials, AuthResponse } from './authTypes'
import { isUserAllowed } from './restrictions'
import { trackActivity } from '@/lib/rbac/analytics'
import { acceptInvite } from '@/lib/orgs/orgActions'

export async function login({ 
  email, 
  password, 
  rememberMe,
  inviteToken,
  orgSlug
}: LoginCredentials): Promise<AuthResponse> {
  const supabase = createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      auth: {
        autoRefreshToken: true,
        persistSession: rememberMe
      }
    }
  )

  const { data, error } = await supabase.auth.signInWithPassword({
    email,
    password
  })

  if (error) {
    if (error.message.includes('Invalid login credentials')) {
      return {
        data: null,
        error: new Error('Account not found'),
        metadata: {
          shouldRedirectToSignup: true,
          message: 'Would you like to create an account?'
        }
      }
    }
    return {
      data: null,
      error
    }
  }

  if (data.user?.email) {
    if (!isUserAllowed(data.user.email)) {
      await supabase.auth.signOut()
      return {
        data: null,
        error: new Error('This email address is not authorized to access this application.'),
        metadata: {
          shouldRedirectToSignup: false,
          message: 'Please contact support if you believe this is a mistake.'
        }
      }
    }

    // Check if this is an OAuth user
    const isOAuthUser = data.user.app_metadata?.provider === 'google'

    // Only check for custom avatar if NOT an OAuth user
    if (!isOAuthUser) {
      const { data: profile } = await supabase
        .from('profiles')
        .select('avatar_url')
        .eq('id', data.user.id)
        .single()

      // If profile has custom avatar, sync it to auth metadata
      if (profile?.avatar_url) {
        await supabase.auth.updateUser({
          data: { 
            avatar_url: profile.avatar_url,
            picture: profile.avatar_url // Also update picture field for consistency
          }
        })
      }
    }

    await trackActivity({
      userId: data.user.id,
      actionType: 'login',
      metadata: {
        timestamp: new Date().toISOString(),
        rememberMe
      }
    }).catch(console.error)

    // Handle invite acceptance if token is present
    if (inviteToken && orgSlug) {
      try {
        const acceptResult = await acceptInvite(inviteToken, orgSlug)
        if (acceptResult.error) {
          return {
            data: null,
            error: new Error(acceptResult.error),
            metadata: {
              redirectTo: '/dashboard' // Fallback to dashboard if invite fails
            }
          }
        }
      } catch (inviteError) {
        console.error('Invite acceptance failed:', inviteError)
        // Continue with login but return error in metadata
        return {
          data: {
            id: data.user.id,
            email: data.user.email,
            created_at: data.user.created_at,
            updated_at: data.user.last_sign_in_at || data.user.created_at
          },
          error: null,
          metadata: {
            inviteError: 'Failed to accept organization invite',
            redirectTo: '/dashboard'
          }
        }
      }
    }

    return {
      data: {
        id: data.user.id,
        email: data.user.email,
        created_at: data.user.created_at,
        updated_at: data.user.last_sign_in_at || data.user.created_at
      },
      error: null,
      metadata: {
        redirectTo: orgSlug ? `/dashboard/orgs/${orgSlug}` : undefined
      }
    }
  }

  return {
    data: null,
    error: new Error('Login failed')
  }
}
