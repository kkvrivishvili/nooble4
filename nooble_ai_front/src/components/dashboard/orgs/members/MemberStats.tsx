'use client'

import { useState } from 'react'
import { useOrgStats } from '@/lib/orgs/members/useOrgStats'
import { StatsOverview } from '@/components/dashboard/orgs/members/StatsOverview'
import { RoleDistribution } from '@/components/dashboard/orgs/members/RoleDistribution'
import { ActivityTrends } from '@/components/dashboard/orgs/members/ActivityTrends'
import { toast } from 'sonner'
import { Button } from '@/components/ui/Button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/Select'

interface MemberStatsProps {
  orgId: string
}

export function MemberStats({ orgId }: MemberStatsProps) {
  const [timeRange, setTimeRange] = useState<'7d' | '30d' | '90d'>('30d')
  const { data, isLoading, error, trend } = useOrgStats(orgId)

  if (error) {
    toast.error('Failed to load statistics')
    return (
      <div 
        role="alert" 
        aria-live="polite" 
        className="flex flex-col items-center justify-center p-6 space-y-4"
      >
        <p className="text-muted-foreground">Failed to load statistics</p>
        <Button 
          variant="outline"
          onClick={() => window.location.reload()}
          aria-label="Retry loading statistics"
        >
          Retry
        </Button>
      </div>
    )
  }

  if (isLoading || !data) {
    return (
      <div className="space-y-4">
        <div className="flex justify-between items-center">
          <div className="animate-pulse w-32 h-8 bg-muted rounded" />
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          {[1, 2].map((i) => (
            <div 
              key={i} 
              className="animate-pulse rounded-lg border p-4 h-[250px] sm:h-[280px] bg-muted" 
            />
          ))}
          <div className="animate-pulse rounded-lg border p-4 h-[400px] bg-muted md:col-span-2" />
        </div>
      </div>
    )
  }

  return (
    <div role="region" aria-label="Member Statistics Dashboard">
      <div className="flex justify-between items-center mb-4">
        <Select
          value={timeRange}
          onValueChange={(value) => setTimeRange(value as '7d' | '30d' | '90d')}
          aria-label="Select time range for statistics"
        >
          <SelectTrigger className="w-[140px] sm:w-[180px]">
            <SelectValue placeholder="Select time range" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="7d">Last 7 days</SelectItem>
            <SelectItem value="30d">Last 30 days</SelectItem>
            <SelectItem value="90d">Last 90 days</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-4">
        <div 
          className="grid gap-4 md:grid-cols-2"
          role="group" 
          aria-label="Key statistics overview"
        >
          <StatsOverview 
            data={data.stats.overview} 
            trend={trend}
          />
          <RoleDistribution data={data.stats.overview.roleDistribution} />
        </div>
        <div className="w-full h-[400px] sm:h-[500px] lg:h-[600px]">
          <ActivityTrends 
            data={data.stats.trends} 
            timeRange={timeRange}
          />
        </div>
      </div>
    </div>
  )
}