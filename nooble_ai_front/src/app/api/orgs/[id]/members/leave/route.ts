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
    message: 'Not authorized to leave organization',
    status: 403
  },
  NOT_FOUND: {
    code: 'member/not-found',
    message: 'Member not found',
    status: 404
  },
  LEAVE_FAILED: {
    code: 'member/leave-failed',
    message: 'Failed to leave organization',
    status: 500
  }
} as const

export async function POST(
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
    const { data: { user }, error: userError } = await supabase.auth.getUser()
    if (userError || !user) {
      console.error('Auth error:', userError)
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

    // Check member count first
    const { data: members, error: membersError } = await supabase
      .from('organization_members')
      .select('user_id, role')
      .eq('org_id', org.id)

    if (membersError) {
      console.error('Members lookup error:', membersError)
      return NextResponse.json(
        { error: MEMBER_ERRORS.LEAVE_FAILED },
        { status: MEMBER_ERRORS.LEAVE_FAILED.status }
      )
    }

    // Early return if only one member
    if (!members || members.length <= 1) {
      return NextResponse.json(
        { 
          error: { 
            code: 'member/sole-member',
            message: 'Cannot leave organization: You are the only member',
            status: 400
          }
        },
        { status: 400 }
      )
    }

    const currentMember = members.find(m => m.user_id === user.id)
    if (!currentMember) {
      console.error('Current user not found in members:', user.id)
      return NextResponse.json(
        { error: MEMBER_ERRORS.NOT_FOUND },
        { status: MEMBER_ERRORS.NOT_FOUND.status }
      )
    }

    let newOwnerId: string | undefined

    if (currentMember.role === 'owner' as OrgRole) {
      // Find another admin to promote to owner
      const nextOwner = members.find(
        m => m.role === 'admin' as OrgRole && m.user_id !== user.id
      )

      if (nextOwner) {
        newOwnerId = nextOwner.user_id
        // Promote next admin to owner
        const { error: updateError } = await supabase
          .from('organization_members')
          .update({ role: 'owner' as OrgRole })
          .eq('org_id', org.id)
          .eq('user_id', nextOwner.user_id)

        if (updateError) {
          console.error('Error promoting next owner:', updateError)
          throw updateError
        }
      } else {
        return NextResponse.json(
          { 
            error: { 
              ...MEMBER_ERRORS.LEAVE_FAILED, 
              message: 'Cannot leave organization: No other admin to take ownership' 
            }
          },
          { status: MEMBER_ERRORS.LEAVE_FAILED.status }
        )
      }
    }

    // Remove member
    const { error: deleteError } = await supabase
      .from('organization_members')
      .delete()
      .eq('org_id', org.id)
      .eq('user_id', user.id)

    if (deleteError) {
      console.error('Error deleting member:', deleteError)
      throw deleteError
    }

    // Track leave event
    await handleEvent(request, {
      userId: user.id,
      type: 'member_leave',
      data: {
        orgId: org.id,
        newOwnerId
      }
    } satisfies EventPayload<'member_leave'>)

    return NextResponse.json({ data: null, error: null })
  } catch (error) {
    console.error('Error leaving organization:', error)
    return NextResponse.json(
      { 
        error: { 
          ...MEMBER_ERRORS.LEAVE_FAILED,
          message: error instanceof Error ? error.message : 'Failed to leave organization'
        }
      },
      { status: MEMBER_ERRORS.LEAVE_FAILED.status }
    )
  }
} 