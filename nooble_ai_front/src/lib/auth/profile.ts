import { getSupabaseBrowserClient } from './config'
import type { ProfileUpdateParams, ProfileResponse } from './authTypes'
import { trackActivity } from '@/lib/rbac/analytics'
import { RateLimitError } from '@/lib/auth/authTypes'
import { ProfileUpdateSchema, AvatarUrlSchema } from '@/middleware/schemas'

// Helper for avatar URL validation and cleanup
async function handleAvatarUpdate(
  supabase: ReturnType<typeof getSupabaseBrowserClient>,
  userId: string,
  newAvatarUrl: string | null | undefined,
  oldAvatarUrl: string | null | undefined
) {
  // Skip if no change
  if (newAvatarUrl === oldAvatarUrl) return { url: oldAvatarUrl, error: null }

  try {
    // Validate new avatar URL
    await AvatarUrlSchema.parseAsync(newAvatarUrl)

    // Clean up old avatar if it was in our storage
    if (oldAvatarUrl?.includes('Avatars')) {
      const oldPath = oldAvatarUrl.split('/').pop()
      if (oldPath) {
        await supabase.storage
          .from('Avatars')
          .remove([oldPath])
      }
    }

    // Update both auth and profile atomically
    const [authUpdate, profileUpdate] = await Promise.all([
      supabase.auth.updateUser({
        data: { 
          avatar_url: newAvatarUrl,
          picture: newAvatarUrl // Keep both synced
        }
      }),
      supabase
        .from('profiles')
        .update({ avatar_url: newAvatarUrl })
        .eq('id', userId)
    ])

    if (authUpdate.error) throw authUpdate.error
    if (profileUpdate.error) throw profileUpdate.error

    return { url: newAvatarUrl, error: null }
  } catch (error) {
    console.error('Avatar update failed:', error)
    return { 
      url: null, 
      error: error instanceof Error ? error : new Error('Avatar update failed')
    }
  }
}

export async function updateProfile({ 
  id, 
  full_name, 
  avatar_url,
  updated_at 
}: ProfileUpdateParams): Promise<ProfileResponse> {
  try {
    const supabase = getSupabaseBrowserClient()

    // Get current user state
    const { data: { user } } = await supabase.auth.getUser()
    if (!user) throw new Error('Not authenticated')

    const isOAuthUser = user.app_metadata?.provider === 'google'

    // Validate input data
    const validatedData = ProfileUpdateSchema.parse({
      id,
      full_name,
      avatar_url,
      updated_at: updated_at || new Date().toISOString()
    })

    // OAuth name restriction
    if (isOAuthUser && full_name !== user.user_metadata.full_name) {
      throw new Error('Cannot change name for Google-linked accounts')
    }

    // Get current profile for comparison
    const { data: currentProfile } = await supabase
      .from('profiles')
      .select('avatar_url')
      .eq('id', id)
      .single()

    // Handle avatar update if needed
    if (avatar_url !== undefined) {
      const { error: avatarError } = await handleAvatarUpdate(
        supabase,
        id,
        avatar_url,
        currentProfile?.avatar_url
      )
      if (avatarError) throw avatarError
    }

    // Update remaining profile data
    const { data, error: profileError } = await supabase
      .from('profiles')
      .update({
        full_name: validatedData.full_name,
        updated_at: validatedData.updated_at
      })
      .eq('id', id)
      .select()
      .single()

    if (profileError) {
      if (profileError.code === '42704' && profileError.message?.includes('429')) {
        throw new RateLimitError('Too many profile updates. Please try again later.')
      }
      throw profileError
    }

    // Track successful update
    if (data) {
      await trackActivity({
        userId: id,
        actionType: 'profile_updated',
        metadata: {
          timestamp: new Date().toISOString(),
          userAgent: window.navigator.userAgent,
          updates: { 
            full_name: validatedData.full_name,
            avatar_updated: avatar_url !== undefined
          }
        }
      }).catch(console.error)
    }

    return { data, error: null }

  } catch (error) {
    console.error('Profile update failed:', error)
    return {
      data: null,
      error: error instanceof Error ? error : new Error('Failed to update profile')
    }
  }
} 