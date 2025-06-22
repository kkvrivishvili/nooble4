import type { PricingStrategy, PricingRedirectConfig } from './pricestrategyTypes'

const redirectPaths: PricingRedirectConfig = {
  freemium: {
    afterSignup: '/dashboard',
    afterLogin: '/dashboard'
  },
  paywall: {
    afterSignup: '/pricing',
    afterLogin: '/dashboard'
  },
  trial: {
    afterSignup: '/dashboard',
    afterLogin: '/dashboard'
  }
}

export function getRedirectPath(
  type: 'signup' | 'login',
  strategy: PricingStrategy = 'freemium'
): string {
  return type === 'signup' 
    ? redirectPaths[strategy].afterSignup 
    : redirectPaths[strategy].afterLogin
} 