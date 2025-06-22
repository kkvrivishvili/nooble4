import formData from 'form-data'
import Mailgun from 'mailgun.js'
import type { TemplateVars } from './emailTypes'

// Initialize Mailgun
const mailgun = new Mailgun(formData)
const mg = mailgun.client({
  username: 'api',
  key: process.env.MAILGUN_API_KEY!
})

// Use full sandbox domain
const DOMAIN = process.env.NODE_ENV === 'development'
  ? 'sandboxe5dd7139d72c454aaef628f26e752b84.mailgun.org'  // Your sandbox domain
  : process.env.MAILGUN_DOMAIN!

const FROM_EMAIL = process.env.MAILGUN_FROM_EMAIL!
const FROM_NAME = process.env.MAILGUN_FROM_NAME!

const APP_URL = process.env.NODE_ENV === 'development'
  ? 'http://localhost:3000'
  : 'https://nextjs-supabase-boilerplate.vercel.app' // Update this to your new domain

interface SendInviteEmailParams {
  to: string
  orgName: string
  inviteUrl: string
  inviterName: string
}

const AUTHORIZED_TEST_EMAILS = [
  // Add your verified emails here
  'marcruud3@gmail.com',
  'solvifydigital.work@gmail.com',
  'marcruud@gmail.com'
]

export async function sendInviteEmail({
  to,
  orgName,
  inviteUrl,
  inviterName
}: SendInviteEmailParams) {
  // In development, only send to authorized emails
  if (process.env.NODE_ENV === 'development') {
    console.log('Checking authorized email:', to)
    console.log('Authorized emails:', AUTHORIZED_TEST_EMAILS)

    if (!AUTHORIZED_TEST_EMAILS.includes(to)) {
      console.log('Development Mode - Unauthorized email, would send:', {
        to,
        from: `${FROM_NAME} <${FROM_EMAIL}>`,
        subject: `Join ${orgName} on Boilerplate`,
        inviteUrl,
        inviterName
      })
      return
    }
    console.log('Email authorized, proceeding with send')
  }

  try {
    console.log('Attempting to send email via Mailgun:', {
      domain: DOMAIN,
      from: `${FROM_NAME} <${FROM_EMAIL}>`,
      to: to
    })

    const templateVars = {
      org_name: orgName,
      inviter_name: inviterName,
      invite_url: inviteUrl.replace('http://localhost:3000/invite?token=', ''),
      expires_in: '48 hours'
    } satisfies TemplateVars['org-invite']

    console.log('Sending email with variables:', templateVars)

    await mg.messages.create(DOMAIN, {
      from: `${FROM_NAME} <${FROM_EMAIL}>`,
      to: [to],
      subject: `Join ${orgName} on Boilerplate`,
      template: "org-invite",
      'h:X-Mailgun-Variables': JSON.stringify(templateVars)
    })

    console.log('Email sent successfully')
  } catch (error) {
    console.error('Failed to send invite email:', error)
    // Log the full error object for debugging
    console.error('Full error details:', JSON.stringify(error, null, 2))
  }
}

// Add more email functions as needed
export async function sendWelcomeEmail() {
  // ...
}

export async function sendPasswordResetEmail() {
  // ...
} 