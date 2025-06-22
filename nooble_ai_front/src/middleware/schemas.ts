import { z } from 'zod'

export const AvatarUrlSchema = z.string()
  .nullable()
  .refine(url => {
    if (!url) return true // Allow null values
    return (
      (url.includes('Avatars') && url.startsWith('https://')) || // Supabase storage URLs
      (url.startsWith('https://') && url.includes('googleusercontent.com')) || // Google avatar URLs
      (url.startsWith('https://') && url.includes('githubusercontent.com')) // GitHub avatar URLs
    )
  }, 'Invalid avatar URL format')

export const UserDataSchema = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  created_at: z.string().datetime(),
  updated_at: z.string().datetime(),
  user_id: z.string().uuid(),
  full_name: z.string().nullable(),
  avatar_url: AvatarUrlSchema,
  profile_updated_at: z.string().datetime().nullable()
})

export const RoleUpdateSchema = z.object({
  user_id: z.string().uuid(),
  role: z.enum(['user', 'admin', 'super_admin'] as const),
  updated_at: z.string().datetime()
})

export const ActivitySchema = z.object({
  user_id: z.string().uuid(),
  action_type: z.string(),
  metadata: z.record(z.unknown()).optional(),
  ip_address: z.string().optional(),
  user_agent: z.string().optional()
})

export const ProfileUpdateSchema = z.object({
  id: z.string().uuid(),
  full_name: z.string().min(1),
  avatar_url: AvatarUrlSchema,
  updated_at: z.string().datetime()
})

export const OrganizationSchema = z.object({
  name: z.string().min(2).max(50),
  slug: z.string()
    .min(2)
    .max(50)
    .regex(/^[a-z0-9-]+$/, 'Slug must be lowercase alphanumeric with dashes')
    .or(z.string().length(0)), // Allow empty string during auto-generation
})

export const OrgMemberSchema = z.object({
  org_id: z.string().uuid(),
  user_id: z.string().uuid(),
  role: z.enum(['owner', 'admin', 'member'] as const),
})

export const OrgInviteSchema = z.object({
  org_id: z.string().uuid(),
  email: z.string().email(),
  role: z.enum(['admin', 'member'] as const),
  token: z.string().uuid().optional(), // Optional because it's generated server-side
  expires_at: z.string().datetime().optional(), // Optional for the same reason
  accepted_at: z.string().datetime().nullable().optional()
})

// Add a new schema for invite validation
export const InviteValidationSchema = z.object({
  token: z.string().uuid(),
  email: z.string().email().optional(), // Optional because we might not need it for all operations
  org_id: z.string().uuid().optional()
})

// Add a new schema for invite acceptance
export const InviteAcceptanceSchema = z.object({
  token: z.string().uuid(),
  org_slug: z.string()
})

