import type { UserRole } from '@/lib/rbac/rbacTypes'
import type { OrgRole } from '@/lib/rbac/rbacTypes'
import { ROLE_PERMISSIONS, ORG_ROLE_PERMISSIONS } from '@/lib/rbac/rbacTypes'

export function checkRoleAccess(role: UserRole, pathname: string): boolean {
  const permissions = ROLE_PERMISSIONS[role]

  if (pathname.startsWith('/dashboard/admin')) {
    return permissions.canAccessAdminPanel
  }

  if (pathname.startsWith('/dashboard/analytics')) {
    return permissions.canViewAnalytics
  }

  return true
}

export function checkOrgAccess(
  orgRole: OrgRole, 
  pathname: string
): boolean {
  const permissions = ORG_ROLE_PERMISSIONS[orgRole]

  // Check settings access by specific section
  if (pathname.includes('/settings')) {
    // Members can only access danger zone
    if (orgRole === 'member') {
      return pathname.includes('/dangerzone')
    }

    // General settings - owners and admins only
    if (pathname.includes('/general')) {
      return permissions.canManageSettings
    }

    // Members settings - owners and admins only
    if (pathname.includes('/members')) {
      return permissions.canManageMembers
    }

    // Billing settings - owners only
    if (pathname.includes('/billing')) {
      return permissions.canManageBilling
    }

    // Danger zone - all roles can access
    if (pathname.includes('/dangerzone')) {
      return true
    }

    // Default settings access - owners and admins only
    return permissions.canManageSettings
  }

  // Allow access to overview by default
  return true
}