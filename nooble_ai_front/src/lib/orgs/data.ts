import { getSupabaseBrowserClient } from '@/lib/auth/config'
import { trackActivity } from '@/lib/rbac/analytics'
import type { 
  Organization, 
  OrgMember, 
  CreateOrgParams, 
  UpdateOrgParams,
  InviteMemberParams,
  OrgResponse 
} from './orgTypes'

export async function createOrganization(params: CreateOrgParams): Promise<OrgResponse<Organization>> {
  try {
    const supabase = getSupabaseBrowserClient()
    const { data: { user } } = await supabase.auth.getUser()
    
    if (!user) throw new Error('No user found')

    const { data, error } = await supabase
      .from('organizations')
      .insert([params])
      .select()
      .single()

    if (error) throw error

    await trackActivity({
      userId: user.id,
      actionType: 'organization_created',
      metadata: { org_id: data.id }
    })

    return { data, error: null }
  } catch (error) {
    return { data: null, error: error as Error }
  }
}

export async function updateOrganization(
  orgId: string, 
  params: UpdateOrgParams
): Promise<OrgResponse<Organization>> {
  try {
    const supabase = getSupabaseBrowserClient()
    const { data: { user } } = await supabase.auth.getUser()
    
    if (!user) throw new Error('No user found')

    const { data, error } = await supabase
      .from('organizations')
      .update(params)
      .eq('id', orgId)
      .select()
      .single()

    if (error) throw error

    await trackActivity({
      userId: user.id,
      actionType: 'organization_updated',
      metadata: { org_id: orgId }
    })

    return { data, error: null }
  } catch (error) {
    return { data: null, error: error as Error }
  }
}

export async function inviteMember(params: InviteMemberParams): Promise<OrgResponse<null>> {
  try {
    const supabase = getSupabaseBrowserClient()
    const { data: { user } } = await supabase.auth.getUser()
    
    if (!user) throw new Error('No user found')

    const { error } = await supabase
      .from('organization_invites')
      .insert([{
        ...params,
        invited_by: user.id
      }])

    if (error) throw error

    await trackActivity({
      userId: user.id,
      actionType: 'member_invited',
      metadata: { 
        org_id: params.org_id,
        invited_email: params.email
      }
    })

    return { data: null, error: null }
  } catch (error) {
    return { data: null, error: error as Error }
  }
}

export async function getOrgMembers(orgId: string): Promise<OrgResponse<OrgMember[]>> {
  try {
    const supabase = getSupabaseBrowserClient()
    const { data, error } = await supabase
      .from('organization_members')
      .select('*')
      .eq('org_id', orgId)

    if (error) throw error
    return { data, error: null }
  } catch (error) {
    return { data: null, error: error as Error }
  }
} 