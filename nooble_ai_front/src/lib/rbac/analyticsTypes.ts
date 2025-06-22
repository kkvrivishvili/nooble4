import type { Database } from '@/types/supabase'
import type { ActivityData } from '@/components/dashboard/admin/analytics/charts/UserActivityChart'
import type { EngagementData } from '@/components/dashboard/admin/analytics/metrics/EngagementStats'

export type ActivityRow = Database['public']['Tables']['user_activity']['Row']

// Activity Response type
export interface ActivityResponse {
  data: ActivityRow[] | null
  error: Error | null
}

// Enhanced Analytics Metrics - matching SQL function output
export interface AnalyticsMetrics {
  totalUsers: number
  activeUsers: number
  loginCount: number
  signupCount: number
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
  activityHistory: Array<{
    date: string
    value: number
  }>
  lastUpdated: string
}

// Update MetricsData to include chart data
export interface MetricsData {
  dailyActiveUsers: number
  totalActions: number
  engagementRate: string
  userGrowth: number
  rateLimits: number
  // Use the component-specific types
  dailyActivity: ActivityData[]
  userEngagement: EngagementData[]
}

export interface AnalyticsResponse {
  data: AnalyticsMetrics | null
  error: Error | null
}

// Activity tracking
export interface TrackActivityParams {
  userId: string
  actionType: string
  metadata?: Record<string, unknown>
  ipAddress?: string
  userAgent?: string
}

export interface TrackActivityResponse {
  success: boolean
  error: Error | null
}

export type AnalyticsData<T = Record<string, unknown>> = {
  timestamp: string
  eventType: string
  userId: string
  metadata: T
}

// Chart tooltip types
export interface ChartTooltipPayload {
  value: number
  dataKey: string
  color: string
}

export interface ChartTooltipProps {
  active?: boolean
  payload?: ChartTooltipPayload[]
  label?: string
}

// Export data types
export interface ExportBasicMetrics {
  date: string
  total_users: number
  active_users: number
  login_count: number
  signup_count: number
  type: 'basic_metrics'
}

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

export type ExportData = ExportBasicMetrics | ExportDailyActivity | ExportActivityDetail

export interface ExportResponse {
  success: boolean
  error: Error | null
}

// Add this new interface to match MetricsOverview component
export interface MetricsOverviewData {
  dailyActiveUsers: number
  totalActions: number
  engagementRate: string
  userGrowth: number
  rateLimits: number
}

// Add the DailyActivityData interface
export interface DailyActivityData {
  day: string
  total_actions: number
  unique_users: number
  action_breakdown: Record<string, number>
}

// Add a helper function to transform AnalyticsMetrics to MetricsOverviewData
export function transformMetricsForOverview(metrics: Partial<AnalyticsMetrics>): MetricsData {
  // Transform daily activity data for the chart
  const dailyActivity = metrics.dailyActivity?.map((day: DailyActivityData) => ({
    date: day.day,
    value: day.total_actions
  })) ?? []

  // Transform engagement data
  const userEngagement = metrics.recentActivities?.map(activity => ({
    type: activity.action_type,
    count: activity.count
  })) ?? []

  // Calculate engagement rate
  const engagementRate = metrics.totalUsers && metrics.activeUsers
    ? `${((metrics.activeUsers / metrics.totalUsers) * 100).toFixed(1)}%`
    : '0%'

  return {
    dailyActiveUsers: metrics.activeUsers ?? 0,
    totalActions: metrics.dailyActivity?.[metrics.dailyActivity.length - 1]?.total_actions ?? 0,
    engagementRate,
    userGrowth: metrics.signupCount ?? 0,
    rateLimits: metrics.rateLimits?.total_limited ?? 0,
    dailyActivity,
    userEngagement
  }
}

// Add this new interface
export interface UserActivityPayload {
  action_type: string
  created_at: string
  id: string
  metadata: Record<string, unknown>
  user_id: string
  ip_address?: string
  user_agent?: string
}