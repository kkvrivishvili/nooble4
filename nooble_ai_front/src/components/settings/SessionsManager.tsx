'use client'

import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/Button'
import { toast } from 'sonner'
import type { SessionRow } from '@/lib/auth/authTypes'
import { cn } from '@/utils/cn'

export function SessionsManager() {
  const [sessions, setSessions] = useState<SessionRow[]>([])
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    fetchSessions()
  }, [])

  const fetchSessions = async () => {
    try {
      setIsLoading(true)
      const response = await fetch('/api/auth/sessions', {
        method: 'GET',
        credentials: 'include'
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.error || 'Failed to fetch sessions')
      }

      const result = await response.json()
      
      // Handle both array and object responses
      const sessionsArray = Array.isArray(result.data) 
        ? result.data 
        : result.data?.sessions || []

      setSessions(sessionsArray)
    } catch (error) {
      console.error('Error fetching sessions:', error)
      toast.error('Failed to fetch sessions')
      setSessions([])
    } finally {
      setIsLoading(false)
    }
  }

  const handleRevoke = async (sessionId: string) => {
    try {
      setIsLoading(true)
      const response = await fetch('/api/auth/sessions', {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ sessionId }),
      })

      const { error } = await response.json()
      if (error) {
        throw new Error(error)
      }

      toast.success('Session revoked successfully')
      fetchSessions()
    } catch (error) {
      toast.error('Failed to revoke session')
      console.error('Session revocation error:', error)
    } finally {
      setIsLoading(false)
    }
  }

  if (isLoading && sessions.length === 0) {
    return <div className="py-4 text-center text-muted-foreground">Loading sessions...</div>
  }

  if (!sessions || sessions.length === 0) {
    return <div className="py-4 text-center text-muted-foreground">No active sessions found</div>
  }

  return (
    <div className="space-y-4">
      {Array.isArray(sessions) && sessions.map((session: SessionRow) => {
        if (!session?.id) return null
        
        return (
          <div 
            key={session.id} 
            className={cn(
              "flex justify-between items-center p-4 rounded-lg border border-border bg-card hover:bg-accent/5 transition-colors",
              session.is_current && "border-primary"
            )}
          >
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <p className="font-medium text-foreground">{session.user_agent || 'Unknown Device'}</p>
                {session.is_current && (
                  <span className="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded">
                    Current
                  </span>
                )}
              </div>
              <p className="text-sm text-muted-foreground">
                Last active: {new Date(session.last_active).toLocaleString()}
              </p>
            </div>
            <Button 
              variant="destructive" 
              size="sm"
              onClick={() => handleRevoke(session.id)}
              disabled={isLoading || session.is_current}
              isLoading={isLoading}
            >
              {session.is_current ? 'Current Session' : 'Revoke'}
            </Button>
          </div>
        )
      })}
    </div>
  )
}