import { getSupabaseBrowserClient } from './config'
import { trackActivity } from '@/lib/rbac/analytics'

export async function requestPasswordReset(email: string) {
  try {
    const supabase = getSupabaseBrowserClient()
    const { error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/auth/reset-password/confirm`,
    })
    
    return { error }
  } catch (error) {
    console.error('Password reset request failed:', error)
    return { error: new Error('Failed to send reset email') }
  }
}

export async function updatePassword(newPassword: string) {
  if (!newPassword || newPassword.length < 8) {
    return { error: new Error('Password must be at least 8 characters long') }
  }

  try {
    const supabase = getSupabaseBrowserClient()
    const { data: { user } } = await supabase.auth.getUser()
    const { error } = await supabase.auth.updateUser({
      password: newPassword
    })

    if (!error && user) {
      await trackActivity({
        userId: user.id,
        actionType: 'password_updated',
        metadata: {
          timestamp: new Date().toISOString(),
          userAgent: window.navigator.userAgent
        }
      }).catch(console.error)
    }

    if (error) throw error
    return { error: null }
  } catch (error) {
    console.error('Password update failed:', error)
    return { error: new Error('Failed to update password') }
  }
}
