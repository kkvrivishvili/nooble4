import { NextResponse } from 'next/server'
import { createServerClient } from '@supabase/ssr'
import type { Database } from '@/types/supabase'
import type { NextRequest } from 'next/server'
import { handleEvent } from '@/middleware/events'
import { updateProfile } from '@/lib/auth/profile'

// Define possible error types
type ProfileError = {
  code: string
  message: string
  status: number
}

const PROFILE_ERRORS: Record<string, ProfileError> = {
  UNAUTHORIZED: {
    code: 'profile/unauthorized',
    message: 'Not authenticated',
    status: 401
  },
  UPDATE_FAILED: {
    code: 'profile/update-failed',
    message: 'Failed to update profile',
    status: 500
  },
  FETCH_FAILED: {
    code: 'profile/fetch-failed',
    message: 'Failed to fetch profile',
    status: 500
  }
} as const

export async function GET(request: NextRequest) {
  try {
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

    const { data: { user }, error: userError } = await supabase.auth.getUser()
    if (userError || !user) {
      return NextResponse.json(
        { error: PROFILE_ERRORS.UNAUTHORIZED },
        { status: PROFILE_ERRORS.UNAUTHORIZED.status }
      )
    }

    // Get existing profile first
    const { data: existingProfile } = await supabase
      .from('profiles')
      .select()
      .eq('id', user.id)
      .single()

    // If we have a custom avatar, ensure it's synced to user metadata
    if (existingProfile?.avatar_url?.includes('Avatars')) {
      await supabase.auth.updateUser({
        data: {
          avatar_url: existingProfile.avatar_url,
          picture: existingProfile.avatar_url
        }
      })
    }

    // Always prioritize custom avatars
    const avatarUrl = existingProfile?.avatar_url?.includes('Avatars')
      ? existingProfile.avatar_url
      : (existingProfile?.avatar_url || user.user_metadata?.avatar_url || user.user_metadata?.picture)

    // Get profile with a single query
    const { data: profile, error: profileError } = await supabase
      .from('profiles')
      .upsert({
        id: user.id,
        user_id: user.id,
        full_name: user.user_metadata.full_name,
        avatar_url: avatarUrl,
        updated_at: new Date().toISOString()
      }, {
        onConflict: 'id'
      })
      .select()
      .single()

    if (profileError) {
      return NextResponse.json(
        { error: PROFILE_ERRORS.FETCH_FAILED },
        { status: PROFILE_ERRORS.FETCH_FAILED.status }
      )
    }

    return NextResponse.json(
      { data: profile },
      {
        headers: {
          'Cache-Control': 'public, max-age=3600, stale-while-revalidate=86400',
          'Vary': 'Accept'
        }
      }
    )
  } catch (err) {
    console.error('Profile fetch error:', err)
    return NextResponse.json(
      { error: PROFILE_ERRORS.FETCH_FAILED },
      { status: PROFILE_ERRORS.FETCH_FAILED.status }
    )
  }
}

export async function PUT(request: NextRequest) {
  try {
    const data = await request.json()
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

    const { data: { user }, error: userError } = await supabase.auth.getUser()
    if (userError || !user) {
      return NextResponse.json(
        { error: PROFILE_ERRORS.UNAUTHORIZED },
        { status: PROFILE_ERRORS.UNAUTHORIZED.status }
      )
    }

    // Determine if this is an avatar update
    const isAvatarUpdate = 'avatar_url' in data
    const isOAuthUser = user.app_metadata?.provider === 'google'

    // For OAuth users, only allow avatar updates
    if (isOAuthUser && !isAvatarUpdate && data.full_name !== user.user_metadata.full_name) {
      return NextResponse.json(
        { 
          error: {
            code: 'profile/oauth-name-locked',
            message: 'Cannot change name for Google-linked accounts',
            status: 403
          }
        },
        { status: 403 }
      )
    }

    // Use new updateProfile function
    const { data: profile, error: updateError } = await updateProfile({
      id: user.id,
      ...data,
      updated_at: new Date().toISOString()
    })

    if (updateError || !profile) {
      return NextResponse.json(
        { error: PROFILE_ERRORS.UPDATE_FAILED },
        { status: PROFILE_ERRORS.UPDATE_FAILED.status }
      )
    }

    // Now TypeScript knows profile is not null
    if (isAvatarUpdate && profile.avatar_url) {
      await handleEvent(request, {
        userId: user.id,
        type: 'avatar_update',
        data: {
          avatarUrl: profile.avatar_url,
          previousUrl: data.previous_avatar_url
        }
      })
    } else {
      await handleEvent(request, {
        userId: user.id,
        type: 'profile_update',
        data: {
          updates: {
            ...data,
            updated_at: profile.updated_at ?? new Date().toISOString(),
          }
        }
      })
    }

    return NextResponse.json({ data: profile })
  } catch (err) {
    console.error('Profile update error:', err)
    return NextResponse.json(
      { error: PROFILE_ERRORS.UPDATE_FAILED },
      { status: PROFILE_ERRORS.UPDATE_FAILED.status }
    )
  }
}