'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { OrgMemberStats } from '@/lib/orgs/members/statsTypes'
import { ArrowUpIcon, ArrowDownIcon } from 'lucide-react'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/Tooltip'

interface StatsOverviewProps {
  data: OrgMemberStats['stats']['overview']
  trend: number
}

export function StatsOverview({ data, trend }: StatsOverviewProps) {
  const activeRatio = data.totalMembers > 0 
    ? (data.activeMembers / data.totalMembers) * 100 
    : 0

  return (
    <Card className="h-[220px] sm:h-[250px]">
      <CardHeader className="pb-3">
        <CardTitle className="text-base sm:text-lg" id="stats-overview-title">Overview</CardTitle>
      </CardHeader>
      <CardContent 
        className="space-y-4"
        role="region"
        aria-labelledby="stats-overview-title"
      >
        {/* Total Members with Trend */}
        <div className="space-y-2">
          <p className="text-sm font-medium text-muted-foreground tracking-wide">
            Total Members
          </p>
          <div className="flex items-baseline space-x-3">
            <p 
              className="text-3xl sm:text-4xl font-bold tracking-tight"
              aria-label={`Total members: ${data.totalMembers}`}
            >
              {data.totalMembers}
            </p>
            {trend !== 0 && (
              <div 
                className={`flex items-center text-sm font-medium ${
                  trend > 0 ? 'text-emerald-500' : 'text-red-500'
                }`}
                aria-label={`${Math.abs(trend)} member ${trend > 0 ? 'increase' : 'decrease'}`}
              >
                {trend > 0 ? (
                  <ArrowUpIcon className="w-3.5 h-3.5 mr-1" />
                ) : (
                  <ArrowDownIcon className="w-3.5 h-3.5 mr-1" />
                )}
                <span className="tabular-nums">{Math.abs(trend)}</span>
              </div>
            )}
          </div>
        </div>

        {/* Activity Status */}
        <div className="space-y-4">
          {/* Status Badges with Tooltips */}
          <div className="flex flex-wrap gap-3">
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-100/10 hover:bg-emerald-100/15 transition-colors">
                    <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                    <span className="text-sm font-medium text-emerald-400">
                      {data.activeMembers} Active
                    </span>
                  </div>
                </TooltipTrigger>
                <TooltipContent>
                  <p>Members who logged in at least once in the last 30 days</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>

            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-gray-500/10 hover:bg-gray-500/15 transition-colors">
                    <span className="w-2 h-2 rounded-full bg-gray-300" />
                    <span className="text-sm font-medium text-gray-400">
                      {data.inactiveMembers} Inactive
                    </span>
                  </div>
                </TooltipTrigger>
                <TooltipContent>
                  <p>Members who haven't logged in for the last 30 days</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>

          {/* Activity Progress Bar */}
          <div className="space-y-2">
            <div className="h-2 rounded-full bg-gray-800/20 overflow-hidden">
              <div 
                className="h-full rounded-full transition-all duration-500 ease-in-out"
                style={{ 
                  width: `${activeRatio}%`,
                  background: 'linear-gradient(90deg, rgba(16,185,129,0.7) 0%, rgba(16,185,129,0.9) 100%)'
                }}
              />
            </div>
            <p className="text-sm text-muted-foreground/80">
              {activeRatio.toFixed(0)}% Active
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
