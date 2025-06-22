import { NextResponse } from 'next/server'
import { createServerClient } from '@supabase/ssr'
import type { Database } from '@/types/supabase'
import type { NextRequest } from 'next/server'
import { handleEvent } from '@/middleware/events'
import type { EventPayload } from '@/middleware/events'

const MEMBER_ERRORS = {
  UNAUTHORIZED: {
    code: 'member/unauthorized',
    message: 'Not authenticated',
    status: 401
  },
  FORBIDDEN: {
    code: 'member/forbidden',
    message: 'Not authorized to view members',
    status: 403
  },
  NOT_FOUND: {
    code: 'member/not-found',
    message: 'Organization not found',
    status: 404
  },
  FETCH_FAILED: {
    code: 'member/fetch-failed',
    message: 'Failed to fetch members',
    status: 500
  }
} as const

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  const { id: slug } = await Promise.resolve(params)
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
        { error: MEMBER_ERRORS.UNAUTHORIZED },
        { status: MEMBER_ERRORS.UNAUTHORIZED.status }
      )
    }

    // Get org_id from slug
    const { data: org, error: orgError } = await supabase
      .from('organizations')
      .select('id')
      .eq('slug', slug)
      .single()

    if (orgError || !org) {
      return NextResponse.json(
        { error: MEMBER_ERRORS.NOT_FOUND },
        { status: MEMBER_ERRORS.NOT_FOUND.status }
      )
    }

    // Check if user is a member (any role can view members)
    const { data: membership } = await supabase
      .from('organization_members')
      .select('role')
      .eq('org_id', org.id)
      .eq('user_id', user.id)
      .single()

    if (!membership) {
      return NextResponse.json(
        { error: MEMBER_ERRORS.FORBIDDEN },
        { status: MEMBER_ERRORS.FORBIDDEN.status }
      )
    }

    // Get potential owners (admins)
    const { data: members, error: membersError } = await supabase
      .from('organization_members')
      .select(`
        user_id,
        role,
        profiles (
          full_name,
          email
        )
      `)
      .eq('org_id', org.id)
      .neq('user_id', user.id)
      .in('role', ['admin', 'owner'])

    if (membersError) throw membersError

    // Track the fetch event
    await handleEvent(request, {
      userId: user.id,
      type: 'member_list',
      data: {
        orgId: org.id,
        count: members?.length ?? 0
      }
    } satisfies EventPayload<'member_list'>)

    return NextResponse.json({ data: members, error: null })
  } catch (error) {
    console.error('Error fetching potential owners:', error)
    return NextResponse.json(
      { data: null, error: MEMBER_ERRORS.FETCH_FAILED },
      { status: MEMBER_ERRORS.FETCH_FAILED.status }
    )
  }
} 