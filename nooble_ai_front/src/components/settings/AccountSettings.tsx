'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/Button'
import { Card, CardContent } from '@/components/ui/Card'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '@/components/ui/AlertDialog'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/Dialog'
import { SessionsManager } from '@/components/settings/SessionsManager'
import { exportUserData } from '@/lib/auth/data'
import { toast } from 'sonner'
import type { ExportResponse } from '@/lib/auth/authTypes'

export function AccountSettings() {
  const router = useRouter()
  const [isLoading, setIsLoading] = useState(false)
  const [showSessions, setShowSessions] = useState(false)

  const handleDataExport = async (): Promise<void> => {
    setIsLoading(true)
    try {
      const { error }: ExportResponse = await exportUserData()
      if (error) throw error
      toast.success('Your data has been exported')
    } catch (error) {
      console.error('Failed to export data:', error)
      toast.error('Failed to export your data')
    } finally {
      setIsLoading(false)
    }
  }

  const handleAccountDeletion = async (): Promise<void> => {
    setIsLoading(true)
    try {
      const response = await fetch('/api/auth/delete', {
        method: 'DELETE',
        credentials: 'include',
      })

      if (!response.ok) {
        throw new Error('Failed to delete account')
      }

      toast.success('Account successfully deleted')
      router.push('/auth/login')
    } catch (error) {
      console.error('Failed to delete account:', error)
      toast.error('Failed to delete account. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Data Management */}
      <div className="space-y-4">
        <h4 className="text-sm font-medium text-foreground">Data Management</h4>
        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div className="space-y-1">
                <p className="font-medium text-foreground">Export Your Data</p>
                <p className="text-sm text-muted-foreground">
                  Download a copy of your data
                </p>
              </div>
              <Button 
                variant="outline"
                size="md"
                onClick={handleDataExport}
                isLoading={isLoading}
              >
                Export
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Account Status */}
      <div className="space-y-4">
        <h4 className="text-sm font-medium text-foreground">Account Status</h4>
        <Card>
          <CardContent className="p-6">
            <div className="flex justify-between items-center">
              <div>
                <h3 className="text-lg font-medium text-foreground">Active Sessions</h3>
                <p className="text-sm text-muted-foreground">
                  Manage your active sessions
                </p>
              </div>
              <Button 
                variant="outline"
                size="md"
                onClick={() => setShowSessions(true)}
              >
                Manage Sessions
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      <Dialog open={showSessions} onOpenChange={setShowSessions}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="text-foreground">Active Sessions</DialogTitle>
            <DialogDescription className="text-muted-foreground">
              View and manage your active sessions across devices.
            </DialogDescription>
          </DialogHeader>
          <SessionsManager />
        </DialogContent>
      </Dialog>

      {/* Danger Zone */}
      <div className="space-y-4">
        <h4 className="text-sm font-medium text-destructive">Danger Zone</h4>
        <Card className="border-destructive">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div className="space-y-1">
                <p className="font-medium text-foreground">Delete Account</p>
                <p className="text-sm text-muted-foreground">
                  Permanently delete your account and all data
                </p>
              </div>
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button 
                    variant="destructive"
                    size="md"
                    isLoading={isLoading}
                  >
                    Delete Account
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent variant="destructive">
                  <AlertDialogHeader>
                    <AlertDialogTitle className="text-foreground">
                      Are you absolutely sure?
                    </AlertDialogTitle>
                    <AlertDialogDescription className="text-muted-foreground">
                      This action cannot be undone. This will permanently delete your
                      account and remove all of your data from our servers.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel asChild>
                      <Button variant="outline" size="md">
                        Cancel
                      </Button>
                    </AlertDialogCancel>
                    <AlertDialogAction asChild>
                      <Button 
                        variant="destructive"
                        size="md"
                        onClick={handleAccountDeletion}
                        isLoading={isLoading}
                      >
                        Delete Account
                      </Button>
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
} 