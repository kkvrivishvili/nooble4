'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import type { ChartTooltipProps } from '@/lib/rbac/analyticsTypes'

export interface EngagementData {
  type: string
  count: number
}

interface EngagementStatsProps {
  data?: EngagementData[]
}

export function EngagementStats({ data = [] }: EngagementStatsProps) {
  const formatType = (type: string | undefined) => {
    if (!type) return ''
    return type
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ')
  }

  const CustomTooltip = ({ active, payload, label }: ChartTooltipProps) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-background/95 p-3 border rounded-lg shadow-lg backdrop-blur-sm border-border">
          <p className="text-xs font-medium mb-2 text-foreground">{formatType(label)}</p>
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <span 
                className="h-2 w-2 rounded-full" 
                style={{ backgroundColor: payload[0].color }} 
              />
              <span className="text-sm text-muted-foreground">Count</span>
            </div>
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
        <CardTitle className="text-foreground">User Engagement</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-[300px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart 
              data={data} 
              layout="vertical"
              margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
            >
              <XAxis type="number" hide />
              <YAxis 
                dataKey="type" 
                type="category"
                tickFormatter={formatType}
                tickLine={false}
                axisLine={false}
                width={120}
                fontSize={12}
                stroke="hsl(var(--muted-foreground))"
              />
              <Tooltip 
                content={<CustomTooltip />}
                cursor={{ fill: 'transparent' }}
              />
              <Legend iconType="circle" />
              <Bar 
                name="Action Count"
                dataKey="count" 
                fill="hsl(var(--primary))"
                radius={[4, 4, 4, 4]}
                barSize={20}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  )
}
