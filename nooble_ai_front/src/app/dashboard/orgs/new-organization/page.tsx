import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'
import type { Database } from '@/types/supabase'
import { CreateOrgForm } from '@/components/dashboard/orgs/CreateOrgForm'

export default async function NewOrganizationPage() {
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

  const { data: { user } } = await supabase.auth.getUser()

  if (!user) {
    return null // Handle this with proper auth redirect
  }

  return (
    <>
      <div className="mx-auto max-w-2xl">
        <div className="flex flex-col gap-8">
          <div>
            <h1 className="text-2xl font-bold">Create new organization</h1>
            <p className="text-sm text-muted-foreground">
              Create a new organization to collaborate with your team. 
              You can add an avatar and other details after creation.
            </p>
          </div>

          <CreateOrgForm />
        </div>
      </div>
    </>
  )
} 