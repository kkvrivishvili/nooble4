import { NextResponse } from 'next/server'
import { createServerClient } from '@supabase/ssr'
import type { Database } from '@/types/supabase'
import type { NextRequest } from 'next/server'
import { isUserAllowed } from '@/lib/auth/restrictions'
import { acceptInvite } from '@/lib/orgs/orgActions'
import { InviteValidationSchema } from '@/middleware/schemas'

export const dynamic = 'force-dynamic'
export const runtime = 'edge'

export async function GET(request: NextRequest) {
  const requestUrl = new URL(request.url)
  const code = requestUrl.searchParams.get('code')
  const inviteToken = requestUrl.searchParams.get('invite_token')
  const orgSlug = requestUrl.searchParams.get('org_slug')
  
  console.log('Callback Route: Received Request', {
    code: code ? 'present' : 'missing',
    allParams: Object.fromEntries(requestUrl.searchParams.entries()),
    cookies: request.cookies.getAll().map(c => c.name)
  })

  // Create response first to handle cookies
  const response = NextResponse.redirect(new URL('/dashboard', request.url))

  try {
    const supabase = createServerClient<Database>(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
      {
        auth: {
          flowType: 'pkce',
          autoRefreshToken: true,
          persistSession: true
        },
        cookies: {
          getAll: () => request.cookies.getAll().map(cookie => ({
            name: cookie.name,
            value: cookie.value,
          })),
          setAll: (cookieValues) => {
            cookieValues.map(({ name, value, ...options }) => {
              response.cookies.set({ name, value, ...options })
            })
          }
        }
      }
    )

    // Handle PKCE code exchange
    if (!code) {
      return NextResponse.redirect(new URL('/auth/error?error=no-auth-params', requestUrl.origin))
    }

    const { error: exchangeError } = await supabase.auth.exchangeCodeForSession(code)
    if (exchangeError) {
      console.error('Code exchange error:', exchangeError)
      return NextResponse.redirect(new URL('/auth/error?error=exchange-failed', requestUrl.origin))
    }

    // Get the user after authentication
    const { data: { user }, error: userError } = await supabase.auth.getUser()
    
    if (userError || !user?.email) {
      console.error('Get user error:', userError)
      return NextResponse.redirect(new URL('/auth/error?error=user-fetch-failed', requestUrl.origin))
    }

    if (!isUserAllowed(user.email)) {
      return NextResponse.redirect(new URL('/auth/error?error=unauthorized', requestUrl.origin))
    }

    // Handle invite acceptance if present
    if (inviteToken && orgSlug) {
      try {
        // Validate invite parameters
        const validatedData = InviteValidationSchema.parse({ 
          token: inviteToken,
          email: user.email // Add email validation
        })
        
        const acceptResult = await acceptInvite(validatedData.token, orgSlug)
        if (acceptResult.error) {
          console.error('Invite acceptance failed:', acceptResult.error)
          return NextResponse.redirect(
            new URL(`/auth/error?error=invite-failed&message=${encodeURIComponent(acceptResult.error)}`, requestUrl.origin)
          )
        }
        
        // Redirect to the org after successful invite acceptance
        return NextResponse.redirect(new URL(`/dashboard/orgs/${orgSlug}`, request.url))
      } catch (inviteError) {
        console.error('Failed to accept invite:', inviteError)
        // Continue with normal flow but add error parameter
        return NextResponse.redirect(
          new URL('/dashboard?invite-error=true', request.url)
        )
      }
    }

    return response
  } catch (error) {
    console.error('Auth callback error:', error)
    return NextResponse.redirect(new URL('/auth/error?error=unknown', requestUrl.origin))
  }
} 