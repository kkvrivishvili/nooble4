import { useState, useEffect } from 'react'
import { getSupabaseBrowserClient } from '@/lib/auth/config'
import type { Profile } from '@/lib/auth/authTypes'

export function useProfile() {
  const [profile, setProfile] = useState<Profile | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const supabase = getSupabaseBrowserClient()

    async function fetchProfile() {
      try {
        const { data: { user }, error: userError } = await supabase.auth.getUser()
        
        if (userError || !user) {
          setProfile(null)
          return
        }

        const { data, error } = await supabase
          .from('profiles')
          .select()
          .eq('id', user.id)
          .single()
        
        if (!error) {
          setProfile(data)
        }
      } catch (error) {
        console.error('Profile fetch error:', error)
        setProfile(null)
      } finally {
        setIsLoading(false)
      }
    }

    fetchProfile()

    const profileSubscription = supabase
      .channel('profile-changes')
      .on('postgres_changes', 
        { 
          event: '*', 
          schema: 'public', 
          table: 'profiles' 
        }, 
        fetchProfile
      )
      .subscribe()

    return () => {
      profileSubscription.unsubscribe()
    }
  }, [])

  return { profile, isLoading }
} 