'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Label } from '@/components/ui/Label'
import { CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { signup } from '@/lib/auth/signup'
import { SocialLogin } from '@/components/auth/SocialLogin'
import { Divider } from '@/components/ui/Divider'
import { PasswordStrengthIndicator } from '@/components/settings/PasswordStrenghtIndicator'
import type { AuthSearchParams } from '@/lib/auth/authTypes'
import { PricingStrategy } from '@/lib/payments/pricestrategyTypes'
import { Checkbox } from '@/components/ui/Checkbox'

interface SignupFormProps {
  searchParams: AuthSearchParams
}

export function SignupForm({ searchParams }: SignupFormProps) {
  const router = useRouter()
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [password, setPassword] = useState('')
  const [isInviteFlow] = useState(!!searchParams.invite)

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setIsLoading(true)
    setError('')

    try {
      const formData = new FormData(event.currentTarget)
      const email = formData.get('email') as string
      const confirmPassword = formData.get('confirmPassword') as string

      const result = await signup({ 
        email, 
        password, 
        confirmPassword,
        inviteToken: searchParams.invite,
        orgSlug: searchParams.org
      })
      
      if (result.error) {
        setError(result.error.message)
        setIsLoading(false)
        return
      }

      if (result.metadata?.redirectTo) {
        router.push(result.metadata.redirectTo)
      } else {
        router.push('/auth/verify-email')
      }
    } catch (error) {
      console.error('Signup error:', error)
      setError('Error creating account')
      setIsLoading(false)
    }
  }

  const searchParamsObject: Record<string, string> = {}
  if (isInviteFlow) {
    if (searchParams.email) searchParamsObject.email = searchParams.email
    if (searchParams.invite) searchParamsObject.invite = searchParams.invite
    if (searchParams.org) searchParamsObject.org = searchParams.org
  } else if (searchParams.email) {
    searchParamsObject.email = searchParams.email
  }

  return (
    <>
      <CardHeader>
        <CardTitle className="text-foreground">
          {isInviteFlow 
            ? "Join Organization" 
            : "Create an account"}
        </CardTitle>
        {isInviteFlow && (
          <p className="text-sm text-muted-foreground mt-2">
            Create an account to accept the invitation
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
              defaultValue={searchParams.email}
              variant="primary"
              size="md"
            />
          </div>
          <div className="space-y-2">
            <Label 
              htmlFor="password" 
              variant="primary"
              size="md"
            >
              Password
            </Label>
            <Input
              id="password"
              name="password"
              type="password"
              autoComplete="new-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              variant="primary"
              size="md"
            />
            <PasswordStrengthIndicator password={password} />
          </div>
          <div className="space-y-2">
            <Label 
              htmlFor="confirmPassword" 
              variant="primary"
              size="md"
            >
              Confirm Password
            </Label>
            <Input
              id="confirmPassword"
              name="confirmPassword"
              type="password"
              autoComplete="new-password"
              required
              variant="primary"
              size="md"
            />
          </div>
          {error && (
            <div className="text-sm text-destructive">
              {error}
            </div>
          )}
          <div className="space-y-4">
            <Checkbox
              id="terms"
              required
              variant="primary"
              size="md"
              label={
                <span className="text-sm text-muted-foreground">
                  I agree to the{' '}
                  <Link 
                    href="/terms" 
                    className="text-primary hover:text-primary/90 transition-colors"
                  >
                    Terms of Service
                  </Link>
                  {' '}and{' '}
                  <Link 
                    href="/privacy" 
                    className="text-primary hover:text-primary/90 transition-colors"
                  >
                    Privacy Policy
                  </Link>
                </span>
              }
            />
            <Button
              type="submit"
              className="w-full"
              disabled={isLoading}
              variant="primary"
              isLoading={isLoading}
            >
              Sign Up
            </Button>
          </div>
          <p className="text-center text-sm text-muted-foreground">
            Already have an account?{' '}
            <Link 
              href={`/auth/login${
                Object.keys(searchParamsObject).length 
                  ? `?${new URLSearchParams(searchParamsObject)}` 
                  : ''
              }`}
              className="text-primary hover:text-primary/90 transition-colors"
            >
              Sign in
            </Link>
          </p>
        </form>
      </CardContent>
    </>
  )
} 