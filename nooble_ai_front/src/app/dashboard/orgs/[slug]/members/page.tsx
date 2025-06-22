import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'
import { notFound } from 'next/navigation'
import type { Database } from '@/types/supabase'
import { InviteMemberForm } from '@/components/dashboard/orgs/InviteMemberForm'
import { MembersList } from '@/components/dashboard/orgs/MembersList'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/Tabs'
import type { OrgMemberWithProfile } from '@/lib/orgs/orgTypes'
import { MemberStats } from '@/components/dashboard/orgs/members/MemberStats'

export default async function OrganizationMembersPage({
  params,
}: {
  params: { slug: string }
}) {
  const cookieStore = await cookies()
  const { slug } = await Promise.resolve(params)
  
  const supabase = createServerClient<Database>(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll: () => {
          return cookieStore.getAll().map(cookie => ({
            name: cookie.name,
            value: cookie.value,
          }))
        },
        setAll: async (cookieValues) => {
          cookieValues.forEach(({ name, value, ...options }) => {
            cookieStore.set({ 
              name, 
              value, 
              ...options 
            })
          })
        }
      }
    }
  )

  // Get current user
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) {
    notFound()
  }

  // First get the organization to verify it exists
  const { data: org, error: orgError } = await supabase
    .from('organizations')
    .select('*')
    .eq('slug', slug)
    .single()

  if (orgError || !org) {
    notFound()
  }

  // Then get members data
  const { data: members, error: membersError } = await supabase
    .from('organization_members')
    .select(`
      org_id,
      user_id,
      role,
      joined_at,
      profiles!inner (
        id,
        full_name,
        email,
        avatar_url
      )
    `)
    .eq('org_id', org.id)

  if (membersError || !members?.length) {
    notFound()
  }

  // Type assertion since we know the structure matches OrgMemberWithProfile
  const typedMembers = members as unknown as OrgMemberWithProfile[]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Members</h1>
        <p className="text-muted-foreground">
          Manage members and roles for {org.name}
        </p>
      </div>

      <div className="space-y-8">
        <Tabs defaultValue="members" className="w-full">
          <TabsList className="flex justify-center space-x-2 w-full sm:w-auto border-b border-border">
            <TabsTrigger 
              value="members"
              className="relative px-4 py-2 text-sm font-semibold transition-all data-[state=active]:text-foreground"
            >
              Members
              <span className="absolute left-0 bottom-0 w-full h-0.5 bg-primary scale-x-0 transition-transform data-[state=active]:scale-x-100" />
            </TabsTrigger>
            <TabsTrigger 
              value="invite"
              className="relative px-4 py-2 text-sm font-semibold transition-all data-[state=active]:text-foreground"
            >
              Invite
              <span className="absolute left-0 bottom-0 w-full h-0.5 bg-primary scale-x-0 transition-transform data-[state=active]:scale-x-100" />
            </TabsTrigger>
            <TabsTrigger 
              value="stats"
              className="relative px-4 py-2 text-sm font-semibold transition-all data-[state=active]:text-foreground"
            >
              Stats
              <span className="absolute left-0 bottom-0 w-full h-0.5 bg-primary scale-x-0 transition-transform data-[state=active]:scale-x-100" />
            </TabsTrigger>
          </TabsList>
          
          <TabsContent value="members" className="p-4 sm:p-6">
            <MembersList orgId={slug} currentUserId={user.id} />
          </TabsContent>
          
          <TabsContent value="invite" className="p-4 sm:p-6">
            <div className="max-w-2xl">
              <h2 className="text-xl font-semibold tracking-tight mb-4">Invite New Members</h2>
              <InviteMemberForm />
            </div>
          </TabsContent>

          <TabsContent value="stats" className="p-4 sm:p-6">
            <div className="max-w-full">
              <h2 className="text-xl font-semibold tracking-tight mb-4">Member Statistics</h2>
              <MemberStats orgId={org.id} />
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}
