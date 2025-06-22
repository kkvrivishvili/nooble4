import { NextResponse } from 'next/server'
import { createServerClient } from '@supabase/ssr'
import type { Database } from '@/types/supabase'
import type { NextRequest } from 'next/server'
import { handleEvent } from '@/middleware/events'
import type { EventPayload } from '@/middleware/events'

export async function DELETE(request: NextRequest) {
  // The route is: /api/orgs/[id]/invites/[inviteId]/route.ts
  // Example pathname: "/api/orgs/abc/invites/def"
  const segments = request.nextUrl.pathname.split('/');
  // segments: ["", "api", "orgs", "abc", "invites", "def"]
  const slug = segments[3];    // org slug or id from URL
  const inviteId = segments[5];  // inviteId from URL

  const response = NextResponse.next();

  const supabase = createServerClient<Database>(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll: () =>
          request.cookies.getAll().map(cookie => ({
            name: cookie.name,
            value: cookie.value,
          })),
        setAll: (cookieValues) => {
          cookieValues.forEach(({ name, value, ...options }) => {
            response.cookies.set({ name, value, ...options });
          });
        },
      },
    }
  );

  try {
    // Auth check
    const { data: { user }, error: userError } = await supabase.auth.getUser();
    if (userError || !user) {
      return NextResponse.json(
        { error: { message: 'Not authenticated' } },
        { status: 401 }
      );
    }

    // Get org ID from slug
    const { data: org } = await supabase
      .from('organizations')
      .select('id')
      .eq('slug', slug)
      .single();

    if (!org) {
      return NextResponse.json(
        { error: { message: 'Organization not found' } },
        { status: 404 }
      );
    }

    // Verify user is admin/owner
    const { data: membership } = await supabase
      .from('organization_members')
      .select('role')
      .eq('org_id', org.id)
      .eq('user_id', user.id)
      .single();

    if (!membership || !['admin', 'owner'].includes(membership.role)) {
      return NextResponse.json(
        { error: { message: 'Not authorized to manage invites' } },
        { status: 403 }
      );
    }

    // Delete the invite
    const { error: deleteError } = await supabase
      .from('organization_invites')
      .delete()
      .eq('id', inviteId)
      .eq('org_id', org.id);

    if (deleteError) throw deleteError;

    // Track event
    await handleEvent(request, {
      userId: user.id,
      type: 'invite_revoked',
      data: {
        orgId: org.id,
        inviteId,
      },
    } satisfies EventPayload<'invite_revoked'>);

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Error cancelling invite:', error);
    return NextResponse.json(
      { error: { message: 'Failed to cancel invite' } },
      { status: 500 }
    );
  }
}

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string; inviteId: string } }
) {
  const response = NextResponse.next()
  // Await params first
  const { id: orgSlug, inviteId: token } = await Promise.resolve(params)

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
          cookieValues.forEach(({ name, value, ...options }) => {
            response.cookies.set({ name, value, ...options })
          })
        }
      }
    }
  )

  try {
    // Get org ID from slug
    const { data: org } = await supabase
      .from('organizations')
      .select('id')
      .eq('slug', orgSlug)
      .single()

    if (!org) {
      return NextResponse.json(
        { error: { message: 'Organization not found' } },
        { status: 404 }
      )
    }

    // Get invite details
    const { data: invite } = await supabase
      .from('organization_invites')
      .select('*, organizations(*)')
      .eq('token', token)
      .eq('org_id', org.id)
      .single()

    if (!invite) {
      return NextResponse.json(
        { error: { message: 'Invite not found' } },
        { status: 404 }
      )
    }

    return NextResponse.json({ data: invite })
  } catch (error) {
    console.error('Error fetching invite:', error)
    return NextResponse.json(
      { error: { message: 'Failed to fetch invite' } },
      { status: 500 }
    )
  }
}
