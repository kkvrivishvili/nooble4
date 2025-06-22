import { redirect } from 'next/navigation'
import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'
import { DashboardWrapper } from '@/components/dashboard/DashboardWrapper'
import type { Database } from '@/types/supabase'

export default async function DashboardLayout({
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
        setAll: () => {}
      }
    }
  )

  const { data: { session } } = await supabase.auth.getSession()
  
  if (!session) {
    redirect('/auth/login')
  }

  return <DashboardWrapper>{children}</DashboardWrapper>
}
