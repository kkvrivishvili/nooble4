import { createServerClient } from '@supabase/ssr'
import { type NextRequest, NextResponse } from 'next/server'
import type { Database } from '@/types/supabase'
import type { RateLimitConfig } from '@/lib/auth/authTypes'
import type { CookieOptions } from '@supabase/ssr'

export async function withRateLimit(
  request: NextRequest,
  config: RateLimitConfig
) {
  const response = NextResponse.next()

  const supabase = createServerClient<Database>(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll: () => {
          return request.cookies.getAll().map(cookie => ({
            name: cookie.name,
            value: cookie.value,
          }))
        },
        setAll: (cookieValues: { name: string; value: string; options?: CookieOptions }[]) => {
          cookieValues.map(({ name, value, options }) => {
            response.cookies.set({
              name,
              value,
              ...options,
            })
          })
        }
      }
    }
  )

  const { data: { user } } = await supabase.auth.getUser()
  if (!user) return response // Allow unauthenticated requests to pass through

  const { data: withinLimit, error } = await supabase.rpc('check_rate_limit', {
    p_user_id: user.id,
    p_action_type: config.actionType,
    p_max_requests: config.maxRequests,
    p_window_minutes: config.windowMinutes
  })

  if (error || !withinLimit) {
    return NextResponse.json(
      {
        error: {
          code: 'rate-limit/exceeded',
          message: `Rate limit exceeded for ${config.actionType}`,
          status: 429
        }
      },
      { status: 429 }
    )
  }

  return response
}