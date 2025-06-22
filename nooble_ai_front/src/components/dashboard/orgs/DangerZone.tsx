'use client'

import { useState } from 'react'
import { useParams } from 'next/navigation'
import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '@/components/ui/AlertDialog'
import { toast } from 'sonner'
import { leaveOrganization } from '@/lib/orgs/orgActions'
import { deleteOrganization, getOrgMembersForTransfer } from '@/lib/orgs/dangerZone'
import { log } from '@/utils/logger'
import type { OrgRole, OrgMemberWithProfile } from '@/lib/orgs/orgTypes'
import { PageLoader } from '@/components/ui/PageLoader'

interface DangerZoneProps {
  currentUserId: string
  userRole: OrgRole
}

export function DangerZone({ currentUserId, userRole }: DangerZoneProps) {
  const params = useParams()
  const orgSlug = params.slug as string
  const [isLoading, setIsLoading] = useState(false)
  const [showDeletePrompt, setShowDeletePrompt] = useState(false)
  const [leaveDialogOpen, setLeaveDialogOpen] = useState(false)
  const [nextOwner, setNextOwner] = useState<OrgMemberWithProfile | null>(null)

  log.info('[DangerZone] Component mounted', { params, currentUserId, orgSlug, userRole })

  const checkIfSoleOwner = async () => {
    try {
      // First get ALL members
      const response = await fetch(`/api/orgs/${orgSlug}/members`)
      if (!response.ok) throw new Error('Failed to fetch members')
      
      const { data: members, error } = await response.json()
      if (error) throw new Error(error.message)
      
      // If no other members found (only current user)
      if (!members || members.length <= 1) {
        return { isSoleOwner: true, nextOwner: null }
      }

      // If current user is owner, check if there's another admin/owner
      if (userRole === 'owner') {
        // Look for other admins/owners among all members
        const otherAdmin = members.find((m: OrgMemberWithProfile) => 
          (m.role === 'admin' || m.role === 'owner') && m.user_id !== currentUserId
        )

        if (!otherAdmin) {
          return { 
            isSoleOwner: false, 
            nextOwner: null, 
            needsAdmin: true  // This will trigger the "promote another member" toast
          }
        }

        return {
          isSoleOwner: false,
          nextOwner: otherAdmin
        }
      }

      // For non-owners, they can always leave
      return {
        isSoleOwner: false,
        nextOwner: null
      }
    } catch (error) {
      log.error('[DangerZone] Failed to check sole owner status', { error })
      throw error
    }
  }

  const handleLeaveClick = async (e: React.MouseEvent) => {
    e.preventDefault()
    setIsLoading(true)
    try {
      const { isSoleOwner, nextOwner: newOwner, needsAdmin } = await checkIfSoleOwner()
      
      if (isSoleOwner) {
        setShowDeletePrompt(true)
      } else if (needsAdmin) {
        toast.error('Cannot leave: Please promote another member to admin first')
      } else {
        setNextOwner(newOwner)
        setLeaveDialogOpen(true)
      }
    } catch (error) {
      toast.error('Failed to check organization status')
    } finally {
      setIsLoading(false)
    }
  }

  const handleLeaveOrg = async () => {
    setIsLoading(true)
    try {
      await leaveOrganization(orgSlug)
      toast.success('Successfully left organization')
      setTimeout(() => {
        window.location.href = '/dashboard'
      }, 1000)
    } catch (error) {
      log.error('[DangerZone] Leave org failed', { error })
      toast.error('Failed to leave organization')
    } finally {
      setIsLoading(false)
      setLeaveDialogOpen(false)
    }
  }

  const handleDeleteOrg = async () => {
    setIsLoading(true)
    try {
      await deleteOrganization(orgSlug)
      toast.success('Organization deleted successfully')
      setTimeout(() => {
        window.location.href = '/dashboard'
      }, 1000)
    } catch (error) {
      log.error('[DangerZone] Delete org failed', { error })
      toast.error('Failed to delete organization')
    }
  }

  return (
    <>
      {isLoading && <PageLoader />}
      <div className="space-y-6">
        <Card>
          <CardContent className="p-6">
            <div className="space-y-4">
              {/* Leave Organization Button */}
              <AlertDialog open={leaveDialogOpen} onOpenChange={setLeaveDialogOpen}>
                <Button 
                  variant="outline"
                  className="w-full justify-start text-destructive"
                  onClick={handleLeaveClick}
                  disabled={isLoading}
                >
                  Leave Organization
                </Button>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Leave Organization?</AlertDialogTitle>
                    <AlertDialogDescription asChild>
                      <div className="space-y-4">
                        <p>
                          This will remove you from the organization. You'll lose access to all resources.
                        </p>
                        
                        {userRole === 'owner' && (
                          <div className="rounded-md bg-muted p-4">
                            {nextOwner ? (
                              <>
                                <p className="font-medium">Ownership Transfer</p>
                                <p className="text-sm text-muted-foreground mt-1">
                                  Organization ownership will be transferred to:{' '}
                                  <span className="font-medium text-foreground">
                                    {nextOwner.profiles?.full_name || nextOwner.profiles?.email || 'Unknown user'}
                                  </span>
                                </p>
                              </>
                            ) : (
                              <>
                                <p className="font-medium text-amber-600">Action Required</p>
                                <p className="text-sm text-muted-foreground mt-1">
                                  Before leaving, you must promote at least one member to admin role.
                                </p>
                              </>
                            )}
                          </div>
                        )}
                      </div>
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                    <AlertDialogAction 
                      onClick={handleLeaveOrg} 
                      disabled={isLoading}
                      className={userRole === 'owner' ? 'bg-amber-600 hover:bg-amber-700' : ''}
                    >
                      {userRole === 'owner' ? 'Transfer & Leave' : 'Leave Organization'}
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>

              {/* Delete Organization Button - Only visible to owners */}
              {userRole === 'owner' && (
                <AlertDialog open={showDeletePrompt} onOpenChange={setShowDeletePrompt}>
                  <AlertDialogTrigger asChild>
                    <Button 
                      variant="destructive"
                      className="w-full justify-start"
                    >
                      Delete Organization
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>
                        {showDeletePrompt ? 'Organization Deletion Required' : 'Delete Organization'}
                      </AlertDialogTitle>
                      <AlertDialogDescription asChild>
                        <div className="space-y-2">
                          {showDeletePrompt ? (
                            <>
                              <span>You are the only member of this organization.</span>
                              <span className="block">To leave, you must delete the organization entirely.</span>
                              <span className="block font-medium text-destructive">This action cannot be undone.</span>
                            </>
                          ) : (
                            <span>
                              This action cannot be undone. This will permanently delete the
                              organization and remove all associated data from our servers.
                            </span>
                          )}
                        </div>
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Cancel</AlertDialogCancel>
                      <AlertDialogAction 
                        onClick={handleDeleteOrg} 
                        disabled={isLoading}
                        className="bg-destructive hover:bg-destructive/90"
                      >
                        Delete Organization
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </>
  )
} 