export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export interface Database {
  public: {
    Tables: {
      users: {
        Row: {
          id: string
          email: string
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          email: string
          created_at?: string
          updated_at?: string
        }
        Update: {
          id?: string
          email?: string
          updated_at?: string
        }
      }
      profiles: {
        Row: {
          id: string
          user_id: string
          full_name?: string
          avatar_url?: string
          updated_at?: string
        }
        Insert: {
          id?: string
          user_id: string
          full_name?: string
          avatar_url?: string
          updated_at?: string
        }
        Update: {
          full_name?: string
          avatar_url?: string
          updated_at?: string
        }
      }
      roles: {
        Row: {
          id: string
          user_id: string
          role: 'user' | 'admin' | 'super_admin'
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          user_id: string
          role?: 'user' | 'admin' | 'super_admin'
          created_at?: string
          updated_at?: string
        }
        Update: {
          role?: 'user' | 'admin' | 'super_admin'
          updated_at?: string
        }
      }
      user_activity: {
        Row: {
          id: string
          user_id: string
          action_type: string
          metadata: Json
          created_at: string
          ip_address?: string
          user_agent?: string
        }
        Insert: {
          id?: string
          user_id: string
          action_type: string
          metadata?: Json
          created_at?: string
          ip_address?: string
          user_agent?: string
        }
        Update: {
          metadata?: Json
          ip_address?: string
          user_agent?: string
        }
      }
      rate_limits: {
        Row: {
          id: string
          user_id: string
          action_type: string
          window_start: string
          request_count: number
        }
        Insert: {
          id?: string
          user_id: string
          action_type: string
          window_start?: string
          request_count?: number
        }
        Update: {
          request_count?: number
        }
      }
      organizations: {
        Row: {
          id: string
          name: string
          slug: string
          avatar_url?: string
          created_at: string
          updated_at: string
        }
        Insert: {
          id?: string
          name: string
          slug: string
          avatar_url?: string
          created_at?: string
          updated_at?: string
        }
        Update: {
          name?: string
          slug?: string
          avatar_url?: string
          updated_at?: string
        }
      }
      organization_members: {
        Row: {
          org_id: string
          user_id: string
          role: 'owner' | 'admin' | 'member'
          joined_at: string
        }
        Insert: {
          org_id: string
          user_id: string
          role: 'owner' | 'admin' | 'member'
          joined_at?: string
        }
        Update: {
          role?: 'owner' | 'admin' | 'member'
        }
      }
      organization_invites: {
        Row: {
          id: string
          org_id: string
          email: string
          role: 'admin' | 'member'
          invited_by: string
          token: string
          expires_at: string
          created_at: string
          accepted_at: string | null
        }
        Insert: {
          id?: string
          org_id: string
          email: string
          role: 'admin' | 'member'
          invited_by: string
          token: string
          expires_at?: string
          created_at?: string
          accepted_at?: string | null
        }
        Update: {
          role?: 'admin' | 'member'
          expires_at?: string
          accepted_at?: string | null
        }
      }
      organization_member_stats_cache: {
        Row: {
          org_id: string
          stats: Json
          role_distribution_history: Json
          cache_version: number
          last_updated: string
        }
        Insert: {
          org_id: string
          stats: Json
          role_distribution_history?: Json
          cache_version?: number
          last_updated?: string
        }
        Update: {
          stats?: Json
          role_distribution_history?: Json
          cache_version?: number
          last_updated?: string
        }
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      check_rate_limit: {
        Args: Record<string, unknown> & {
          p_user_id: string
          p_action_type: string
          p_max_requests: number
          p_window_minutes: number
        }
        Returns: boolean
      }
      get_basic_metrics: {
        Args: Record<string, never>
        Returns: {
          totalUsers: number
          activeUsers: number
          loginCount: number
          signupCount: number
        }
      }
      get_detailed_analytics: {
        Args: Record<string, never>
        Returns: {
          rateLimits: {
            total_limited: number
            recent_limits: Array<{
              action_type: string
              request_count: number
              window_start: string
              unique_users: number
            }>
          }
          recentActivities: Array<{
            action_type: string
            count: number
            unique_users: number
            last_activity: string
          }>
          dailyActivity: Array<{
            day: string
            unique_users: number
            total_actions: number
            action_breakdown: Record<string, number>
          }>
          lastUpdated: string
        }
      }
      get_org_member_stats: {
        Args: {
          org_id: string
        }
        Returns: {
          stats: {
            overview: {
              totalMembers: number
              activeMembers: number
              inactiveMembers: number
              roleDistribution: Record<'owner' | 'admin' | 'member', number>
            }
            trends: Array<{
              date: string
              joins: number
              departures: number
            }>
          }
          roleHistory: Array<{
            date: string
            distribution: Record<'owner' | 'admin' | 'member', number>
          }>
        }
      }
    }
    Enums: {
      user_role: 'user' | 'admin' | 'super_admin'
    }
  }
  storage: {
    buckets: {
      Avatars: {
        id: string
        name: string
        owner: string
        created_at: string
        updated_at: string
        public: boolean
      }
    }
  }
}
