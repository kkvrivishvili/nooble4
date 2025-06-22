'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Input } from '@/components/ui/Input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/Select'
import type { AnalyticsMetrics } from '@/lib/rbac/analyticsTypes'
import { formatDate } from '@/utils/date'
import { ExportButton } from '@/components/dashboard/admin/analytics/ExportButton'
import { getAnalyticsMetrics } from '@/lib/rbac/analytics'

interface ActivityLogProps {
  initialMetrics?: Partial<AnalyticsMetrics>
  realtimeCount?: number
}

export function ActivityLog({ initialMetrics, realtimeCount = 0 }: ActivityLogProps) {
  const [metrics, setMetrics] = useState<Partial<AnalyticsMetrics>>(initialMetrics ?? {})
  const [filter, setFilter] = useState('')
  const [timeRange, setTimeRange] = useState('24h')

  // Fetch metrics on mount
  useEffect(() => {
    async function fetchMetrics() {
      const response = await getAnalyticsMetrics()
      if (response.data) {
        setMetrics(response.data)
      }
    }
    fetchMetrics()
  }, [])

  // Debug logs
  console.log('Raw metrics:', metrics)
  console.log('Recent activities:', metrics.recentActivities)

  // Filter activities based on search term and time range
  const filteredActivities = metrics.recentActivities?.filter(activity => {
    if (!activity) return false
    
    const matchesSearch = activity.action_type.toLowerCase().includes(filter.toLowerCase())
    const activityDate = new Date(activity.last_activity)
    const now = new Date()
    const daysDiff = Math.floor((now.getTime() - activityDate.getTime()) / (1000 * 60 * 60 * 24))

    let matchesTimeRange = true
    switch (timeRange) {
      case '24h':
        matchesTimeRange = daysDiff <= 1
        break
      case '7d':
        matchesTimeRange = daysDiff <= 7
        break
      case '30d':
        matchesTimeRange = daysDiff <= 30
        break
      case 'rate_limits':
        // Include activities that appear in recent_limits
        matchesTimeRange = metrics.rateLimits?.recent_limits.some(
          limit => limit.action_type === activity.action_type
        ) ?? false
        break
    }

    return matchesSearch && matchesTimeRange
  }) ?? []

  // Debug log
  console.log('Filtered activities:', filteredActivities)

  return (
    <div className="space-y-6">
      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="text-foreground">Activity Filters</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-4">
            <Input 
              placeholder="Search activities..." 
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="max-w-sm bg-background"
            />
            <Select value={timeRange} onValueChange={setTimeRange}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Select time range" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="24h">Last 24 hours</SelectItem>
                <SelectItem value="7d">Last 7 days</SelectItem>
                <SelectItem value="30d">Last 30 days</SelectItem>
                <SelectItem value="rate_limits">Rate Limits</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Real-time Counter */}
      {realtimeCount > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-foreground">Recent Activity</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-foreground">
              {realtimeCount} new actions
            </div>
            <p className="text-sm text-muted-foreground">
              since you opened this page
            </p>
          </CardContent>
        </Card>
      )}

      {/* Activity Timeline */}
      <Card>
        <CardHeader>
          <CardTitle className="text-foreground">Activity Timeline</CardTitle>
        </CardHeader>
        <CardContent>
          {filteredActivities.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-4">
              No activities found for the selected filters.
            </p>
          ) : (
            <div className="space-y-4">
              {filteredActivities.map((activity, index) => {
                // Find matching rate limit data if it exists
                const rateLimitInfo = timeRange === 'rate_limits' 
                  ? metrics.rateLimits?.recent_limits.find(
                      limit => limit.action_type === activity.action_type
                    )
                  : null

                return (
                  <div 
                    key={`${activity.action_type}-${activity.last_activity}-${index}`}
                    className="flex justify-between items-start border-b border-border pb-4 last:border-0"
                  >
                    <div>
                      <p className="font-medium text-foreground">
                        {rateLimitInfo 
                          ? `Rate Limited: ${formatActionType(activity.action_type)}`
                          : formatActionType(activity.action_type)
                        }
                      </p>
                      <p className="text-sm text-muted-foreground">
                        {activity.unique_users} unique users • {activity.count} times
                        {rateLimitInfo && (
                          <> • {rateLimitInfo.request_count} requests in window</>
                        )}
                      </p>
                    </div>
                    <p className="text-sm text-muted-foreground">
                      {formatDate(activity.last_activity)}
                    </p>
                  </div>
                )
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Export Options */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-base font-semibold text-foreground">Export Data</CardTitle>
          <ExportButton />
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Download analytics data in CSV format including daily activities, user actions, and basic metrics.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}

function formatActionType(type: string): string {
  return type
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}