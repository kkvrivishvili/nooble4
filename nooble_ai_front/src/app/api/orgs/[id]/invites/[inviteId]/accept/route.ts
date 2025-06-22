import { NextResponse } from 'next/server'
import { createServerClient } from '@supabase/ssr'
import type { Database } from '@/types/supabase'
import type { NextRequest } from 'next/server'
import { handleEvent } from '@/middleware/events'
import type { EventPayload } from '@/middleware/events'

const ACCEPT_ERRORS = {
  UNAUTHORIZED: {
    code: 'accept/unauthorized',
    message: 'Not authenticated',
    status: 401,
  },
  NOT_FOUND: {
    code: 'accept/not-found',
    message: 'Invite not found',
    status: 404,
  },
  ALREADY_ACCEPTED: {
    code: 'accept/already-accepted',
    message: 'Invite already accepted',
    status: 400,
  },
  EXPIRED: {
    code: 'accept/expired',
    message: 'Invite has expired',
    status: 400,
  },
  FAILED: {
    code: 'accept/failed',
    message: 'Failed to accept invite',
    status: 500,
  },
} as const;

export async function POST(request: NextRequest): Promise<NextResponse> {
  // Parse dynamic route parameters from the URL
  // The pathname should be something like:
  // "/api/orgs/{orgId}/invites/{inviteId}/accept"
  const segments = request.nextUrl.pathname.split('/');
  // segments example: ["", "api", "orgs", "{orgId}", "invites", "{inviteId}", "accept"]
  const orgId = segments[3]; // index 3 is the orgId
  const inviteId = segments[5]; // index 5 is the inviteId

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
        { error: ACCEPT_ERRORS.UNAUTHORIZED },
        { status: ACCEPT_ERRORS.UNAUTHORIZED.status }
      );
    }

    // Get and validate invite
    const { data: invite, error: inviteError } = await supabase
      .from('organization_invites')
      .select('*')
      .eq('id', inviteId)
      .eq('org_id', orgId)
      .single();

    if (inviteError || !invite) {
      return NextResponse.json(
        { error: ACCEPT_ERRORS.NOT_FOUND },
        { status: ACCEPT_ERRORS.NOT_FOUND.status }
      );
    }

    // Check if already accepted
    if (invite.accepted_at) {
      return NextResponse.json(
        { error: ACCEPT_ERRORS.ALREADY_ACCEPTED },
        { status: ACCEPT_ERRORS.ALREADY_ACCEPTED.status }
      );
    }

    // Check if expired
    if (new Date(invite.expires_at) < new Date()) {
      return NextResponse.json(
        { error: ACCEPT_ERRORS.EXPIRED },
        { status: ACCEPT_ERRORS.EXPIRED.status }
      );
    }

    // Begin transaction (calls a stored procedure)
    const { error: transactionError } = await supabase.rpc('accept_invite', {
      p_invite_id: inviteId,
      p_user_id: user.id,
    });
    if (transactionError) throw transactionError;

    // Delete the invite after successful acceptance
    const { error: deleteError } = await supabase
      .from('organization_invites')
      .delete()
      .eq('id', inviteId)
      .eq('org_id', orgId);

    if (deleteError) {
      console.error('Failed to delete accepted invite:', deleteError);
      // Don't throw - invite was still accepted successfully
    }

    // Track event
    await handleEvent(request, {
      userId: user.id,
      type: 'invite_accepted',
      data: {
        orgId,
        inviteId,
      },
    } satisfies EventPayload<'invite_accepted'>);

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error('Error accepting invite:', error);
    return NextResponse.json(
      { error: ACCEPT_ERRORS.FAILED },
      { status: ACCEPT_ERRORS.FAILED.status }
    );
  }
}
