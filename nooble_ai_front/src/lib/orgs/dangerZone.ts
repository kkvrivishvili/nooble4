import type { OrgResponse } from './orgTypes'
import type { Database } from '@/types/supabase'
import { log } from '@/utils/logger'

// Types
type OrganizationMember = Database['public']['Tables']['organization_members']['Row']
type Profile = Database['public']['Tables']['profiles']['Row']
type User = Database['public']['Tables']['users']['Row']

// Update interface to match database types
interface DangerZoneMember {
  user_id: string
  role: OrganizationMember['role']
  profiles: {
    full_name: Profile['full_name']
    email: User['email']
  } | null
}

// Add type for the raw database response
interface RawMemberData {
  user_id: string
  role: OrganizationMember['role']
  profiles: {
    full_name: string | null
    email: string | null
  } | null
}

interface TransferOwnershipParams {
  orgSlug: string
  newOwnerId: string
}

// Functions
export async function getOrgMembersForTransfer(orgSlug: string): Promise<OrgResponse<DangerZoneMember[]>> {
  try {
    const response = await fetch(`/api/orgs/${orgSlug}/members/potential-owners`)
    if (!response.ok) throw new Error('Failed to fetch potential owners')
    
    const { data, error } = await response.json()
    if (error) throw error

    return { data, error: null }
  } catch (error) {
    log.error('[DangerZone] Error in getOrgMembersForTransfer', { error })
    return { data: null, error: error as Error }
  }
}

export async function transferOwnership({ orgSlug, newOwnerId }: TransferOwnershipParams): Promise<OrgResponse<null>> {
  try {
    const response = await fetch(`/api/orgs/${orgSlug}/members/transfer`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ newOwnerId })
    })

    const { data, error } = await response.json()
    if (!response.ok) {
      throw new Error(error?.message || 'Failed to transfer ownership')
    }

    return { data: null, error: null }
  } catch (error) {
    log.error('[DangerZone] Transfer ownership failed', { error })
    return { data: null, error: error as Error }
  }
}

export async function leaveOrganization(orgSlug: string): Promise<OrgResponse<null>> {
  try {
    const response = await fetch(`/api/orgs/${orgSlug}/members/leave`, {
      method: 'POST'
    })

    const { data, error } = await response.json()
    
    if (!response.ok) {
      throw new Error(error?.message || 'Failed to leave organization')
    }

    return { data: null, error: null }
  } catch (error) {
    log.error('[DangerZone] Leave organization failed', { error })
    return { data: null, error: error as Error }
  }
}

export async function deleteOrganization(orgSlug: string): Promise<OrgResponse<null>> {
  try {
    const response = await fetch(`/api/orgs/${orgSlug}/delete`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json'
      }
    })

    const { data, error } = await response.json()
    
    if (!response.ok) {
      throw new Error(error?.message || 'Failed to delete organization')
    }

    return { data: null, error: null }
  } catch (error) {
    log.error('[DangerZone] Delete organization failed', { error })
    return { data: null, error: error as Error }
  }
} 