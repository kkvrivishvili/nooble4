import { NextResponse } from 'next/server'
import { createServerClient } from '@supabase/ssr'
import type { Database } from '@/types/supabase'
import type { NextRequest } from 'next/server'

// Define error types
const PROFILE_ERRORS = {
  UNAUTHORIZED: {
    code: 'profile/unauthorized',
    message: 'Not authenticated',
    status: 401
  },
  DELETE_FAILED: {
    code: 'profile/delete-failed',
    message: 'Failed to delete profile',
    status: 500
  } as const
}

export async function DELETE(request: NextRequest) {
  try {
    const response = new NextResponse()

    // Create client with new cookie methods
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

    // Get the user
    const { data: { user }, error: authError } = await supabase.auth.getUser()
    if (authError || !user) {
      return NextResponse.json(
        { error: PROFILE_ERRORS.UNAUTHORIZED },
        { status: PROFILE_ERRORS.UNAUTHORIZED.status }
      )
    }

    // Delete user data from database first
    const { error: dbError } = await supabase
      .from('profiles')
      .delete()
      .eq('id', user.id)

    if (dbError) {
      console.error('DB deletion error:', dbError)
      throw new Error('Failed to delete user data')
    }

    // Create service role client with new cookie methods
    const serviceRoleClient = createServerClient<Database>(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.SUPABASE_SERVICE_ROLE_KEY!,
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

    // Delete the user
    const { error: deleteError } = await serviceRoleClient.auth.admin.deleteUser(
      user.id
    )

    if (deleteError) {
      console.error('Auth deletion error:', deleteError)
      throw new Error('Failed to delete user account')
    }

    // Clear auth cookies
    const cookieOptions = {
      path: '/',
      domain: request.nextUrl.hostname,
      secure: process.env.NODE_ENV === 'production',
      maxAge: 0
    }

    response.cookies.set('sb-access-token', '', cookieOptions)
    response.cookies.set('sb-refresh-token', '', cookieOptions)
    
    return NextResponse.json({ success: true }, { status: 200 })
  } catch (error) {
    console.error('Delete account error:', error)
    return NextResponse.json(
      { error: PROFILE_ERRORS.DELETE_FAILED },
      { status: PROFILE_ERRORS.DELETE_FAILED.status }
    )
  }
}