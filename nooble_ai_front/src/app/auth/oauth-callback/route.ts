import { NextResponse } from 'next/server'
import { createServerClient } from '@supabase/ssr'
import type { Database } from '@/types/supabase'
import type { NextRequest } from 'next/server'
import { isUserAllowed } from '@/lib/auth/restrictions'

const OAUTH_ERRORS = {
  NO_CODE: {
    code: 'auth/no-code',
    message: 'No authorization code provided',
    status: 400
  },
  EXCHANGE_FAILED: {
    code: 'auth/exchange-failed',
    message: 'Failed to exchange code for session',
    status: 500
  },
  INVALID_STATE: {
    code: 'auth/invalid-state',
    message: 'Invalid OAuth state',
    status: 400
  },
  UNAUTHORIZED: {
    code: 'auth/unauthorized',
    message: 'Email not authorized',
    status: 403
  },
  INVITE_INVALID: {
    code: 'auth/invite-invalid',
    message: 'Invalid invite token',
    status: 400
  },
  INVITE_FAILED: {
    code: 'auth/invite-failed',
    message: 'Failed to accept invite',
    status: 400
  }
} as const

function handleError(errorType: keyof typeof OAUTH_ERRORS, requestUrl: URL): NextResponse {
  const error = OAUTH_ERRORS[errorType]
  return NextResponse.redirect(
    new URL(`/auth/error?error=${error.code}`, requestUrl.origin),
    { status: error.status }
  )
}

export const dynamic = 'force-dynamic'
export const runtime = 'edge'

export async function GET(request: NextRequest) {
  const requestUrl = new URL(request.url)
  const code = requestUrl.searchParams.get('code')
  const inviteToken = requestUrl.searchParams.get('invite_token')
  const orgSlug = requestUrl.searchParams.get('org_slug')
  const next = requestUrl.searchParams.get('next') || '/dashboard'
  const codeVerifier = request.cookies.get('sb-lbrlhpjeffkoaydsnsry-auth-token-code-verifier')?.value

  console.log('OAuth Callback Debug:', {
    hasCode: !!code,
    hasCodeVerifier: !!codeVerifier,
    inviteToken,
    orgSlug,
    cookies: request.cookies.getAll().map(c => c.name),
  })

  if (!code || !codeVerifier) {
    console.error('Missing code or verifier:', { code, codeVerifier })
    return handleError('EXCHANGE_FAILED', requestUrl)
  }

  // Create response first based on flow type
  const redirectUrl = inviteToken && orgSlug
    ? `/dashboard/orgs/${orgSlug}/invite?token=${inviteToken}`
    : next

  const response = NextResponse.redirect(new URL(redirectUrl, request.url))

  const supabase = createServerClient<Database>(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll: () => request.cookies.getAll().map(cookie => ({
          name: cookie.name,
          value: cookie.value,
        })),
        setAll: (cookieValues) => {
          cookieValues.forEach(({ name, value, ...options }) => {
            response.cookies.set({ name, value, ...options })
          })
        }
      }
    }
  )

  try {
    // Exchange the code for a session
    const { data: { session }, error: exchangeError } =
      await supabase.auth.exchangeCodeForSession(code)

    if (exchangeError || !session) {
      console.error('Auth exchange error:', exchangeError)
      return handleError('EXCHANGE_FAILED', requestUrl)
    }

    // Always handle profile and role setup
    await handleProfileSetup(supabase, session.user)
    await handleRoleSetup(supabase, session.user)

    // Return the response with proper cookies set
    return response
  } catch (error) {
    console.error('OAuth callback error:', error)
    return handleError('EXCHANGE_FAILED', requestUrl)
  }
}

// Helper functions to keep the main flow clean
async function handleProfileSetup(supabase: any, user: any) {
  const { data: existingProfile } = await supabase
    .from('profiles')
    .select('avatar_url')
    .eq('id', user.id)
    .single()

  // If we have a custom avatar, update the user metadata to use it instead
  if (existingProfile?.avatar_url?.includes('Avatars')) {
    await supabase.auth.updateUser({
      data: {
        avatar_url: existingProfile.avatar_url,
        picture: existingProfile.avatar_url // Override both fields
      }
    })
  }

  const { error: profileError } = await supabase
    .from('profiles')
    .upsert({
      id: user.id,
      user_id: user.id,
      full_name: user.user_metadata.full_name || user.user_metadata.name,
      avatar_url: existingProfile?.avatar_url?.includes('Avatars')
        ? existingProfile.avatar_url
        : (user.user_metadata.avatar_url || user.user_metadata.picture),
      updated_at: new Date().toISOString()
    }, {
      onConflict: 'id'
    })

  if (profileError) {
    console.error('Profile sync failed:', profileError)
  }
}

async function handleRoleSetup(supabase: any, user: any) {
  const { data: existingRole, error: roleCheckError } = await supabase
    .from('roles')
    .select('role')
    .eq('user_id', user.id)
    .single()

  if (!existingRole && !roleCheckError) {
    const { error: insertError } = await supabase
      .from('roles')
      .insert({
        user_id: user.id,
        role: 'user',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      })
      .select()
      .single()

    if (insertError) {
      console.error('Role creation failed:', insertError)
      return
    }
  }
}