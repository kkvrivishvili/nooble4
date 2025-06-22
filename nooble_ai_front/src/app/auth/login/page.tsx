import { LoginForm } from '@/components/auth/LoginForm'
import type { PricingStrategy } from '@/lib/payments/pricestrategyTypes'
import { Suspense } from 'react'
import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'
import type { Database } from '@/types/supabase'
import type { ResponseCookie } from 'next/dist/compiled/@edge-runtime/cookies'
import { redirect } from 'next/navigation'

export default async function LoginPage({
  searchParams: rawSearchParams
}: {
  searchParams: { 
    code?: string
    invite_token?: string
    org_slug?: string
    error?: string 
    strategy?: PricingStrategy
    type?: string
    redirect_to?: string
  }
}) {
  const searchParams = await Promise.resolve(rawSearchParams)
  const cookieStore = await cookies()
  
  console.log('Login Page: Auth Flow', {
    params: searchParams,
    hasCode: searchParams.code ? 'present' : 'missing',
    cookies: cookieStore.getAll().map(c => c.name)
  })

  // Handle auth code exchange on the server
  if (searchParams.code) {
    const supabase = createServerClient<Database>(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
      {
        auth: {
          flowType: 'pkce',
          detectSessionInUrl: true,
          persistSession: true
        },
        cookies: {
          getAll: () => {
            return cookieStore.getAll().map((cookie) => ({
              name: cookie.name,
              value: cookie.value,
            }))
          },
          setAll: async (cookieValues) => {
            cookieValues.forEach(({ name, value, ...options }) => {
              cookieStore.set({ name, value, ...options } as ResponseCookie)
            })
          }
        }
      }
    )

    try {
      const { error } = await supabase.auth.exchangeCodeForSession(searchParams.code)
      if (error) throw error

      // If this was an invite verification, redirect to accept the invite
      if (searchParams.invite_token && searchParams.org_slug) {
        return redirect(`/dashboard/orgs/${searchParams.org_slug}/invite?token=${searchParams.invite_token}`)
      }

      // Otherwise redirect to the original destination or dashboard
      return redirect(searchParams.redirect_to || '/dashboard')
    } catch (error) {
      console.error('Error exchanging code:', error)
      searchParams.error = 'auth/exchange-failed'
    }
  }

  return (
    <div className="mx-auto max-w-[350px] space-y-6">
      <Suspense fallback={<div>Loading...</div>}>
        <LoginForm searchParams={searchParams} />
      </Suspense>
    </div>
  )
} 