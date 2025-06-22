'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/Button'
import { toast } from 'sonner'
import type { OrgRole } from '@/lib/orgs/orgTypes'
import { formatDate } from '@/utils/date'
import { OrgAvatar } from '@/components/dashboard/orgs/OrgAvatar'
import { socialLogin } from '@/lib/auth/socialLogin'
import { Icons } from '@/components/ui/Icons'
import type { Organization } from '@/lib/orgs/orgTypes'
import { declineInvite } from '@/lib/orgs/orgActions'

interface InviteFormData {
  id: string
  token: string
  org_id: string
  email: string
  role: Exclude<OrgRole, 'owner'>
  expires_at: string
  organizations: Organization
  profiles: {
    full_name: string | null
    avatar_url: string | null
  }
}

interface InviteFormProps {
  invite: InviteFormData
  user: { id: string; email: string } | null
}

export function InviteForm({ invite, user }: InviteFormProps) {
  const router = useRouter()
  const [isPending, setIsPending] = useState(false)
  const [isDeclining, setIsDeclining] = useState(false)

  async function acceptInvite() {
    setIsPending(true)
    
    try {
      // If no user, redirect to OAuth flow
      if (!user) {
        socialLogin(
          'google', 
          'freemium',
          invite.token,
          invite.organizations.slug
        )
        return
      }

      // Check if the user's email matches the invite email
      if (user.email.toLowerCase() !== invite.email.toLowerCase()) {
        toast.error(
          `This invite is for ${invite.email}. You are currently logged in as ${user.email}. Please log out and sign in with the correct account.`,
          {
            duration: 6000,
          }
        )
        setTimeout(() => {
          router.push('/auth/logout?returnUrl=' + encodeURIComponent(`/invite?token=${invite.token}`))
        }, 1500)
        return
      }

      const response = await fetch(`/api/orgs/${invite.org_id}/invites/${invite.id}/accept`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json'
        }
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.error?.message || 'Failed to accept invite')
      }

      toast.success('Invitation accepted successfully')
      router.push(`/dashboard/orgs/${invite.organizations.slug}`)
    } catch (error) {
      console.error('Error accepting invite:', error)
      toast.error(error instanceof Error ? error.message : 'Failed to accept invite')
    } finally {
      setIsPending(false)
    }
  }

  async function handleDecline() {
    setIsDeclining(true)
    try {
      const { error } = await declineInvite(invite.token, invite.organizations.slug)
      if (error) throw new Error(error)
      
      toast.success('Invitation declined')
      router.push('/dashboard')
    } catch (error) {
      console.error('Error declining invite:', error)
      toast.error(error instanceof Error ? error.message : 'Failed to decline invite')
    } finally {
      setIsDeclining(false)
    }
  }

  // Always show the OAuth login form if there's no user
  if (!user) {
    return (
      <div className="space-y-8">
        {/* Organization Info */}
        <div className="flex flex-col items-center space-y-4">
          <OrgAvatar 
            organization={invite.organizations}
            className="h-24 w-24"
          />
          <div className="text-center space-y-2">
            <h1 className="text-2xl font-semibold">
              Join {invite.organizations.name}
            </h1>
            <p className="text-muted-foreground">
              You've been invited to join as <span className="font-medium">{invite.role}</span>
            </p>
          </div>
        </div>

        {/* Process Steps */}
        <div className="space-y-4 bg-muted/50 rounded-lg p-4">
          <h2 className="font-medium text-center">Next steps:</h2>
          <ol className="space-y-3 text-sm">
            <li className="flex items-start gap-3">
              <div className="flex-none flex h-6 w-6 items-center justify-center rounded-full bg-primary/10 text-primary text-sm font-medium">
                1
              </div>
              <span>Sign in with Google using the email address <span className="font-medium">{invite.email}</span></span>
            </li>
            <li className="flex items-start gap-3">
              <div className="flex-none flex h-6 w-6 items-center justify-center rounded-full bg-primary/10 text-primary text-sm font-medium">
                2
              </div>
              <span>Review and accept the invitation to join {invite.organizations.name}</span>
            </li>
            <li className="flex items-start gap-3">
              <div className="flex-none flex h-6 w-6 items-center justify-center rounded-full bg-primary/10 text-primary text-sm font-medium">
                3
              </div>
              <span>Get access to the organization's dashboard and resources</span>
            </li>
          </ol>
        </div>

        {/* OAuth Button */}
        <Button 
          className="w-full"
          size="lg"
          onClick={() => socialLogin(
            'google', 
            'freemium',
            invite.token,
            invite.organizations.slug
          )}
        >
          <Icons.google className="mr-2 h-5 w-5" />
          Continue with Google
        </Button>

        {/* Additional Info */}
        <div className="text-center space-y-2">
          <p className="text-sm text-muted-foreground">
            This invite expires on {formatDate(invite.expires_at)}
          </p>
          <p className="text-xs text-muted-foreground">
            Make sure to sign in with {invite.email}
          </p>
        </div>

        <div className="flex flex-col items-center gap-4">
          <div className="relative w-full">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-background px-2 text-muted-foreground">Or</span>
            </div>
          </div>
          
          <Button
            variant="outline"
            className="w-full"
            onClick={() => router.push('/dashboard')}
          >
            Decline Invitation
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {user.email.toLowerCase() !== invite.email.toLowerCase() && (
        <div className="rounded-md bg-yellow-50 p-4">
          <div className="flex">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-yellow-400" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M8.485 3.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 3.495zM10 6a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 6zm0 9a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-yellow-800">
                Wrong account
              </h3>
              <div className="mt-2 text-sm text-yellow-700">
                <p>
                  You are currently logged in as {user.email}. This invitation was sent to {invite.email}.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="flex flex-col items-center space-y-4 text-center">
        <OrgAvatar 
          organization={invite.organizations}
          className="h-16 w-16"
        />
        <div className="space-y-2">
          <h1 className="text-2xl font-semibold tracking-tight">
            Accept Invitation
          </h1>
          <p className="text-sm text-muted-foreground">
            You've been invited to join {invite.organizations.name || 'an organization'}
          </p>
        </div>
      </div>

      <div className="space-y-4">
        <div className="space-y-2">
          <p className="text-sm">
            <span className="font-medium">Organization:</span> {invite.organizations.name || 'Loading...'}
          </p>
          <p className="text-sm">
            <span className="font-medium">Email:</span> {invite.email}
          </p>
          <p className="text-sm">
            <span className="font-medium">Role:</span> {invite.role}
          </p>
          <p className="text-sm">
            <span className="font-medium">Expires:</span>{' '}
            {formatDate(invite.expires_at)}
          </p>
        </div>

        <div className="flex gap-4">
          <Button
            className="flex-1"
            variant="primary"
            onClick={acceptInvite}
            isLoading={isPending}
            disabled={user.email.toLowerCase() !== invite.email.toLowerCase()}
          >
            Accept Invitation
          </Button>
          
          <Button
            className="flex-1"
            variant="outline"
            onClick={handleDecline}
            isLoading={isDeclining}
            disabled={user.email.toLowerCase() !== invite.email.toLowerCase()}
          >
            Decline
          </Button>
        </div>
      </div>
    </div>
  )
} 