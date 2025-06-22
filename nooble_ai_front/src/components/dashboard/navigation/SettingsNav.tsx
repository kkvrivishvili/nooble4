'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { cn } from '@/utils/cn'
import { Settings, Users, CreditCard, AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import type { OrgRole } from '@/lib/orgs/orgTypes'

interface SettingsNavProps {
  orgSlug: string
  userRole: OrgRole
}

export function SettingsNav({ orgSlug, userRole }: SettingsNavProps) {
  const pathname = usePathname()
  const router = useRouter()
  const baseUrl = `/dashboard/orgs/${orgSlug}/settings`

  // Handle base settings route
  if (pathname === baseUrl) {
    // Redirect members to dangerzone, others to general
    const redirectPath = userRole === 'member' 
      ? `${baseUrl}/dangerzone`
      : `${baseUrl}/general`
    router.replace(redirectPath)
  }

  // For members, only show danger zone
  if (userRole === 'member') {
    const dangerZoneUrl = `${baseUrl}/dangerzone`
    
    return (
      <nav className="w-64 h-full border-r border-border">
        <div className="p-4">
          <h2 className="font-semibold text-foreground mb-2">Settings</h2>
        </div>
        <div className="space-y-1 px-3">
          <Link href={dangerZoneUrl}>
            <Button
              variant="ghost"
              size="sm"
              className={cn(
                "w-full justify-start text-muted-foreground",
                pathname === dangerZoneUrl ? "bg-accent text-foreground" : "hover:text-foreground",
                "text-destructive hover:text-destructive"
              )}
            >
              <AlertTriangle className="h-4 w-4 mr-2" />
              Danger Zone
            </Button>
          </Link>
        </div>
      </nav>
    )
  }

  // Define links with role-based access
  const links = [
    {
      href: `${baseUrl}/general`,
      label: 'General',
      icon: Settings,
      allowedRoles: ['owner', 'admin'] as OrgRole[]
    },
    {
      href: `${baseUrl}/members`,
      label: 'Members',
      icon: Users,
      allowedRoles: ['owner', 'admin'] as OrgRole[]
    },
    {
      href: `${baseUrl}/billing`,
      label: 'Billing',
      icon: CreditCard,
      allowedRoles: ['owner'] as OrgRole[]
    },
    {
      href: `${baseUrl}/dangerzone`,
      label: 'Danger Zone',
      icon: AlertTriangle,
      allowedRoles: ['owner', 'admin', 'member'] as OrgRole[],
      className: 'text-destructive hover:text-destructive'
    }
  ]

  // For admin/owner, show their allowed links
  const allowedLinks = links.filter(link => 
    link.allowedRoles.includes(userRole)
  )

  return (
    <nav className="w-64 h-full border-r border-border">
      <div className="p-4">
        <h2 className="font-semibold text-foreground mb-2">Settings</h2>
      </div>
      <div className="space-y-1 px-3">
        {allowedLinks.map(({ href, label, icon: Icon, className }) => (
          <Link key={href} href={href}>
            <Button
              variant="ghost"
              size="sm"
              className={cn(
                "w-full justify-start text-muted-foreground",
                pathname === href ? "bg-accent text-foreground" : "hover:text-foreground",
                className
              )}
            >
              <Icon className="h-4 w-4 mr-2" />
              {label}
            </Button>
          </Link>
        ))}
      </div>
    </nav>
  )
} 