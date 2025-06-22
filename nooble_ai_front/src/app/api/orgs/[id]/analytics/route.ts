import { NextResponse } from 'next/server'
import { createServerClient } from '@supabase/ssr'
import type { Database } from '@/types/supabase'
import type { NextRequest } from 'next/server'
import { handleEvent } from '@/middleware/events'
import type { EventPayload } from '@/middleware/events'

// Define error types
const ANALYTICS_ERRORS = {
  UNAUTHORIZED: {
    code: 'analytics/unauthorized',
    message: 'Not authenticated',
    status: 401
  },
  FORBIDDEN: {
    code: 'analytics/forbidden',
    message: 'Not authorized to view analytics',
    status: 403
  },
  NOT_FOUND: {
    code: 'analytics/not-found',
    message: 'Organization not found',
    status: 404
  },
  FETCH_FAILED: {
    code: 'analytics/fetch-failed',
    message: 'Failed to fetch analytics',
    status: 500
  }
} as const

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  const { id: orgId } = await Promise.resolve(params)
  const response = NextResponse.next()
  
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
          cookieValues.map(({ name, value, ...options }) => {
            response.cookies.set({ name, value, ...options })
          })
        }
      }
    }
  )

  try {
    const { data: { user }, error: userError } = await supabase.auth.getUser()
    if (userError || !user) {
      return NextResponse.json(
        { error: ANALYTICS_ERRORS.UNAUTHORIZED },
        { status: ANALYTICS_ERRORS.UNAUTHORIZED.status }
      )
    }

    // Check membership directly with orgId
    const { data: membership, error: membershipError } = await supabase
      .from('organization_members')
      .select('role')
      .eq('org_id', orgId)
      .eq('user_id', user.id)
      .single()

    if (membershipError || !membership) {
      return NextResponse.json(
        { error: ANALYTICS_ERRORS.FORBIDDEN },
        { status: ANALYTICS_ERRORS.FORBIDDEN.status }
      )
    }

    // Fetch stats
    const { data: stats, error: statsError } = await supabase
      .rpc('get_org_member_stats', {
        p_org_id: orgId
      })

    if (statsError) throw statsError

    // Track analytics view event
    await handleEvent(request, {
      userId: user.id,
      type: 'analytics_view',
      data: {
        orgId
      }
    } satisfies EventPayload<'analytics_view'>)

    // Add cache headers
    const headers = new Headers()
    headers.set('Cache-Control', 's-maxage=300') // Cache for 5 minutes

    return NextResponse.json({ data: stats, error: null }, { headers })
  } catch (error) {
    console.error('Analytics fetch error:', error)
    return NextResponse.json(
      { data: null, error: ANALYTICS_ERRORS.FETCH_FAILED },
      { status: ANALYTICS_ERRORS.FETCH_FAILED.status }
    )
  }
}
