/**
 * Auth Restrictions Configuration
 * 
 * DEVELOPMENT:
 * - Set NODE_ENV=development to enable testMode (allows all users)
 * - Or configure ALLOWED_EMAILS/ALLOWED_DOMAINS for testing specific accounts
 * 
 * PRODUCTION:
 * 1. First deployment (closed beta):
 *    - Set specific ALLOWED_EMAILS for beta testers
 *    - Example: ALLOWED_EMAILS=user1@domain.com,user2@domain.com
 * 
 * 2. Organization/Enterprise setup:
 *    - Set ALLOWED_DOMAINS for company-wide access
 *    - Example: ALLOWED_DOMAINS=company.com,subsidiary.com
 * 
 * 3. Public launch:
 *    - Option 1: Remove all env variables to allow everyone
 *    - Option 2: Keep restrictions but expand allowed list
 *    - Option 3: Implement custom logic in isUserAllowed()
 */

// Add this at the top with other env configurations
export const AUTH_CONFIG = {
  // Easy toggle for auth restrictions
  ENABLE_RESTRICTIONS: process.env.ENABLE_AUTH_RESTRICTIONS === 'true',
  // For quick testing, set to false to enforce restrictions in dev
  TEST_MODE: process.env.NODE_ENV === 'development'
} as const

export type AuthRestriction = {
  allowedEmails?: string[]
  allowedDomains?: string[]
}

/**
 * Default restrictions from environment variables
 * 
 * Usage:
 * 1. Development: 
 *    NODE_ENV=development (testMode=true)
 * 
 * 2. Production:
 *    ALLOWED_EMAILS=email1,email2
 *    ALLOWED_DOMAINS=domain1,domain2
 * 
 * 3. No Restrictions:
 *    Leave both ALLOWED_EMAILS and ALLOWED_DOMAINS unset
 */
export const DEFAULT_AUTH_RESTRICTIONS: AuthRestriction = {
  allowedEmails: process.env.ALLOWED_EMAILS?.split(',').map(email => email.trim()) || [],
  allowedDomains: process.env.ALLOWED_DOMAINS?.split(',').map(domain => domain.trim()) || [],
}

/**
 * Checks if a user's email is allowed based on configured restrictions
 * 
 * @param email - User's email address
 * @param restrictions - Optional custom restrictions (defaults to env config)
 * @returns boolean - Whether the user is allowed
 * 
 * Production Scenarios:
 * 1. Closed Beta:
 *    - Configure ALLOWED_EMAILS in production env
 *    - Only listed emails can access
 * 
 * 2. Organization Access:
 *    - Configure ALLOWED_DOMAINS in production env
 *    - Anyone with matching email domain can access
 * 
 * 3. Public Access:
 *    - Remove all env restrictions
 *    - Function will return true for all emails
 * 
 * 4. Custom Logic:
 *    - Modify this function to add custom rules
 *    - Example: Check against user database, validate subscriptions, etc.
 */
export function isUserAllowed(
  email: string, 
  restrictions: AuthRestriction = DEFAULT_AUTH_RESTRICTIONS
): boolean {
  // Quick bypass if restrictions are disabled
  if (!AUTH_CONFIG.ENABLE_RESTRICTIONS || AUTH_CONFIG.TEST_MODE) {
    console.log('Auth restrictions disabled:', 
      !AUTH_CONFIG.ENABLE_RESTRICTIONS ? 'globally' : 'in test mode')
    return true
  }
  
  // Check specific allowed emails
  if (restrictions.allowedEmails?.length) {
    return restrictions.allowedEmails.includes(email.toLowerCase())
  }
  
  // Check allowed domains
  if (restrictions.allowedDomains?.length) {
    return restrictions.allowedDomains.some(domain => 
      email.toLowerCase().endsWith(domain.toLowerCase())
    )
  }
  
  // No restrictions configured - allow all users
  return true
}