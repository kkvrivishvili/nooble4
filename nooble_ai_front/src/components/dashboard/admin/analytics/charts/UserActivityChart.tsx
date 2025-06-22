'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import type { ChartTooltipProps } from '@/lib/rbac/analyticsTypes'

export interface ActivityData {
  date: string
  value: number
}

interface UserActivityChartProps {
  data?: ActivityData[]
}

export function UserActivityChart({ data = [] }: UserActivityChartProps) {
  console.log('Activity Chart Data:', data)
  
  const formatDate = (date: string | undefined) => {
    if (!date) return ''
    return new Date(date).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric'
    }).replace(',', '')
  }

  if (data.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-foreground">User Activity</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-[300px] flex items-center justify-center text-muted-foreground">
            No activity data available
          </div>
        </CardContent>
      </Card>
    )
  }

  const CustomTooltip = ({ active, payload, label }: ChartTooltipProps) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-background/95 p-3 border rounded-lg shadow-lg backdrop-blur-sm border-border">
          <p className="text-xs font-medium mb-2 text-foreground">{formatDate(label)}</p>
          <div className="flex items-center justify-between gap-4">
            <span className="text-sm text-muted-foreground">Total Actions:</span>
            <span className="text-sm font-medium text-foreground">{payload[0].value}</span>
          </div>
        </div>
      )
    }
    return null
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-foreground">User Activity</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-[300px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart 
              data={data} 
              margin={{ top: 20, right: 20, left: 20, bottom: 20 }}
              barGap={8}
            >
              <XAxis 
                dataKey="date" 
                stroke="hsl(var(--muted-foreground))"
                fontSize={12}
                tickFormatter={formatDate}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                stroke="hsl(var(--muted-foreground))"
                fontSize={12}
                tickLine={false}
                axisLine={false}
                width={35}
              />
              <Tooltip 
                content={<CustomTooltip />}
                cursor={{ fill: 'transparent' }}
              />
              <Bar 
                dataKey="value" 
                fill="hsl(var(--primary))"
                radius={[4, 4, 0, 0]}
                maxBarSize={32}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  )
}
