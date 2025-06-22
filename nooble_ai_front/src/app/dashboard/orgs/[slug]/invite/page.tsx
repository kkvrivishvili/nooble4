import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'
import { redirect } from 'next/navigation'
import { Card } from '@/components/ui/Card'
import { InviteAcceptance } from '@/components/dashboard/orgs/InviteAcceptance'
import type { Database } from '@/types/supabase'

interface PageProps {
  params: { slug: string }
  searchParams: { token?: string }
}

export default async function InvitePage({
  params,
  searchParams
}: PageProps) {
  // Await cookies and params
  const cookieStore = await cookies()
  const { slug } = await params
  const { token } = await searchParams

  const supabase = createServerClient<Database>(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll: () => cookieStore.getAll().map(cookie => ({
          name: cookie.name,
          value: cookie.value,
        })),
        setAll: async (cookieValues) => {
          cookieValues.map(({ name, value, ...options }) => {
            cookieStore.set({ name, value, ...options })
          })
        }
      }
    }
  )

  // Get user instead of session for security
  const { data: { user }, error: userError } = await supabase.auth.getUser()
  if (userError || !user) {
    redirect('/auth/login')
  }

  // Verify invite exists and matches user
  const { data: invite } = await supabase
    .from('organization_invites')
    .select('*, organizations(*)')
    .eq('token', token)
    .single()

  if (!invite || invite.email !== user.email) {
    redirect('/dashboard')
  }

  return (
    <div className="container max-w-lg py-10">
      <Card>
        <InviteAcceptance 
          invite={invite} 
          orgSlug={slug}
        />
      </Card>
    </div>
  )
} 