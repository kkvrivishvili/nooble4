import { NextResponse } from 'next/server'
import { createServerClient } from '@supabase/ssr'
import type { Database } from '@/types/supabase'
import type { UserRole } from '@/lib/rbac/rbacTypes'
import { ROLE_PERMISSIONS } from '@/lib/rbac/rbacTypes'

// Helper to create supabase client with consistent cookie handling
const createSupabaseClient = (request: Request) => {
  const response = NextResponse.next()
  
  return createServerClient<Database>(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll: () => {
          const cookieString = request.headers.get('cookie') || ''
          return cookieString.split(';')
            .filter(Boolean)
            .map(cookie => {
              const [name, ...rest] = cookie.trim().split('=')
              return {
                name,
                value: rest.join('=')
              }
            })
        },
        setAll: (cookieValues) => {
          cookieValues.map(({ name, value, ...options }) => {
            response.cookies.set({ name, value, ...options })
          })
        }
      }
    }
  )
}

export async function GET(request: Request) {
  try {
    const supabase = createSupabaseClient(request)
    
    // Check authentication and admin role
    const { data: { session } } = await supabase.auth.getSession()
    if (!session?.user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    // Get user's role
    const { data: roleData } = await supabase
      .from('roles')
      .select('role')
      .eq('user_id', session.user.id)
      .maybeSingle()

    const role = roleData?.role as UserRole || 'user'

    if (!ROLE_PERMISSIONS[role].canAccessAdminPanel) {
      return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
    }

    // Fetch admin dashboard data
    const [basicMetrics, detailedAnalytics] = await Promise.all([
      supabase.rpc('get_basic_metrics'),
      supabase.rpc('get_detailed_analytics')
    ])

    if (basicMetrics.error) throw basicMetrics.error
    if (detailedAnalytics.error) throw detailedAnalytics.error

    const combinedData = {
      ...basicMetrics.data,
      ...detailedAnalytics.data,
      lastUpdated: new Date().toISOString()
    }

    return NextResponse.json({ metrics: combinedData })
  } catch (err) {
    console.error('Admin route error:', err)
    return NextResponse.json(
      { error: err instanceof Error ? err.message : 'Internal server error' },
      { status: 500 }
    )
  }
}

export async function POST(request: Request) {
  try {
    const supabase = createSupabaseClient(request)
    const { action, ...data } = await request.json()

    // Check authentication and admin role
    const { data: { session } } = await supabase.auth.getSession()
    if (!session?.user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
    }

    // Get user's role
    const { data: roleData } = await supabase
      .from('roles')
      .select('role')
      .eq('user_id', session.user.id)
      .maybeSingle()

    const role = roleData?.role as UserRole || 'user'

    if (!ROLE_PERMISSIONS[role].canAccessAdminPanel) {
      return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
    }

    switch (action) {
      case 'update_user_role':
        if (!ROLE_PERMISSIONS[role].canManageRoles) {
          return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
        }
        const { userId, newRole } = data
        const { error: roleError } = await supabase
          .from('roles')
          .upsert({ user_id: userId, role: newRole })

        if (roleError) throw roleError
        return NextResponse.json({ status: 'success' })

      case 'delete_user':
        if (!ROLE_PERMISSIONS[role].canManageUsers) {
          return NextResponse.json({ error: 'Forbidden' }, { status: 403 })
        }
        const { targetUserId } = data
        const { error: deleteError } = await supabase
          .from('profiles')
          .delete()
          .eq('id', targetUserId)

        if (deleteError) throw deleteError
        return NextResponse.json({ status: 'success' })

      default:
        return NextResponse.json(
          { error: 'Invalid action' },
          { status: 400 }
        )
    }
  } catch (err) {
    console.error('Admin action error:', err)
    return NextResponse.json(
      { error: err instanceof Error ? err.message : 'Internal server error' },
      { status: 500 }
    )
  }
}