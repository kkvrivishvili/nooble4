import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'
import { notFound } from 'next/navigation'
import type { Database } from '@/types/supabase'
import { OrgAvatar } from '@/components/dashboard/orgs/OrgAvatar'
import type { OrgRole } from '@/lib/orgs/orgTypes'

// Use the Database type to ensure we match the schema
type OrganizationWithMembers = Database['public']['Tables']['organizations']['Row'] & {
  organization_members: {
    role: OrgRole
  }[]
}

export default async function OrganizationDashboard({
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

  const { data: org, error } = await supabase
    .from('organizations')
    .select(`
      *,
      organization_members (
        role
      )
    `)
    .eq('slug', slug)
    .single()

  if (error || !org) {
    notFound()
  }

  const organization = org as OrganizationWithMembers

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between border-b pb-4">
        <div className="flex items-center space-x-4">
          <OrgAvatar organization={organization} />
          <div>
            <h1 className="text-2xl font-bold">{organization.name}</h1>
            <p className="text-sm text-muted-foreground">
              Organization Dashboard
            </p>
          </div>
        </div>
      </div>

      <div className="grid gap-6">
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {/* Placeholder for dashboard cards/stats */}
          <div className="rounded-lg border p-4">
            <h3 className="font-semibold">Members</h3>
            <p className="text-2xl font-bold">
              {organization.organization_members.length}
            </p>
          </div>
          
          <div className="rounded-lg border p-4">
            <h3 className="font-semibold">Created</h3>
            <p className="text-2xl font-bold">
              {new Date(organization.created_at).toLocaleDateString()}
            </p>
          </div>
        </div>

        {/* Placeholder for future dashboard components */}
        <div className="rounded-lg border p-4">
          <h3 className="font-semibold mb-4">Recent Activity</h3>
          <p className="text-sm text-muted-foreground">
            No recent activity
          </p>
        </div>
      </div>
    </div>
  )
} 