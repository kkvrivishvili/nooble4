import type { OrgRole, OrgMember } from './orgTypes'
import { toast } from 'sonner'
import { InviteAcceptanceSchema } from '@/middleware/schemas'

export async function fetchMembers(orgSlug: string) {
  const response = await fetch(`/api/orgs/${orgSlug}/members`)
  if (!response.ok) {
    throw new Error('Failed to fetch members')
  }

  const { data, error } = await response.json()
  if (error) throw new Error(error.message)
  
  return data
}

export async function updateMemberRole(
  orgId: string, 
  memberId: string, 
  newRole: OrgRole
) {
  try {
    const response = await fetch(`/api/orgs/${orgId}/members`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ userId: memberId, role: newRole })
    })

    const { error } = await response.json()
    
    if (!response.ok) {
      if (error?.code === 'member/last-owner') {
        toast.error('Cannot change role - organization must have at least one owner')
      } else {
        toast.error(error?.message || 'Failed to update member role')
      }
      throw new Error(error?.message || 'Failed to update member role')
    }
    
    toast.success('Member role updated')
    return null
  } catch (error) {
    // Error toast already shown above
    throw error
  }
}

export async function removeMember(orgSlug: string, memberId: string) {
  try {
    const response = await fetch(`/api/orgs/${orgSlug}/members`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ userId: memberId })
    })

    const { data, error } = await response.json()
    
    if (!response.ok) {
      if (error?.code === 'member/last-owner') {
        toast.error('Cannot remove the last owner of the organization')
      } else if (error?.code === 'member/forbidden') {
        toast.error('You do not have permission to remove members')
      } else {
        toast.error(error?.message || 'Failed to remove member')
      }
      throw new Error(error?.message || 'Failed to remove member')
    }
    
    toast.success('Member removed successfully')
    return data
  } catch (error) {
    // Error toast already shown above
    throw error
  }
}

export async function leaveOrganization(orgSlug: string) {
  try {
    const response = await fetch(`/api/orgs/${orgSlug}/members/leave`, {
      method: 'POST'
    })

    const { data, error } = await response.json()
    
    if (!response.ok) {
      // Show a more user-friendly message based on the error
      if (error?.code === 'member/sole-member') {
        toast.error('You cannot leave as you are the only member in this organization')
      } else {
        toast.error(error?.message || 'Failed to leave organization')
      }
      throw new Error(error?.message || 'Failed to leave organization')
    }
    
    toast.success('Successfully left organization')
    return data
  } catch (error) {
    // Let the error propagate but don't show another toast
    // since we already showed one in the if (!response.ok) block
    throw error
  }
}

export async function inviteMember(
  orgSlug: string,
  email: string,
  role: Exclude<OrgRole, 'owner'>
) {
  try {
    // First get the org ID and current user's role
    const orgResponse = await fetch(`/api/orgs/${orgSlug}`)
    if (!orgResponse.ok) {
      throw new Error('Failed to fetch organization')
    }
    const { data: org } = await orgResponse.json()

    const membersResponse = await fetch(`/api/orgs/${orgSlug}/members`)
    if (!membersResponse.ok) {
      throw new Error('Failed to fetch members')
    }
    const { data: members } = await membersResponse.json() as { data: OrgMember[] }

    // Get current user from auth endpoint
    const userResponse = await fetch('/api/auth/user')
    if (!userResponse.ok) {
      throw new Error('Failed to fetch current user')
    }
    const { data: currentUser } = await userResponse.json()

    const currentUserRole = members.find((m: OrgMember) => m.user_id === currentUser.id)?.role

    if (!currentUserRole || !['admin', 'owner'].includes(currentUserRole)) {
      toast.error('Only administrators can invite new members')
      throw new Error('Insufficient permissions')
    }

    const response = await fetch(`/api/orgs/${org.id}/invites`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, role })
    })

    const { error } = await response.json()
    
    if (!response.ok) {
      if (error?.code === 'invite/already-member') {
        toast.error('User is already a member of this organization')
      } else if (error?.code === 'invite/exists') {
        toast.error('This email already has a pending invite. Check the pending invites section to manage it.')
      } else if (error?.code === 'invite/self-invite') {
        toast.error('You cannot invite yourself to an organization')
      } else {
        toast.error(error?.message || 'Failed to send invite')
      }
      throw new Error(error?.message || 'Failed to send invite')
    }
    
    toast.success('Invitation sent successfully')
    return null
  } catch (error) {
    // Error toast already shown above
    throw error
  }
}

export async function acceptInvite(inviteToken: string, orgSlug: string) {
  try {
    // First get the invite details to get orgId and inviteId
    const inviteResponse = await fetch(`/api/orgs/${orgSlug}/invites/${inviteToken}`)
    if (!inviteResponse.ok) {
      throw new Error('Failed to fetch invite details')
    }
    const { data: invite } = await inviteResponse.json()

    // Now we can call the accept endpoint with proper IDs
    const response = await fetch(
      `/api/orgs/${invite.org_id}/invites/${invite.id}/accept`, 
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      }
    )

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.error?.message || 'Failed to accept invite')
    }

    toast.success('Successfully joined organization')
    return { data: invite, error: null }
  } catch (error) {
    console.error('Accept invite error:', error)
    const errorMessage = error instanceof Error ? error.message : 'Failed to accept invite'
    toast.error(errorMessage)
    return { data: null, error: errorMessage }
  }
}

export async function declineInvite(inviteToken: string, orgSlug: string) {
  try {
    // We don't need to fetch invite details first anymore
    const response = await fetch(
      `/api/orgs/${orgSlug}/invites/${inviteToken}/decline`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      }
    )

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.error?.message || 'Failed to decline invite')
    }

    return { data: true, error: null }
  } catch (error) {
    console.error('Decline invite error:', error)
    const errorMessage = error instanceof Error ? error.message : 'Failed to decline invite'
    return { data: null, error: errorMessage }
  }
} 