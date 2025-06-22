import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'
import type { Database } from '@/types/supabase'
import type { ResponseCookie } from 'next/dist/compiled/@edge-runtime/cookies'
import type { Organization, OrgMember } from '@/lib/orgs/orgTypes'
import Link from 'next/link'
import { Plus, Building2 } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { OrgAvatar } from '@/components/dashboard/orgs/OrgAvatar'

export default async function OrganizationsPage() {
  const cookieStore = await cookies()
  
  const supabase = createServerClient<Database>(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll: () => {
          return cookieStore.getAll().map((cookie) => ({
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
            } as ResponseCookie)
          })
        }
      }
    }
  )

  const { data: { user } } = await supabase.auth.getUser()
  console.log('Current user:', user?.id)

  // First get user's memberships
  const { data: memberships } = await supabase
    .from('organization_members')
    .select('org_id, role')
    .eq('user_id', user?.id);

  // Then get the organizations
  const { data: orgs, error: queryError } = await supabase
    .from('organizations')
    .select('*')
    .in('id', memberships?.map(m => m.org_id) || [])
    .order('created_at', { ascending: false });

  console.log('Orgs query result:', { orgs, error: queryError })

  // Combine the data
  const typedOrgs = orgs?.map(org => ({
    ...org,
    organization_members: [
      { role: memberships?.find(m => m.org_id === org.id)?.role }
    ]
  })) as (Organization & { 
    organization_members: Pick<OrgMember, 'role'>[] 
  })[] | null;

  return (
    <>
      <div className="flex justify-between items-center border-b pb-4">
        <h2 className="text-2xl font-bold">Your organizations</h2>
        <Link href="/dashboard/orgs/new-organization">
          <Button className="flex items-center">
            <Plus className="mr-2 h-4 w-4" />
            Create new organization
          </Button>
        </Link>
      </div>

      <div className="mt-8">
        {typedOrgs?.length ? (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {typedOrgs.map((org) => (
              <Link key={org.id} href={`/dashboard/orgs/${org.slug}`}>
                <Card>
                  <CardHeader className="flex flex-row items-center gap-4">
                    <OrgAvatar organization={org} />
                    <div>
                      <CardTitle>{org.name}</CardTitle>
                      <CardDescription className="flex items-center gap-2">
                        {org.slug}
                        {org.organization_members[0]?.role && (
                          <span className="text-xs text-muted-foreground">
                            • {org.organization_members[0].role}
                          </span>
                        )}
                      </CardDescription>
                    </div>
                  </CardHeader>
                </Card>
              </Link>
            ))}
          </div>
        ) : (
          <Card className="flex flex-col items-center justify-center p-8 text-center">
            <Building2 className="h-12 w-12 text-muted-foreground/50" />
            <h3 className="mt-4 text-lg font-semibold">No organizations yet</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Create your first organization to get started
            </p>
            <Link href="/dashboard/orgs/new-organization">
              <Button className="mt-4">
                Create organization
              </Button>
            </Link>
          </Card>
        )}
      </div>
    </>
  )
}
