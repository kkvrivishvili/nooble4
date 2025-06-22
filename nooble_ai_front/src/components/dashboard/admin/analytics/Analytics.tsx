'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { getSupabaseBrowserClient } from '@/lib/auth/config'
import { toast } from 'sonner'
import { MetricsOverview } from '@/components/dashboard/admin/analytics/metrics/MetricsOverview'
import { transformMetricsForOverview } from '@/lib/rbac/analyticsTypes'
import type { AnalyticsMetrics, UserActivityPayload } from '@/lib/rbac/analyticsTypes'
import type { Database } from '@/types/supabase'
import type { SupabaseClient } from '@supabase/supabase-js'

export function AnalyticsDashboard() {
  const [metrics, setMetrics] = useState<AnalyticsMetrics | null>(null)
  const [realtimeCount, setRealtimeCount] = useState(0)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    fetchMetrics()
    const supabase = getSupabaseBrowserClient() as SupabaseClient<Database>
    
    const subscription = supabase
      .channel('analytics-changes')
      .on(
        'postgres_changes' as const, 
        { 
          event: 'INSERT',
          schema: 'public',
          table: 'user_activity' 
        },
        (payload: { new: UserActivityPayload }) => {
          console.log('New activity:', payload.new.action_type)
          setRealtimeCount(prev => prev + 1)
          void fetchMetrics()
        }
      )
      .subscribe()

    return () => {
      void subscription.unsubscribe()
    }
  }, [])

  const fetchMetrics = async () => {
    try {
      const supabase = getSupabaseBrowserClient() as SupabaseClient<Database>
      
      const [basicMetrics, detailedAnalytics] = await Promise.all([
        supabase.rpc('get_basic_metrics'),
        supabase.rpc('get_detailed_analytics')
      ])
      
      if (basicMetrics.error) throw basicMetrics.error
      if (detailedAnalytics.error) throw detailedAnalytics.error

      const combinedData: AnalyticsMetrics = {
        ...basicMetrics.data,
        ...detailedAnalytics.data,
        lastUpdated: new Date().toISOString()
      }

      setMetrics(combinedData)
    } catch (error) {
      console.error('Failed to fetch analytics:', error)
      toast.error('Failed to load analytics')
    } finally {
      setIsLoading(false)
    }
  }

  if (isLoading) {
    return (
      <Card>
        <CardContent className="p-6">
          <div className="flex items-center justify-center">
            Loading analytics...
          </div>
        </CardContent>
      </Card>
    )
  }

  if (!metrics) return null

  return (
    <div className="space-y-8">
      <MetricsOverview metrics={transformMetricsForOverview(metrics)} />

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Recent Activity</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {realtimeCount} new actions
            </div>
            <p className="text-sm text-muted-foreground">
              since you opened this page
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-foreground">Rate Limits</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-foreground">
              {metrics.rateLimits?.total_limited || 0}
            </div>
            <p className="text-sm text-muted-foreground">
              Rate limited requests today
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-foreground">Total Users</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-foreground">{metrics.totalUsers}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-foreground">Active Today</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-foreground">{metrics.activeUsers}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-foreground">Total Logins</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-foreground">{metrics.loginCount}</div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
