import { NextResponse } from 'next/server'
import { createServerClient } from '@supabase/ssr'
import type { Database } from '@/types/supabase'
import type { NextRequest } from 'next/server'
import { handleEvent } from '@/middleware/events'
import type { EventPayload } from '@/middleware/events'
import { Organization } from '@/lib/orgs/orgTypes'


class OrgAvatarError extends Error {
  code: string
  status: number

  constructor(code: string, message: string, status: number) {
    super(message)
    this.name = 'OrgAvatarError'
    this.code = code
    this.status = status
  }
}

const AVATAR_ERRORS = {
  UNAUTHORIZED: new OrgAvatarError(
    'org-avatar/unauthorized',
    'Not authenticated',
    401
  ),
  FORBIDDEN: new OrgAvatarError(
    'org-avatar/forbidden',
    'Not authorized to modify this organization',
    403
  ),
  INVALID_FILE: new OrgAvatarError(
    'org-avatar/invalid-file',
    'Invalid file provided',
    400
  ),
  UPDATE_FAILED: new OrgAvatarError(
    'org-avatar/update-failed',
    'Failed to update organization avatar',
    500
  ),
  DELETE_FAILED: new OrgAvatarError(
    'org-avatar/delete-failed',
    'Failed to delete organization avatar',
    500
  )
}

export async function POST(request: NextRequest): Promise<NextResponse<{ data: Organization | null, error: Error | null }>> {
  try {
    const response = NextResponse.next()
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
          setAll: (cookieValues) => {
            cookieValues.map(({ name, value, ...options }) => {
              response.cookies.set({ name, value, ...options })
            })
          }
        }
      }
    )

    const { data: { user }, error: userError } = await supabase.auth.getUser()
    console.log('Current user:', user?.id)

    if (userError || !user) {
      return NextResponse.json(
        { 
          data: null,
          error: AVATAR_ERRORS.UNAUTHORIZED 
        },
        { status: AVATAR_ERRORS.UNAUTHORIZED.status }
      )
    }

    const formData = await request.formData()
    const file = formData.get('file') as File
    const orgId = formData.get('orgId') as string

    if (!file || !orgId) {
      return NextResponse.json(
        { 
          data: null,
          error: AVATAR_ERRORS.INVALID_FILE 
        },
        { status: AVATAR_ERRORS.INVALID_FILE.status }
      )
    }

    // Check membership
    const { data: membership, error: membershipError } = await supabase
      .from('organization_members')
      .select('role')
      .eq('org_id', orgId)
      .eq('user_id', user.id)
      .single()

    console.log('Membership:', membership, 'Error:', membershipError)

    if (!membership || !['owner', 'admin'].includes(membership.role)) {
      console.log('Permission denied:', { membership, role: membership?.role })
      return NextResponse.json(
        { 
          data: null,
          error: AVATAR_ERRORS.FORBIDDEN 
        },
        { status: AVATAR_ERRORS.FORBIDDEN.status }
      )
    }

    // Upload to Supabase Storage
    const fileExt = file.name.split('.').pop()
    const fileName = `${orgId}/${orgId}.${fileExt}`

    const { error: uploadError } = await supabase.storage
      .from('OrgAvatars')
      .upload(fileName, file, {
        contentType: file.type, // Use the actual file type
        upsert: true
      })

    if (uploadError) {
      console.error('Upload error:', uploadError)
      throw uploadError
    }

    // Get the public URL
    const { data: { publicUrl: avatar_url } } = supabase.storage
      .from('OrgAvatars')
      .getPublicUrl(fileName)

    // Update the organization record
    const { data: org, error: updateError } = await supabase
      .from('organizations')
      .update({ 
        avatar_url,
        updated_at: new Date().toISOString()
      })
      .eq('id', orgId)
      .select()
      .single()

    if (updateError) throw updateError

    // Track avatar update event with new type
    await handleEvent(request, {
      userId: user.id,
      type: 'org_avatar_update',
      data: {
        orgId,
        avatarUrl: avatar_url,
        previousUrl: org?.avatar_url || null
      }
    } satisfies EventPayload<'org_avatar_update'>)

    return NextResponse.json({ 
      data: org,
      error: null
    })

  } catch (error) {
    console.error('Organization avatar upload error:', error)
    return NextResponse.json(
      { 
        data: null,
        error: AVATAR_ERRORS.UPDATE_FAILED 
      },
      { status: AVATAR_ERRORS.UPDATE_FAILED.status }
    )
  }
}

export async function DELETE(request: NextRequest): Promise<NextResponse<{ data: Organization | null, error: Error | null }>> {
  try {
    const response = NextResponse.next()
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
          setAll: (cookieValues) => {
            cookieValues.map(({ name, value, ...options }) => {
              response.cookies.set({ name, value, ...options })
            })
          }
        }
      }
    )

    const { data: { user }, error: userError } = await supabase.auth.getUser()
    if (userError || !user) {
      return NextResponse.json(
        { 
          data: null,
          error: AVATAR_ERRORS.UNAUTHORIZED 
        },
        { status: AVATAR_ERRORS.UNAUTHORIZED.status }
      )
    }

    const { searchParams } = new URL(request.url)
    const orgId = searchParams.get('orgId')

    if (!orgId) {
      return NextResponse.json(
        { 
          data: null,
          error: AVATAR_ERRORS.INVALID_FILE 
        },
        { status: AVATAR_ERRORS.INVALID_FILE.status }
      )
    }

    // Check if user is admin/owner of the org
    const { data: membership } = await supabase
      .from('organization_members')
      .select('role')
      .eq('org_id', orgId)
      .eq('user_id', user.id)
      .single()

    if (!membership || !['owner', 'admin'].includes(membership.role)) {
      return NextResponse.json(
        { 
          data: null,
          error: AVATAR_ERRORS.FORBIDDEN 
        },
        { status: AVATAR_ERRORS.FORBIDDEN.status }
      )
    }

    // Get current org to get the avatar URL
    const { data: org } = await supabase
      .from('organizations')
      .select('avatar_url')
      .eq('id', orgId)
      .single()

    if (org?.avatar_url) {
      // Extract the filename from the URL
      const fileName = org.avatar_url.split('/').pop()
      if (fileName) {
        const { error: deleteError } = await supabase.storage
          .from('OrgAvatars')
          .remove([`${orgId}/${fileName}`])

        if (deleteError) throw deleteError
      }
    }

    // Update organization record
    const { data: updatedOrg, error: updateError } = await supabase
      .from('organizations')
      .update({ 
        avatar_url: null,
        updated_at: new Date().toISOString()
      })
      .eq('id', orgId)
      .select()
      .single()

    if (updateError) throw updateError

    return NextResponse.json({ 
      data: updatedOrg,
      error: null
    })

  } catch (error) {
    console.error('Organization avatar delete error:', error)
    return NextResponse.json(
      { 
        data: null,
        error: AVATAR_ERRORS.DELETE_FAILED 
      },
      { status: AVATAR_ERRORS.DELETE_FAILED.status }
    )
  }
}