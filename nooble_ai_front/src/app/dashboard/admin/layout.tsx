import { redirect } from 'next/navigation'
import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'
import { AdminNav } from '@/components/dashboard/navigation/AdminNav'
import type { Database } from '@/types/supabase'

export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode
}) {
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
        setAll: () => {} // Empty function since middleware handles setting
      }
    }
  )

  // Use getUser() instead of getSession()
  const { data: { user }, error } = await supabase.auth.getUser()
  if (error || !user) {
    redirect('/auth/login')
  }
  
  // Check admin role using user.id
  const { data: role } = await supabase
    .from('roles')
    .select('role')
    .eq('user_id', user.id)
    .maybeSingle()
    
  if (!role || !['admin', 'super_admin'].includes(role.role)) {
    redirect('/dashboard')
  }

  return (
    <div className="min-h-screen bg-background">
      <AdminNav />
      <main className="p-8">
        <div className="mx-auto max-w-4xl space-y-6">
          {children}
        </div>
      </main>
    </div>
  )
}
