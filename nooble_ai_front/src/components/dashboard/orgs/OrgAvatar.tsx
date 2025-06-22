'use client'

import * as React from "react"
import * as AvatarPrimitive from "@radix-ui/react-avatar"
import { cn } from "@/utils/cn"
import { Building2 } from "lucide-react"
import type { ComponentRef } from "react"
import { Organization } from "@/lib/orgs/orgTypes"

type ImageLoadingStatus = 'idle' | 'loading' | 'loaded' | 'error'

interface OrgAvatarProps extends React.ComponentPropsWithoutRef<typeof AvatarPrimitive.Root> {
  className?: string
  organization: Organization | null
}

interface OrgAvatarImageProps extends React.ComponentPropsWithoutRef<typeof AvatarPrimitive.Image> {
  'data-refresh'?: boolean
}

const OrgAvatar = React.forwardRef<ComponentRef<typeof AvatarPrimitive.Root>, OrgAvatarProps>(
  ({ className, organization, ...props }, ref) => (
    <AvatarPrimitive.Root
      ref={ref}
      className={cn(
        "relative flex h-10 w-10 shrink-0 overflow-hidden rounded-full bg-muted",
        className
      )}
      {...props}
    >
      {organization?.avatar_url ? (
        <OrgAvatarImage src={organization.avatar_url} />
      ) : (
        <OrgAvatarFallback />
      )}
    </AvatarPrimitive.Root>
  )
)

const OrgAvatarImage = React.forwardRef<
  ComponentRef<typeof AvatarPrimitive.Image>,
  OrgAvatarImageProps
>(({ className, src, 'data-refresh': shouldRefresh, ...props }, ref) => {
  const [status, setStatus] = React.useState<ImageLoadingStatus>('idle')
  const [retryCount, setRetryCount] = React.useState(0)
  const imageRef = React.useRef<string | null>(null)

  const imageSrc = React.useMemo(() => {
    if (!src) return null
    
    if (src.includes('Avatars') || src.includes('Organizations')) {
      return shouldRefresh ? `${src}?t=${Date.now()}` : src
    }
    
    if (src.startsWith('http')) {
      try {
        const url = new URL(src)
        if (!shouldRefresh) {
          url.searchParams.set('cache', Math.floor(Date.now() / 3600000).toString())
        }
        return url.toString()
      } catch {
        return src
      }
    }
    
    return src
  }, [src, shouldRefresh])

  React.useEffect(() => {
    if (imageSrc !== imageRef.current) {
      imageRef.current = imageSrc
      setStatus('idle')
      setRetryCount(0)
    }
  }, [imageSrc])

  const handleError = React.useCallback(() => {
    if (retryCount < 2) {
      setRetryCount(prev => prev + 1)
      setStatus('loading')
    } else {
      setStatus('error')
    }
  }, [retryCount])

  if (status === 'idle' && !imageSrc) return null
  if (status === 'error') return null

  return (
    <AvatarPrimitive.Image
      ref={ref}
      src={imageSrc || undefined}
      className={cn(
        "aspect-square h-full w-full transition-opacity duration-300",
        status === 'loaded' ? "opacity-100" : "opacity-0",
        className
      )}
      onLoadingStatusChange={setStatus}
      onError={handleError}
      {...props}
    />
  )
})

const OrgAvatarFallback = React.forwardRef<
  ComponentRef<typeof AvatarPrimitive.Fallback>,
  React.ComponentPropsWithoutRef<typeof AvatarPrimitive.Fallback>
>(({ className, children, ...props }, ref) => (
  <AvatarPrimitive.Fallback
    ref={ref}
    className={cn(
      "flex h-full w-full items-center justify-center rounded-full bg-muted text-muted-foreground",
      className
    )}
    {...props}
  >
    {children || <Building2 className="h-5 w-5" />}
  </AvatarPrimitive.Fallback>
))

OrgAvatar.displayName = AvatarPrimitive.Root.displayName
OrgAvatarImage.displayName = "OrgAvatarImage"
OrgAvatarFallback.displayName = AvatarPrimitive.Fallback.displayName

export { OrgAvatar, OrgAvatarImage, OrgAvatarFallback }