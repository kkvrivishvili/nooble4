'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { exportAnalyticsData } from '@/lib/rbac/data'
import { toast } from 'sonner'

export function ExportButton() {
  const [isLoading, setIsLoading] = useState(false)

  const handleExport = async () => {
    setIsLoading(true)
    try {
      const result = await exportAnalyticsData()
      if (!result.success) {
        throw result.error
      }
      toast.success('Analytics data exported successfully')
    } catch (error) {
      console.error('Export failed:', error)
      toast.error('Failed to export analytics data')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <Button 
      variant="outline"
      size="sm" 
      onClick={handleExport}
      disabled={isLoading}
      className="text-foreground hover:text-foreground"
    >
      {isLoading ? 'Exporting...' : 'Export Analytics Data'}
    </Button>
  )
} 