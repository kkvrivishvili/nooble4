import { NextResponse } from 'next/server'
import { createServerClient } from '@supabase/ssr'
import type { Database } from '@/types/supabase'
import type { NextRequest } from 'next/server'
import { handleEvent } from '@/middleware/events'
import type { EventPayload } from '@/middleware/events'
import { Organization } from '@/lib/orgs/orgTypes'
import { OrganizationSchema } from '@/middleware/schemas'

class OrgUpdateError extends Error {
  code: string
  status: number

  constructor(code: string, message: string, status: number) {
    super(message)
    this.name = 'OrgUpdateError'
    this.code = code
    this.status = status
  }
}

const UPDATE_ERRORS = {
  UNAUTHORIZED: new OrgUpdateError(
    'org-update/unauthorized',
    'Not authenticated',
    401
  ),
  FORBIDDEN: new OrgUpdateError(
    'org-update/forbidden',
    'Not authorized to modify this organization',
    403
  ),
  SLUG_TAKEN: new OrgUpdateError(
    'org-update/slug-taken',
    'Organization URL is already taken',
    400
  ),
  UPDATE_FAILED: new OrgUpdateError(
    'org-update/failed',
    'Failed to update organization',
    500
  )
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: { id: string } }
): Promise<NextResponse<{ data: Organization | null, error: Error | null }>> {
  // Await params first
  const { id } = await Promise.resolve(params)
  
  try {
    const supabase = createServerClient<Database>(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
      {
        cookies: {
          getAll: () => {
            return request.cookies.getAll().map(cookie => ({
              name: cookie.name,
              value: cookie.value,
            }))
          },
          setAll: () => {} // We don't need to set cookies for this endpoint
        }
      }
    )

    const { data: { user }, error: userError } = await supabase.auth.getUser()
    if (userError || !user) {
      return NextResponse.json(
        { 
          data: null,
          error: UPDATE_ERRORS.UNAUTHORIZED 
        },
        { status: UPDATE_ERRORS.UNAUTHORIZED.status }
      )
    }

    // Parse and validate request body
    const body = await request.json()
    const { name, slug } = OrganizationSchema.pick({
      name: true,
      slug: true,
    }).parse(body)

    // Check if user has access to this organization
    const { data: membership } = await supabase
      .from('organization_members')
      .select('role')
      .eq('org_id', id)
      .eq('user_id', user.id)
      .single()

    if (!membership || !['owner', 'admin'].includes(membership.role)) {
      return NextResponse.json(
        { 
          data: null,
          error: UPDATE_ERRORS.FORBIDDEN 
        },
        { status: UPDATE_ERRORS.FORBIDDEN.status }
      )
    }

    // Check if slug is already taken
    const { data: existingOrg } = await supabase
      .from('organizations')
      .select('id')
      .eq('slug', slug)
      .neq('id', id)
      .single()

    if (existingOrg) {
      return NextResponse.json(
        { 
          data: null,
          error: UPDATE_ERRORS.SLUG_TAKEN 
        },
        { status: UPDATE_ERRORS.SLUG_TAKEN.status }
      )
    }

    // Update organization
    const { data: org, error: updateError } = await supabase
      .from('organizations')
      .update({ 
        name, 
        slug,
        updated_at: new Date().toISOString()
      })
      .eq('id', id)
      .select()
      .single()

    if (updateError) throw updateError

    // Track organization update event
    await handleEvent(request, {
      userId: user.id,
      type: 'org_update',
      data: {
        orgId: id,
        updates: {
          name,
          slug
        }
      }
    } satisfies EventPayload<'org_update'>)

    return NextResponse.json({ 
      data: org,
      error: null
    })

  } catch (error) {
    console.error('Organization update error:', error)
    return NextResponse.json(
      { 
        data: null,
        error: UPDATE_ERRORS.UPDATE_FAILED 
      },
      { status: UPDATE_ERRORS.UPDATE_FAILED.status }
    )
  }
} 