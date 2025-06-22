import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/Tabs'
import { RoleManager } from '@/components/dashboard/admin/roles/RoleManager'
import { AnalyticsDashboard } from '@/components/dashboard/admin/analytics/Analytics'
import { SystemHealth } from '@/components/dashboard/admin/system/SystemHealth'
import type { Database } from '@/types/supabase'
import type { ResponseCookie } from 'next/dist/compiled/@edge-runtime/cookies'
import { ActivityLog } from '@/components/dashboard/admin/analytics/AnalyticsLog'

export default async function AdminDashboardPage() {
  const cookieStore = await cookies()
  
  const supabase = createServerClient<Database>(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll: () => {
          return cookieStore.getAll().map((cookie) => ({
            name: cookie.name,
            value: cookie.value,
          }))
        },
        setAll: (cookieValues) => {
          cookieValues.map(({ name, value, ...options }) => {
            cookieStore.set({ 
              name, 
              value, 
              ...options 
            } as ResponseCookie)
          })
        }
      }
    }
  )

  const { data: metrics } = await supabase
    .rpc('get_analytics_metrics')

  // Prepare for future payment metrics
  const enhancedMetrics = {
    ...metrics,
    // Placeholder for future payment metrics
    mrr: 0,
    subscriptions: 0,
    // Placeholder for system metrics
    apiCalls: 0,
    errorRate: '0%',
    integrations: {
      stripe: 'unknown',
      openai: process.env.OPENAI_API_KEY ? 'healthy' : 'unknown'
    }
  }

  return (
    <>
      <div className="border-b pb-4">
        <h2 className="text-2xl font-bold">Admin Dashboard</h2>
      </div>
      
      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="users">User Management</TabsTrigger>
          <TabsTrigger value="activity">Activity Log</TabsTrigger>
          <TabsTrigger value="system">System</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <AnalyticsDashboard />
        </TabsContent>

        <TabsContent value="users">
          <RoleManager />
        </TabsContent>

        <TabsContent value="activity">
          <ActivityLog initialMetrics={enhancedMetrics} />
        </TabsContent>

        <TabsContent value="system">
          <SystemHealth metrics={enhancedMetrics} />
        </TabsContent>
      </Tabs>
    </>
  )
}