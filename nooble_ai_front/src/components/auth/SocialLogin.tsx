'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { socialLogin } from '@/lib/auth/socialLogin'
import type { Provider } from '@supabase/supabase-js'
import type { PricingStrategy } from '@/lib/payments/pricestrategyTypes'
import type { AuthSearchParams } from '@/lib/auth/authTypes'
import { createBrowserClient } from '@supabase/ssr'

interface SocialLoginProps {
  strategy?: PricingStrategy
  searchParams?: AuthSearchParams
}

export function SocialLogin({ 
  strategy = 'freemium',
  searchParams 
}: SocialLoginProps) {
  const [isLoading, setIsLoading] = useState<Provider | null>(null)

  const handleSocialLogin = async (provider: Provider) => {
    try {
      setIsLoading(provider)

      // Sign out any existing session first
      const supabase = createBrowserClient(
        process.env.NEXT_PUBLIC_SUPABASE_URL!,
        process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
      )
      await supabase.auth.signOut()

      const { error } = await socialLogin(
        provider, 
        strategy,
        searchParams?.invite,
        searchParams?.org
      )
      
      if (error) {
        console.error('Social login error:', error)
        return
      }
    } catch (error) {
      console.error('Social login failed:', error)
    } finally {
      setIsLoading(null)
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <Button 
        onClick={() => handleSocialLogin('google')}
        variant="outline"
        size="lg"
        isLoading={isLoading === 'google'}
        className="w-full bg-background text-foreground hover:bg-accent"
      >
        {!isLoading && (
          <svg className="mr-2 h-4 w-4" viewBox="0 0 24 24">
            <path
              fill="currentColor"
              d="M12.48 10.92v3.28h7.84c-.24 1.84-.853 3.187-1.787 4.133-1.147 1.147-2.933 2.4-6.053 2.4-4.827 0-8.6-3.893-8.6-8.72s3.773-8.72 8.6-8.72c2.6 0 4.507 1.027 5.907 2.347l2.307-2.307C18.747 1.44 16.133 0 12.48 0 5.867 0 .307 5.387.307 12s5.56 12 12.173 12c3.573 0 6.267-1.173 8.373-3.36 2.16-2.16 2.84-5.213 2.84-7.667 0-.76-.053-1.467-.173-2.053H12.48z"
            />
          </svg>
        )}
        Continue with Google
      </Button>
    </div>
  )
}
