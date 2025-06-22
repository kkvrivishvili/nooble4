import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
import { authMiddleware } from '@/middleware/auth'
import { validationMiddleware } from '@/middleware/validation'
import { isAuthRoute, isProtectedRoute } from '@/middleware/routes'
import { withRateLimit } from '@/middleware/rateLimit'
import { createServerClient } from '@supabase/ssr'
import type { Database } from '@/types/supabase'
import { handleEvent } from './events'

export async function middleware(request: NextRequest) {
  // Skip middleware for static files and API routes
  if (
    request.nextUrl.pathname.startsWith('/_next') ||
    request.nextUrl.pathname.startsWith('/static') ||
    request.nextUrl.pathname.startsWith('/public') ||
    request.nextUrl.pathname.startsWith('/favicon.ico')
  ) {
    return NextResponse.next()
  }

  // Add error handling
  try {
    // Handle auth routes first
    if (isAuthRoute(request.nextUrl.pathname)) {
      return NextResponse.next()
    }

    // Run auth middleware for protected routes
    if (isProtectedRoute(request.nextUrl.pathname)) {
      const authResponse = await authMiddleware(request)
      
      // Important: Return the auth response instead of checking status
      if (authResponse instanceof NextResponse) {
        return authResponse
      }
    }

    // Settings route protection
    if (request.nextUrl.pathname.includes('/settings/')) {
      const orgSlugMatch = request.nextUrl.pathname.match(/\/orgs\/([^\/]+)/)
      if (orgSlugMatch) {
        const orgSlug = orgSlugMatch[1]
        
        // Create Supabase client
        const supabase = createServerClient<Database>(
          process.env.NEXT_PUBLIC_SUPABASE_URL!,
          process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
          {
            cookies: {
              get(name: string) {
                return request.cookies.get(name)?.value
              },
              set(name: string, value: string, options: any) {
                // We don't need to set cookies in middleware
              },
              remove(name: string, options: any) {
                // We don't need to remove cookies in middleware
              },
            },
          }
        )

        // Get the user session
        const { data: { session } } = await supabase.auth.getSession()
        if (!session?.user) {
          return NextResponse.redirect(new URL('/auth/login', request.url))
        }

        // Get user's role in the organization
        const { data: orgMember } = await supabase
          .from('organization_members')
          .select('role, organizations!inner(slug)')
          .eq('organizations.slug', orgSlug)
          .eq('user_id', session.user.id)
          .single()

        if (!orgMember) {
          return NextResponse.redirect(new URL('/dashboard', request.url))
        }

        // If member, only allow access to dangerzone
        if (orgMember.role === 'member') {
          const isDangerZone = request.nextUrl.pathname.endsWith('/dangerzone')
          if (!isDangerZone) {
            return NextResponse.redirect(
              new URL(`/dashboard/orgs/${orgSlug}/settings/dangerzone`, request.url)
            )
          }
        }
      }
    }

    // Run rate limiting for API routes
    if (request.nextUrl.pathname.startsWith('/api/')) {
      const rateLimitResponse = await withRateLimit(request, {
        actionType: request.nextUrl.pathname,
        maxRequests: 100, // Adjust based on route needs
        windowMinutes: 15
      })
      
      if (rateLimitResponse.status === 429) {
        return rateLimitResponse
      }
      
      return validationMiddleware(request)
    }

    // Handle events for specific routes
    if (request.nextUrl.pathname.startsWith('/api/events')) {
      try {
        const body = await request.json()
        return handleEvent(request, body)
      } catch (err) {
        const error = err instanceof Error ? err : new Error('Unknown error')
        console.error('Event payload error:', error.message)
        return NextResponse.json(
          { error: 'Invalid event payload' },
          { status: 400 }
        )
      }
    }

  } catch (error) {
    console.error('Middleware error:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }

  return NextResponse.next()
}

// Keep your existing config
export const config = {
  matcher: [
    /*
     * Match all paths except:
     * 1. /api routes
     * 2. /_next (Next.js internals)
     * 3. /_static (inside /public)
     * 4. /_vercel (Vercel internals)
     * 5. Static files (favicon.ico, manifest.json, robots.txt)
     */
    '/((?!api|_next|_static|_vercel|[\\w-]+\\.\\w+).*)',
  ],
}

