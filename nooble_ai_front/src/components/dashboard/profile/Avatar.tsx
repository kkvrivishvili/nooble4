"use client"

import * as React from "react"
import * as AvatarPrimitive from "@radix-ui/react-avatar"
import { cn } from "@/utils/cn"
import { User } from "lucide-react"
import type { ComponentRef } from "react"

// Add a simple cache for avatar URLs
const avatarCache = new Map<string, { url: string, timestamp: number }>()
const CACHE_DURATION = 5 * 60 * 1000 // 5 minutes

type ImageLoadingStatus = 'idle' | 'loading' | 'loaded' | 'error'

interface AvatarProps extends React.ComponentPropsWithoutRef<typeof AvatarPrimitive.Root> {
  className?: string
}

// Extend the Image props to include our custom attributes
interface AvatarImageProps extends React.ComponentPropsWithoutRef<typeof AvatarPrimitive.Image> {
  'data-refresh'?: boolean
}

const Avatar = React.forwardRef<ComponentRef<typeof AvatarPrimitive.Root>, AvatarProps>(
  ({ className, ...props }, ref) => (
    <AvatarPrimitive.Root
      ref={ref}
      className={cn(
        "relative flex h-10 w-10 shrink-0 overflow-hidden rounded-full bg-muted",
        className
      )}
      {...props}
    />
  )
)

const AvatarImage = React.forwardRef<
  ComponentRef<typeof AvatarPrimitive.Image>,
  AvatarImageProps
>(({ className, src, 'data-refresh': shouldRefresh, ...props }, ref) => {
  const [status, setStatus] = React.useState<ImageLoadingStatus>('idle')
  const [retryCount, setRetryCount] = React.useState(0)
  const imageRef = React.useRef<string | null>(null)

  // Memoize the image URL with caching
  const imageSrc = React.useMemo(() => {
    if (!src) return null
    
    // Check cache first
    const now = Date.now()
    const cached = avatarCache.get(src)
    if (cached && !shouldRefresh && (now - cached.timestamp < CACHE_DURATION)) {
      return cached.url
    }
    
    let finalUrl = src
    // For Supabase Storage URLs (our avatars)
    if (src.includes('Avatars') || src.includes('Organizations')) {
      finalUrl = shouldRefresh ? `${src}?t=${now}` : src
    }
    // For external URLs (like Google avatars)
    else if (src.startsWith('http')) {
      try {
        const url = new URL(src)
        if (!shouldRefresh) {
          // Cache for 1 hour by adding a cache buster that changes every hour
          url.searchParams.set('cache', Math.floor(now / 3600000).toString())
        }
        finalUrl = url.toString()
      } catch {
        finalUrl = src
      }
    }
    
    // Update cache
    avatarCache.set(src, { url: finalUrl, timestamp: now })
    return finalUrl
  }, [src, shouldRefresh])

  // Reset status when src changes
  React.useEffect(() => {
    if (imageSrc !== imageRef.current) {
      imageRef.current = imageSrc
      setStatus('idle')
      setRetryCount(0)
    }
  }, [imageSrc])

  // Handle loading errors with retry logic
  const handleError = React.useCallback(() => {
    if (retryCount < 2) { // Max 2 retries
      setRetryCount(prev => prev + 1)
      setStatus('loading')
    } else {
      setStatus('error')
    }
  }, [retryCount])

  // Show nothing while loading the first time
  if (status === 'idle' && !imageSrc) return null

  // Show fallback on error
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

const AvatarFallback = React.forwardRef<
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
    {children || <User className="h-5 w-5" />}
  </AvatarPrimitive.Fallback>
))

Avatar.displayName = AvatarPrimitive.Root.displayName
AvatarImage.displayName = AvatarPrimitive.Image.displayName
AvatarFallback.displayName = AvatarPrimitive.Fallback.displayName

export { Avatar, AvatarImage, AvatarFallback }