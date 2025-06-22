'use client'

import { useEffect, useState } from 'react'
import { getSupabaseBrowserClient } from '@/lib/auth/config'
import { ROLE_PERMISSIONS } from './rbacTypes'
import type { UserRole } from './rbacTypes'
import type { AuthChangeEvent } from '@supabase/supabase-js'

export function useRole() {
  const [role, setRole] = useState<UserRole>('user')
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  useEffect(() => {
    let isMounted = true
    const supabase = getSupabaseBrowserClient()

    async function fetchRole() {
      try {
        const { data: { session } } = await supabase.auth.getSession()
        
        if (!session?.user || !isMounted) {
          setIsLoading(false)
          return
        }
        
        const { data, error } = await supabase
          .from('roles')
          .select('role')
          .eq('user_id', session.user.id)
          .maybeSingle()
        
        if (error) {
          console.error('Error fetching role:', error)
          setError(error)
          setRole('user')
          return
        }

        if (isMounted) {
          setRole(data?.role || 'user')
          setError(null)
        }
      } catch (error) {
        console.error('Error in role fetch:', error)
        setError(error as Error)
        setRole('user')
      } finally {
        if (isMounted) {
          setIsLoading(false)
        }
      }
    }

    fetchRole()

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event: AuthChangeEvent) => {
      if (event === 'SIGNED_IN') {
        fetchRole()
      } else if (event === 'SIGNED_OUT') {
        setRole('user')
      }
    })

    return () => {
      isMounted = false
      subscription.unsubscribe()
    }
  }, [])

  return { role, isLoading, error }
}

export function usePermissions() {
  const { role, isLoading } = useRole()
  
  return {
    permissions: role ? ROLE_PERMISSIONS[role] : ROLE_PERMISSIONS.user,
    isLoading
  }
}