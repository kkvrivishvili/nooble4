import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'
import { notFound } from 'next/navigation'
import type { Database } from '@/types/supabase'
import { OrgAvatarUpload } from '@/components/dashboard/orgs/OrgAvatarUpload'
import { OrgNameForm } from '@/components/dashboard/orgs/OrgNameForm'
import type { OrgRole } from '@/lib/orgs/orgTypes'

type Organization = Database['public']['Tables']['organizations']['Row'] & {
  organization_members: {
    role: OrgRole
  }[]
}

export default async function OrganizationSettings({
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

  const organization = org as Organization

  return (
    <div className="space-y-10">
      <div>
        <h1 className="text-2xl font-bold">Organization Settings</h1>
        <p className="text-sm text-muted-foreground">
          Manage your organizations profile and settings.
        </p>
      </div>

      <div className="space-y-8">
        <div>
          <h3 className="text-lg font-medium mb-4">Organization Logo</h3>
          <OrgAvatarUpload 
            orgId={organization.id}
            currentAvatar={organization.avatar_url || null}
          />
        </div>

        <div>
          <h3 className="text-lg font-medium mb-4">Organization Name</h3>
          <OrgNameForm 
            organization={organization}
          />
        </div>
      </div>
    </div>
  )
} 