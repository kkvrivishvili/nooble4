import type { PricingStrategy } from '@/lib/payments/pricestrategyTypes'
import type { UserRole, OrgRole } from '@/lib/rbac/rbacTypes'

// Base routes that don't require auth
export const publicRoutes = [
  '/', 
  '/auth/login', 
  '/auth/signup', 
  '/auth/reset-password',
  '/auth/reset-password/confirm',
  '/pricing'
]

// Admin routes
export const adminRoutes = {
  main: '/dashboard/admin',
  users: '/dashboard/admin/users',
  roles: '/dashboard/admin/roles',
  settings: '/dashboard/admin/settings'
}

// Profile routes - user-centric settings
export const profileRoutes = {
  main: '/dashboard/profile',
  edit: '/dashboard/profile/edit',
  notifications: '/dashboard/profile/notifications'
}

// Settings routes - system/account level settings
export const settingsRoutes = {
  main: '/dashboard/settings',
  security: '/dashboard/settings/security',
  billing: '/dashboard/settings/billing',
  apiKeys: '/dashboard/settings/api'
}

// Organization routes
export const orgRoutes = {
  main: '/dashboard/orgs',
  new: '/dashboard/orgs/new-organization',
  view: (slug: string) => `/dashboard/orgs/${slug}`,
  members: (slug: string) => `/dashboard/orgs/${slug}/members`,
  settings: {
    main: (slug: string) => `/dashboard/orgs/${slug}/settings`,
    general: (slug: string) => `/dashboard/orgs/${slug}/settings/general`,
    members: (slug: string) => `/dashboard/orgs/${slug}/settings/members`,
    billing: (slug: string) => `/dashboard/orgs/${slug}/settings/billing`,
    dangerZone: (slug: string) => `/dashboard/orgs/${slug}/settings/dangerzone`,
  }
} as const

// Auth routes that need special handling
export const authRoutes = {
  public: ['/auth/login', '/auth/signup', '/auth/reset-password'],
  protected: ['/auth/reset-password/confirm'],
  callback: ['/auth/callback', '/auth/oauth-callback']
}

// Routes that require authentication
export const protectedRoutes = [
  '/dashboard',
  ...Object.values(profileRoutes),
  ...Object.values(settingsRoutes),
  ...Object.values(adminRoutes),
  '/dashboard/orgs',
  '/dashboard/orgs/new-organization',
  '/dashboard/orgs/*' // This will cover all organization-specific routes
]

// Helper functions
export function isProfileRoute(pathname: string): boolean {
  return Object.values(profileRoutes)
    .some(route => pathname.startsWith(route))
}

export function isSettingsRoute(pathname: string): boolean {
  return Object.values(settingsRoutes)
    .some(route => pathname.startsWith(route))
}

export function isAuthRoute(pathname: string): boolean {
  return Object.values(authRoutes)
    .flat()
    .some(route => pathname.startsWith(route))
}

export function isAdminRoute(pathname: string): boolean {
  return pathname.startsWith('/dashboard/admin')
}

export function isProtectedRoute(pathname: string): boolean {
  return protectedRoutes.some(route => pathname.startsWith(route))
}

// Payment required routes based on strategy
export const paymentRequiredRoutes = {
  freemium: ['/pro-features', '/api/pro'],
  paywall: [...protectedRoutes], // All protected routes require payment
  trial: [] // No routes require payment during trial
}

export function isPaymentRequiredRoute(
  pathname: string, 
  strategy: PricingStrategy = 'freemium'
): boolean {
  return paymentRequiredRoutes[strategy].some(route => 
    pathname.startsWith(route)
  )
}

export function shouldCheckPayment(
  pathname: string,
  strategy: PricingStrategy = 'freemium'
): boolean {
  return isProtectedRoute(pathname) || isPaymentRequiredRoute(pathname, strategy)
}

export const roleRestrictedRoutes: Record<UserRole, string[]> = {
  user: [],
  admin: [
    '/dashboard/admin',
    '/dashboard/admin/users',
    '/dashboard/analytics'
  ],
  super_admin: [
    '/dashboard/admin',
    '/dashboard/admin/users',
    '/dashboard/admin/roles',
    '/dashboard/analytics',
    '/dashboard/settings/system'
  ]
}

export function isRouteAllowedForRole(pathname: string, role: UserRole): boolean {
  if (role === 'super_admin') return true
  return !roleRestrictedRoutes[role].some(route => pathname.startsWith(route))
}

// Helper function for org routes
export function isOrgRoute(pathname: string): boolean {
  return pathname.startsWith('/dashboard/orgs')
}

// Organization role-based route restrictions
export const orgRoleRestrictedRoutes: Record<OrgRole, string[]> = {
  member: [
    '/settings/general',
    '/settings/members',
    '/settings/billing'
  ],
  admin: [
    '/settings/billing'
  ],
  owner: []
}

// Helper to check if a route is allowed for an org role
export function isOrgRouteAllowedForRole(pathname: string, role: OrgRole): boolean {
  const restrictedRoutes = orgRoleRestrictedRoutes[role]
  return !restrictedRoutes.some(route => pathname.includes(route))
}

// Helper to get the settings section from a pathname
export function getOrgSettingsSection(pathname: string): string | null {
  const match = pathname.match(/\/settings\/([^/]+)/)
  return match ? match[1] : null
}

// Update isSpecificOrgRoute to handle settings routes
export function isSpecificOrgRoute(pathname: string): boolean {
  const orgPathRegex = /^\/dashboard\/orgs\/(?!new-organization)[^/]+/
  const isOrgRoute = orgPathRegex.test(pathname)
  
  if (isOrgRoute) {
    const section = getOrgSettingsSection(pathname)
    if (section) {
      // For members, only allow dangerzone
      if (pathname.includes('/settings') && section !== 'dangerzone') {
        return false
      }
    }
  }
  
  return isOrgRoute
}