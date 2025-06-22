import { createBrowserClient } from '@supabase/ssr'
import type { SessionsResponse, SessionResponse } from './authTypes'
import { trackActivity } from '@/lib/rbac/analytics'

export async function getUserSessions(): Promise<SessionsResponse> {
  try {
    const supabase = createBrowserClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
    )

    const { data: { user }, error: userError } = await supabase.auth.getUser()
    if (userError || !user) {
      return {
        data: [],
        error: new Error('Not authenticated')
      }
    }

    const { data: { session: currentSession } } = await supabase.auth.getSession()

    // Get the current session and format it
    const formattedSession = currentSession ? [{
      id: currentSession.access_token,
      user_id: user.id,
      created_at: new Date(currentSession.expires_at! * 1000).toISOString(),
      last_active: new Date().toISOString(),
      user_agent: window.navigator.userAgent,
      is_current: true
    }] : []

    return {
      data: formattedSession,
      error: null
    }
  } catch (error) {
    console.error('Sessions fetch failed:', error)
    return {
      data: [],
      error: new Error('Failed to fetch sessions')
    }
  }
}

export async function revokeSession(): Promise<SessionResponse> {
  try {
    const supabase = createBrowserClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
    )

    const { data: { user } } = await supabase.auth.getUser()

    if (user) {
      // Track session revocation
      await trackActivity({
        userId: user.id,
        actionType: 'session_revoked',
        metadata: {
          timestamp: new Date().toISOString(),
          userAgent: window.navigator.userAgent
        }
      }).catch(console.error)
    }

    const { error } = await supabase.auth.signOut({
      scope: 'global'
    })

    if (error) {
      console.error('Session revocation error:', error)
      return {
        data: null,
        error: new Error(error.message)
      }
    }

    return {
      data: null,
      error: null
    }
  } catch (error) {
    console.error('Session revocation failed:', error)
    return {
      data: null,
      error: new Error('Failed to revoke session')
    }
  }
} 