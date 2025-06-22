import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { UserActivityChart } from '@/components/dashboard/admin/analytics/charts/UserActivityChart'
import { MetricsOverview } from '@/components/dashboard/admin/analytics/metrics/MetricsOverview'
import { EngagementStats } from '@/components/dashboard/admin/analytics/metrics/EngagementStats'
import type { Database } from '@/types/supabase'
import type { AnalyticsMetrics, MetricsData } from '@/lib/rbac/analyticsTypes'
import { ExportButton } from '@/components/dashboard/admin/analytics/ExportButton'


function transformMetrics(data: AnalyticsMetrics): MetricsData {
  // Transform daily activity data for the chart
  const dailyActivity = data.dailyActivity?.map(day => ({
    date: day.day,
    value: day.total_actions
  })) ?? []

  console.log('Raw daily activity:', data.dailyActivity) // Debug log
  console.log('Transformed activity:', dailyActivity)    // Debug log

  // Transform engagement data
  const userEngagement = data.recentActivities?.map(activity => ({
    type: activity.action_type,
    count: activity.count // Match EngagementData type
  })) ?? []

  // Calculate engagement rate
  const engagementRate = data.totalUsers > 0
    ? `${((data.activeUsers / data.totalUsers) * 100).toFixed(1)}%`
    : '0%'

  return {
    dailyActiveUsers: data.activeUsers ?? 0,
    totalActions: data.dailyActivity?.[data.dailyActivity.length - 1]?.total_actions ?? 0,
    engagementRate,
    userGrowth: data.signupCount ?? 0,
    rateLimits: data.rateLimits?.total_limited ?? 0,
    dailyActivity,
    userEngagement
  }
}

export default async function AnalyticsPage() {
  const cookieStore = await cookies()
  
  const supabase = createServerClient<Database>(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll: () => {
          return cookieStore.getAll().map(cookie => ({
            name: cookie.name,
            value: cookie.value,
          }))
        },
        setAll: async (cookieValues) => {
          cookieValues.forEach(({ name, value, options }) => {
            cookieStore.set(name, value, options)
          })
        }
      }
    }
  )

  // Fetch both sets of metrics
  const [basicMetrics, detailedAnalytics] = await Promise.all([
    supabase.rpc('get_basic_metrics'),
    supabase.rpc('get_detailed_analytics')
  ])

  const combinedData = {
    ...basicMetrics.data,
    ...detailedAnalytics.data
  }

  const metrics = combinedData ? transformMetrics(combinedData as AnalyticsMetrics) : undefined

  return (
    <div className="space-y-6">
      <div className="border-b pb-4">
        <h2 className="text-2xl font-bold">Analytics</h2>
      </div>

      {/* Key Metrics Overview */}
      <MetricsOverview metrics={metrics} />

      {/* Activity Charts */}
      <div className="grid gap-6 md:grid-cols-2">
        <UserActivityChart data={metrics?.dailyActivity} />
        <EngagementStats data={metrics?.userEngagement} />
      </div>

      {/* Export Section */}
      <div className="grid gap-6 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Export Data</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-2">
              <ExportButton />
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
