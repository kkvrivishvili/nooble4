'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Users, Activity, MousePointerClick, ArrowUpRight } from 'lucide-react'

interface MetricsData {
  dailyActiveUsers: number
  totalActions: number
  engagementRate: string
  userGrowth: number
  rateLimits: number
}

interface MetricsOverviewProps {
  metrics?: MetricsData
}

export function MetricsOverview({ metrics }: MetricsOverviewProps) {
  const cards = [
    {
      title: "Daily Active Users",
      value: metrics?.dailyActiveUsers || 0,
      icon: Users,
      description: "Active users today"
    },
    {
      title: "Total Actions",
      value: metrics?.totalActions || 0,
      icon: Activity,
      description: "Actions performed today"
    },
    {
      title: "Engagement Rate",
      value: metrics?.engagementRate || "0%",
      icon: MousePointerClick,
      description: "User engagement"
    },
    {
      title: "User Growth",
      value: metrics?.userGrowth || 0,
      icon: ArrowUpRight,
      description: "New users this week"
    }
  ]

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      {cards.map((card) => (
        <Card key={card.title}>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-foreground">
              {card.title}
            </CardTitle>
            <card.icon className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-foreground">{card.value}</div>
            <p className="text-xs text-muted-foreground">
              {card.description}
            </p>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
