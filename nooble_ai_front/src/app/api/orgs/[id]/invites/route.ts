import { NextResponse } from 'next/server'
import { createServerClient } from '@supabase/ssr'
import type { Database } from '@/types/supabase'
import type { NextRequest } from 'next/server'
import { handleEvent } from '@/middleware/events'
import type { EventPayload } from '@/middleware/events'
import type { OrgRole } from '@/lib/orgs/orgTypes'
import type { PostgrestError } from '@supabase/supabase-js'
import { v4 as uuidv4 } from 'uuid'
import { sendInviteEmail } from '@/lib/orgs/email/sendEmail'

// Define error types
const INVITE_ERRORS = {
  UNAUTHORIZED: {
    code: 'invite/unauthorized',
    message: 'Not authenticated',
    status: 401
  },
  FORBIDDEN: {
    code: 'invite/forbidden',
    message: 'Not authorized to manage invites',
    status: 403
  },
  NOT_FOUND: {
    code: 'invite/not-found',
    message: 'Organization not found',
    status: 404
  },
  ALREADY_MEMBER: {
    code: 'invite/already-member',
    message: 'User is already a member',
    status: 400
  },
  INVITE_EXISTS: {
    code: 'invite/exists',
    message: 'This email already has a pending invite. Check the pending invites section to manage it.',
    status: 400
  },
  FAILED: {
    code: 'invite/failed',
    message: 'Failed to process invite',
    status: 500
  },
  SELF_INVITE: {
    code: 'invite/self-invite',
    message: 'You cannot invite yourself to an organization',
    status: 400
  }
} as const

type InviteWithOrg = Database['public']['Tables']['organization_invites']['Row'] & {
  organizations: Pick<Database['public']['Tables']['organizations']['Row'], 'slug' | 'name'>
}


export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
): Promise<NextResponse> {
  // Await params before using
  const { id } = await Promise.resolve(params)
  const slug = id
  const response = NextResponse.next()
  
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
        }
      }
    }
  );
  
  try {
    const { data: { user }, error: userError } = await supabase.auth.getUser();
    if (userError || !user) {
      return NextResponse.json(
        { error: { code: 'invite/unauthorized', message: 'Not authenticated', status: 401 } },
        { status: 401 }
      );
    }
    
    // If slug equals 'pending', return all pending invites for the user
    if (slug === 'pending') {
      const { data, error } = await supabase
        .from('organization_invites')
        .select(`
          id,
          organizations!inner (
            slug,
            name
          )
        `)
        .eq('email', user.email)
        .is('accepted_at', null)
        .gt('expires_at', new Date().toISOString()) as { 
          data: InviteWithOrg[] | null, 
          error: PostgrestError | null 
        };
      
      if (error) throw error;
      
      return NextResponse.json({
        data: data?.map(invite => ({
          id: invite.id,
          org_slug: invite.organizations.slug,
          org_name: invite.organizations.name
        }))
      });
    }
    
    // Get org ID from slug
    const { data: org, error: orgError } = await supabase
      .from('organizations')
      .select('id')
      .eq('slug', slug)
      .single();
    
    if (orgError || !org) {
      console.log('Org not found:', { slug, error: orgError });
      return NextResponse.json(
        { error: { code: 'invite/not-found', message: 'Organization not found', status: 404 } },
        { status: 404 }
      );
    }

    console.log('Found org:', { slug, org_id: org.id });
    
    // Check membership
    const { data: membership, error: membershipError } = await supabase
      .from('organization_members')
      .select('role')
      .eq('org_id', org.id)
      .eq('user_id', user.id)
      .single();
    
    if (membershipError || !membership) {
      console.log('Membership check failed:', { org_id: org.id, user_id: user.id, error: membershipError });
      return NextResponse.json(
        { error: { code: 'invite/forbidden', message: 'Not authorized to manage invites', status: 403 } },
        { status: 403 }
      );
    }

    // First get ALL invites to debug
    const { data: allInvites, error: allInvitesError } = await supabase
      .from('organization_invites')
      .select('*')
      .eq('org_id', org.id);

    console.log('All invites for org:', { 
      org_id: org.id,
      count: allInvites?.length,
      invites: allInvites
    });

    // Then get filtered invites
    const { data: invites, error: invitesError } = await supabase
      .from('organization_invites')
      .select(`
        id,
        email,
        role,
        invited_by,
        expires_at,
        created_at,
        accepted_at,
        token
      `)
      .eq('org_id', org.id)
      .is('accepted_at', null)
      .gt('expires_at', new Date().toISOString());
    
    console.log('Filtered invites:', {
      count: invites?.length,
      currentTime: new Date().toISOString(),
      invites: invites?.map(i => ({
        id: i.id,
        email: i.email,
        accepted_at: i.accepted_at,
        expires_at: i.expires_at
      }))
    });

    if (invitesError) {
      console.error('Error fetching filtered invites:', invitesError);
      throw invitesError;
    }
    
    const formattedInvites = invites?.map(invite => ({
      id: invite.id,
      email: invite.email,
      role: invite.role,
      expires_at: invite.expires_at,
      created_at: invite.created_at,
      token: invite.token
    })) || [];
    
    return NextResponse.json({ data: formattedInvites, error: null });
  } catch (error) {
    console.error('Error in GET /invites:', error);
    return NextResponse.json(
      { error: INVITE_ERRORS.FAILED },
      { status: INVITE_ERRORS.FAILED.status }
    );
  }
}



