'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Label } from '@/components/ui/Label'
import { Checkbox } from '@/components/ui/Checkbox'
import { CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { login } from '@/lib/auth/login'
import type { PricingStrategy } from '@/lib/payments/pricestrategyTypes'
import { SocialLogin } from '@/components/auth/SocialLogin'
import { Divider } from '@/components/ui/Divider'
import { createBrowserClient } from '@supabase/ssr'
import { acceptInvite } from '@/lib/orgs/orgActions'
import type { AuthSearchParams } from '@/lib/auth/authTypes'

interface LoginFormProps {
  searchParams: AuthSearchParams
}

export function LoginForm({ searchParams }: LoginFormProps) {
  const router = useRouter()
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [rememberMe, setRememberMe] = useState(false)
  const [showSignupPrompt, setShowSignupPrompt] = useState(false)
  const [emailForSignup, setEmailForSignup] = useState('')
  const [isInviteFlow] = useState(!!searchParams.invite)

  useEffect(() => {
    if (searchParams.code) {
      const handleAuthSuccess = async () => {
        try {
          const supabase = createBrowserClient(
            process.env.NEXT_PUBLIC_SUPABASE_URL!,
            process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
          )

          const { data: { session } } = await supabase.auth.getSession()

          if (session && searchParams.invite && searchParams.org) {
            try {
              await acceptInvite(searchParams.invite, searchParams.org)
              router.push(`/dashboard/orgs/${searchParams.org}`)
              return
            } catch (inviteError) {
              console.error('Failed to accept invite:', inviteError)
            }
          }
          
          router.push('/dashboard')
        } catch (error) {
          console.error('Error handling auth success:', error)
          router.push('/auth/login?error=auth/post-auth-failed')
        }
      }

      handleAuthSuccess()
    }
  }, [searchParams, router])

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setIsLoading(true)
    setError('')
    setShowSignupPrompt(false)

    try {
      const formData = new FormData(event.currentTarget)
      const email = formData.get('email') as string
      const password = formData.get('password') as string

      const result = await login({ 
        email, 
        password, 
        rememberMe,
        inviteToken: searchParams.invite,
        orgSlug: searchParams.org
      })
      
      if (result.error) {
        if (result.metadata?.shouldRedirectToSignup) {
          setShowSignupPrompt(true)
          setEmailForSignup(email)
        } else {
          setError(result.error.message)
        }
        setIsLoading(false)
        return
      }

      if (result.metadata?.redirectTo) {
        router.push(result.metadata.redirectTo)
        return
      }

      router.push('/dashboard')
    } catch (error) {
      console.error('Login error:', error)
      setError('Invalid email or password')
      setIsLoading(false)
    }
  }

  return (
    <>
      <CardHeader>
        <CardTitle className="text-foreground">
          {isInviteFlow 
            ? "Sign in to Join Organization" 
            : "Welcome back"}
        </CardTitle>
        {isInviteFlow && (
          <p className="text-sm text-muted-foreground mt-2">
            Sign in to accept the invitation
          </p>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        <SocialLogin 
          strategy={process.env.NEXT_PUBLIC_PRICING_STRATEGY as PricingStrategy} 
          searchParams={searchParams}
        />
        
        <Divider className="text-muted-foreground">
          or continue with
        </Divider>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label 
              htmlFor="email"
              variant="primary"
              size="md"
            >
              Email
            </Label>
            <Input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              required
              placeholder="name@example.com"
              variant="primary"
              size="md"
            />
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label 
                htmlFor="password"
                variant="primary"
                size="md"
              >
                Password
              </Label>
              <Link 
                href="/auth/reset-password" 
                className="text-sm text-primary hover:text-primary/90 transition-colors"
              >
                Forgot password?
              </Link>
            </div>
            <Input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
              variant="primary"
              size="md"
            />
          </div>
          <div className="flex items-center space-x-2">
            <Checkbox
              id="remember"
              checked={rememberMe}
              onChange={(e) => setRememberMe(e.target.checked)}
              variant="primary"
              size="md"
              label="Stay signed in for 30 days"
            />
          </div>
          {(error || showSignupPrompt) && (
            <div className="text-sm text-destructive space-y-2">
              {error && !showSignupPrompt && <p>{error}</p>}
              {showSignupPrompt && (
                <p>
                  This account doesn&apos;t exist.{' '}
                  <Link 
                    href={`/auth/signup?email=${encodeURIComponent(emailForSignup)}`}
                    className="text-primary hover:text-primary/90 transition-colors"
                  >
                    Create an account
                  </Link>
                  ?
                </p>
              )}
            </div>
          )}
          <Button
            type="submit"
            className="w-full"
            disabled={isLoading}
            variant="primary"
            isLoading={isLoading}
          >
            Sign In
          </Button>
          
          {!showSignupPrompt && (
            <p className="text-center text-sm text-muted-foreground">
              Don&apos;t have an account?{' '}
              <Link 
                href={`/auth/signup${
                  isInviteFlow 
                    ? `?${new URLSearchParams({
                        ...(searchParams.email && { email: searchParams.email }),
                        ...(searchParams.invite && { invite: searchParams.invite }),
                        ...(searchParams.org && { org: searchParams.org })
                      })}`
                    : searchParams.email 
                      ? `?email=${searchParams.email}`
                      : ''
                }`}
                className="text-primary hover:text-primary/90 transition-colors"
              >
                Sign up
              </Link>
            </p>
          )}
        </form>
      </CardContent>
    </>
  )
}