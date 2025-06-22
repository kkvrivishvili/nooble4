import { createServerClient } from '@supabase/ssr'
import type { Database } from '@/types/supabase'

type OrganizationInvite = Database['public']['Tables']['organization_invites']['Row']
type OrganizationDetails = Database['public']['Tables']['organizations']['Row']

export async function getInviteDetails(token: string) {
  const supabase = createServerClient<Database>(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        // Using the new recommended cookie methods
        getAll: () => [],  // Return empty array as we don't need cookies for this query
        setAll: () => { },  // No-op since we're not setting cookies
      }
    }
  )

  const { data: rawInvite, error: inviteError } = await supabase
    .from('organization_invites')
    .select(`
      *,
      organizations (
        id,
        name,
        slug,
        avatar_url,
        created_at,
        updated_at
      )
    `)
    .eq('token', token)
    .single()

  if (!rawInvite || inviteError) {
    throw new Error('Invalid invite')
  }

  // Get current user if logged in
  const { data: { user } } = await supabase.auth.getUser()

  return {
    invite: {
      ...rawInvite,
      organizations: rawInvite.organizations as OrganizationDetails
    },
    currentUser: user ? {
      id: user.id,
      email: user.email ?? ''
    } : null
  }
} 