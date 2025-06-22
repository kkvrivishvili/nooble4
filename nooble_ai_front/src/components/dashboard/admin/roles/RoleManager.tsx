'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { RoleGate } from '@/components/rbac/RoleGate'
import { getSupabaseBrowserClient } from '@/lib/auth/config'
import { toast } from 'sonner'
import type { UserRole } from '@/lib/rbac/rbacTypes'
import type { Tables } from '@/types/api'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from '@/components/ui/AlertDialog'

interface UserWithRole {
  id: string
  email: string
  role: UserRole
  created_at: string
}

interface Profile {
  id: string
  full_name: string | null
  updated_at: string | null
}

export function RoleManager() {
  const [users, setUsers] = useState<UserWithRole[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [selectedRole, setSelectedRole] = useState<{ userId: string, role: UserRole } | null>(null)

  useEffect(() => {
    fetchUsers()
  }, [])

  const fetchUsers = async () => {
    try {
      const supabase = getSupabaseBrowserClient()
      const { data: profiles, error: profilesError } = await supabase
        .from('profiles')
        .select(`
          id,
          full_name,
          updated_at
        `)
        .order('updated_at', { ascending: false })

      if (profilesError) throw profilesError

      const { data: roles, error: rolesError } = await supabase
        .from('roles')
        .select('user_id, role')

      if (rolesError) throw rolesError

      const transformedData = profiles?.map((profile: Profile) => ({
        id: profile.id,
        email: profile.full_name || 'Unknown',
        created_at: profile.updated_at || new Date().toISOString(),
        role: (roles as Tables['roles']['Row'][])?.find((r) => r.user_id === profile.id)?.role || 'user'
      })) || []
      
      setUsers(transformedData)
    } catch (error) {
      console.error('Failed to fetch users:', error)
      toast.error('Failed to load users')
    } finally {
      setIsLoading(false)
    }
  }

  const handleRoleChange = async (userId: string, newRole: UserRole) => {
    try {
      const supabase = getSupabaseBrowserClient()
      const { error } = await supabase
        .from('roles')
        .update({ 
          role: newRole,
          updated_at: new Date().toISOString()
        })
        .eq('user_id', userId)

      if (error) throw error
      
      setUsers(users.map(user => 
        user.id === userId ? { ...user, role: newRole } : user
      ))
      toast.success("User's role updated successfully")
    } catch (error) {
      console.error('Failed to update role:', error)
      toast.error('Failed to update role')
    }
  }

  if (isLoading) {
    return (
      <Card>
        <CardContent className="p-6">
          <div className="flex items-center justify-center text-muted-foreground">
            Loading users...
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-foreground">User Role Management</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {users.map(user => (
            <div key={user.id} className="flex items-center justify-between p-4 border border-border rounded-lg bg-background">
              <div>
                <p className="font-medium text-foreground">{user.email}</p>
                <p className="text-sm text-muted-foreground">
                  Joined {new Date(user.created_at).toLocaleDateString()}
                </p>
              </div>
              <RoleGate allowedRoles={['super_admin']}>
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button 
                      variant="outline"
                      className="w-[140px]"
                      isLoading={isLoading}
                      size="sm"
                    >
                      {user.role}
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent variant="primary">
                    <AlertDialogHeader>
                      <AlertDialogTitle>Change User Role</AlertDialogTitle>
                      <AlertDialogDescription>
                        Are you sure you want to change this user&apos;s role? This action cannot be undone.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <div className="grid grid-cols-3 gap-2 py-4">
                      {(['user', 'admin', 'super_admin'] as const).map((role) => (
                        <Button
                          key={role}
                          variant={selectedRole?.role === role ? 'primary' : 'outline'}
                          className="w-full"
                          onClick={() => setSelectedRole({ userId: user.id, role })}
                        >
                          {role}
                        </Button>
                      ))}
                    </div>
                    <AlertDialogFooter>
                      <AlertDialogCancel asChild>
                        <Button variant="outline">
                          Cancel
                        </Button>
                      </AlertDialogCancel>
                      <AlertDialogAction asChild>
                        <Button 
                          variant="primary"
                          onClick={() => {
                            if (selectedRole) {
                              handleRoleChange(selectedRole.userId, selectedRole.role)
                            }
                          }}
                        >
                          Continue
                        </Button>
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </RoleGate>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
