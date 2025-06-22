'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/Button'
import { CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { acceptInvite, declineInvite } from '@/lib/orgs/orgActions'
import { toast } from 'sonner'
import type { Database } from '@/types/supabase'

type Invite = Database['public']['Tables']['organization_invites']['Row'] & {
  organizations: Database['public']['Tables']['organizations']['Row']
}

interface InviteAcceptanceProps {
  invite: Invite
  orgSlug: string
}

export function InviteAcceptance({ invite, orgSlug }: InviteAcceptanceProps) {
  const router = useRouter()
  const [isLoading, setIsLoading] = useState(false)
  const [isDeclining, setIsDeclining] = useState(false)

  async function handleAccept() {
    setIsLoading(true)
    try {
      await acceptInvite(invite.token, orgSlug)
      router.push(`/dashboard/orgs/${orgSlug}`)
    } catch (error) {
      console.error('Failed to accept invite:', error)
      setIsLoading(false)
    }
  }

  async function handleDecline() {
    setIsDeclining(true)
    try {
      await declineInvite(invite.token, orgSlug)
      toast.success('Invitation declined')
      router.push('/dashboard')
    } catch (error) {
      console.error('Failed to decline invite:', error)
      toast.error('Failed to decline invitation')
      setIsDeclining(false)
    }
  }

  return (
    <>
      <CardHeader>
        <CardTitle>Join {invite.organizations.name}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-muted-foreground">
          You have been invited to join {invite.organizations.name} as a{invite.role === 'admin' ? 'n' : ''} {invite.role}.
        </p>
        <div className="flex gap-4">
          <Button
            onClick={handleAccept}
            isLoading={isLoading}
            variant="primary"
          >
            Accept Invitation
          </Button>
          <Button
            onClick={handleDecline}
            isLoading={isDeclining}
            variant="outline"
          >
            Decline
          </Button>
        </div>
      </CardContent>
    </>
  )
} 