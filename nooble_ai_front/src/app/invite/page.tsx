import { getInviteDetails } from '@/lib/orgs/inviteService'
import { redirect } from 'next/navigation'
import { cookies } from 'next/headers'
import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { AlertCircle, Code2 } from 'lucide-react'
import { InviteForm } from '@/components/auth/InviteForm'
import Link from 'next/link'

export default async function InvitePage({
  searchParams,
}: {
  searchParams: { token?: string }
}) {
  const params = await Promise.resolve(searchParams)
  const token = params.token
  
  console.log('Received token from URL:', token)
  
  if (!token) {
    console.log('No token provided, redirecting to error page')
    redirect('/auth/error?error=invalid-invite')
  }

  const cookieStore = await cookies()

  try {
    console.log('Fetching invite details for token:', token)
    const { invite, currentUser } = await getInviteDetails(token, cookieStore)

    console.log('Invite details:', { invite, currentUser })

    // If invite exists, check its status
    if (invite.accepted_at) {
      console.log('Invite already accepted:', invite.accepted_at)
      return renderError('This invite has already been accepted')
    }

    if (new Date(invite.expires_at) < new Date()) {
      console.log('Invite expired:', invite.expires_at)
      return renderError('This invite has expired')
    }

    return (
      <>
        <div className="fixed top-4 left-4">
          <Link href="/" target="_blank" rel="noopener noreferrer">
            <Code2 className="h-8 w-8 text-primary hover:text-primary/80 transition-colors" />
          </Link>
        </div>
        <div className="min-h-screen flex items-center justify-center p-4">
          <div className="w-full max-w-lg">
            <Card>
              <CardContent className="pt-6">
                <InviteForm 
                  invite={{
                    id: invite.id,
                    token: token,
                    org_id: invite.org_id,
                    email: invite.email,
                    role: invite.role,
                    expires_at: invite.expires_at,
                    organizations: invite.organizations,
                    profiles: { full_name: null, avatar_url: null } // We'll load this client-side if needed
                  }}
                  user={currentUser}
                />
              </CardContent>
            </Card>
          </div>
        </div>
      </>
    )
  } catch (error) {
    console.error('Invite error:', error)
    return renderError('This invite appears to be invalid')
  }
}

// Helper function for error rendering
function renderError(message: string) {
  return (
    <>
      <div className="fixed top-4 left-4">
        <Link href="/" target="_blank" rel="noopener noreferrer">
          <Code2 className="h-8 w-8 text-primary hover:text-primary/80 transition-colors" />
        </Link>
      </div>
      <div className="min-h-screen flex items-center justify-center p-4">
        <div className="w-full max-w-lg">
          <Card>
            <CardContent className="pt-6 text-center">
              <div className="mb-4 flex justify-center">
                <AlertCircle className="h-12 w-12 text-destructive" />
              </div>
              <h1 className="text-xl font-semibold mb-4">Invalid Invite</h1>
              <p className="text-muted-foreground mb-6">{message}</p>
              <Link href="/auth/login">
                <Button 
                  variant="primary"
                  size="md"
                  className="min-w-[200px]"
                >
                  Return to Login
                </Button>
              </Link>
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  )
} 

