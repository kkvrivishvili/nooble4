'use client'

import { Building2 } from 'lucide-react'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import Link from 'next/link'
import { useState, useEffect } from 'react'

interface PendingInvite {
  id: string
  org_slug: string
  org_name: string
}

export function EmptyOrgState() {
  const [pendingInvites, setPendingInvites] = useState<PendingInvite[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    async function fetchPendingInvites() {
      try {
        const response = await fetch('/api/orgs/pending/invites')
        if (!response.ok) throw new Error('Failed to fetch invites')
        const { data } = await response.json()
        setPendingInvites(data)
      } catch (error) {
        console.error('Error fetching pending invites:', error)
      } finally {
        setIsLoading(false)
      }
    }

    fetchPendingInvites()
  }, [])

  if (isLoading) {
    return (
      <Card className="flex flex-col items-center justify-center p-8 text-center">
        <p className="text-muted-foreground">Loading...</p>
      </Card>
    )
  }

  if (pendingInvites.length > 0) {
    return (
      <Card className="flex flex-col items-center justify-center p-8 text-center">
        <Building2 className="h-12 w-12 text-muted-foreground/50" />
        <h3 className="mt-4 text-lg font-semibold text-foreground">You have pending invites!</h3>
        <p className="mt-2 text-sm text-muted-foreground">
          Check your email for organization invites, or create your own organization
        </p>
        <div className="mt-4 flex flex-col gap-2">
          <Button 
            asChild
            variant="primary"
            size="md"
          >
            <Link href="/dashboard/orgs/new-organization">
              Create organization
            </Link>
          </Button>
          <Button 
            variant="outline"
            size="md"
            asChild
            className="text-foreground hover:text-foreground"
          >
            <Link href="/dashboard/invites">
              View pending invites ({pendingInvites.length})
            </Link>
          </Button>
        </div>
      </Card>
    )
  }

  return (
    <Card className="flex flex-col items-center justify-center p-8 text-center">
      <Building2 className="h-12 w-12 text-muted-foreground/50" />
      <h3 className="mt-4 text-lg font-semibold text-foreground">No organizations yet</h3>
      <p className="mt-2 text-sm text-muted-foreground">
        Create your first organization to get started
      </p>
      <Button 
        asChild 
        variant="primary"
        size="md"
        className="mt-4"
      >
        <Link href="/dashboard/orgs/new-organization" className="flex items-center">
          Create organization
        </Link>
      </Button>
    </Card>
  )
}