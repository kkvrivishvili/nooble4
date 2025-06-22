'use client'

import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Label } from '@/components/ui/Label'
import { updatePassword } from '@/lib/auth/password'
import { PasswordStrengthIndicator } from '@/components/settings/PasswordStrenghtIndicator'
import { Eye, EyeOff } from 'lucide-react'
import { getSupabaseBrowserClient } from '@/lib/auth/config'

export function SecuritySettings() {
  const [isLoading, setIsLoading] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)
  const [showPasswords, setShowPasswords] = useState({
    current: false,
    new: false,
    confirm: false
  })
  const [formData, setFormData] = useState({
    currentPassword: '',
    newPassword: '',
    confirmPassword: ''
  })
  const [userEmail, setUserEmail] = useState('')

  useEffect(() => {
    const getUserEmail = async () => {
      const supabase = getSupabaseBrowserClient()
      const { data: { user } } = await supabase.auth.getUser()
      if (user?.email) {
        setUserEmail(user.email)
      }
    }
    getUserEmail()
  }, [])

  const validatePassword = (password: string) => {
    const requirements = [
      password.length >= 8,
      /[a-z]/.test(password),
      /[A-Z]/.test(password),
      /[0-9]/.test(password),
      /[^a-zA-Z0-9]/.test(password)
    ]
    return requirements.every(Boolean)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    setMessage(null)

    if (!validatePassword(formData.newPassword)) {
      setMessage({ type: 'error', text: 'Password does not meet requirements' })
      setIsLoading(false)
      return
    }

    if (formData.newPassword !== formData.confirmPassword) {
      setMessage({ type: 'error', text: 'New passwords do not match' })
      setIsLoading(false)
      return
    }

    try {
      const { error } = await updatePassword(formData.newPassword)
      if (error) throw error
      setMessage({ type: 'success', text: 'Password updated successfully' })
      setFormData({ currentPassword: '', newPassword: '', confirmPassword: '' })
    } catch (error) {
      console.error('Failed to update password:', error)
      setMessage({ type: 'error', text: 'Failed to update password' })
    } finally {
      setIsLoading(false)
    }
  }

  const togglePasswordVisibility = (field: keyof typeof showPasswords) => {
    setShowPasswords(prev => ({ ...prev, [field]: !prev[field] }))
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <input
        type="text"
        autoComplete="username"
        value={userEmail}
        readOnly
        className="hidden"
        aria-hidden="true"
      />

      {message && (
        <div className={`p-3 rounded-md ${
          message.type === 'success' ? 'bg-success/10 text-success' : 'bg-destructive/10 text-destructive'
        }`}>
          {message.text}
        </div>
      )}

      <div className="space-y-2">
        <Label 
          htmlFor="currentPassword"
          variant="primary"
          size="md"
        >
          Current Password
        </Label>
        <div className="relative">
          <Input
            id="currentPassword"
            type={showPasswords.current ? 'text' : 'password'}
            autoComplete="current-password"
            value={formData.currentPassword}
            onChange={(e) => setFormData(prev => ({ ...prev, currentPassword: e.target.value }))}
            required
            variant="primary"
            size="md"
          />
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="absolute right-0 top-0 h-full px-3 text-muted-foreground hover:text-foreground"
            onClick={() => togglePasswordVisibility('current')}
          >
            {showPasswords.current ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </Button>
        </div>
      </div>

      <div className="space-y-2">
        <Label 
          htmlFor="newPassword"
          variant="primary"
          size="md"
        >
          New Password
        </Label>
        <div className="relative">
          <Input
            id="newPassword"
            type={showPasswords.new ? 'text' : 'password'}
            autoComplete="new-password"
            value={formData.newPassword}
            onChange={(e) => setFormData(prev => ({ ...prev, newPassword: e.target.value }))}
            required
            variant="primary"
            size="md"
          />
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="absolute right-0 top-0 h-full px-3 text-muted-foreground hover:text-foreground"
            onClick={() => togglePasswordVisibility('new')}
          >
            {showPasswords.new ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </Button>
        </div>
        {formData.newPassword && (
          <PasswordStrengthIndicator password={formData.newPassword} />
        )}
      </div>

      <div className="space-y-2">
        <Label 
          htmlFor="confirmPassword"
          variant="primary"
          size="md"
        >
          Confirm New Password
        </Label>
        <div className="relative">
          <Input
            id="confirmPassword"
            type={showPasswords.confirm ? 'text' : 'password'}
            autoComplete="new-password"
            value={formData.confirmPassword}
            onChange={(e) => setFormData(prev => ({ ...prev, confirmPassword: e.target.value }))}
            required
            variant="primary"
            size="md"
          />
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="absolute right-0 top-0 h-full px-3 text-muted-foreground hover:text-foreground"
            onClick={() => togglePasswordVisibility('confirm')}
          >
            {showPasswords.confirm ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </Button>
        </div>
      </div>

      <Button 
        type="submit" 
        variant="primary"
        size="md"
        isLoading={isLoading}
      >
        Update Password
      </Button>
    </form>
  )
} 