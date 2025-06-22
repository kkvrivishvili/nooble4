'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { OrganizationSchema } from '@/middleware/schemas'
import type { CreateOrgParams } from '@/lib/orgs/orgTypes'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Label } from '@/components/ui/Label'
import { OrgSlugInput } from './OrgSlugInput'
import { toast } from 'sonner'

type CreateOrgFormData = CreateOrgParams

export function CreateOrgForm() {
  const router = useRouter()
  const [isSubmitting, setIsSubmitting] = useState(false)

  const form = useForm<CreateOrgFormData>({
    resolver: zodResolver(OrganizationSchema),
    defaultValues: {
      name: '',
      slug: ''
    }
  })

  const { register, handleSubmit, watch, formState: { errors } } = form
  const name = watch('name')

  const onSubmit = async (data: CreateOrgFormData) => {
    try {
      setIsSubmitting(true)
      const response = await fetch('/api/orgs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: data.name,
          slug: data.slug
        })
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.error?.message || 'Failed to create organization')
      }

      const { data: org } = await response.json()
      toast.success('Organization created successfully')
      router.push(`/dashboard/orgs/${org.slug}`)
      router.refresh()
    } catch (error) {
      console.error('Create org error:', error)
      toast.error(error instanceof Error ? error.message : 'Failed to create organization')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-8">
      <div className="space-y-4">
        <div>
          <Label 
            htmlFor="name" 
            variant="primary"
            size="md"
          >
            Organization name
          </Label>
          <Input
            id="name"
            {...register('name')}
            placeholder="Acme Inc."
            disabled={isSubmitting}
            variant="primary"
            size="md"
          />
          {errors.name && (
            <p className="mt-1 text-sm text-destructive">{errors.name.message}</p>
          )}
        </div>

        <div>
          <OrgSlugInput
            {...register('slug')}
            name={name}
            disabled={isSubmitting}
            error={errors.slug?.message}
            variant="primary"
            size="md"
          />
        </div>
      </div>

      <div className="flex justify-end">
        <Button 
          type="submit" 
          variant="primary"
          size="md"
          isLoading={isSubmitting}
        >
          Create organization
        </Button>
      </div>
    </form>
  )
} 