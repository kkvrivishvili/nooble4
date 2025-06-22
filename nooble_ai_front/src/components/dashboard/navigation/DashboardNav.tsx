'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { LogoutButton } from '@/components/auth/LogoutButton'
import { Button } from '@/components/ui/Button'
import { cn } from '@/utils/cn'
import {
  User as UserIcon,
  Settings,
  LayoutDashboard,
  ShieldCheck,
  Building2
} from 'lucide-react'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/DropdownMenu'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/dashboard/profile/Avatar'
import { profileRoutes, settingsRoutes } from '@/middleware/routes'
import { useRole } from '@/lib/rbac/hooks'
import { useProfile } from '@/lib/profile/hooks'

export function DashboardNav() {
  const pathname = usePathname()
  const { role } = useRole()
  const { profile } = useProfile()

  const navItems = [
    {
      href: '/dashboard',
      label: 'Dashboard',
      icon: LayoutDashboard,
    },
    {
      href: profileRoutes.main,
      label: 'Profile',
      icon: UserIcon,
    },
    {
      href: settingsRoutes.main,
      label: 'Settings',
      icon: Settings,
    },
    // Only show admin link for admin users
    ...(['admin', 'super_admin'].includes(role) ? [
      {
        href: '/dashboard/admin',
        label: 'Admin',
        icon: ShieldCheck,
      }
    ] : []),
  ]

  return (
    <nav className="fixed left-0 flex w-64 h-screen border-r border-border bg-card">
      <div className="flex flex-col w-full">
        <div className="p-6">
          <Link href="/dashboard" className="flex items-center">
            <span className="text-lg font-semibold text-foreground">Dashboard</span>
          </Link>
        </div>

        <div className="flex-1 px-3">
          {navItems.map(({ href, label, icon: Icon }) => (
            <Link key={href} href={href}>
              <Button
                variant="ghost"
                size="sm"
                className={cn(
                  "w-full justify-start mb-1 text-muted-foreground",
                  pathname === href && "bg-accent text-foreground"
                )}
              >
                <Icon className="h-4 w-4 mr-2" />
                {label}
              </Button>
            </Link>
          ))}
        </div>

        {/* User section at bottom */}
        <div className="border-t border-border p-4">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button 
                variant="ghost" 
                size="sm"
                className="w-full justify-start gap-2 text-foreground hover:bg-accent"
              >
                <Avatar className="h-8 w-8">
                  <AvatarImage
                    src={profile?.avatar_url || ''}
                    alt={profile?.full_name || 'User'}
                  />
                  <AvatarFallback>
                    {profile?.full_name?.[0]?.toUpperCase() || 'U'}
                  </AvatarFallback>
                </Avatar>
                <span className="flex-1 text-left">
                  {profile?.full_name || 'Account'}
                </span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuLabel className="text-foreground">Personal Account</DropdownMenuLabel>
              <DropdownMenuItem asChild>
                <Link href={profileRoutes.main} className="flex items-center text-muted-foreground hover:text-foreground">
                  <UserIcon className="mr-2 h-4 w-4" />
                  Profile
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <Link href={settingsRoutes.main} className="flex items-center text-muted-foreground hover:text-foreground">
                  <Settings className="mr-2 h-4 w-4" />
                  Settings
                </Link>
              </DropdownMenuItem>
              
              <DropdownMenuSeparator />
              
              <DropdownMenuLabel className="text-foreground">Organizations</DropdownMenuLabel>
              <DropdownMenuItem asChild>
                <Link href="/dashboard/orgs" className="flex items-center text-muted-foreground hover:text-foreground">
                  <Building2 className="mr-2 h-4 w-4" />
                  Manage Organizations
                </Link>
              </DropdownMenuItem>
              
              <DropdownMenuSeparator />
              
              <LogoutButton />
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </nav>
  )
} 
