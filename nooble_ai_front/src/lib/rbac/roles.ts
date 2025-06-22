import { getSupabaseBrowserClient } from '@/lib/auth/config'
import type { RoleResponse, UserWithRoleResponse } from './rbacTypes'
import { Database } from '@/types/supabase'

export async function getUserRole(userId: string): Promise<RoleResponse> {
  try {
    const supabase = getSupabaseBrowserClient()
    const { data, error } = await supabase
      .from('roles')
      .select('*')
      .eq('user_id', userId)
      .single()

    if (error) throw error
    return { data, error: null }
  } catch (error) {
    return { data: null, error: error as Error }
  }
}

export async function getUserWithRole(userId: string): Promise<UserWithRoleResponse> {
  try {
    const supabase = getSupabaseBrowserClient()
    const { data, error } = await supabase
      .from('users')
      .select(`
        *,
        role:roles(*),
        profile:profiles(*)
      `)
      .eq('id', userId)
      .single()

    if (error) throw error
    return { data, error: null }
  } catch (error) {
    return { data: null, error: error as Error }
  }
}

export async function subscribeToRoleUpdates(userId: string): Promise<RoleResponse> {
  try {
    const supabase = getSupabaseBrowserClient()
    
    // Get initial role
    const { data, error } = await supabase
      .from('roles')
      .select('*')
      .eq('user_id', userId)
      .single()

    if (error) throw error

    // Setup realtime subscription
    const subscription = supabase
      .channel(`role-updates-${userId}`)
      .on(
        'postgres_changes',
        {
          event: '*',
          schema: 'public',
          table: 'roles',
          filter: `user_id=eq.${userId}`
        },
        async (payload: { new: Database['public']['Tables']['roles']['Row'] }) => {
          if (payload.new) {
            console.log('Role updated:', payload.new.role)
            await supabase.auth.refreshSession()
          }
        }
      )
      .subscribe()

    return { data, error: null, subscription }
  } catch (error) {
    return { data: null, error: error as Error }
  }
}
