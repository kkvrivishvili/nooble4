'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { cn } from '@/utils/cn'

interface OrgNavProps {
  organization: {
    slug: string
    name: string
  }
}

export function OrgNav({ organization }: OrgNavProps) {
  const pathname = usePathname()
  const baseUrl = `/dashboard/orgs/${organization.slug}`

  const links = [
    {
      href: baseUrl,
      label: 'Overview'
    },
    {
      href: `${baseUrl}/members`,
      label: 'Members'
    },
    {
      href: `${baseUrl}/settings/general`,
      label: 'Settings'
    }
  ]

  return (
    <nav className="border-b border-border">
      <div className="px-4">
        <div className="flex h-16 items-center">
          <div className="flex space-x-8">
            {links.map(link => (
              <Link
                key={link.href}
                href={link.href}
                className={cn(
                  'inline-flex items-center border-b-2 px-1 pt-1 text-sm font-medium transition-colors',
                  pathname === link.href
                    ? 'border-primary text-foreground'
                    : 'border-transparent text-muted-foreground hover:border-border hover:text-foreground'
                )}
              >
                {link.label}
              </Link>
            ))}
          </div>
        </div>
      </div>
    </nav>
  )
} 