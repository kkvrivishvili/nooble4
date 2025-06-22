'use client'

import { useState, useEffect } from 'react'
import { getSupabaseBrowserClient } from '@/lib/auth/config'
import type { Organization, OrgMember, OrgRole } from './orgTypes'
import type { AuthChangeEvent } from '@supabase/supabase-js'

export function useOrganization(orgId?: string) {
  const [organization, setOrganization] = useState<Organization | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  useEffect(() => {
    let isMounted = true
    const supabase = getSupabaseBrowserClient()

    async function fetchOrg() {
      try {
        if (!orgId) {
          setIsLoading(false)
          return
        }

        const { data, error } = await supabase
          .from('organizations')
          .select('*')
          .eq('id', orgId)
          .single()

        if (error) throw error

        if (isMounted) {
          setOrganization(data)
          setError(null)
        }
      } catch (error) {
        console.error('Error fetching organization:', error)
        if (isMounted) {
          setError(error as Error)
          setOrganization(null)
        }
      } finally {
        if (isMounted) {
          setIsLoading(false)
        }
      }
    }

    fetchOrg()

    return () => {
      isMounted = false
    }
  }, [orgId])

  return { organization, isLoading, error }
}

export function useOrgRole(orgId?: string) {
  const [role, setRole] = useState<OrgRole | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  useEffect(() => {
    let isMounted = true
    const supabase = getSupabaseBrowserClient()

    async function fetchRole() {
      try {
        const { data: { user } } = await supabase.auth.getUser()
        
        if (!user || !orgId || !isMounted) {
          setIsLoading(false)
          return
        }
        
        const { data, error } = await supabase
          .from('organization_members')
          .select('role')
          .eq('org_id', orgId)
          .eq('user_id', user.id)
          .single()
        
        if (error) throw error

        if (isMounted) {
          setRole(data?.role || null)
          setError(null)
        }
      } catch (error) {
        console.error('Error fetching org role:', error)
        if (isMounted) {
          setError(error as Error)
          setRole(null)
        }
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
        setRole(null)
      }
    })

    return () => {
      isMounted = false
      subscription.unsubscribe()
    }
  }, [orgId])

  return { role, isLoading, error }
}

export function useOrgMembers(orgId?: string) {
  const [members, setMembers] = useState<OrgMember[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  useEffect(() => {
    let isMounted = true
    const supabase = getSupabaseBrowserClient()

    async function fetchMembers() {
      try {
        if (!orgId) {
          setIsLoading(false)
          return
        }

        const { data, error } = await supabase
          .from('organization_members')
          .select('*')
          .eq('org_id', orgId)

        if (error) throw error

        if (isMounted) {
          setMembers(data)
          setError(null)
        }
      } catch (error) {
        console.error('Error fetching org members:', error)
        if (isMounted) {
          setError(error as Error)
          setMembers([])
        }
      } finally {
        if (isMounted) {
          setIsLoading(false)
        }
      }
    }

    fetchMembers()

    // Set up realtime subscription for member updates
    const subscription = supabase
      .channel(`org-members-${orgId}`)
      .on('postgres_changes', {
        event: '*',
        schema: 'public',
        table: 'organization_members',
        filter: `org_id=eq.${orgId}`
      }, () => {
        fetchMembers()
      })
      .subscribe()

    return () => {
      isMounted = false
      subscription.unsubscribe()
    }
  }, [orgId])

  return { members, isLoading, error }
} 