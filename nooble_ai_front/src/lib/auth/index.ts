export * from './authTypes'
export * from './login'
export * from './signup'
export * from './logout'
export * from './delete'

import { getSupabaseBrowserClient } from './config'
import type { UserRow } from '@/types/api'

export async function getCurrentUser(): Promise<UserRow | null> {
  const supabase = getSupabaseBrowserClient()
  const { data: { user } } = await supabase.auth.getUser()
  return user as UserRow | null
}

export async function getSession() {
  const supabase = getSupabaseBrowserClient()
  const { data: { session } } = await supabase.auth.getSession()
  return session
}
