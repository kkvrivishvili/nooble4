import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
import { createServerClient } from '@supabase/ssr'
import type { Database } from '@/types/supabase'
import type { OrgRole } from '@/lib/orgs/orgTypes'

type EventType = 
  | 'avatar_update'
  | 'profile_update'
  | 'settings_update'
  | 'org_avatar_update'
  | 'org_update'
  | 'member_update'
  | 'member_remove'
  | 'member_leave'
  | 'member_list'
  | 'org_delete'
  | 'ownership_transfer'
  | 'invite_created'
  | 'invite_accepted'
  | 'invite_declined'
  | 'invite_rejected'
  | 'invite_resent'
  | 'invite_revoked'
  | 'analytics_view'

interface BaseEventData {
  timestamp?: string
  ip_address?: string
  user_agent?: string
}

interface AvatarUpdateData extends BaseEventData {
  avatarUrl: string | null
  previousUrl?: string | null
}

interface ProfileUpdateData extends BaseEventData {
  updates: Partial<Database['public']['Tables']['profiles']['Row']>
}

interface SettingsUpdateData extends BaseEventData {
  updates: Record<string, unknown>
}

interface OrgAvatarUpdateData extends BaseEventData {
  orgId: string
  avatarUrl: string | null
  previousUrl?: string | null
}

interface OrgUpdateData extends BaseEventData {
  orgId: string
  updates: {
    name?: string
    slug?: string
  }
}

interface MemberUpdateData extends BaseEventData {
  orgId: string
  userId: string
  updates: {
    role: OrgRole
  }
}

interface MemberRemoveData extends BaseEventData {
  orgId: string
  userId: string
}

interface MemberLeaveData extends BaseEventData {
  orgId: string
  newOwnerId?: string
}

interface InviteCreateData extends BaseEventData {
  orgId: string
  email: string
  role: Exclude<OrgRole, 'owner'>
}

interface InviteActionData extends BaseEventData {
  orgId: string
  inviteId: string
}

interface InviteResendData extends BaseEventData {
  orgId: string
  inviteId: string
  email: string
}

interface MemberListData extends BaseEventData {
  orgId: string
  count: number
}

interface OrgDeleteData extends BaseEventData {
  orgId: string
}

interface OwnershipTransferData extends BaseEventData {
  orgId: string
  newOwnerId: string
}

interface AnalyticsViewData extends BaseEventData {
  orgId: string
}

type EventData = {
  'avatar_update': AvatarUpdateData
  'profile_update': ProfileUpdateData
  'settings_update': SettingsUpdateData
  'org_avatar_update': OrgAvatarUpdateData
  'org_update': OrgUpdateData
  'member_update': MemberUpdateData
  'member_remove': MemberRemoveData
  'member_leave': MemberLeaveData
  'member_list': MemberListData
  'org_delete': OrgDeleteData
  'ownership_transfer': OwnershipTransferData
  'invite_created': InviteCreateData
  'invite_accepted': InviteActionData
  'invite_declined': InviteActionData
  'invite_rejected': InviteActionData
  'invite_resent': InviteResendData
  'invite_revoked': InviteActionData
  'analytics_view': AnalyticsViewData
}

export type EventPayload<T extends EventType> = {
  userId: string
  type: T
  data: EventData[T]
}

export async function handleEvent<T extends EventType>(
  request: NextRequest, 
  payload: EventPayload<T>
) {
  const response = NextResponse.next()
  
  const supabase = createServerClient<Database>(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll: () => request.cookies.getAll().map(cookie => ({
          name: cookie.name,
          value: cookie.value,
        })),
        setAll: (cookieValues) => {
          cookieValues.map(({ name, value, ...options }) => {
            response.cookies.set({ name, value, ...options })
          })
        }
      }
    }
  )

  try {
    // Add request metadata
    const eventData = {
      ...payload.data,
      timestamp: new Date().toISOString(),
      ip_address: request.headers.get('x-forwarded-for'),
      user_agent: request.headers.get('user-agent')
    }

    // Log the event
    await supabase
      .from('events')
      .insert({
        user_id: payload.userId,
        event_type: payload.type,
        metadata: eventData
      })

    // Handle specific event types
    switch (payload.type) {
      case 'avatar_update':
        await supabase
          .from('profiles')
          .update({ 
            avatar_url: (payload.data as AvatarUpdateData).avatarUrl,
            updated_at: new Date().toISOString()
          })
          .eq('id', payload.userId)
        break

      case 'org_avatar_update':
        await supabase
          .from('organizations')
          .update({
            avatar_url: (payload.data as OrgAvatarUpdateData).avatarUrl,
            updated_at: new Date().toISOString()
          })
          .eq('id', (payload.data as OrgAvatarUpdateData).orgId)
        break

      case 'member_update':
        await supabase
          .from('organization_members')
          .update({
            role: (payload.data as MemberUpdateData).updates.role,
            updated_at: new Date().toISOString()
          })
          .eq('org_id', (payload.data as MemberUpdateData).orgId)
          .eq('user_id', (payload.data as MemberUpdateData).userId)
        break

      case 'member_remove':
        // No need for additional handling since the member is already removed
        // We just want to track the event
        break

      case 'org_update':
        // No need for additional handling since the org is already updated
        // We just want to track the event
        break

      case 'member_leave':
        // No additional handling needed since the member is already removed
        // and ownership transfer is handled in the leave route
        // We just want to track the event
        break

      case 'invite_created':
      case 'invite_accepted':
      case 'invite_declined':
      case 'invite_rejected':
      case 'invite_resent':
      case 'invite_revoked':
        // These are just tracking events, no additional handling needed
        break

      // Add other event type handlers as needed
    }

    return response

  } catch (error) {
    if (error instanceof Error) {
      console.error('Event handling error:', error.message)
    }
    return NextResponse.json(
      { error: 'Failed to process event' },
      { status: 500 }
    )
  }
} 