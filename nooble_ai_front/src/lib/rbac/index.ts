export * from './rbacTypes'
export * from './analyticsTypes'
export * from './roles'
export * from './analytics'

import { getSupabaseBrowserClient } from '@/lib/auth/config'
import type { UserRole } from './rbacTypes'

export async function getCurrentUserRole(): Promise<UserRole | null> {
  const supabase = getSupabaseBrowserClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) return null

  const { data } = await supabase
    .from('roles')
    .select('role')
    .eq('user_id', user.id)
    .single()

  return data?.role || null
}

// Re-export ROLE_PERMISSIONS for hooks
export { ROLE_PERMISSIONS } from './rbacTypes'