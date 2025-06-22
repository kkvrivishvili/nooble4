'use client'

import { useRole } from '@/lib/rbac/hooks'
import type { UserRole } from '@/lib/rbac/rbacTypes'

interface RoleGateProps {
  children: React.ReactNode
  allowedRoles?: UserRole[]
  requireAllRoles?: boolean
}

export function RoleGate({ 
  children, 
  allowedRoles = ['admin', 'super_admin'],
  requireAllRoles = false 
}: RoleGateProps) {
  const { role, isLoading } = useRole()
  
  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-4">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    )
  }

  const hasAccess = requireAllRoles
    ? allowedRoles.every(r => r === role)
    : allowedRoles.some(r => r === role)

  if (!hasAccess) {
    return null
  }

  return <>{children}</>
}
