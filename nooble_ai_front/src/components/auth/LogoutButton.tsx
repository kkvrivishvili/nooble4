'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/Button'
import { logout } from '@/lib/auth/logout'

export function LogoutButton() {
  const router = useRouter()
  const [isLoading, setIsLoading] = useState(false)

  const handleLogout = async () => {
    try {
      setIsLoading(true)
      const { error } = await logout()

      if (error) {
        console.error('Logout error:', error)
        return
      }

      // Redirect to login page after logout
      router.push('/auth/login')
    } catch (error) {
      console.error('Logout failed:', error)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <Button 
      onClick={handleLogout}
      variant="ghost"
      size="sm"
      isLoading={isLoading}
      className="text-muted-foreground hover:text-foreground"
    >
      Logout
    </Button>
  )
}
