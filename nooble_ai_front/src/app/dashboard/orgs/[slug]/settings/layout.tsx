import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'
import { SettingsNav } from '@/components/dashboard/navigation/SettingsNav'
import type { Database } from '@/types/supabase'
import type { OrgRole } from '@/lib/orgs/orgTypes'
import type { CookieOptions } from '@supabase/ssr'
import { redirect } from 'next/navigation'

interface SettingsLayoutProps {
  children: React.ReactNode
  params: { slug: string }
}

export default async function SettingsLayout({ 
  children, 
  params 
}: SettingsLayoutProps) {
  const cookieStore = await cookies()
  const { slug } = await Promise.resolve(params)
  const pathname = cookieStore.get('next-url')?.value || ''

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
        setAll: async (cookieValues: { name: string; value: string; options?: CookieOptions }[]) => {
          cookieValues.forEach(({ name, value, options }) => {
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

  // Get authenticated user data
  const { data: { user }, error: userError } = await supabase.auth.getUser()
  
  if (!user || userError) {
    throw new Error('Unauthorized')
  }

  // Get user's role in the organization
  const { data: orgMember } = await supabase
    .from('organization_members')
    .select('role, organizations!inner(slug)')
    .eq('organizations.slug', slug)
    .eq('user_id', user.id)
    .single()

  if (!orgMember) {
    throw new Error('Not a member of this organization')
  }

  const userRole = orgMember.role as OrgRole

  // If member, redirect all settings routes to dangerzone except dangerzone itself
  if (userRole === 'member') {
    const isSettingsRoute = pathname.includes('/settings')
    const isDangerZone = pathname.includes('/dangerzone')
    
    if (isSettingsRoute && !isDangerZone) {
      redirect(`/dashboard/orgs/${slug}/settings/dangerzone`)
    }
  }

  return (
    <div className="flex">
      <SettingsNav orgSlug={slug} userRole={userRole} />
      <div className="flex-1 p-6">
        <div className="max-w-4xl">
          {children}
        </div>
      </div>
    </div>
  )
}
