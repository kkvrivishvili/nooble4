'use client'

import { useState } from 'react'
import { useParams } from 'next/navigation'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import * as z from 'zod'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/Select'
import { toast } from 'sonner'
import type { InviteMemberParams, OrgInvite } from '@/lib/orgs/orgTypes'

const formSchema = z.object({
  email: z.string().email('Invalid email address'),
  role: z.enum(['admin', 'member'])
})

type FormData = z.infer<typeof formSchema>

export function InviteMemberForm() {
  const params = useParams()
  const [isPending, setIsPending] = useState(false)

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      role: undefined
    }
  })
  
  const { register, handleSubmit, reset, formState: { errors }, setValue, watch } = form
  const selectedRole = watch('role')

  async function onSubmit(data: FormData) {
    setIsPending(true)

    try {
      const payload: InviteMemberParams = {
        org_id: params.slug as string,
        email: data.email,
        role: data.role
      }

      const response = await fetch(`/api/orgs/${params.slug}/invites`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      })

      const result = await response.json()

      if (!response.ok) {
        // Handle specific error cases
        switch (result.error?.code) {
          case 'invite/already-member':
            toast.error('This user is already a member of your organization')
            break
          case 'invite/exists':
            toast.error(
              'This email already has a pending invite. You can manage it in the pending invites section below.'
            )
            break
          case 'invite/self-invite':
            toast.error('You cannot invite yourself to an organization you\'re already in')
            break
          case 'invite/unauthorized':
            toast.error('You need to be signed in to invite members')
            break
          case 'invite/forbidden':
            toast.error('You don\'t have permission to invite members to this organization')
            break
          case 'invite/not-found':
            toast.error('Organization not found. Please refresh the page.')
            break
          case 'invite/failed':
            toast.error('Something went wrong while creating the invite. Please try again.')
            break
          default:
            toast.error(result.error?.message || 'Failed to create invitation')
        }
        return
      }

      const invite = result.data as OrgInvite
      
      if (invite) {
        if (result.metadata?.emailError) {
          toast.warning(
            'Invite created but the email delivery failed. You can resend the invitation from the pending invites section.',
            {
              duration: 5000 // Give them more time to read this
            }
          )
        } else {
          toast.success(`Invitation sent successfully to ${data.email}`, {
            description: `They will receive an email with instructions to join as a ${data.role}.`
          })
        }
        reset() // Clear the form
      }
    } catch (error) {
      console.error('Failed to create invite:', error)
      toast.error('Failed to create invitation. Please check your connection and try again.')
    } finally {
      setIsPending(false)
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      <div className="flex items-end gap-4">
        <div className="flex-1">
          <Input
            {...register('email')}
            placeholder="Enter email address"
            disabled={isPending}
            variant="primary"
            size="md"
          />
          {errors.email && (
            <p className="mt-1 text-sm text-destructive">
              {errors.email.message}
            </p>
          )}
        </div>
        <Select
          value={selectedRole}
          onValueChange={(value) => setValue('role', value as 'admin' | 'member')}
          disabled={isPending}
        >
          <SelectTrigger className="w-[180px] bg-background">
            <SelectValue placeholder="Select a role" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="member">Member</SelectItem>
            <SelectItem value="admin">Admin</SelectItem>
          </SelectContent>
        </Select>
        <Button 
          type="submit" 
          variant="primary"
          size="md"
          isLoading={isPending}
        >
          Invite
        </Button>
      </div>
    </form>
  )
} 