'use client'

import { useEffect } from 'react'
import { DashboardNav } from '@/components/dashboard/navigation/DashboardNav'
import { PageLoader } from '@/components/ui/PageLoader'
import { useMinimumLoadingTime } from '@/lib/utils/useMinimumLoadingTime'

interface DashboardWrapperProps {
  children: React.ReactNode
}

export function DashboardWrapper({ children }: DashboardWrapperProps) {
  const { isLoading, endLoading } = useMinimumLoadingTime({
    minimumLoadingTime: 2200,
    initialLoadingState: true
  })

  useEffect(() => {
    endLoading()
  }, [endLoading])

  if (isLoading) {
    return <PageLoader />
  }

  return (
    <div className="flex min-h-screen bg-background">
      <DashboardNav />
      <main className="flex-1 ml-64">
        <div className="p-8">
          <div className="mx-auto max-w-4xl">
            {children}
          </div>
        </div>
      </main>
    </div>
  )
} 