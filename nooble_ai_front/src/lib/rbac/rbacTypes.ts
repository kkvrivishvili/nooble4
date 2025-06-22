import type { UserRow, ProfileRow } from '@/types/api'
import type { Database } from '@/types/supabase'
import type { RealtimeChannel, RealtimePostgresChangesPayload } from '@supabase/supabase-js'

// Role types
export type UserRole = 'user' | 'admin' | 'super_admin'
export type RoleRow = Database['public']['Tables']['roles']['Row']

// Role permissions mapping
export const ROLE_PERMISSIONS: Record<UserRole, RolePermissions> = {
  user: {
    canManageUsers: false,
    canViewAnalytics: false,
    canManageRoles: false,
    canAccessAdminPanel: false,
    canManageSettings: false
  },
  admin: {
    canManageUsers: true,
    canViewAnalytics: true,
    canManageRoles: false,
    canAccessAdminPanel: true,
    canManageSettings: true
  },
  super_admin: {
    canManageUsers: true,
    canViewAnalytics: true,
    canManageRoles: true,
    canAccessAdminPanel: true,
    canManageSettings: true
  }
} as const

export interface RolePermissions {
  canManageUsers: boolean
  canViewAnalytics: boolean
  canManageRoles: boolean
  canAccessAdminPanel: boolean
  canManageSettings: boolean
}

// Role responses with better error typing
export interface RoleResponse {
  data: RoleRow | null
  error: Error | null
  subscription?: RealtimeChannel
}

export interface RolesResponse {
  data: RoleRow[]
  error: Error | null
}

// Combined user and role data
export interface UserWithRole extends UserRow {
  role: RoleRow
  profile?: ProfileRow
}

export interface UserWithRoleResponse {
  data: UserWithRole | null
  error: Error | null
}

// Helper function to check if a role has a specific permission
export function hasPermission(role: UserRole, permission: keyof RolePermissions): boolean {
  return ROLE_PERMISSIONS[role][permission]
}

// Add new types for realtime
export type RoleUpdatePayload = RealtimePostgresChangesPayload<{
  old: RoleRow
  new: RoleRow
}>

export type RoleChannel = RealtimeChannel

// Add org roles
export type OrgRole = 'owner' | 'admin' | 'member'

// Add org permissions
export interface OrgPermissions {
  canManageSettings: boolean
  canManageMembers: boolean
  canManageBilling: boolean
}

export const ORG_ROLE_PERMISSIONS: Record<OrgRole, OrgPermissions> = {
  owner: {
    canManageSettings: true,
    canManageMembers: true,
    canManageBilling: true
  },
  admin: {
    canManageSettings: true,
    canManageMembers: true,
    canManageBilling: false
  },
  member: {
    canManageSettings: false,
    canManageMembers: false,
    canManageBilling: false
  }
}
