import type { UserRow, ProfileRow } from '@/types/api'
import { PricingStrategy } from '../payments/pricestrategyTypes'

// Basic auth credentials
export interface LoginCredentials {
  email: string
  password: string
  rememberMe?: boolean
  inviteToken?: string  // Add these for org invites
  orgSlug?: string
}

export interface SignupCredentials extends LoginCredentials {
  confirmPassword: string
}

// Password reset types
export interface PasswordResetRequest {
  email: string
}

export interface PasswordUpdateCredentials {
  password: string
  confirmPassword: string
}

// Auth responses
export interface AuthResponse {
  data: UserRow | null
  error: Error | null
  metadata?: {
    shouldRedirectToSignup?: boolean
    message?: string
    redirectTo?: string  // Add this for org redirects
    inviteError?: string  // Add for invite-specific errors
    inviteStatus?: 'pending' | 'accepted' | 'expired'
  }
}

export interface ResetRequestResponse {
  success: boolean
  error: Error | null
}

export interface PasswordUpdateResponse {
  success: boolean
  error: Error | null
}

// Session types
export interface SessionRow {
  id: string
  user_id: string
  created_at: string
  last_active: string
  user_agent?: string
  ip_address?: string
  is_current: boolean
}

export interface SessionResponse {
  data: SessionRow | null
  error: Error | null
}

export interface SessionsResponse {
  data: SessionRow[]
  error: Error | null
}

// Profile management types
export interface ProfileUpdateParams {
  id: string
  full_name?: string
  avatar_url?: string | null | undefined
  updated_at?: string
}

export interface ProfileResponse {
  data: ProfileRow | null
  error: Error | null
}

export interface Profile {
  id: string
  full_name?: string
  avatar_url?: string | null
  updated_at?: string
}

// Combined user and profile data
export interface UserProfile extends UserRow {
  profile?: ProfileRow
}

export interface UserProfileResponse {
  data: UserProfile | null
  error: Error | null
}

// Data export types
export interface ExportedData {
  user: {
    email: string | null
    created_at: string
  }
  profile: ProfileRow | null
  sessions: SessionRow[]
}

export interface ExportResponse {
  success: boolean
  error: Error | null
}

// Export data types
export interface ExportDailyActivity {
  date: string
  unique_users: number
  total_actions: number
  type: 'daily_activity'
}

export interface ExportActivityDetail {
  date: string
  action_type: string
  unique_users: number
  count: number
  type: 'activity_detail'
}

export type ExportData = ExportDailyActivity | ExportActivityDetail

// Add to your existing types
export type RateLimitConfig = {
  actionType: string;
  maxRequests: number;
  windowMinutes: number;
}

export class RateLimitError extends Error {
  code: 'rate-limit/exceeded'
  status: 429

  constructor(message: string) {
    super(message)
    this.name = 'RateLimitError'
    this.code = 'rate-limit/exceeded'
    this.status = 429
  }
}

// Add this to your existing types
export interface AuthSearchParams {
  email?: string
  invite?: string
  org?: string
  error?: string
  strategy?: PricingStrategy
  code?: string
}

// Add to existing interfaces
export interface InviteAuthParams {
  token: string
  org_slug: string
  email: string
}

// Add invite-specific error
export class InviteError extends Error {
  code: 'invite/invalid' | 'invite/expired' | 'invite/already-accepted'
  status: 400 | 401 | 410

  constructor(
    code: 'invite/invalid' | 'invite/expired' | 'invite/already-accepted',
    message: string
  ) {
    super(message)
    this.name = 'InviteError'
    this.code = code
    this.status = code === 'invite/expired' ? 410 : 400
  }
}
