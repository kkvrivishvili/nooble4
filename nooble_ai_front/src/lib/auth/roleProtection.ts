import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'
import type { Database } from '@/types/supabase'
import type { UserRole } from '@/lib/rbac/rbacTypes'

export async function checkRole(allowedRoles: UserRole[]) {
  const cookieStore = await cookies()
  
  const supabase = createServerClient<Database>(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll: () => {
          return cookieStore.getAll().map((cookie) => ({
            name: cookie.name,
            value: cookie.value,
          }))
        },
        setAll: () => {} // Empty implementation since middleware handles it
      }
    }
  )

  const { data: { session } } = await supabase.auth.getSession()
  if (!session?.user) {
    throw new Error('Unauthorized')
  }

  const { data: role } = await supabase
    .from('roles')
    .select('role')
    .eq('user_id', session.user.id)
    .single()

  if (!role || !allowedRoles.includes(role.role)) {
    throw new Error('Forbidden')
  }

  return { user: session.user, role: role.role }
}