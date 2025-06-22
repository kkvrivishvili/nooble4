import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
import { createServerClient } from '@supabase/ssr'
import { UserDataSchema, RoleUpdateSchema, ActivitySchema, ProfileUpdateSchema, OrganizationSchema, OrgMemberSchema, OrgInviteSchema, InviteValidationSchema, InviteAcceptanceSchema } from './schemas'
import type { UserRole } from '@/lib/rbac/rbacTypes'
import { ROLE_PERMISSIONS } from '@/lib/rbac/rbacTypes'
import type { Database } from '@/types/supabase'

async function getUserRole(request: NextRequest): Promise<UserRole | null> {
  const response = NextResponse.next()
  
  const supabase = createServerClient(
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
  if (!session?.user) return null

  const { data: roleData } = await supabase
    .from('roles')
    .select('role')
    .eq('user_id', session.user.id)
    .maybeSingle()

  return roleData?.role || 'user'
}

export async function validationMiddleware(request: NextRequest) {
  const role = await getUserRole(request)
  
  // API route validation
  if (request.nextUrl.pathname.startsWith('/api/')) {
    try {
      // For multipart form data (avatar upload)
      if (request.nextUrl.pathname.startsWith('/api/profile/avatar')) {
        if (request.method === 'POST') {
          const formData = await request.formData()
          const file = formData.get('file') as File | null
          
          if (!file) {
            return NextResponse.json(
              { 
                error: {
                  message: 'No file provided',
                  code: 'validation-error'
                }
              },
              { status: 400 }
            )
          }
        }
        return NextResponse.next()
      }

      const body = await request.json()

      // Account export validation
      if (request.nextUrl.pathname.startsWith('/api/account/export')) {
        UserDataSchema.parse(body)
      }

      // Role management validation
      if (request.nextUrl.pathname.startsWith('/api/admin/roles')) {
        if (!role || !ROLE_PERMISSIONS[role].canManageRoles) {
          return NextResponse.json(
            { error: 'Unauthorized' },
            { status: 403 }
          )
        }
        RoleUpdateSchema.parse(body)
      }

      // Analytics validation
      if (request.nextUrl.pathname.startsWith('/api/analytics')) {
        if (!role || !ROLE_PERMISSIONS[role].canViewAnalytics) {
          return NextResponse.json(
            { error: 'Unauthorized' },
            { status: 403 }
          )
        }
        ActivitySchema.parse(body)
      }

      // Profile update validation
      if (request.nextUrl.pathname.startsWith('/api/profile')) {
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

        // For multipart form data (avatar upload)
        if (request.nextUrl.pathname.includes('/avatar')) {
          const formData = await request.formData()
          const file = formData.get('file') as File | null
          
          if (!file) {
            return NextResponse.json(
              { error: { message: 'No file provided', code: 'validation-error' }},
              { status: 400 }
            )
          }
        } else {
          // For regular profile updates
          const body = await request.json()
          
          // Get user session to check if OAuth
          const { data: { session } } = await supabase.auth.getSession()
          const isOAuthUser = session?.user?.app_metadata?.provider === 'google'
          
          if (isOAuthUser && 'full_name' in body && 
              body.full_name !== session.user.user_metadata.full_name) {
            return NextResponse.json(
              { 
                error: { 
                  message: 'Cannot change name for Google-linked accounts',
                  code: 'validation-error'
                }
              },
              { status: 403 }
            )
          }
          
          ProfileUpdateSchema.parse(body)
        }
      }

      // Organization and invite validation
      if (request.nextUrl.pathname.startsWith('/api/organizations') || 
          request.nextUrl.pathname.startsWith('/api/orgs')) {
        
        if (request.method === 'POST') {
          OrganizationSchema.parse(body)
        }
        
        if (request.nextUrl.pathname.includes('/members')) {
          OrgMemberSchema.parse(body)
        }
        
        // Update invite validation to handle token-based system
        if (request.nextUrl.pathname.includes('/invites')) {
          // Different validation for different operations
          if (request.method === 'POST') {
            // For creating new invites
            OrgInviteSchema.parse(body)
          } else if (request.method === 'PUT' && request.nextUrl.pathname.includes('/accept')) {
            // For accepting invites
            InviteAcceptanceSchema.parse(body)
          }
        }

        if (request.nextUrl.pathname.includes('/avatar')) {
          const formData = await request.formData()
          const file = formData.get('file') as File | null
          
          if (!file) {
            return NextResponse.json(
              { error: { message: 'No file provided', code: 'validation-error' }},
              { status: 400 }
            )
          }
        }
      }

      // Add validation for the new invite-specific endpoints
      if (request.nextUrl.pathname.startsWith('/api/invite')) {
        if (request.nextUrl.pathname.includes('/validate')) {
          // Validate query parameters for GET requests
          const { searchParams } = new URL(request.url)
          InviteValidationSchema.parse({
            token: searchParams.get('token')
          })
        } else if (request.nextUrl.pathname.includes('/accept')) {
          // Validate POST body for accept requests
          InviteAcceptanceSchema.parse(body)
        }
      }

      return NextResponse.next()
    } catch (err) {
      console.error('Validation error:', err)
      return NextResponse.json(
        { 
          error: {
            message: err instanceof Error ? err.message : 'Invalid data format',
            code: 'validation-error'
          }
        },
        { status: 400 }
      )
    }
  }

  return NextResponse.next()
} 