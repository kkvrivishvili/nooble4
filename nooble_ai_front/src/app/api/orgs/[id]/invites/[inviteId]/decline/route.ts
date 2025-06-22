import { NextResponse } from 'next/server'
import { createServerClient } from '@supabase/ssr'
import type { Database } from '@/types/supabase'
import type { NextRequest } from 'next/server'
import { handleEvent } from '@/middleware/events'
import type { EventPayload } from '@/middleware/events'

// Use same error types as main route
const INVITE_ERRORS = {
  UNAUTHORIZED: {
    code: 'invite/unauthorized',
    message: 'Not authenticated',
    status: 401
  },
  FORBIDDEN: {
    code: 'invite/forbidden',
    message: 'Not authorized to manage invites',
    status: 403
  },
  NOT_FOUND: {
    code: 'invite/not-found',
    message: 'Invite not found',
    status: 404
  },
  FAILED: {
    code: 'invite/failed',
    message: 'Failed to process invite',
    status: 500
  }
} as const

export async function POST(request: NextRequest): Promise<NextResponse> {
  const segments = request.nextUrl.pathname.split('/')
  const slug = segments[3]
  const token = segments[5]
  
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
          cookieValues.forEach(({ name, value, ...options }) => {
            response.cookies.set({ name, value, ...options })
          })
        }
      }
    }
  )

  try {
    // Auth check
    const { data: { user }, error: userError } = await supabase.auth.getUser()
    if (userError || !user) {
      return NextResponse.json(
        { error: INVITE_ERRORS.UNAUTHORIZED },
        { status: INVITE_ERRORS.UNAUTHORIZED.status }
      )
    }

    // Get org ID from slug first
    const { data: org } = await supabase
      .from('organizations')
      .select('id')
      .eq('slug', slug)
      .single()

    if (!org) {
      console.error('Organization not found:', { slug })
      return NextResponse.json(
        { error: INVITE_ERRORS.NOT_FOUND },
        { status: INVITE_ERRORS.NOT_FOUND.status }
      )
    }

    // First get the invite using the token
    const { data: invite, error: inviteError } = await supabase
      .from('organization_invites')
      .select('*')
      .eq('token', token)
      .eq('org_id', org.id)
      .single()

    if (inviteError || !invite) {
      console.error('Invite not found:', { token, orgId: org.id, error: inviteError })
      return NextResponse.json(
        { error: INVITE_ERRORS.NOT_FOUND },
        { status: INVITE_ERRORS.NOT_FOUND.status }
      )
    }

    console.log('Found invite to decline:', { 
      id: invite.id,
      token: invite.token,
      orgId: org.id,
      userEmail: user.email 
    })

    // Delete using RLS policy
    const { error: deleteError } = await supabase
      .from('organization_invites')
      .delete()
      .eq('token', token)
      .eq('org_id', org.id)
      .eq('email', user.email)

    if (deleteError) {
      console.error('Delete error:', deleteError)
      return NextResponse.json(
        { error: INVITE_ERRORS.FAILED },
        { status: INVITE_ERRORS.FAILED.status }
      )
    }

    // Track event
    await handleEvent(request, {
      userId: user.id,
      type: 'invite_declined',
      data: {
        orgId: org.id,
        inviteId: invite.id,
      },
    } satisfies EventPayload<'invite_declined'>)

    return NextResponse.json({ success: true })
  } catch (error) {
    console.error('Error declining invite:', error)
    return NextResponse.json(
      { error: INVITE_ERRORS.FAILED },
      { status: INVITE_ERRORS.FAILED.status }
    )
  }
} 