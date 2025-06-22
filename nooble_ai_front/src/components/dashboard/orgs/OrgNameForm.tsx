'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import * as z from 'zod'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { toast } from 'sonner'
import type { Organization } from '@/lib/orgs/orgTypes'
import { slugify } from '@/utils/slugify'

const formSchema = z.object({
  name: z.string()
    .min(2, 'Name must be at least 2 characters')
    .max(50, 'Name must be less than 50 characters')
})

type FormData = z.infer<typeof formSchema>

interface OrgNameFormProps {
  organization: Organization
}

interface OrgUpdateError {
  name: string
  code: string
  status: number
  message?: string
}

export function OrgNameForm({ organization }: OrgNameFormProps) {
  const router = useRouter()
  const [isPending, setIsPending] = useState(false)

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: organization.name
    }
  })

  const { register, handleSubmit, formState: { errors } } = form

  async function onSubmit(data: FormData) {
    setIsPending(true)

    try {
      const slug = slugify(data.name)
      
      const response = await fetch(`/api/orgs/${organization.id}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          name: data.name,
          slug 
        }),
      })

      const result = await response.json()

      if (!response.ok) {
        // Handle structured error response
        const error = result.error as OrgUpdateError
        
        switch (error.code) {
          case 'org-update/slug-taken':
            toast.error('This organization name is already taken')
            break
          case 'org-update/unauthorized':
            toast.error('You must be logged in to update the organization')
            break
          case 'org-update/forbidden':
            toast.error('You don\'t have permission to update this organization')
            break
          default:
            toast.error('Failed to update organization')
        }
        return
      }

      toast.success('Organization name updated')
      router.refresh()
      router.push(`/dashboard/orgs/${slug}/settings/general`)
    } catch (error) {
      console.error('Failed to update organization:', error)
      toast.error('Something went wrong. Please try again.')
    } finally {
      setIsPending(false)
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 max-w-md">
      <div className="flex items-center gap-4">
        <Input
          {...register('name')}
          placeholder="Enter organization name"
          disabled={isPending}
          className="bg-background"
        />
        <Button 
          type="submit" 
          variant="primary"
          size="md"
          isLoading={isPending}
        >
          Save
        </Button>
      </div>
      {errors.name && (
        <p className="text-sm text-destructive">
          {errors.name.message}
        </p>
      )}
    </form>
  )
} 