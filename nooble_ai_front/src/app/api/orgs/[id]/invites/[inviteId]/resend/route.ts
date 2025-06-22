import { NextResponse } from 'next/server'
import { createServerClient } from '@supabase/ssr'
import type { Database } from '@/types/supabase'
import type { NextRequest } from 'next/server'
import { handleEvent } from '@/middleware/events'
import type { EventPayload } from '@/middleware/events'
import { sendInviteEmail } from '@/lib/orgs/email/sendEmail'

export async function POST(request: NextRequest): Promise<NextResponse> {
  // Extract dynamic segments from the pathname.
  // For a route like "/api/orgs/[id]/invites/[inviteId]/resend"
  // the pathname will look like: "/api/orgs/abc/invites/def/resend"
  const segments = request.nextUrl.pathname.split('/');
  // segments example: ["", "api", "orgs", "abc", "invites", "def", "resend"]
  const orgId = segments[3];    // "abc"
  const inviteId = segments[5]; // "def"

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

    // Get org ID and invite details
    const { data: invite } = await supabase
      .from('organization_invites')
      .select('*, organizations!inner(id, slug, name)')
      .eq('id', inviteId)
      .eq('organizations.slug', orgId)
      .single();

    if (!invite) {
      return NextResponse.json(
        { error: { message: 'Invite not found' } },
        { status: 404 }
      );
    }

    // Verify user is admin/owner
    const { data: membership } = await supabase
      .from('organization_members')
      .select('role')
      .eq('org_id', invite.org_id)
      .eq('user_id', user.id)
      .single();

    if (!membership || !['admin', 'owner'].includes(membership.role)) {
      return NextResponse.json(
        { error: { message: 'Not authorized to manage invites' } },
        { status: 403 }
      );
    }

    // Update invite expiry
    const { error: updateError } = await supabase
      .from('organization_invites')
      .update({
        expires_at: new Date(Date.now() + 48 * 60 * 60 * 1000).toISOString(),
      })
      .eq('id', inviteId);

    if (updateError) throw updateError;

    // Resend invite email with fallback for inviter name
    await sendInviteEmail({
      to: invite.email,
      orgName: invite.organizations.name,
      inviteUrl: `${process.env.NEXT_PUBLIC_APP_URL}/invite?token=${invite.token}`,
      inviterName: user.email || 'A team member',
    });

    // Track event
    await handleEvent(request, {
      userId: user.id,
      type: 'invite_resent',
      data: {
        orgId: invite.org_id,
        inviteId,
        email: invite.email,
      },
    } satisfies EventPayload<'invite_resent'>);

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Error resending invite:', error);
    return NextResponse.json(
      { error: { message: 'Failed to resend invite' } },
      { status: 500 }
    );
  }
}