import { NextResponse } from 'next/server'
import { createServerClient } from '@supabase/ssr'
import type { Database } from '@/types/supabase'
import type { NextRequest } from 'next/server'
import { handleEvent } from '@/middleware/events'
import type { EventPayload } from '@/middleware/events'
import type { OrgRole } from '@/lib/orgs/orgTypes'

// Define error types
const MEMBER_ERRORS = {
  UNAUTHORIZED: {
    code: 'member/unauthorized',
    message: 'Not authenticated',
    status: 401
  },
  FORBIDDEN: {
    code: 'member/forbidden',
    message: 'Not authorized to manage members',
    status: 403
  },
  NOT_FOUND: {
    code: 'member/not-found',
    message: 'Member not found',
    status: 404
  },
  UPDATE_FAILED: {
    code: 'member/update-failed',
    message: 'Failed to update member',
    status: 500
  },
  LAST_OWNER: {
    code: 'member/last-owner',
    message: 'Cannot change role - organization must have at least one owner',
    status: 400
  }
} as const

export async function GET(
  request: NextRequest,
  context: { params: { id: string } }
) {
  // Await the entire params object
  const params = await Promise.resolve(context.params)
  const slug = params.id
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

    // First get the org_id from the slug
    const { data: org, error: orgError } = await supabase
      .from('organizations')
      .select('id')
      .eq('slug', slug)
      .single()

    if (orgError || !org) {
      console.error('Org lookup error:', orgError)
      return NextResponse.json(
        { error: MEMBER_ERRORS.NOT_FOUND },
        { status: MEMBER_ERRORS.NOT_FOUND.status }
      )
    }

    // Then verify user has access to this org
    const { data: membership, error: membershipError } = await supabase
      .from('organization_members')
      .select('role')
      .eq('org_id', org.id)
      .eq('user_id', user.id)
      .single()

    if (membershipError) {
      console.error('Membership error:', membershipError)
    }

    if (!membership) {
      return NextResponse.json(
        { error: MEMBER_ERRORS.FORBIDDEN },
        { status: MEMBER_ERRORS.FORBIDDEN.status }
      )
    }

    // Replace the two separate queries with a single join
    const { data: members, error: membersError } = await supabase
      .from('organization_members')
      .select(`
        org_id,
        user_id,
        role,
        joined_at,
        profiles!inner (
          id,
          full_name,
          email,
          avatar_url
        )
      `)
      .eq('org_id', org.id)

    if (membersError) {
      console.error('Members fetch error:', membersError)
      throw membersError
    }

    console.log('Members data:', members)

    return NextResponse.json({ data: members, error: null })
  } catch (error) {
    console.error('Error fetching members:', error)
    return NextResponse.json(
      { data: null, error: MEMBER_ERRORS.UPDATE_FAILED },
      { status: MEMBER_ERRORS.UPDATE_FAILED.status }
    )
  }
}

export async function PUT(
  request: NextRequest,
  context: { params: { id: string } }
) {
  // Await the params first
  const params = await Promise.resolve(context.params)
  const slug = params.id
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
    const { userId, role } = await request.json()
    const newRole = role as OrgRole

    const { data: { user }, error: userError } = await supabase.auth.getUser()
    if (userError || !user) {
      return NextResponse.json(
        { error: MEMBER_ERRORS.UNAUTHORIZED },
        { status: MEMBER_ERRORS.UNAUTHORIZED.status }
      )
    }

    // First get the org_id from the slug
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

    // Check if this would remove the last owner
    if (newRole !== 'owner') {
      const { data: owners } = await supabase
        .from('organization_members')
        .select('user_id')
        .eq('org_id', org.id)
        .eq('role', 'owner')

      if (owners?.length === 1 && owners[0].user_id === userId) {
        return NextResponse.json(
          { error: MEMBER_ERRORS.LAST_OWNER },
          { status: MEMBER_ERRORS.LAST_OWNER.status }
        )
      }
    }

    // Update the member's role
    const { error: updateError } = await supabase
      .from('organization_members')
      .update({ role: newRole })
      .eq('org_id', org.id)
      .eq('user_id', userId)

    if (updateError) {
      console.error('Error updating member role:', updateError)
      return NextResponse.json(
        { error: MEMBER_ERRORS.UPDATE_FAILED },
        { status: MEMBER_ERRORS.UPDATE_FAILED.status }
      )
    }

    // Track member update event
    await handleEvent(request, {
      userId: user.id,
      type: 'member_update',
      data: {
        orgId: org.id, // Use org.id instead of params.id
        userId,
        updates: {
          role: newRole
        }
      }
    } satisfies EventPayload<'member_update'>)

    return NextResponse.json({ data: null, error: null })
  } catch (error) {
    console.error('Error updating member:', error)
    return NextResponse.json(
      { data: null, error: MEMBER_ERRORS.UPDATE_FAILED },
      { status: MEMBER_ERRORS.UPDATE_FAILED.status }
    )
  }
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  // Await params and use slug
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
    const { userId } = await request.json()

    const { data: { user }, error: userError } = await supabase.auth.getUser()
    if (userError || !user) {
      return NextResponse.json(
        { error: MEMBER_ERRORS.UNAUTHORIZED },
        { status: MEMBER_ERRORS.UNAUTHORIZED.status }
      )
    }

    // First get the org_id from the slug
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

    // Verify requester is admin/owner
    const { data: membership } = await supabase
      .from('organization_members')
      .select('role')
      .eq('org_id', org.id)  // Use org.id instead of params.id
      .eq('user_id', user.id)
      .single()

    if (!membership || !['admin', 'owner'].includes(membership.role)) {
      return NextResponse.json(
        { error: MEMBER_ERRORS.FORBIDDEN },
        { status: MEMBER_ERRORS.FORBIDDEN.status }
      )
    }

    // First delete the member
    const { error: deleteError } = await supabase
      .from('organization_members')
      .delete()
      .eq('org_id', org.id)
      .eq('user_id', userId)

    if (deleteError) throw deleteError

    // Then clean up any existing invites for this email
    const { data: memberEmail } = await supabase
      .from('profiles')
      .select('email')
      .eq('id', userId)
      .single()

    if (memberEmail?.email) {
      const { error: inviteCleanupError } = await supabase
        .from('organization_invites')
        .delete()
        .eq('org_id', org.id)
        .eq('email', memberEmail.email)

      if (inviteCleanupError) {
        console.error('Failed to cleanup invites:', inviteCleanupError)
        // Don't throw - member removal was successful
      }
    }

    // Track member removal event
    await handleEvent(request, {
      userId: user.id,
      type: 'member_remove',
      data: {
        orgId: org.id,
        userId
      }
    } satisfies EventPayload<'member_remove'>)

    return NextResponse.json({ data: null, error: null })
  } catch (error) {
    console.error('Error removing member:', error)
    return NextResponse.json(
      { data: null, error: MEMBER_ERRORS.UPDATE_FAILED },
      { status: MEMBER_ERRORS.UPDATE_FAILED.status }
    )
  }
} 