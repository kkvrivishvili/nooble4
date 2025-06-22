export type OrgRole = 'owner' | 'admin' | 'member'

export interface Organization {
  id: string
  name: string
  slug: string
  avatar_url?: string
  created_at: string
  updated_at: string
}

// Base OrgMember type (for database operations)
export interface OrgMember {
  org_id: string
  user_id: string
  role: OrgRole
  joined_at: string
}

// Extended type for UI with profiles
export interface OrgMemberWithProfile extends OrgMember {
  profiles: {
    id: string
    email: string | null
    full_name: string | null
    avatar_url: string | null
  } | null
}

export interface OrgInvite {
  id: string
  org_id: string
  email: string
  role: Exclude<OrgRole, 'owner'>
  invited_by: string
  token: string
  expires_at: string
  created_at: string
  accepted_at: string | null
}

export interface CreateOrgParams {
  name: string
  slug?: string // Optional, can be generated from name
}

export interface UpdateOrgParams {
  name?: string
  slug?: string
  avatar_url?: string
}

export interface InviteMemberParams {
  org_id: string
  email: string
  role: Exclude<OrgRole, 'owner'>
}

export type OrgResponse<T> = {
  data: T | null
  error: Error | null
}

// Add new types for invite operations
export interface InviteValidation {
  token: string
  email?: string
  org_id?: string
}

export interface InviteAcceptance {
  token: string
  org_slug: string
}

export interface InviterProfile {
  full_name: string | null
  avatar_url: string | null
}
