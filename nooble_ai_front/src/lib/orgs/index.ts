export * from './orgTypes'
export * from './organizations'
export * from './hooks'

import { getSupabaseBrowserClient } from '@/lib/auth/config'
import type { Organization, OrgRole } from './orgTypes'

export async function getCurrentUserOrg(): Promise<Organization | null> {
  const supabase = getSupabaseBrowserClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) return null

  const { data } = await supabase
    .from('organizations')
    .select(`
      *,
      organization_members!inner (role)
    `)
    .eq('organization_members.user_id', user.id)
    .single()

  return data
}

export async function getCurrentOrgRole(orgId: string): Promise<OrgRole | null> {
  const supabase = getSupabaseBrowserClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) return null

  const { data } = await supabase
    .from('organization_members')
    .select('role')
    .eq('org_id', orgId)
    .eq('user_id', user.id)
    .single()

  return data?.role || null
} 