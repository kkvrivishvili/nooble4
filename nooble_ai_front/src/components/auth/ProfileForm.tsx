'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Label } from '@/components/ui/Label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/Tabs'
import { updateProfile } from '@/lib/auth/profile'
import type { UserRow, ProfileRow } from '@/types/api'
import { AvatarUpload } from '@/components/dashboard/profile/AvatarUpload'
import { toast } from 'sonner'
import { RateLimitError } from '@/lib/auth/authTypes'


interface ProfileFormProps {
  profile: ProfileRow
  user: UserRow & {
    app_metadata?: {
      provider?: string
    }
    user_metadata?: {
      full_name?: string
    }
  }
}

export function ProfileForm({ profile, user }: ProfileFormProps) {
  const router = useRouter()
  const [isLoading, setIsLoading] = useState(false)
  const [pendingAvatarUrl, setPendingAvatarUrl] = useState<string | null>(null)
  const [formData, setFormData] = useState({
    full_name: profile?.full_name || '',
    avatar_url: profile?.avatar_url || null,
  })

  const isOAuthUser = user.app_metadata?.provider === 'google'

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { id, value } = e.target
    setFormData(prev => ({
      ...prev,
      [id]: value
    }))
  }

  const handleAvatarUpdate = (url: string | null) => {
    if (url && !url.includes('Avatars')) {
      console.error('Invalid avatar URL received:', url)
      toast.error('Invalid avatar URL format')
      return
    }
    
    setPendingAvatarUrl(url)
    setFormData(prev => ({
      ...prev,
      avatar_url: url
    }))
  }

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    setIsLoading(true)

    try {
      const avatarUrl = pendingAvatarUrl ?? formData.avatar_url
      if (avatarUrl && !avatarUrl.includes('Avatars')) {
        throw new Error('Invalid avatar URL format')
      }

      const { error } = await updateProfile({
        id: profile.id,
        full_name: formData.full_name,
        avatar_url: avatarUrl,
        updated_at: new Date().toISOString()
      })

      if (error) {
        if (error instanceof RateLimitError) {
          toast.error('Too many updates. Please wait a minute and try again.')
          return
        }
        throw error
      }
      
      setFormData(prev => ({
        ...prev,
        avatar_url: avatarUrl
      }))
      setPendingAvatarUrl(null)
      
      toast.success('Profile updated successfully')
      router.refresh()

    } catch (error) {
      console.error('Profile update failed:', error)
      setFormData(prev => ({
        ...prev,
        avatar_url: profile.avatar_url?.includes('Avatars') ? profile.avatar_url : null
      }))
      setPendingAvatarUrl(null)
      toast.error(error instanceof Error ? error.message : 'Failed to update profile')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <Tabs defaultValue="general" className="w-full">
      <TabsList className="grid w-full grid-cols-2">
        <TabsTrigger value="general">General</TabsTrigger>
        <TabsTrigger value="preferences">Preferences</TabsTrigger>
      </TabsList>

      <TabsContent value="general">
        <Card>
          <CardHeader>
            <CardTitle className="text-foreground">Profile Information</CardTitle>
            <CardDescription className="text-muted-foreground">
              Update your personal information and how others see you on the platform.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="mb-6">
              <AvatarUpload
                context={{
                  type: 'user',
                  id: profile.id
                }}
                currentAvatar={formData.avatar_url}
                onUploadComplete={handleAvatarUpdate}
                isFormSubmitting={isLoading}
              />
            </div>

            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="grid gap-6 md:grid-cols-2">
                <div className="space-y-2">
                  <Label 
                    htmlFor="full_name"
                    variant="primary"
                    size="md"
                  >
                    Full Name
                  </Label>
                  <Input
                    id="full_name"
                    value={formData.full_name}
                    onChange={handleChange}
                    placeholder="Enter your full name"
                    disabled={isOAuthUser}
                    aria-description={isOAuthUser ? "Name cannot be changed for Google accounts" : undefined}
                    variant="primary"
                    size="md"
                  />
                  {isOAuthUser && (
                    <p className="text-sm text-muted-foreground mt-1">
                      Name is managed by your Google account
                    </p>
                  )}
                </div>

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
                    type="email"
                    value={user.email}
                    disabled
                    variant="primary"
                    size="md"
                  />
                </div>
              </div>

              <div className="flex justify-end">
                <Button 
                  type="submit" 
                  isLoading={isLoading}
                  disabled={!pendingAvatarUrl && formData.full_name === profile.full_name}
                  variant="primary"
                >
                  Save Changes
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </TabsContent>

      <TabsContent value="preferences">
        <Card>
          <CardHeader>
            <CardTitle className="text-foreground">Preferences</CardTitle>
            <CardDescription className="text-muted-foreground">
              Manage your notification preferences and account settings.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {/* We'll add notification preferences here later */}
            <p className="text-sm text-muted-foreground">
              Notification preferences coming soon...
            </p>
          </CardContent>
        </Card>
      </TabsContent>
    </Tabs>
  )
} 