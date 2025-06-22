import { getSupabaseBrowserClient } from '@/lib/auth/config'
import type { 
  ActivityResponse, 
  AnalyticsResponse, 
  AnalyticsMetrics,
  TrackActivityParams, 
  TrackActivityResponse,
  DailyActivityData
} from './analyticsTypes'
import type { RateLimitConfig } from '@/lib/auth/authTypes'
import type { Database } from '@/types/supabase'

// Add type for rate limit data
type RateLimit = Database['public']['Functions']['get_detailed_analytics']['Returns']['rateLimits']['recent_limits'][0]

export async function getUserActivity(userId: string): Promise<ActivityResponse> {
  try {
    const supabase = getSupabaseBrowserClient()
    const { data, error } = await supabase
      .from('user_activity')
      .select('*')
      .eq('user_id', userId)
      .order('created_at', { ascending: false })

    if (error) throw error
    return { data, error: null }
  } catch (error) {
    return { data: [], error: error as Error }
  }
}

export async function getAnalyticsMetrics(): Promise<AnalyticsResponse> {
  try {
    const supabase = getSupabaseBrowserClient()
    
    // Fetch both basic and detailed metrics
    const [basicMetrics, detailedAnalytics] = await Promise.all([
      supabase.rpc('get_basic_metrics'),
      supabase.rpc('get_detailed_analytics')
    ])

    console.log('Basic metrics:', basicMetrics.data)
    console.log('Detailed analytics:', detailedAnalytics.data)

    if (basicMetrics.error) throw basicMetrics.error
    if (detailedAnalytics.error) throw detailedAnalytics.error

    // Transform rate limits into activities format with proper typing
    const recentActivities = detailedAnalytics.data?.rateLimits?.recent_limits?.map((limit: RateLimit) => ({
      action_type: limit.action_type,
      count: limit.request_count,
      unique_users: limit.unique_users,
      last_activity: limit.window_start
    })) ?? []

    // Combine the data ensuring it matches AnalyticsMetrics interface
    const combinedData: AnalyticsMetrics = {
      totalUsers: basicMetrics.data?.totalUsers ?? 0,
      activeUsers: basicMetrics.data?.activeUsers ?? 0,
      loginCount: basicMetrics.data?.loginCount ?? 0,
      signupCount: basicMetrics.data?.signupCount ?? 0,
      rateLimits: detailedAnalytics.data?.rateLimits ?? { total_limited: 0, recent_limits: [] },
      recentActivities,
      dailyActivity: detailedAnalytics.data?.dailyActivity ?? [],
      activityHistory: detailedAnalytics.data?.dailyActivity?.map((day: DailyActivityData) => ({
        date: day.day,
        value: day.total_actions
      })) ?? [],
      lastUpdated: new Date().toISOString()
    }

    console.log('Combined data:', combinedData)

    return { data: combinedData, error: null }
  } catch (error) {
    console.error('Analytics error:', error)
    return { data: null, error: error as Error }
  }
}

export async function trackActivity(params: TrackActivityParams): Promise<TrackActivityResponse> {
  try {
    const supabase = getSupabaseBrowserClient()
    const { error } = await supabase
      .from('user_activity')
      .insert([{
        user_id: params.userId,
        action_type: params.actionType,
        metadata: params.metadata,
        ip_address: params.ipAddress,
        user_agent: params.userAgent
      }])

    if (error) throw error
    return { success: true, error: null }
  } catch (error) {
    return { success: false, error: error as Error }
  }
}

// Add rate limit tracking
export async function trackRateLimitExceeded(
  params: TrackActivityParams & { 
    rateLimitConfig: RateLimitConfig 
  }
): Promise<TrackActivityResponse> {
  try {
    const supabase = getSupabaseBrowserClient()
    const { error } = await supabase
      .from('user_activity')
      .insert([{
        user_id: params.userId,
        action_type: 'rate_limit_exceeded',
        metadata: {
          limitedAction: params.actionType,
          maxRequests: params.rateLimitConfig.maxRequests,
          windowMinutes: params.rateLimitConfig.windowMinutes,
          timestamp: new Date().toISOString()
        },
        ip_address: params.ipAddress,
        user_agent: params.userAgent
      }])

    if (error) throw error
    return { success: true, error: null }
  } catch (error) {
    return { success: false, error: error as Error }
  }
}

// Get rate limit status for a user
export async function getRateLimitStatus(
  userId: string,
  actionType: string
): Promise<ActivityResponse> {
  try {
    const supabase = getSupabaseBrowserClient()
    const { data, error } = await supabase
      .from('rate_limits')
      .select('*')
      .eq('user_id', userId)
      .eq('action_type', actionType)
      .order('window_start', { ascending: false })
      .limit(1)

    if (error) throw error
    return { data, error: null }
  } catch (error) {
    return { data: [], error: error as Error }
  }
}

// Get all rate limits for analytics
export async function getRateLimitAnalytics(): Promise<AnalyticsResponse> {
  try {
    const supabase = getSupabaseBrowserClient()
    const { data, error } = await supabase
      .from('user_activity')
      .select('*')
      .eq('action_type', 'rate_limit_exceeded')
      .order('created_at', { ascending: false })

    if (error) throw error
    return { data, error: null }
  } catch (error) {
    return { data: null, error: error as Error }
  }
}
