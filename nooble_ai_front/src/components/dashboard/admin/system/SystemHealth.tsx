import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import type { AnalyticsMetrics } from '@/lib/rbac/analyticsTypes'
import { formatDate } from '@/utils/date'

export function SystemHealth({ metrics }: { metrics: Partial<AnalyticsMetrics> }) {
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-foreground">System Status</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <StatusIndicator 
              name="Database" 
              status="healthy" 
            />
            <div className="text-sm text-muted-foreground mt-2">
              Last updated: {metrics?.lastUpdated ? formatDate(metrics.lastUpdated) : 'Never'}
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-foreground">Daily Activity</CardTitle>
        </CardHeader>
        <CardContent>
          {metrics?.dailyActivity?.length === 0 ? (
            <p className="text-sm text-muted-foreground">No activity data available</p>
          ) : (
            <div className="space-y-2">
              {metrics?.dailyActivity?.map((day) => (
                <div key={day.day} className="flex justify-between items-center">
                  <div>
                    <p className="font-medium text-foreground">{formatDate(day.day)}</p>
                    <p className="text-sm text-muted-foreground">
                      {day.unique_users} unique users
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="font-medium text-foreground">{day.total_actions} actions</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function StatusIndicator({ 
  name, 
  status 
}: { 
  name: string
  status: 'healthy' | 'warning' | 'error' | 'unknown'
}) {
  const colors = {
    healthy: 'text-green-500',
    warning: 'text-yellow-500',
    error: 'text-red-500',
    unknown: 'text-muted-foreground'
  } as const

  const bgColors = {
    healthy: 'bg-green-500',
    warning: 'bg-yellow-500',
    error: 'bg-red-500',
    unknown: 'bg-muted'
  } as const

  return (
    <div className="flex items-center justify-between">
      <span className="text-foreground">{name}</span>
      <div className="flex items-center gap-2">
        <div className={`w-2 h-2 rounded-full ${bgColors[status]}`} />
        <span className={`text-sm capitalize ${colors[status]}`}>{status}</span>
      </div>
    </div>
  )
}