import { NextResponse } from 'next/server'
import { createServerClient } from '@supabase/ssr'
import type { Database } from '@/types/supabase'
import type { NextRequest } from 'next/server'
import { slugify } from '@/utils/slugify'

// Define error types
type OrgError = {
  code: string
  message: string
  status: number
}

const ORG_ERRORS: Record<string, OrgError> = {
  UNAUTHORIZED: {
    code: 'orgs/unauthorized',
    message: 'Not authenticated',
    status: 401
  },
  FETCH_FAILED: {
    code: 'orgs/fetch-failed',
    message: 'Failed to fetch organizations',
    status: 500
  },
  CREATE_FAILED: {
    code: 'orgs/create-failed', 
    message: 'Failed to create organization',
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

    const { data: { session } } = await supabase.auth.getSession()
    
    if (!session) {
      return NextResponse.json(
        { error: ORG_ERRORS.UNAUTHORIZED },
        { status: ORG_ERRORS.UNAUTHORIZED.status }
      )
    }

    const { data: orgs, error } = await supabase
      .from('organizations')
      .select(`
        *,
        organization_members!inner(role)
      `)
      .eq('organization_members.user_id', session.user.id)

    if (error) {
      console.error('Fetch orgs error:', error)
      return NextResponse.json(
        { error: ORG_ERRORS.FETCH_FAILED },
        { status: ORG_ERRORS.FETCH_FAILED.status }
      )
    }

    return NextResponse.json({ data: orgs })
  } catch (err) {
    console.error('Organizations error:', err)
    return NextResponse.json(
      { error: ORG_ERRORS.FETCH_FAILED },
      { status: ORG_ERRORS.FETCH_FAILED.status }
    )
  }
}

export async function POST(request: NextRequest) {
  try {
    const supabase = createServerClient<Database>(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
      {
        cookies: {
          getAll: () => request.cookies.getAll().map(cookie => ({
            name: cookie.name,
            value: cookie.value,
          })),
          setAll: () => {}
        }
      }
    )

    const { data: { user }, error: userError } = await supabase.auth.getUser()
    if (userError || !user) throw userError || new Error('No user found')

    const body = await request.json()

    const { data: org, error: orgError } = await supabase
      .rpc('create_organization_with_owner', {
        p_name: body.name,
        p_slug: body.slug || slugify(body.name),
        p_avatar_url: body.avatar_url || null,
        p_user_id: user.id
      })
      .single()

    if (orgError) {
      console.error('Create org error:', orgError)
      if (orgError.code === '23505') {
        return NextResponse.json(
          { 
            error: {
              code: 'orgs/duplicate',
              message: 'An organization with this slug already exists',
              status: 409
            }
          },
          { status: 409 }
        )
      }
      throw orgError
    }

    return NextResponse.json({ data: org })
  } catch (err) {
    console.error('Create organization error:', err)
    return NextResponse.json(
      { 
        error: {
          code: 'orgs/create-failed',
          message: err instanceof Error ? err.message : 'Failed to create organization',
          status: 500
        }
      },
      { status: 500 }
    )
  }
}