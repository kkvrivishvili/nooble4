import { NextResponse } from 'next/server'
import { createServerClient } from '@supabase/ssr'
import type { Database } from '@/types/supabase'
import type { NextRequest } from 'next/server'
import type { ProfileResponse } from '@/lib/auth/authTypes'
import { AvatarUrlSchema, ProfileUpdateSchema } from '@/middleware/schemas'
import { handleEvent } from '@/middleware/events'
import { isUserAllowed } from '@/lib/auth/restrictions'
import type { EventPayload } from '@/middleware/events'
import { ProfileUpdateParams } from '@/lib/auth/authTypes'

// Create proper error class to match ProfileResponse type
class AvatarError extends Error {
  code: string
  status: number

  constructor(code: string, message: string, status: number) {
    super(message)
    this.name = 'AvatarError'
    this.code = code
    this.status = status
  }
}

const AVATAR_ERRORS = {
  UNAUTHORIZED: new AvatarError(
    'avatar/unauthorized',
    'Not authenticated',
    401
  ),
  FORBIDDEN: new AvatarError(
    'avatar/forbidden',
    'User not allowed',
    403
  ),
  NOT_FOUND: new AvatarError(
    'avatar/not-found',
    'User record not found',
    404
  ),
  INVALID_FILE: new AvatarError(
    'avatar/invalid-file',
    'Invalid file provided',
    400
  ),
  PROFILE_ERROR: new AvatarError(
    'avatar/profile-error',
    'Failed to fetch profile',
    500
  ),
  UPLOAD_FAILED: new AvatarError(
    'avatar/upload-failed',
    'Failed to upload avatar',
    500
  ),
  UPDATE_FAILED: new AvatarError(
    'avatar/update-failed',
    'Failed to update profile',
    500
  ),
  DELETE_FAILED: new AvatarError(
    'avatar/delete-failed',
    'Failed to delete avatar',
    500
  )
} as const

const ALLOWED_FILE_TYPES = ['image/jpeg', 'image/png', 'image/webp']
const MAX_FILE_SIZE = 5 * 1024 * 1024 // 5MB

export async function POST(request: NextRequest): Promise<NextResponse<ProfileResponse>> {
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

    // Get authenticated user using getUser() instead of getSession()
    const { data: { user }, error: userError } = await supabase.auth.getUser()
    if (userError || !user) {
      return NextResponse.json(
        { data: null, error: AVATAR_ERRORS.UNAUTHORIZED },
        { status: AVATAR_ERRORS.UNAUTHORIZED.status }
      )
    }

    // Verify user is allowed
    if (!isUserAllowed(user.email!)) {
      return NextResponse.json(
        { data: null, error: AVATAR_ERRORS.FORBIDDEN },
        { status: AVATAR_ERRORS.FORBIDDEN.status }
      )
    }

    // File validation with proper error handling
    const formData = await request.formData()
    const file = formData.get('file') as File | null

    if (!file || !ALLOWED_FILE_TYPES.includes(file.type)) {
      return NextResponse.json(
        { data: null, error: AVATAR_ERRORS.INVALID_FILE },
        { status: AVATAR_ERRORS.INVALID_FILE.status }
      )
    }

    if (file.size > MAX_FILE_SIZE) {
      return NextResponse.json(
        { data: null, error: AVATAR_ERRORS.INVALID_FILE },
        { status: AVATAR_ERRORS.INVALID_FILE.status }
      )
    }

    // Get current avatar
    const { data: profile, error: profileError } = await supabase
      .from('profiles')
      .select('avatar_url')
      .eq('id', user.id)
      .single()

    if (profileError) {
      return NextResponse.json(
        { data: null, error: AVATAR_ERRORS.PROFILE_ERROR },
        { status: AVATAR_ERRORS.PROFILE_ERROR.status }
      )
    }

    // Delete old avatar if exists
    if (profile?.avatar_url?.includes('Avatars')) {
      await supabase.storage
        .from('Avatars')
        .remove([profile.avatar_url.split('Avatars/')[1]])
    }

    // Upload new avatar
    const fileName = `${user.id}/${Date.now()}-${file.name}`
    const { data: uploadData, error: uploadError } = await supabase
      .storage
      .from('Avatars')
      .upload(fileName, file, {
        cacheControl: '3600',
        upsert: false
      })

    if (uploadError) {
      return NextResponse.json(
        { data: null, error: AVATAR_ERRORS.UPLOAD_FAILED },
        { status: AVATAR_ERRORS.UPLOAD_FAILED.status }
      )
    }

    // Get public URL
    const { data: { publicUrl } } = supabase
      .storage
      .from('Avatars')
      .getPublicUrl(uploadData.path)

    // Validate URL using schema
    const urlValidation = AvatarUrlSchema.safeParse(publicUrl)
    if (!urlValidation.success) {
      await supabase.storage.from('Avatars').remove([uploadData.path])
      return NextResponse.json(
        { data: null, error: AVATAR_ERRORS.UPLOAD_FAILED },
        { status: AVATAR_ERRORS.UPLOAD_FAILED.status }
      )
    }

    // Get current profile data first
    const { data: profileData, error: profileDataError } = await supabase
      .from('profiles')
      .select('full_name, avatar_url')
      .eq('id', user.id)
      .single()

    if (profileDataError) {
      return NextResponse.json(
        { data: null, error: AVATAR_ERRORS.PROFILE_ERROR },
        { status: AVATAR_ERRORS.PROFILE_ERROR.status }
      )
    }

    // Validate profile update using ProfileUpdateParams type
    const profileValidation = ProfileUpdateSchema.safeParse({
      id: user.id,
      full_name: profileData?.full_name ?? '',
      avatar_url: publicUrl,
      updated_at: new Date().toISOString()
    } satisfies ProfileUpdateParams)

    if (!profileValidation.success) {
      await supabase.storage.from('Avatars').remove([uploadData.path])
      return NextResponse.json(
        { data: null, error: AVATAR_ERRORS.UPDATE_FAILED },
        { status: AVATAR_ERRORS.UPDATE_FAILED.status }
      )
    }

    // Update profile
    const { error: userUpdateError } = await supabase.auth.updateUser({
      data: {
        avatar_url: publicUrl
      }
    })

    if (userUpdateError) {
      await supabase.storage.from('Avatars').remove([uploadData.path])
      return NextResponse.json(
        { data: null, error: AVATAR_ERRORS.UPDATE_FAILED },
        { status: AVATAR_ERRORS.UPDATE_FAILED.status }
      )
    }

    const { data: updatedProfile, error: updateError } = await supabase
      .from('profiles')
      .update({ 
        avatar_url: publicUrl,
        updated_at: new Date().toISOString()
      })
      .eq('id', user.id)
      .select()
      .single()

    if (updateError) {
      await supabase.storage.from('Avatars').remove([uploadData.path])
      return NextResponse.json(
        { data: null, error: AVATAR_ERRORS.UPDATE_FAILED },
        { status: AVATAR_ERRORS.UPDATE_FAILED.status }
      )
    }

    // Track activity
    await handleEvent(request, {
      userId: user.id,
      type: 'avatar_update',
      data: {
        avatarUrl: publicUrl,
        previousUrl: profile?.avatar_url || null
      }
    } satisfies EventPayload<'avatar_update'>)

    return NextResponse.json({ 
      data: updatedProfile,
      error: null 
    })

  } catch (error) {
    console.error('Avatar upload error:', error)
    return NextResponse.json(
      { data: null, error: AVATAR_ERRORS.UPLOAD_FAILED },
      { status: AVATAR_ERRORS.UPLOAD_FAILED.status }
    )
  }
}

