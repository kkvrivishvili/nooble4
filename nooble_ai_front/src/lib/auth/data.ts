import { getSupabaseBrowserClient } from '@/lib/auth/config'
import type { ExportResponse } from '@/lib/auth/authTypes'
import { RateLimitError } from '@/lib/auth/authTypes'
import Papa from 'papaparse'

// Rate limit configurations can be moved to a constants file
export const RATE_LIMITS = {
  EXPORT_DATA: {
    actionType: 'export_data',
    maxRequests: 5,
    windowMinutes: 60
  }
} as const

export async function exportUserData(): Promise<ExportResponse> {
  try {
    const supabase = getSupabaseBrowserClient()
    const { data: { user } } = await supabase.auth.getUser()
    
    if (!user) throw new Error('No user found')

    // The middleware will handle rate limiting automatically
    const { data: profile, error: profileError } = await supabase
      .from('profiles')
      .select('*')
      .eq('id', user.id)
      .single()

    if (profileError) {
      // Check if error is rate limit related
      if (profileError.code === '429') {
        const rateLimitError = new RateLimitError('Too many export attempts. Please try again later.')
        return { success: false, error: rateLimitError }
      }
      throw profileError
    }

    // Format data for CSV matching our database schema
    const csvData = [
      {
        // User data
        id: user.id,
        email: user.email,
        created_at: user.created_at,
        updated_at: user.updated_at,
        
        // Profile data
        user_id: profile?.user_id || '',
        full_name: profile?.full_name || '',
        avatar_url: profile?.avatar_url || '',
        profile_updated_at: profile?.updated_at || '',
      }
    ]

    // Convert to CSV with specific options for Excel compatibility
    const csv = Papa.unparse(csvData, {
      header: true,
      delimiter: ',',
      newline: '\r\n', // Windows-style newlines for Excel
      columns: [
        // User fields
        'id',
        'email',
        'created_at',
        'updated_at',
        // Profile fields
        'user_id',
        'full_name',
        'avatar_url',
        'profile_updated_at'
      ]
    })

    // Add BOM for Excel UTF-8 detection
    const BOM = '\uFEFF'
    const csvContent = BOM + csv

    // Download with specific MIME type for Excel
    const blob = new Blob([csvContent], { 
      type: 'text/csv;charset=utf-8;' 
    })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `user-data-${new Date().toISOString()}.csv`
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