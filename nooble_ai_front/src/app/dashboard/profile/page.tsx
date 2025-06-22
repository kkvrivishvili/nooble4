import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'
import { redirect } from 'next/navigation'
import { ProfileForm } from '@/components/auth/ProfileForm'
import type { Database } from '@/types/supabase'
import type { ProfileRow, UserRow } from '@/types/api'

export default async function ProfilePage() {
  const cookieStore = await cookies()
  
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
          cookieValues.forEach(({ name, value, options }) => {
            cookieStore.set(name, value, options)
          })
        }
      }
    }
  )

  const { data: { user } } = await supabase.auth.getUser()
  
  if (!user) {
    redirect('/auth/login')
  }

  // Get or create the profile
  let { data: profile } = await supabase
    .from('profiles')
    .select(`
      id,
      full_name,
      avatar_url,
      updated_at
    `)
    .eq('id', user.id)
    .single()

  if (!profile) {
    const { data: newProfile, error } = await supabase
      .from('profiles')
      .insert([
        {
          id: user.id,
          updated_at: new Date().toISOString(),
        },
      ])
      .select()
      .single()

    if (error) throw error
    profile = newProfile
  }

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-medium">Profile</h3>
        <p className="text-sm text-muted-foreground">
          View and manage your profile information.
        </p>
      </div>
      
      <ProfileForm profile={profile as ProfileRow} user={user as UserRow} />
    </div>
  )
} 
