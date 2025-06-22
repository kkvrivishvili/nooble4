'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { OrgMemberStats } from '@/lib/orgs/members/statsTypes'
import { UsersIcon, ShieldCheckIcon, StarIcon } from 'lucide-react'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/Tooltip'

interface RoleDistributionProps {
  data: OrgMemberStats['stats']['overview']['roleDistribution']
}

const ROLE_COLORS = {
  owner: 'text-rose-500 bg-rose-500/15 hover:bg-rose-500/20',
  admin: 'text-cyan-500 bg-cyan-500/15 hover:bg-cyan-500/20',
  member: 'text-blue-500 bg-blue-500/15 hover:bg-blue-500/20'
} as const

const ROLE_ICONS = {
  owner: StarIcon,
  admin: ShieldCheckIcon,
  member: UsersIcon
} as const

const ROLE_DESCRIPTIONS = {
  owner: 'Full access and control over the organization',
  admin: 'Can manage members and organization settings',
  member: 'Basic access to organization features'
} as const

export function RoleDistribution({ data }: RoleDistributionProps) {
  const total = Object.values(data).reduce((sum, count) => sum + count, 0)
  
  return (
    <Card className="h-[220px] sm:h-[250px]">
      <CardHeader className="pb-3">
        <CardTitle className="text-base sm:text-lg" id="role-distribution-title">
          Role Distribution
        </CardTitle>
      </CardHeader>
      <CardContent 
        className="space-y-4"
        role="region"
        aria-labelledby="role-distribution-title"
      >
        {/* Role Stats */}
        <div className="space-y-2">
          {(Object.entries(data) as [keyof typeof ROLE_COLORS, number][]).map(([role, count]) => {
            const Icon = ROLE_ICONS[role]
            const percentage = total > 0 ? (count / total) * 100 : 0
            
            return (
              <TooltipProvider key={role}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <div 
                      className={`flex items-center justify-between p-2 rounded-lg transition-colors ${ROLE_COLORS[role]}`}
                      role="button"
                      aria-label={`${role}: ${count} members (${percentage.toFixed(0)}%)`}
                    >
                      <div className="flex items-center gap-2">
                        <Icon className="w-4 h-4" />
                        <span className="text-sm font-medium capitalize">
                          {role}
                        </span>
                      </div>
                      <div className="flex items-center gap-1.5 min-w-[4.5rem] justify-end">
                        <span className="text-sm font-medium tabular-nums">
                          {count}
                        </span>
                        <span className="text-xs text-muted-foreground tabular-nums">
                          ({percentage.toFixed(0)}%)
                        </span>
                      </div>
                    </div>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>{ROLE_DESCRIPTIONS[role]}</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            )
          })}
        </div>

        {/* Total Members Summary */}
        <div className="pt-1">
          <p className="text-sm text-muted-foreground">
            Total Roles Assigned: {total}
          </p>
        </div>
      </CardContent>
    </Card>
  )
}