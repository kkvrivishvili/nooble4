import { getSupabaseBrowserClient } from '@/lib/auth/config'
import { trackActivity } from '@/lib/rbac/analytics'
import { OrgInviteSchema, InviteValidationSchema } from '@/middleware/schemas'
import type { 
  Organization, 
  OrgMember, 
  CreateOrgParams, 
  UpdateOrgParams,
  InviteMemberParams,
  OrgResponse,
  OrgInvite
} from './orgTypes'

export async function getUserOrganizations(): Promise<OrgResponse<(Organization & { organization_members: Pick<OrgMember, 'role'>[] })[]>> {
  try {
    const supabase = getSupabaseBrowserClient()
    const { data: { user } } = await supabase.auth.getUser()
    
    if (!user) throw new Error('No user found')

    const { data, error } = await supabase
      .from('organizations')
      .select(`
        *,
        organization_members!inner(role)
      `)
      .eq('organization_members.user_id', user.id)
      .order('created_at', { ascending: false })

    if (error) throw error

    await trackActivity({
      userId: user.id,
      actionType: 'organizations_viewed',
      metadata: { count: data?.length || 0 }
    })

    return { data, error: null }
  } catch (error) {
    return { data: null, error: error as Error }
  }
}

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

    const token = crypto.randomUUID()
    const expires_at = new Date()
    expires_at.setHours(expires_at.getHours() + 48)

    // Validate with schema before inserting
    const inviteData = OrgInviteSchema.parse({
      ...params,
      invited_by: user.id,
      token,
      expires_at: expires_at.toISOString()
    })

    const { error } = await supabase
      .from('organization_invites')
      .insert([inviteData])

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

export async function validateInvite(token: string): Promise<OrgResponse<OrgInvite>> {
  try {
    // Validate input with schema
    const validatedData = InviteValidationSchema.parse({ token })
    
    const supabase = getSupabaseBrowserClient()
    const { data, error } = await supabase
      .from('organization_invites')
      .select(`
        *,
        organizations (
          id,
          name,
          slug,
          avatar_url
        ),
        inviter:profiles!invited_by (
          email,
          full_name,
          avatar_url
        )
      `)
      .eq('token', validatedData.token)
      .single()

    if (error) throw error
    if (!data) throw new Error('Invite not found')

    // Check if expired
    if (new Date(data.expires_at) < new Date()) {
      throw new Error('Invite has expired')
    }

    // Check if already accepted
    if (data.accepted_at) {
      throw new Error('Invite has already been accepted')
    }

    return { data, error: null }
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