export async function DELETE(request: NextRequest): Promise<NextResponse<ProfileResponse>> {
  try {
    const response = new NextResponse()
    
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

    // Get authenticated user first
    const { data: { user }, error: userError } = await supabase.auth.getUser()
    if (userError || !user) {
      return NextResponse.json(
        { data: null, error: AVATAR_ERRORS.UNAUTHORIZED },
        { status: AVATAR_ERRORS.UNAUTHORIZED.status }
      )
    }

    // Get current avatar
    const { data: profile, error: profileError } = await supabase
      .from('profiles')
      .select('avatar_url')
      .eq('id', user.id)
      .single()

    if (profileError) {
      return NextResponse.json(
        { data: null, error: AVATAR_ERRORS.PROFILE_ERROR },
        { status: AVATAR_ERRORS.PROFILE_ERROR.status }
      )
    }

    // Delete from storage if exists
    if (profile?.avatar_url?.includes('Avatars')) {
      const { error: deleteError } = await supabase
        .storage
        .from('Avatars')
        .remove([profile.avatar_url.split('Avatars/')[1]])

      if (deleteError) {
        console.error('Storage deletion error:', deleteError)
      }
    }

    // Update profile
    const { data: updatedProfile, error: updateError } = await supabase
      .from('profiles')
      .update({ 
        avatar_url: null,
        updated_at: new Date().toISOString()
      })
      .eq('id', user.id)
      .select()
      .single()

    if (updateError) {
      return NextResponse.json(
        { data: null, error: AVATAR_ERRORS.UPDATE_FAILED },
        { status: AVATAR_ERRORS.UPDATE_FAILED.status }
      )
    }

    // Track deletion event
    await handleEvent(request, {
      userId: user.id,
      type: 'avatar_update',
      data: {
        avatarUrl: null,
        previousUrl: profile?.avatar_url || null
      }
    } satisfies EventPayload<'avatar_update'>)

    return NextResponse.json({ 
      data: updatedProfile,
      error: null 
    })

  } catch (error) {
    console.error('Avatar delete error:', error)
    return NextResponse.json(
      { data: null, error: AVATAR_ERRORS.DELETE_FAILED },
      { status: AVATAR_ERRORS.DELETE_FAILED.status }
    )
  }
}
