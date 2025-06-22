'use client'

import { useState, useEffect } from 'react'
import { Avatar, AvatarImage, AvatarFallback } from '@/components/dashboard/profile/Avatar'
import { Button } from '@/components/ui/Button'
import { 
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from '@/components/ui/DropdownMenu'
import { MoreVertical, LogOut, UserMinus } from 'lucide-react'
import type { OrgMember, OrgRole } from '@/lib/orgs/orgTypes'
import { 
  fetchMembers,
  updateMemberRole, 
  removeMember, 
  leaveOrganization 
} from '@/lib/orgs/orgActions'

interface MembersListProps {
  orgId: string
  currentUserId: string
}

interface MemberWithProfile extends OrgMember {
  profiles: {
    id: string
    full_name: string | null
    avatar_url: string | null
    email: string | null
  } | null
}

export function MembersList({ orgId, currentUserId }: MembersListProps) {
  const [members, setMembers] = useState<MemberWithProfile[]>([])
  const [currentUserRole, setCurrentUserRole] = useState<OrgRole>()

  useEffect(() => {
    async function loadMembers() {
      try {
        const data = await fetchMembers(orgId)
        setMembers(data)
        const currentMember = data.find((member: MemberWithProfile) => member.user_id === currentUserId)
        if (currentMember) {
          setCurrentUserRole(currentMember.role)
        }
      } catch (error) {
        console.error('Error loading members:', error)
      }
    }
    loadMembers()
  }, [orgId, currentUserId])

  // Helper to check if user can manage members
  const canManageMembers = currentUserRole === 'owner' || currentUserRole === 'admin'

  // Helper to check if user can manage roles
  const canManageRoles = (member: MemberWithProfile) => {
    // Only owners can change roles
    if (currentUserRole !== 'owner') return false
    
    // Can't change your own role
    if (member.user_id === currentUserId) return false

    return true
  }

  const handleRoleUpdate = async (memberId: string, newRole: OrgRole) => {
    try {
      await updateMemberRole(orgId, memberId, newRole)
      setMembers(members.map(member => 
        member.user_id === memberId ? { ...member, role: newRole } : member
      ))
    } catch {
      // Error is handled by updateMemberRole
    }
  }

  const handleRemoveMember = async (memberId: string) => {
    try {
      await removeMember(orgId, memberId)
      setMembers(members.filter(member => member.user_id !== memberId))
    } catch {
      // Error is handled by removeMember
    }
  }

  const handleLeaveOrg = async () => {
    try {
      await leaveOrganization(orgId)
      // Only redirect after a small delay to show the success toast
      setTimeout(() => {
        window.location.href = '/dashboard'
      }, 1000)
    } catch {
      // Error toast is already handled in leaveOrganization
    }
  }

  return (
    <div className="space-y-4">
      <div className="rounded-md border border-border">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border bg-muted/50">
              <th className="p-4 text-left font-medium text-foreground">Member</th>
              <th className="p-4 text-left font-medium text-foreground">Role</th>
              <th className="p-4 text-right font-medium text-foreground">Actions</th>
            </tr>
          </thead>
          <tbody>
            {members.map((member: MemberWithProfile) => (
              <tr key={member.user_id} className="border-b border-border">
                <td className="p-4">
                  <div className="flex items-center gap-3">
                    <Avatar>
                      {member.profiles?.avatar_url && (
                        <AvatarImage 
                          src={member.profiles.avatar_url}
                          alt={member.profiles?.full_name || 'Member avatar'}
                        />
                      )}
                      <AvatarFallback>
                        {member.profiles?.full_name?.[0]?.toUpperCase() || 'U'}
                      </AvatarFallback>
                    </Avatar>
                    <div className="font-medium text-foreground">
                      {member.profiles?.full_name || member.profiles?.email || 'Unnamed Member'}
                    </div>
                  </div>
                </td>
                <td className="p-4">
                  {canManageRoles(member) ? (
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button 
                          variant="ghost"
                          size="sm" 
                          className="w-[110px] justify-start text-foreground"
                        >
                          {member.role.charAt(0).toUpperCase() + member.role.slice(1)}
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent>
                        <DropdownMenuItem 
                          onClick={() => handleRoleUpdate(member.user_id, 'owner')}
                          disabled={member.role === 'owner'}
                          className="text-foreground"
                        >
                          Owner
                        </DropdownMenuItem>
                        <DropdownMenuItem 
                          onClick={() => handleRoleUpdate(member.user_id, 'admin')}
                          disabled={member.role === 'admin'}
                          className="text-foreground"
                        >
                          Admin
                        </DropdownMenuItem>
                        <DropdownMenuItem 
                          onClick={() => handleRoleUpdate(member.user_id, 'member')}
                          disabled={member.role === 'member'}
                          className="text-foreground"
                        >
                          Member
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  ) : (
                    <span className="px-2 py-1 text-foreground">
                      {member.role.charAt(0).toUpperCase() + member.role.slice(1)}
                    </span>
                  )}
                </td>
                <td className="p-4 text-right">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button 
                        variant="ghost"
                        size="sm"
                      >
                        <MoreVertical className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      {member.user_id === currentUserId ? (
                        <DropdownMenuItem 
                          onClick={handleLeaveOrg}
                          className="text-destructive"
                        >
                          <LogOut className="mr-2 h-4 w-4" />
                          Leave organization
                        </DropdownMenuItem>
                      ) : (
                        canManageMembers && (
                          <DropdownMenuItem 
                            onClick={() => handleRemoveMember(member.user_id)}
                            className="text-destructive"
                          >
                            <UserMinus className="mr-2 h-4 w-4" />
                            Remove member
                          </DropdownMenuItem>
                        )
                      )}
                    </DropdownMenuContent>
                  </DropdownMenu>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
} 