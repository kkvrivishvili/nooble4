import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
import { createServerClient } from '@supabase/ssr'
import type { OrgRole } from '@/lib/orgs/orgTypes'

async function getOrgRole(request: NextRequest, orgId: string): Promise<OrgRole | null> {
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

  const { data } = await supabase
    .from('organization_members')
    .select('role')
    .eq('org_id', orgId)
    .eq('user_id', session.user.id)
    .single()

  return data?.role || null
}

export function checkOrgAccess(role: OrgRole | null, action: string): boolean {
  if (!role) return false

  switch (action) {
    case 'update':
      return ['owner', 'admin'].includes(role)
    case 'delete':
      return role === 'owner'
    case 'invite':
      return ['owner', 'admin'].includes(role)
    case 'manage_members':
      return ['owner', 'admin'].includes(role)
    case 'view':
      return ['owner', 'admin', 'member'].includes(role)
    case 'access_danger_zone':
      return ['owner', 'admin', 'member'].includes(role)
    case 'delete_org':
      return role === 'owner'
    case 'leave_org':
      return ['owner', 'admin', 'member'].includes(role)
    case 'transfer_ownership':
      return role === 'owner'
    default:
      return false
  }
}

export async function orgsMiddleware(request: NextRequest) {
  try {
    // Update to handle both API patterns
    if (!request.nextUrl.pathname.startsWith('/api/organizations') && 
        !request.nextUrl.pathname.startsWith('/api/orgs')) {
      return NextResponse.next()
    }

    // Extract org ID from URL if present (handle both patterns)
    const orgIdMatch = request.nextUrl.pathname.match(/\/(organizations|orgs)\/([^\/]+)/)
    const orgId = orgIdMatch ? orgIdMatch[2] : null

    if (orgId) {
      const role = await getOrgRole(request, orgId)
      
      // Check permissions based on the action
      if (request.method === 'PUT' || request.method === 'PATCH') {
        if (!checkOrgAccess(role, 'update')) {
          return NextResponse.json({ error: 'Unauthorized' }, { status: 403 })
        }
      }
      
      if (request.method === 'DELETE') {
        if (!checkOrgAccess(role, 'delete')) {
          return NextResponse.json({ error: 'Unauthorized' }, { status: 403 })
        }
      }
      
      if (request.nextUrl.pathname.includes('/members')) {
        if (!checkOrgAccess(role, 'manage_members')) {
          return NextResponse.json({ error: 'Unauthorized' }, { status: 403 })
        }
      }
      
      if (request.nextUrl.pathname.includes('/invites')) {
        if (!checkOrgAccess(role, 'invite')) {
          return NextResponse.json({ error: 'Unauthorized' }, { status: 403 })
        }
      }

      if (request.nextUrl.pathname.includes('/settings/dangerzone')) {
        // Allow access to view the page
        if (request.method === 'GET') {
          if (!checkOrgAccess(role, 'access_danger_zone')) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 403 })
          }
        }

        // Check specific actions
        if (request.method === 'POST' || request.method === 'DELETE') {
          const action = request.nextUrl.searchParams.get('action')
          if (!checkOrgAccess(role, action || '')) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 403 })
          }
        }
      }
    }

    return NextResponse.next()
  } catch (error) {
    console.error('Orgs middleware error:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
} 