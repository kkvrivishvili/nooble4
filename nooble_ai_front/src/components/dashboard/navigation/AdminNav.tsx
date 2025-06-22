'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Button } from '@/components/ui/Button'
import { RoleGate } from '@/components/rbac/RoleGate'
import { cn } from '@/utils/cn'
import type { UserRole } from '@/lib/rbac/rbacTypes'
import { 
  Activity,  
  LineChart,
  Building2,
  Boxes,
} from 'lucide-react'

interface NavItem {
  href: string
  label: string
  icon: React.ElementType
  roles: UserRole[]
}

const navItems: NavItem[] = [
  {
    href: '/dashboard/admin',
    label: 'Overview',
    icon: Activity,
    roles: ['admin', 'super_admin']
  },
  {
    href: '/dashboard/admin/analytics',
    label: 'Analytics',
    icon: LineChart,
    roles: ['admin', 'super_admin']
  },
  {
    href: '/dashboard/admin/organization',
    label: 'Organization',
    icon: Building2,
    roles: ['super_admin']
  },
  {
    href: '/dashboard/admin/integrations',
    label: 'Integrations',
    icon: Boxes,
    roles: ['admin', 'super_admin']
  },
]

export function AdminNav() {
  const pathname = usePathname()

  return (
    <nav className="flex items-center space-x-4 lg:space-x-6 mb-8">
      {navItems.map(({ href, label, icon: Icon, roles }) => (
        <RoleGate key={href} allowedRoles={roles}>
          <Link href={href}>
            <Button 
              variant="ghost"
              size="sm"
              className={cn(
                "text-muted-foreground transition-colors hover:text-foreground",
                pathname === href && "bg-accent text-foreground"
              )}
            >
              <Icon className="h-4 w-4 mr-2" />
              {label}
            </Button>
          </Link>
        </RoleGate>
      ))}
    </nav>
  )
}