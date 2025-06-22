import { getSupabaseBrowserClient } from '@/lib/auth/config'
import type { ExportResponse, ExportData } from '@/lib/rbac/analyticsTypes'
import type { Database } from '@/types/supabase'
import type { SupabaseClient } from '@supabase/supabase-js'
import Papa from 'papaparse'

type RateLimit = Database['public']['Functions']['get_detailed_analytics']['Returns']['rateLimits']['recent_limits'][0]

export async function exportAnalyticsData(): Promise<ExportResponse> {
  try {
    const supabase = getSupabaseBrowserClient() as SupabaseClient<Database>
    
    // Fetch both basic and detailed metrics
    const [basicMetrics, detailedAnalytics] = await Promise.all([
      supabase.rpc('get_basic_metrics'),
      supabase.rpc('get_detailed_analytics')
    ])

    if (basicMetrics.error) throw basicMetrics.error
    if (detailedAnalytics.error) throw detailedAnalytics.error
    if (!basicMetrics.data || !detailedAnalytics.data) throw new Error('No data returned from analytics')

    const { data: basicData } = basicMetrics
    const { data: detailedData } = detailedAnalytics

    // Format data for CSV with null checks
    const csvData: ExportData[] = [
      // Basic metrics as single row
      {
        date: new Date().toISOString(),
        total_users: basicData.totalUsers,
        active_users: basicData.activeUsers,
        login_count: basicData.loginCount,
        signup_count: basicData.signupCount,
        type: 'basic_metrics' as const
      }
    ]

    // Add rate limits if available
    if (detailedData.rateLimits?.recent_limits?.length) {
      csvData.push(
        ...detailedData.rateLimits.recent_limits.map((limit: RateLimit) => ({
          date: limit.window_start,
          action_type: limit.action_type,
          unique_users: limit.unique_users,
          count: limit.request_count,
          type: 'activity_detail' as const
        }))
      )
    }

    // Convert to CSV with specific options for Excel compatibility
    const csv = Papa.unparse(csvData, {
      header: true,
      delimiter: ',',
      newline: '\r\n',
    })

    const BOM = '\uFEFF'
    const csvContent = BOM + csv

    const blob = new Blob([csvContent], { 
      type: 'text/csv;charset=utf-8;' 
    })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `analytics-data-${new Date().toISOString()}.csv`
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)

    return { success: true, error: null }
  } catch (error) {
    console.error('Export failed:', error)
    return { success: false, error: error as Error }
  }
}