export async function POST(
  request: NextRequest,
  { params }: { params: { id: string } }
): Promise<NextResponse> {
  // Await params before using
  const { id } = await Promise.resolve(params)
  const slug = id
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
    const { email, role } = await request.json()
    console.log('Received invite request:', { email, role, slug })

    // Explicitly type check the role
    if (!['admin', 'member'].includes(role as OrgRole)) {
      return NextResponse.json(
        { error: { message: 'Invalid role specified' } },
        { status: 400 }
      )
    }

    // First get the org_id from the slug
    const { data: org, error: orgError } = await supabase
      .from('organizations')
      .select('id, name')
      .eq('slug', slug)
      .single()

    if (orgError || !org) {
      return NextResponse.json(
        { error: INVITE_ERRORS.NOT_FOUND },
        { status: INVITE_ERRORS.NOT_FOUND.status }
      )
    }

    const { data: { user }, error: userError } = await supabase.auth.getUser()
    if (userError || !user) {
      return NextResponse.json(
        { error: INVITE_ERRORS.UNAUTHORIZED },
        { status: INVITE_ERRORS.UNAUTHORIZED.status }
      )
    }

    // Add check for self-invite
    if (user.email === email) {
      return NextResponse.json(
        { error: INVITE_ERRORS.SELF_INVITE },
        { status: INVITE_ERRORS.SELF_INVITE.status }
      )
    }

    // Verify requester is admin/owner
    const { data: membership } = await supabase
      .from('organization_members')
      .select('role')
      .eq('org_id', org.id)
      .eq('user_id', user.id)
      .single()

    if (!membership || !['admin', 'owner'].includes(membership.role)) {
      return NextResponse.json(
        { error: INVITE_ERRORS.FORBIDDEN },
        { status: INVITE_ERRORS.FORBIDDEN.status }
      )
    }

    // First check if user is already a member
    const { data: existingMember } = await supabase
      .from('organization_members')
      .select('user_id')
      .eq('org_id', org.id)
      .eq('email', email)
      .single()

    if (existingMember) {
      return NextResponse.json(
        { error: INVITE_ERRORS.ALREADY_MEMBER },
        { status: INVITE_ERRORS.ALREADY_MEMBER.status }
      )
    }

    // Check for existing PENDING invite only
    const { data: existingInvite } = await supabase
      .from('organization_invites')
      .select('id')
      .eq('org_id', org.id)
      .eq('email', email)
      .is('accepted_at', null)  // Only check unaccepted invites
      .gt('expires_at', new Date().toISOString())
      .single()

    if (existingInvite) {
      return NextResponse.json(
        { error: INVITE_ERRORS.INVITE_EXISTS },
        { status: INVITE_ERRORS.INVITE_EXISTS.status }
      )
    }

    // Generate invite token
    const token = uuidv4()
    console.log('Generated token:', token)

    const expires_at = new Date()
    expires_at.setHours(expires_at.getHours() + 48)

    // Log the full invite data before creation
    const inviteData = {
      org_id: org.id,
      email,
      role,
      invited_by: user.id,
      token,
      expires_at: expires_at.toISOString()
    }
    console.log('Attempting to create invite with data:', inviteData)

    const { data: invite, error: inviteError } = await supabase
      .from('organization_invites')
      .insert(inviteData)
      .select()
      .single()

    console.log('Insert response:', { 
      success: !inviteError,
      invite,
      error: inviteError
    })

    if (inviteError) {
      console.error('Failed to create invite:', inviteError)
      throw inviteError
    }

    // Immediate verification query
    const { data: verifyInvite, error: verifyError } = await supabase
      .from('organization_invites')
      .select('*')
      .eq('token', token)
      .single()

    console.log('Verification query results:', {
      found: !!verifyInvite,
      invite: verifyInvite,
      error: verifyError
    })

    if (!verifyInvite) {
      console.error('Invite verification failed - invite not found in database')
      throw new Error('Invite creation verification failed')
    }

    // Send custom invite email with null check for inviter email
    await sendInviteEmail({
      to: email,
      orgName: org.name,
      inviteUrl: `${process.env.NEXT_PUBLIC_APP_URL}/invite?token=${token}`,
      inviterName: user.email || 'A team member' // Provide fallback
    })

    console.log('Email sent successfully')

    // Track invite creation event
    await handleEvent(request, {
      userId: user.id,
      type: 'invite_created',
      data: {
        orgId: org.id,
        email,
        role
      }
    } satisfies EventPayload<'invite_created'>)

    console.log('New invite details:', {
      id: invite?.id,
      email: invite?.email,
      accepted_at: invite?.accepted_at,  // Should be null
      expires_at: invite?.expires_at,
      created_at: invite?.created_at
    });

    return NextResponse.json({ data: invite, error: null })
  } catch (error) {
    console.error('Error creating invite:', error)
    return NextResponse.json(
      { data: null, error: INVITE_ERRORS.FAILED },
      { status: INVITE_ERRORS.FAILED.status }
    )
  }
} 
