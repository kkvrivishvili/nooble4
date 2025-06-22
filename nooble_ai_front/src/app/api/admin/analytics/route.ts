import { NextResponse } from 'next/server'
import { createServerClient } from '@supabase/ssr'
import type { Database } from '@/types/supabase'
import type { NextRequest } from 'next/server'

// Define possible error types
type AnalyticsError = {
  code: string
  message: string
  status: number
}

const ANALYTICS_ERRORS: Record<string, AnalyticsError> = {
  UNAUTHORIZED: {
    code: 'analytics/unauthorized',
    message: 'Not authenticated',
    status: 401
  },
  FORBIDDEN: {
    code: 'analytics/forbidden',
    message: 'Not authorized to access analytics',
    status: 403
  },
  FETCH_FAILED: {
    code: 'analytics/fetch-failed',
    message: 'Failed to fetch analytics data',
    status: 500
  },
  // Add rate limit errors
  RATE_LIMIT_EXCEEDED: {
    code: 'analytics/rate-limit-exceeded',
    message: 'Rate limit exceeded for this action',
    status: 429
  },
  RATE_LIMIT_FETCH_FAILED: {
    code: 'analytics/rate-limit-fetch-failed',
    message: 'Failed to fetch rate limit data',
    status: 500
  }
} as const

export async function GET(request: NextRequest) {
  try {
    const response = NextResponse.next()
    
    const supabase = createServerClient<Database>(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
      {
        cookies: {
          getAll: () => {
            return request.cookies.getAll().map(cookie => ({
              name: cookie.name,
              value: cookie.value,
            }))
          },
          setAll: (cookieValues) => {
            cookieValues.map(({ name, value, ...options }) => {
              response.cookies.set({ name, value, ...options })
            })
          }
        }
      }
    )

    // Get the last 7 days of activity data
    const startDate = new Date()
    startDate.setDate(startDate.getDate() - 7)

    const { data: activityData, error: activityError } = await supabase
      .from('user_activity')
      .select('created_at, action_type')
      .gte('created_at', startDate.toISOString())
      .order('created_at', { ascending: true })

    if (activityError) {
      console.error('Activity fetch error:', activityError)
      return NextResponse.json(ANALYTICS_ERRORS.FETCH_FAILED, 
        { status: ANALYTICS_ERRORS.FETCH_FAILED.status }
      )
    }

    // Process activity data for the chart
    const dailyActivity = activityData.reduce((acc: Record<string, number>, curr) => {
      const day = new Date(curr.created_at).toISOString().split('T')[0]
      acc[day] = (acc[day] || 0) + 1
      return acc
    }, {})

    // Ensure we have entries for all days, even if no activity
    const chartData = []
    for (let i = 0; i < 7; i++) {
      const date = new Date()
      date.setDate(date.getDate() - i)
      const dateStr = date.toISOString().split('T')[0]
      chartData.unshift({
        date: dateStr,
        value: dailyActivity[dateStr] || 0
      })
    }

    // Get action type breakdown for engagement stats
    const actionBreakdown = activityData.reduce((acc: Record<string, number>, curr) => {
      acc[curr.action_type] = (acc[curr.action_type] || 0) + 1
      return acc
    }, {})

    return NextResponse.json({
      activityHistory: chartData,
      actionBreakdown: Object.entries(actionBreakdown).map(([type, count]) => ({
        type,
        count
      })),
      lastUpdated: new Date().toISOString()
    })

  } catch (err) {
    console.error('Analytics error:', err)
    return NextResponse.json(
      ANALYTICS_ERRORS.FETCH_FAILED,
      { status: ANALYTICS_ERRORS.FETCH_FAILED.status }
    )
  }
}