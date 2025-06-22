import { NextResponse } from 'next/server'
import { createServerClient } from '@supabase/ssr'
import type { Database } from '@/types/supabase'

export async function POST(request: Request) {
  try {
    const { action, ...data } = await request.json()
    const response = NextResponse.next()
    
    const supabase = createServerClient<Database>(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
      {
        cookies: {
          getAll: () => {
            const cookieString = request.headers.get('cookie') || ''
            return cookieString.split(';')
              .filter(Boolean)
              .map(cookie => {
                const [name, ...rest] = cookie.trim().split('=')
                return {
                  name,
                  value: rest.join('=')
                }
              })
          },
          setAll: (cookieValues) => {
            cookieValues.map(({ name, value, ...options }) => {
              response.cookies.set({ name, value, ...options })
            })
          }
        }
      }
    )

    switch (action) {
      case 'login':
        const { email, password } = data
        const { data: loginData, error: loginError } = await supabase.auth.signInWithPassword({
          email,
          password
        })
        if (loginError) throw loginError
        return NextResponse.json({ status: 'success', data: loginData })

      case 'signup':
        const { email: signupEmail, password: signupPassword } = data
        const { data: signupData, error: signupError } = await supabase.auth.signUp({
          email: signupEmail,
          password: signupPassword
        })
        if (signupError) throw signupError
        return NextResponse.json({ status: 'success', data: signupData })

      default:
        return NextResponse.json(
          { error: 'Invalid action' },
          { status: 400 }
        )
    }
  } catch (err) {
    console.error('Auth error:', err)
    return NextResponse.json(
      { error: err instanceof Error ? err.message : 'Internal server error' },
      { status: 500 }
    )
  }
}