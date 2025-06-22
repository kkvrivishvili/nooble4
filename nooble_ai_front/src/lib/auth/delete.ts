import type { ExportResponse } from '@/lib/auth/authTypes'
import { getSupabaseBrowserClient } from './config'
import { trackActivity } from '@/lib/rbac/analytics'

export async function deleteAccount(): Promise<ExportResponse> {
  try {
    const supabase = getSupabaseBrowserClient()
    const { data: { user } } = await supabase.auth.getUser()

    if (user) {
      await trackActivity({
        userId: user.id,
        actionType: 'account_deleted',
        metadata: {
          timestamp: new Date().toISOString(),
          userAgent: window.navigator.userAgent
        }
      }).catch(console.error)
    }

    const response = await fetch('/api/auth/delete', {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
      },
    })

    const data = await response.json()

    if (!response.ok) {
      throw new Error(data.error.message || 'Failed to delete account')
    }

    return { success: true, error: null }
  } catch (error) {
    console.error('Account deletion error:', error)
    return { 
      success: false, 
      error: error instanceof Error ? error : new Error('Failed to delete account') 
    }
  }
} 