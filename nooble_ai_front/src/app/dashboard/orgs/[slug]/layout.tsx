import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'
import { notFound } from 'next/navigation'
import { OrgNav } from '@/components/dashboard/orgs/OrgNav'
import type { Database } from '@/types/supabase'

interface LayoutProps {
  children: React.ReactNode
  params: { slug: string }
}

export default async function OrganizationLayout({
  children,
  params,
}: LayoutProps) {
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

  const { data: org } = await supabase
    .from('organizations')
    .select('*')
    .eq('slug', slug)
    .single()

  if (!org) {
    notFound()
  }

  return (
    <div>
      <OrgNav organization={org} />
      <div className="p-6">
        {children}
      </div>
    </div>
  )
} 
