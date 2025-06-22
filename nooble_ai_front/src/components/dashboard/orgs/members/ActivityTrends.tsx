'use client'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { OrgMemberStats } from '@/lib/orgs/members/statsTypes'
import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  Legend, 
  ResponsiveContainer,
  Brush,
  ReferenceLine
} from 'recharts'

interface ActivityTrendsProps {
  data: OrgMemberStats['stats']['trends']
  timeRange: '7d' | '30d' | '90d'
}

// Helper to generate sample data if real data is empty
const generateSampleData = (timeRange: '7d' | '30d' | '90d') => {
  const days = timeRange === '7d' ? 7 : timeRange === '30d' ? 30 : 90
  const data = []
  
  for (let i = days; i >= 0; i--) {
    const date = new Date()
    date.setDate(date.getDate() - i)
    
    data.push({
      date: date.toISOString(),
      joins: Math.floor(Math.random() * 3),  // 0-2 joins per day
      departures: Math.floor(Math.random() * 2)  // 0-1 departures per day
    })
  }
  
  return data
}

export function ActivityTrends({ data, timeRange }: ActivityTrendsProps) {
  // Use real data if available, otherwise use sample data
  const chartData = data?.length ? data : generateSampleData(timeRange)

  return (
    <Card className="h-full">
      <CardHeader className="p-4 sm:p-6">
        <CardTitle id="activity-trends-title">Member Activity</CardTitle>
      </CardHeader>
      <CardContent 
        className="p-2 sm:p-4 md:p-6 h-[calc(100%-4rem)]"
        role="region"
        aria-labelledby="activity-trends-title"
      >
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={chartData}
            margin={{ 
              top: 20, 
              right: 10, 
              left: 0, 
              bottom: 20,
              ...window.innerWidth > 640 && { right: 20, left: 10 },
              ...window.innerWidth > 1024 && { right: 30, left: 10, bottom: 40 }
            }}
            aria-label="Member activity trends chart"
          >
            <CartesianGrid 
              strokeDasharray="3 3" 
              stroke="#374151" 
              vertical={false}
              opacity={0.5}
            />
            <ReferenceLine y={0} stroke="#4B5563" strokeDasharray="3 3" />
            <XAxis 
              dataKey="date" 
              tickFormatter={(date) => {
                const d = new Date(date)
                return window.innerWidth < 640 
                  ? `${d.getDate()}/${d.getMonth() + 1}`
                  : d.toLocaleDateString('en-US', { 
                      month: 'short',
                      day: 'numeric'
                    })
              }}
              stroke="#6B7280"
              tick={{ fill: '#9CA3AF' }}
              tickLine={{ stroke: '#4B5563' }}
              dy={10}
              height={40}
              minTickGap={20}
            />
            <YAxis 
              stroke="#6B7280"
              tick={{ fill: '#9CA3AF' }}
              tickLine={{ stroke: '#4B5563' }}
              width={30}
              tickCount={5}
              domain={[0, 'auto']}
              dx={-5}
            />
            <Tooltip 
              labelFormatter={(date) => {
                const d = new Date(date)
                return d.toLocaleDateString('en-US', { 
                  weekday: 'short',
                  year: 'numeric',
                  month: 'short',
                  day: 'numeric'
                })
              }}
              contentStyle={{ 
                background: '#1F2937', 
                border: '1px solid #374151',
                borderRadius: '6px',
                padding: '12px',
                boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)'
              }}
              itemStyle={{ color: '#E5E7EB', padding: '4px 0' }}
              cursor={{ stroke: '#4B5563', strokeWidth: 1 }}
            />
            <Legend 
              verticalAlign="top" 
              height={36}
              wrapperStyle={{ 
                paddingBottom: '20px',
                paddingTop: '10px'
              }}
              iconType="circle"
            />
            <Line 
              type="monotone" 
              dataKey="joins" 
              stroke="#4ECDC4" 
              strokeWidth={2.5}
              name="Joins"
              dot={{ fill: '#4ECDC4', strokeWidth: 2, r: 4 }}
              activeDot={{ r: 7, strokeWidth: 2 }}
              animationDuration={300}
              aria-label="Member joins trend line"
            />
            <Line 
              type="monotone" 
              dataKey="departures" 
              stroke="#FF6B6B" 
              strokeWidth={2.5}
              name="Departures"
              dot={{ fill: '#FF6B6B', strokeWidth: 2, r: 4 }}
              activeDot={{ r: 7, strokeWidth: 2 }}
              animationDuration={300}
              aria-label="Member departures trend line"
            />
            <Brush 
              dataKey="date"
              height={30}
              stroke="#4B5563"
              fill="#1F2937"
              tickFormatter={(date) => {
                const d = new Date(date)
                return `${d.getDate()}/${d.getMonth() + 1}`
              }}
              y={window.innerWidth < 640 ? 360 : window.innerWidth < 1024 ? 420 : 460}
            />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}