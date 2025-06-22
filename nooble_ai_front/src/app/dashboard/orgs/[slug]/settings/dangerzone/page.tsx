import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'
import { DangerZone } from '@/components/dashboard/orgs/DangerZone'
import type { Database } from '@/types/supabase'
import type { OrgRole } from '@/lib/orgs/orgTypes'
import type { CookieOptions } from '@supabase/ssr'

export default async function DangerZonePage({ 
  params 
}: { 
  params: { slug: string } 
}) {
  const cookieStore = await cookies()
  const resolvedParams = await Promise.resolve(params)
  const { slug } = resolvedParams

  const supabase = createServerClient<Database>(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll: () => cookieStore.getAll().map((cookie) => ({
          name: cookie.name,
          value: cookie.value,
        })),
        setAll: async (cookieValues: { name: string; value: string; options?: CookieOptions }[]) => {
          cookieValues.forEach(({ name, value, options }) => {
            cookieStore.set({ name, value, ...options })
          })
        }
      }
    }
  )

  const { data: { user } } = await supabase.auth.getUser()
  if (!user) throw new Error('Not authenticated')

  const { data: org } = await supabase
    .from('organizations')
    .select('id')
    .eq('slug', slug)
    .single()

  if (!org) throw new Error('Organization not found')

  const { data: orgMember } = await supabase
    .from('organization_members')
    .select('role')
    .eq('org_id', org.id)
    .eq('user_id', user.id)
    .single()

  if (!orgMember) throw new Error('Not a member of this organization')
  
  const userRole = orgMember.role as OrgRole
  console.log('Fetched role:', userRole)

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-destructive">Danger Zone</h2>
        <p className="text-muted-foreground">
          Critical actions for the organization. Be careful, some actions are irreversible.
        </p>
      </div>

      <DangerZone 
        currentUserId={user.id}
        userRole={userRole}
      />
    </div>
  )
}
