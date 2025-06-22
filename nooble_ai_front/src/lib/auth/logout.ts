import { createBrowserClient } from '@supabase/ssr'
import type { AuthResponse } from './authTypes'
import { trackActivity } from '@/lib/rbac/analytics'

export async function logout(): Promise<AuthResponse> {
  const supabase = createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  )

  // Get user before signing out
  const { data: { user } } = await supabase.auth.getUser()

  const { error } = await supabase.auth.signOut()

  if (error) {
    return {
      data: null,
      error
    }
  }

  // Explicitly clear PKCE-related cookies
  document.cookie = 'sb-access-token=; Max-Age=0; path=/'
  document.cookie = 'sb-refresh-token=; Max-Age=0; path=/'
  document.cookie = 'sb-lbrlhpjeffkoaydsnsry-auth-token-code-verifier=; Max-Age=0; path=/'

  // Track the logout if we had a user
  if (user) {
    await trackActivity({
      userId: user.id,
      actionType: 'logout',
      metadata: {
        timestamp: new Date().toISOString(),
        userAgent: window.navigator.userAgent
      }
    }).catch(console.error) // Non-blocking
  }

  return {
    data: null,
    error: null
  }
}
