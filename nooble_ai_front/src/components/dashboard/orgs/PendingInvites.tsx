'use client'

import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/Button'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '@/components/ui/AlertDialog'
import { toast } from 'sonner'
import type { OrgInvite } from '@/lib/orgs/orgTypes'

interface PendingInvitesProps {
  orgId: string
}

export function PendingInvites({ orgId }: PendingInvitesProps) {
  const [invites, setInvites] = useState<OrgInvite[]>([])
  const [isLoading, setIsLoading] = useState(true)

  // Add loading state for individual actions
  const [loadingInviteId, setLoadingInviteId] = useState<string | null>(null)

  async function fetchInvites() {
    try {
      const response = await fetch(`/api/orgs/${orgId}/invites`)
      if (!response.ok) {
        const { error } = await response.json()
        switch (error?.code) {
          case 'invite/unauthorized':
            toast.error('Please sign in to view invites')
            break
          case 'invite/forbidden':
            toast.error('You don\'t have permission to view invites')
            break
          default:
            toast.error('Failed to load pending invites')
        }
        throw new Error(error?.message || 'Failed to fetch invites')
      }
      const { data } = await response.json()
      setInvites(data || [])
    } catch (error) {
      console.error('Error fetching invites:', error)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchInvites()
  }, [orgId])

  async function cancelInvite(inviteId: string) {
    setLoadingInviteId(inviteId)
    try {
      const response = await fetch(`/api/orgs/${orgId}/invites/${inviteId}`, {
        method: 'DELETE'
      })

      const { error } = await response.json()
      
      if (!response.ok) {
        switch (error?.code) {
          case 'invite/unauthorized':
            toast.error('You need to be signed in to cancel invites')
            break
          case 'invite/forbidden':
            toast.error('You don\'t have permission to cancel invites')
            break
          case 'invite/not-found':
            toast.error('This invite no longer exists')
            setInvites(invites.filter(invite => invite.id !== inviteId))
            break
          default:
            toast.error('Failed to cancel invitation')
        }
        throw new Error(error?.message || 'Failed to cancel invite')
      }

      // Immediately update local state
      setInvites(prevInvites => prevInvites.filter(invite => invite.id !== inviteId))
      toast.success('Invitation cancelled successfully')
    } catch (error) {
      console.error('Error cancelling invite:', error)
    } finally {
      setLoadingInviteId(null)
    }
  }

  async function resendInvite(inviteId: string) {
    try {
      const response = await fetch(`/api/orgs/${orgId}/invites/${inviteId}/resend`, {
        method: 'POST'
      })

      const { error } = await response.json()
      
      if (!response.ok) {
        switch (error?.code) {
          case 'invite/unauthorized':
            toast.error('You need to be signed in to resend invites')
            break
          case 'invite/forbidden':
            toast.error('You don\'t have permission to resend invites')
            break
          case 'invite/not-found':
            toast.error('This invite no longer exists')
            setInvites(invites.filter(invite => invite.id !== inviteId))
            break
          case 'invite/email-failed':
            toast.warning('Invite updated but email delivery failed. You can try resending again.')
            break
          default:
            toast.error('Failed to resend invitation')
        }
        throw new Error(error?.message || 'Failed to resend invite')
      }
      
      toast.success('Invitation resent successfully', {
        description: 'A new email has been sent to the invitee.'
      })
    } catch (error) {
      console.error('Error resending invite:', error)
    }
  }

  if (isLoading) {
    return <div className="text-muted-foreground">Loading invites...</div>
  }

  if (invites.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        No pending invitations
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="rounded-md border border-border">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border bg-muted/50">
              <th className="p-4 text-left font-medium text-foreground">Email</th>
              <th className="p-4 text-left font-medium text-foreground">Role</th>
              <th className="p-4 text-left font-medium text-foreground">Expires</th>
              <th className="p-4 text-right font-medium text-foreground">Actions</th>
            </tr>
          </thead>
          <tbody>
            {invites.map((invite) => (
              <tr key={invite.id} className="border-b border-border">
                <td className="p-4">
                  <div className="font-medium text-foreground">{invite.email}</div>
                </td>
                <td className="p-4 capitalize text-foreground">{invite.role}</td>
                <td className="p-4 text-muted-foreground">
                  {new Date(invite.expires_at).toLocaleDateString()}
                </td>
                <td className="p-4 text-right">
                  <div className="flex justify-end gap-2">
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button
                          variant="outline"
                          size="sm"
                          isLoading={isLoading}
                        >
                          Resend
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent variant="primary">
                        <AlertDialogHeader>
                          <AlertDialogTitle>Resend Invitation</AlertDialogTitle>
                          <AlertDialogDescription>
                            Are you sure you want to resend the invitation to {invite.email}?
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel asChild>
                            <Button variant="outline">
                              Cancel
                            </Button>
                          </AlertDialogCancel>
                          <AlertDialogAction asChild>
                            <Button 
                              variant="primary"
                              onClick={() => resendInvite(invite.id)}
                              isLoading={isLoading}
                            >
                              Resend Invite
                            </Button>
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>

                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button
                          variant="destructive"
                          size="sm"
                          isLoading={loadingInviteId === invite.id}
                        >
                          Cancel
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent variant="destructive">
                        <AlertDialogHeader>
                          <AlertDialogTitle>Cancel Invitation</AlertDialogTitle>
                          <AlertDialogDescription>
                            Are you sure you want to cancel the invitation for {invite.email}? This action cannot be undone.
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel asChild>
                            <Button variant="outline">
                              Go Back
                            </Button>
                          </AlertDialogCancel>
                          <AlertDialogAction asChild>
                            <Button 
                              variant="destructive"
                              onClick={() => cancelInvite(invite.id)}
                              isLoading={loadingInviteId === invite.id}
                            >
                              Cancel Invite
                            </Button>
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
} 