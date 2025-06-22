import type { OrgRole } from '../orgTypes'

// Base stats interfaces
export interface OrgMemberStats {
  stats: {
    overview: {
      totalMembers: number
      activeMembers: number
      inactiveMembers: number
      roleDistribution: Record<OrgRole, number>
    }
    trends: ActivityTrend[]
  }
  roleHistory: RoleHistoryEntry[]
}

// Specific type interfaces
export interface ActivityTrend {
  date: string
  joins: number
  departures: number
}

export interface RoleHistoryEntry {
  date: string
  distribution: Record<OrgRole, number>
}

// Service params
export interface StatsTimeRange {
  range: '7d' | '30d' | '90d'
}

// Service response type
export interface StatsResponse {
  data: OrgMemberStats | null
  error: Error | null
}

export type TimeRange = '7d' | '30d' | '90d'