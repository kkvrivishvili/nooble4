import { createServerClient } from '@supabase/ssr'
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
import { isProtectedRoute, isProfileRoute } from './routes'
import type { UserRole } from '@/lib/rbac/rbacTypes'
import { isUserAllowed } from '@/lib/auth/restrictions'
import type { Session } from '@supabase/supabase-js'
import type { Database } from '@/types/supabase'
import { checkOrgAccess } from './rbac'

type Profile = Database['public']['Tables']['profiles']['Row']

const CALLBACK_ROUTES = ['/auth/callback', '/auth/oauth-callback']

export async function authMiddleware(request: NextRequest) {
  try {
    const response = NextResponse.next()
    
    // Skip for static and public files
    if (
      request.nextUrl.pathname.startsWith('/_next') ||
      request.nextUrl.pathname.startsWith('/static') ||
      request.nextUrl.pathname.startsWith('/public')
    ) {
      return response
    }

    // Enhanced OAuth callback handling
    if (request.nextUrl.pathname === '/auth/oauth-callback') {
      const code = request.nextUrl.searchParams.get('code')
      const inviteToken = request.nextUrl.searchParams.get('invite_token')
      const orgSlug = request.nextUrl.searchParams.get('org_slug')
      
      if (code && inviteToken && orgSlug) {
        // Redirect to callback while preserving all params
        const callbackUrl = new URL('/auth/callback', request.url)
        request.nextUrl.searchParams.forEach((value, key) => {
          callbackUrl.searchParams.set(key, value)
        })
        
        // Important: Set returnUrl for after auth completion
        callbackUrl.searchParams.set('returnUrl', `/dashboard/orgs/${orgSlug}/invite?token=${inviteToken}`)
        
        return NextResponse.redirect(callbackUrl)
      }
    }

    // Allow all callback routes to complete
    if (CALLBACK_ROUTES.some(route => request.nextUrl.pathname.startsWith(route))) {
      return response
    }

    // Enhanced PKCE debug logging
    console.log('Middleware: PKCE Flow Debug', {
      path: request.nextUrl.pathname,
      hasCode: request.nextUrl.searchParams.has('code'),
      hasCodeVerifier: request.cookies.has('code_verifier'),
      allCookies: request.cookies.getAll().map(c => c.name),
      searchParams: Object.fromEntries(request.nextUrl.searchParams.entries())
    })

    const supabase = createServerClient<Database>(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
      {
        auth: {
          flowType: 'pkce',
          detectSessionInUrl: true,
          persistSession: true,
          autoRefreshToken: true,
          storage: {
            getItem: (key) => {
              const value = request.cookies.get(key)?.value
              console.log('Cookie Get:', { key, hasValue: !!value })
              return value ?? null
            },
            setItem: (key, value, options = {}) => {
              console.log('Cookie Set:', { key, hasValue: !!value })
              response.cookies.set({
                name: key,
                value,
                ...options,
                sameSite: 'lax',
                httpOnly: true,
                secure: process.env.NODE_ENV === 'production'
              })
            },
            removeItem: (key) => {
              console.log('Cookie Remove:', { key })
              response.cookies.set({
                name: key,
                value: '',
                maxAge: 0
              })
            }
          }
        },
        cookies: {
          getAll: () => {
            return request.cookies.getAll().map(cookie => ({
              name: cookie.name,
              value: cookie.value,
            }))
          },
          setAll: (cookieValues) => {
            cookieValues.map(({ name, value, ...options }) => {
              response.cookies.set({ name, value, ...options })
            })
          }
        }
      }
    )

    // Get session first
    const { data: { session }, error: sessionError } = await supabase.auth.getSession()
    
    if (sessionError) {
      console.error('Session error:', sessionError.message)
      return NextResponse.redirect(new URL('/auth/login', request.url))
    }

    // Add settings route protection
    if (request.nextUrl.pathname.includes('/settings/')) {
      if (!session) {
        return NextResponse.redirect(new URL('/auth/login', request.url))
      }

      // Get org slug from URL
      const orgSlugMatch = request.nextUrl.pathname.match(/\/orgs\/([^\/]+)/)
      if (orgSlugMatch) {
        const orgSlug = orgSlugMatch[1]
        
        // Get user's role in the organization
        const { data: orgMember } = await supabase
          .from('organization_members')
          .select('role')
          .eq('organizations.slug', orgSlug)
          .eq('user_id', session.user.id)
          .single()

        if (!orgMember) {
          return NextResponse.redirect(new URL('/dashboard', request.url))
        }

        // If user is a member, only allow access to dangerzone
        if (orgMember.role === 'member') {
          const isAccessingDangerzone = request.nextUrl.pathname.endsWith('/dangerzone')
          if (!isAccessingDangerzone) {
            return NextResponse.redirect(
              new URL(`/dashboard/orgs/${orgSlug}/settings/dangerzone`, request.url)
            )
          }
        }
      }
    }

    // Handle invite acceptance after session is established
    if (session?.user && request.nextUrl.pathname.includes('/invite')) {
      const token = request.nextUrl.searchParams.get('token')
      if (token) {
        const { data: invite } = await supabase
          .from('organization_invites')
          .select('*')
          .eq('token', token)
          .single()

        if (invite && invite.email === session.user.email) {
          // Accept invite and redirect
          await supabase.rpc('accept_invite', {
            p_invite_id: invite.id,
            p_user_id: session.user.id
          })
          
          return NextResponse.redirect(
            new URL(`/dashboard/orgs/${invite.org_id}`, request.url)
          )
        }
      }
    }

    // Handle invite flow
    if (request.nextUrl.pathname.startsWith('/auth/') && 
        request.nextUrl.searchParams.has('invite_token')) {
      const inviteToken = request.nextUrl.searchParams.get('invite_token')
      const orgSlug = request.nextUrl.searchParams.get('org_slug')
      
      // For new signups with invite
      if (request.nextUrl.pathname === '/auth/signup') {
        return NextResponse.next()
      }

      // For existing users accepting invite
      if (request.nextUrl.pathname === '/auth/login') {
        return NextResponse.next()
      }

      // After successful auth, redirect to accept invite page
      if (request.nextUrl.pathname === '/auth/callback' && inviteToken && orgSlug) {
        return NextResponse.redirect(
          new URL(`/dashboard/orgs/${orgSlug}/invite?token=${inviteToken}`, request.url)
        )
      }
    }

    // Handle all auth-related paths and magic links
    if (request.nextUrl.searchParams.has('code') || 
        request.nextUrl.pathname.startsWith('/auth/')) {
      
      const token = request.nextUrl.searchParams.get('token')
      const code = request.nextUrl.searchParams.get('code')
      
      console.log('Middleware: Auth Flow', {
        path: request.nextUrl.pathname,
        token: token ? 'present' : 'missing',
        code: code ? 'present' : 'missing',
        allParams: Object.fromEntries(request.nextUrl.searchParams.entries()),
        cookies: request.cookies.getAll().map(c => c.name)
      })

      // For magic links with PKCE
      if (request.nextUrl.searchParams.get('type') === 'magiclink') {
        const callbackUrl = new URL('/auth/callback', request.url)
        // Preserve all search params
        request.nextUrl.searchParams.forEach((value, key) => {
          callbackUrl.searchParams.set(key, value)
        })
        return NextResponse.redirect(callbackUrl)
      }

      // For OAuth callbacks
      if (request.nextUrl.pathname === '/auth/oauth-callback' && code) {
        return NextResponse.redirect(new URL(`/auth/callback?code=${code}`, request.url))
      }

      // For any other code-based auth
      if (code && !request.nextUrl.pathname.startsWith('/auth/callback')) {
        const callbackUrl = new URL('/auth/callback', request.url)
        request.nextUrl.searchParams.forEach((value, key) => {
          callbackUrl.searchParams.set(key, value)
        })
        return NextResponse.redirect(callbackUrl)
      }
    }

    // Inside authMiddleware function
    if (request.nextUrl.pathname === '/invite') {
      const token = request.nextUrl.searchParams.get('token')
      if (!token) {
        return NextResponse.redirect(new URL('/auth/login', request.url))
      }

      // Allow access to invite page without auth
      return NextResponse.next()
    }

    // Track activity for authenticated users
    if (session?.user) {
      const lastActivity = request.cookies.get('last_activity')?.value
      const currentPath = request.nextUrl.pathname

      // Only track if this is a new path or first activity
      if (!lastActivity || lastActivity !== currentPath) {
        await supabase.from('user_activity').insert({
          user_id: session.user.id,
          action_type: lastActivity ? 'page_view' : 'login',
          metadata: {
            path: currentPath,
            timestamp: new Date().toISOString()
          },
          user_agent: request.headers.get('user-agent'),
          ip_address: request.headers.get('x-forwarded-for')
        })

        // Update last activity cookie
        response.cookies.set({
          name: 'last_activity',
          value: currentPath,
          maxAge: 60 * 60 * 24, // 24 hours
          path: '/'
        })
      }
    }

    // Check session expiry
    if (session?.expires_at) {
      const expiresAt = new Date(session.expires_at * 1000)
      const now = new Date()

      if (expiresAt <= now || (expiresAt.getTime() - now.getTime()) < 5 * 60 * 1000) {
        try {
          const { data: { session: newSession }, error: refreshError } = 
            await supabase.auth.refreshSession()
          
          if (refreshError || !newSession) {
            throw refreshError || new Error('Failed to refresh session')
          }
        } catch (error) {
          console.error('Session refresh failed:', error)
          return NextResponse.redirect(new URL('/auth/login', request.url))
        }
      }
    }

    // Get user's role if session exists
    let userRole: UserRole | null = null
    if (session?.user) {
      const { data: roleData } = await supabase
        .from('roles')
        .select('role')
        .eq('user_id', session.user.id)
        .maybeSingle()
      
      userRole = roleData?.role || 'user'
    }

    // Handle protected routes
    if (isProtectedRoute(request.nextUrl.pathname)) {
      if (!session) {
        const redirectUrl = new URL('/auth/login', request.url)
        // Preserve the original URL to redirect back after login
        redirectUrl.searchParams.set('returnUrl', request.nextUrl.pathname)
        return NextResponse.redirect(redirectUrl)
      }

      // Verify user exists and is allowed
      const { data: { user }, error: userError } = await supabase.auth.getUser()
      if (userError || !user || !isUserAllowed(user.email!)) {
        clearAuthCookies(response)
        return NextResponse.redirect(new URL('/auth/login', request.url))
      }

      // Verify database record exists
      const { error: dbError } = await supabase
        .from('users')
        .select('id')
        .eq('id', user.id)
        .single()

      if (dbError) {
        clearAuthCookies(response)
        return NextResponse.redirect(new URL('/auth/login', request.url))
      }

      // Add role to headers
      if (userRole) {
        response.headers.set('x-user-role', userRole)
      }
    }

    // Profile route handling
    if (isProfileRoute(request.nextUrl.pathname)) {
      if (!session) {
        const callbackUrl = encodeURIComponent(request.nextUrl.pathname)
        return NextResponse.redirect(
          new URL(`/auth/login?callbackUrl=${callbackUrl}`, request.url)
        )
      }

      const { data: profile } = await supabase
        .from('profiles')
        .select('*')
        .eq('id', session.user.id)
        .single()

      // Enhanced avatar sync logic
      const avatarSync = async (
        session: Session, 
        profile: Profile | null
      ) => {
        const isOAuthUser = session.user.app_metadata?.provider === 'google'
        const oauthPicture = session.user.user_metadata?.picture
        const currentAvatar = profile?.avatar_url
        
        // Case 1: New OAuth user, no profile
        if (isOAuthUser && !profile) {
          return await supabase.from('profiles').upsert({
            id: session.user.id,
            user_id: session.user.id,
            full_name: session.user.user_metadata.full_name,
            avatar_url: oauthPicture,
            updated_at: new Date().toISOString()
          })
        }
        
        // Case 2: Existing profile with custom avatar
        if (currentAvatar && currentAvatar !== session.user.user_metadata?.avatar_url) {
          return await supabase.auth.updateUser({
            data: { 
              avatar_url: currentAvatar,
              picture: currentAvatar 
            }
          })
        }
        
        // Case 3: OAuth user without custom avatar
        if (isOAuthUser && !currentAvatar && oauthPicture) {
          return await supabase.from('profiles').upsert({
            id: session.user.id,
            avatar_url: oauthPicture,
            updated_at: new Date().toISOString()
          })
        }
      }

      await avatarSync(session, profile)

      if (!profile && !request.nextUrl.pathname.includes('/profile/setup')) {
        return NextResponse.redirect(new URL('/dashboard/profile/setup', request.url))
      }
    }

    // Add org role checks
    if (request.nextUrl.pathname.startsWith('/dashboard/orgs/')) {
      if (!session) {
        const callbackUrl = encodeURIComponent(request.nextUrl.pathname)
        return NextResponse.redirect(
          new URL(`/auth/login?callbackUrl=${callbackUrl}`, request.url)
        )
      }

      const orgSlugMatch = request.nextUrl.pathname.match(/\/orgs\/([^\/]+)/)
      if (orgSlugMatch) {
        const orgSlug = orgSlugMatch[1]
        const { data: orgMember } = await supabase
          .from('organization_members')
          .select('role, organizations!inner(slug)')
          .eq('organizations.slug', orgSlug)
          .eq('user_id', session.user.id)
          .single()

        if (!orgMember) {
          return NextResponse.redirect(new URL('/dashboard', request.url))
        }

        // Check permissions based on role and path
        if (!checkOrgAccess(orgMember.role, request.nextUrl.pathname)) {
          return NextResponse.redirect(new URL('/dashboard', request.url))
        }

        // Add org role to headers for use in components
        response.headers.set('x-org-role', orgMember.role)
      }
    }

    return response
  } catch (error) {
    console.error('Auth middleware error:', error)
    return NextResponse.next()
  }
}

function clearAuthCookies(response: NextResponse) {
  response.cookies.set({
    name: 'sb-access-token',
    value: '',
    maxAge: 0,
  })
  response.cookies.set({
    name: 'sb-refresh-token',
    value: '',
    maxAge: 0,
  })
}
