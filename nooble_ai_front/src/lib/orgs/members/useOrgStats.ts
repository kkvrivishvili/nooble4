'use client'

import { useState, useEffect } from 'react'
import { getSupabaseBrowserClient } from '@/lib/auth/config'
import type { OrgMemberStats, ActivityTrend } from './statsTypes'

interface UseOrgStatsReturn {
  data: OrgMemberStats | null
  isLoading: boolean
  error: Error | null
  trend: number
}

const calculateTrend = (trends: ActivityTrend[], days: number = 30): number => {
  if (!trends.length) return 0
  
  // Sort trends by date
  const sortedTrends = [...trends].sort((a, b) => 
    new Date(a.date).getTime() - new Date(b.date).getTime()
  )

  // Get the net change over the period
  let netChange = 0
  const cutoffDate = new Date()
  cutoffDate.setDate(cutoffDate.getDate() - days)

  sortedTrends.forEach(trend => {
    if (new Date(trend.date) >= cutoffDate) {
      netChange += trend.joins - trend.departures
    }
  })

  return netChange
}

const transformStats = (rawData: any): OrgMemberStats => {
  if (!rawData?.stats) {
    // Return default structure matching our updated interface
    return {
      stats: {
        overview: {
          totalMembers: 0,
          activeMembers: 0,
          inactiveMembers: 0,
          roleDistribution: {
            owner: 0,
            admin: 0,
            member: 0
          }
        },
        trends: []
      },
      roleHistory: []
    }
  }

  return {
    stats: {
      overview: rawData.stats.overview,
      trends: rawData.stats.trends || []
    },
    roleHistory: rawData.roleHistory || []
  }
}

export function useOrgStats(orgId: string): UseOrgStatsReturn {
  const [data, setData] = useState<OrgMemberStats | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  useEffect(() => {
    let isMounted = true
    const supabase = getSupabaseBrowserClient()

    async function fetchStats() {
      try {
        // Let RLS handle the permissions
        const response = await fetch(`/api/orgs/${orgId}/analytics`)
        if (!response.ok) {
          throw new Error('Failed to fetch stats')
        }

        const { data: statsData } = await response.json()
        const transformedData = transformStats(statsData)

        if (isMounted) {
          setData(transformedData)
          setError(null)
        }
      } catch (error) {
        console.error('Error fetching org stats:', error)
        if (isMounted) {
          setError(error as Error)
          setData(null)
        }
      } finally {
        if (isMounted) {
          setIsLoading(false)
        }
      }
    }

    fetchStats()

    // Refresh stats every 5 minutes
    const interval = setInterval(fetchStats, 1000 * 60 * 5)

    return () => {
      isMounted = false
      clearInterval(interval)
    }
  }, [orgId])

  // Calculate trend from the data
  const trend = data ? calculateTrend(data.stats.trends) : 0

  // Return data with calculated trend
  return { 
    data,
    isLoading, 
    error,
    trend // Now we can access the trend in our components
  }
}
