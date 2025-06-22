import { NextResponse } from 'next/server'
import { createServerClient } from '@supabase/ssr'
import type { Database } from '@/types/supabase'
import type { NextRequest } from 'next/server'
import { handleEvent } from '@/middleware/events'
import type { EventPayload } from '@/middleware/events'

// Define error types
const ORG_ERRORS = {
  UNAUTHORIZED: {
    code: 'org/unauthorized',
    message: 'Not authenticated',
    status: 401
  },
  FORBIDDEN: {
    code: 'org/forbidden',
    message: 'Not authorized to delete organization',
    status: 403
  },
  NOT_FOUND: {
    code: 'org/not-found',
    message: 'Organization not found',
    status: 404
  },
  DELETE_FAILED: {
    code: 'org/delete-failed',
    message: 'Failed to delete organization',
    status: 500
  }
} as const

export async function DELETE(
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
        { error: ORG_ERRORS.UNAUTHORIZED },
        { status: ORG_ERRORS.UNAUTHORIZED.status }
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
        { error: ORG_ERRORS.NOT_FOUND },
        { status: ORG_ERRORS.NOT_FOUND.status }
      )
    }

    // Check if user is owner
    const { data: membership } = await supabase
      .from('organization_members')
      .select('role')
      .eq('org_id', org.id)
      .eq('user_id', user.id)
      .single()

    if (!membership || membership.role !== 'owner') {
      return NextResponse.json(
        { error: ORG_ERRORS.FORBIDDEN },
        { status: ORG_ERRORS.FORBIDDEN.status }
      )
    }

    // Delete the organization - no need to check for other members
    const { error: deleteError } = await supabase
      .from('organizations')
      .delete()
      .eq('id', org.id)

    if (deleteError) throw deleteError

    // Track deletion event
    await handleEvent(request, {
      userId: user.id,
      type: 'org_delete',
      data: {
        orgId: org.id
      }
    } satisfies EventPayload<'org_delete'>)

    return NextResponse.json({ data: null, error: null })
  } catch (error) {
    console.error('Error deleting organization:', error)
    return NextResponse.json(
      { data: null, error: ORG_ERRORS.DELETE_FAILED },
      { status: ORG_ERRORS.DELETE_FAILED.status }
    )
  }
} 