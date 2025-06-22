export type PricingStrategy = 'freemium' | 'paywall' | 'trial'

export interface PricingRedirectConfig {
  freemium: {
    afterSignup: string
    afterLogin: string
  }
  paywall: {
    afterSignup: string
    afterLogin: string
  }
  trial: {
    afterSignup: string
    afterLogin: string
  }
} 