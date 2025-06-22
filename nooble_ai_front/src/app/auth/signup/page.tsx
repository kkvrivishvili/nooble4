import { SignupForm } from '@/components/auth/SignupForm'
import type { PricingStrategy } from '@/lib/payments/pricestrategyTypes'
import { Suspense } from 'react'

export default async function SignupPage({
  searchParams
}: {
  searchParams: {
    email?: string
    invite?: string
    org?: string
    error?: string
    strategy?: PricingStrategy
  }
}) {
  const params = await Promise.resolve(searchParams)

  return (
    <div className="mx-auto max-w-[350px] space-y-6">
      <Suspense fallback={<div>Loading...</div>}>
        <SignupForm searchParams={params} />
      </Suspense>
    </div>
  )
} 