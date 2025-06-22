import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'
import { AlertCircle, CreditCard, Receipt, Wallet } from 'lucide-react'
import type { Database } from '@/types/supabase'
import type { OrgRole } from '@/lib/orgs/orgTypes'
import type { CookieOptions } from '@supabase/ssr'

export default async function BillingPage({ 
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

  return (
    <div className="space-y-10">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Billing & Subscription</h2>
        <p className="text-muted-foreground">
          Manage your organization's billing settings and subscription plan.
        </p>
      </div>

      {/* Coming Soon Alert */}
      <div className="flex items-center gap-3 rounded-lg border bg-card p-4">
        <AlertCircle className="h-5 w-5 text-primary" />
        <div>
          <p className="font-medium">Billing System Coming Soon</p>
          <p className="text-sm text-muted-foreground">
            We're currently implementing Stripe for secure payment processing.
          </p>
        </div>
      </div>

      {/* Billing Sections */}
      <div className="grid gap-6">
        {/* Current Plan */}
        <div className="rounded-lg border bg-card p-6">
          <div className="flex items-center gap-3 mb-4">
            <Wallet className="h-5 w-5 text-primary" />
            <h3 className="text-lg font-medium">Current Plan</h3>
          </div>
          <div className="space-y-2">
            <div className="flex justify-between items-center">
              <p className="font-medium">Free Tier</p>
              <button className="text-sm text-primary hover:underline" disabled>
                Upgrade Plan
              </button>
            </div>
            <p className="text-sm text-muted-foreground">
              Basic features for small teams getting started
            </p>
          </div>
        </div>

        {/* Payment Method */}
        <div className="rounded-lg border bg-card p-6">
          <div className="flex items-center gap-3 mb-4">
            <CreditCard className="h-5 w-5 text-primary" />
            <h3 className="text-lg font-medium">Payment Method</h3>
          </div>
          <button 
            className="text-sm text-primary hover:underline"
            disabled
          >
            Add payment method
          </button>
        </div>

        {/* Billing History */}
        <div className="rounded-lg border bg-card p-6">
          <div className="flex items-center gap-3 mb-4">
            <Receipt className="h-5 w-5 text-primary" />
            <h3 className="text-lg font-medium">Billing History</h3>
          </div>
          <p className="text-sm text-muted-foreground">
            No billing history available
          </p>
        </div>
      </div>
    </div>
  )
}
