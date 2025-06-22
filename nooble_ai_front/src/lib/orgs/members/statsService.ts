import { createServerClient } from '@supabase/ssr'
import type { Database } from '@/types/supabase'
import type { OrgMemberStats, StatsResponse } from './statsTypes'

export async function getOrgStats(orgId: string): Promise<StatsResponse> {
  const supabase = createServerClient<Database>(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll: () => [],
        setAll: () => {},
      }
    }
  )

  try {
    const { data, error } = await supabase
      .rpc('get_org_member_stats', { 
        p_org_id: orgId  // Changed from org_id to p_org_id
      })

    if (error) throw error

    return {
      data: data as OrgMemberStats,
      error: null
    }
  } catch (error) {
    return {
      data: null,
      error: error as Error
    }
  }
}
