'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Label } from '@/components/ui/Label'
import { CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { requestPasswordReset } from '@/lib/auth/password'

export default function RequestResetPage() {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setIsLoading(true)
    setError('')

    const formData = new FormData(event.currentTarget)
    const email = formData.get('email') as string

    try {
      const { error } = await requestPasswordReset(email)
      
      if (error) {
        setError(error.message)
        return
      }

      setSuccess(true)
    } catch (error) {
      console.error('Reset password error:', error)
      setError('Failed to reset password')
    } finally {
      setIsLoading(false)
    }
  }

  if (success) {
    return (
      <>
        <CardHeader>
          <CardTitle>Check your email</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">
            We&apos;ll send you a link to reset your password. Please check your email.
          </p>
        </CardContent>
      </>
    )
  }

  return (
    <>
      <CardHeader>
        <CardTitle>Reset Password</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              name="email"
              type="email"
              required
              placeholder="name@example.com"
            />
          </div>
          {error && (
            <div className="text-sm text-red-500">
              {error}
            </div>
          )}
          <Button
            type="submit"
            className="w-full"
            disabled={isLoading}
          >
            {isLoading ? 'Sending...' : 'Send Reset Link'}
          </Button>
        </form>
      </CardContent>
    </>
  )
}
