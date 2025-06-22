import { NextResponse } from 'next/server'
import { createServerClient } from '@supabase/ssr'
import type { Database } from '@/types/supabase'
import type { NextRequest } from 'next/server'
import { handleEvent } from '@/middleware/events'
import type { EventPayload } from '@/middleware/events'

const TRANSFER_ERRORS = {
  UNAUTHORIZED: {
    code: 'transfer/unauthorized',
    message: 'Not authenticated',
    status: 401
  },
  FORBIDDEN: {
    code: 'transfer/forbidden',
    message: 'Not authorized to transfer ownership',
    status: 403
  },
  NOT_FOUND: {
    code: 'transfer/not-found',
    message: 'Organization or member not found',
    status: 404
  },
  TRANSFER_FAILED: {
    code: 'transfer/failed',
    message: 'Failed to transfer ownership',
    status: 500
  },
  INVALID_REQUEST: {
    code: 'transfer/invalid-request',
    message: 'Invalid transfer request',
    status: 400
  }
} as const

export async function POST(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  const { id: slug } = await Promise.resolve(params)
  const response = NextResponse.next()
  
  const supabase = createServerClient<Database>(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll: () => request.cookies.getAll().map(cookie => ({
          name: cookie.name,
          value: cookie.value,
        })),
        setAll: (cookieValues) => {
          cookieValues.map(({ name, value, ...options }) => {
            response.cookies.set({ name, value, ...options })
          })
        }
      }
    }
  )

  try {
    const { newOwnerId } = await request.json()
    if (!newOwnerId) {
      return NextResponse.json(
        { error: TRANSFER_ERRORS.INVALID_REQUEST },
        { status: TRANSFER_ERRORS.INVALID_REQUEST.status }
      )
    }

    const { data: { user }, error: userError } = await supabase.auth.getUser()
    if (userError || !user) {
      return NextResponse.json(
        { error: TRANSFER_ERRORS.UNAUTHORIZED },
        { status: TRANSFER_ERRORS.UNAUTHORIZED.status }
      )
    }

    // Call RPC function
    const { error: transferError } = await supabase.rpc('transfer_org_ownership', {
      p_org_slug: slug,
      p_current_owner_id: user.id,
      p_new_owner_id: newOwnerId
    })

    if (transferError) throw transferError

    // Track transfer event
    await handleEvent(request, {
      userId: user.id,
      type: 'ownership_transfer',
      data: {
        orgId: slug,
        newOwnerId
      }
    } satisfies EventPayload<'ownership_transfer'>)

    return NextResponse.json({ data: null, error: null })
  } catch (error) {
    console.error('Error transferring ownership:', error)
    return NextResponse.json(
      { data: null, error: TRANSFER_ERRORS.TRANSFER_FAILED },
      { status: TRANSFER_ERRORS.TRANSFER_FAILED.status }
    )
  }
} 