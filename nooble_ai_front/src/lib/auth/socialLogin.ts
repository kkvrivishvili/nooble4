import type { Provider } from '@supabase/supabase-js'
import type { AuthResponse } from './authTypes'
import { getRedirectPath } from '@/lib/payments/redirects'
import { PricingStrategy } from '../payments/pricestrategyTypes'
import { getOAuthClient } from './config'
import { InviteValidationSchema } from '@/middleware/schemas'

export const ENABLED_PROVIDERS = {
  google: true,
  github: false, // Disabled by default
  // Add more providers here
} as const

export function getSupportedProviders() {
  return Object.entries(ENABLED_PROVIDERS)
    .filter(([, enabled]) => enabled)
    .map(([provider]) => provider)
}

export async function socialLogin(
  provider: Provider,
  strategy: PricingStrategy = 'freemium',
  inviteToken?: string,
  orgSlug?: string
): Promise<AuthResponse> {
  const supabase = getOAuthClient()
  
  // Build redirect URL with invite parameters
  const redirectParams = new URLSearchParams()
  
  if (inviteToken) {
    // We want to handle the invite acceptance after successful OAuth
    redirectParams.set('invite_token', inviteToken)
    if (orgSlug) {
      redirectParams.set('org_slug', orgSlug)
    }
    // Set returnUrl for after auth completion
    redirectParams.set('returnUrl', `/dashboard/orgs/${orgSlug}/invite?token=${inviteToken}`)
  } else {
    // Normal flow without invite
    redirectParams.set('next', getRedirectPath('login', strategy))
  }

  // Validate invite token if present
  if (inviteToken) {
    try {
      InviteValidationSchema.parse({ token: inviteToken })
    } catch (error) {
      console.error('Invalid invite token:', error)
      return {
        data: null,
        error: new Error('Invalid invite token')
      }
    }
  }

  const { error } = await supabase.auth.signInWithOAuth({
    provider,
    options: {
      redirectTo: `${window.location.origin}/auth/oauth-callback?${redirectParams}`,
      scopes: 'email profile',
      queryParams: {
        // Add access_type to ensure we get a refresh token
        access_type: 'offline',
        // Prompt to ensure we always get consent
        prompt: 'consent'
      }
    },
  })

  if (error) {
    return { data: null, error }
  }

  return { data: null, error: null }
} 