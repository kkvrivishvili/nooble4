'use client'

import { useState, useEffect } from 'react'
import { useParams } from 'next/navigation'
import { createBrowserClient } from '@supabase/ssr'
import { InviteMemberForm } from '@/components/dashboard/orgs/InviteMemberForm'
import { MembersList } from '@/components/dashboard/orgs/MembersList'
import { PendingInvites } from '@/components/dashboard/orgs/PendingInvites'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/Tabs'
import { PageLoader } from '@/components/ui/PageLoader'
import { useMinimumLoadingTime } from '@/lib/utils/useMinimumLoadingTime'
import type { Database } from '@/types/supabase'

export default function MembersPage() {
  const params = useParams()
  const [activeTab, setActiveTab] = useState('active')
  const [currentUserId, setCurrentUserId] = useState<string>('')
  const { isLoading, endLoading } = useMinimumLoadingTime()
  
  const supabase = createBrowserClient<Database>(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  )

  useEffect(() => {
    async function getCurrentUser() {
      const { data: { user } } = await supabase.auth.getUser()
      if (user) {
        setCurrentUserId(user.id)
      }
      endLoading()
    }
    getCurrentUser()
  }, [supabase, endLoading])

  const handleTabChange = (value: string) => {
    setActiveTab(value)
  }

  return (
    <div className="space-y-6">
      {isLoading && <PageLoader />}
      
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Organization</h2>
        <p className="text-muted-foreground">
          Manage the settings of the organization.
        </p>
      </div>

      <InviteMemberForm />

      <Tabs value={activeTab} onValueChange={handleTabChange}>
        <TabsList>
          <TabsTrigger value="active">Active members</TabsTrigger>
          <TabsTrigger value="pending">Pending invitations</TabsTrigger>
        </TabsList>
        <TabsContent value="active" className="min-h-[200px]">
          <MembersList orgId={params.slug as string} currentUserId={currentUserId} />
        </TabsContent>
        <TabsContent value="pending">
          <PendingInvites orgId={params.slug as string} />
        </TabsContent>
      </Tabs>
    </div>
  )
} 