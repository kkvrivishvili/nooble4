'use client'

import { Button } from '@/components/ui/Button'

export function BillingSettings() {
  return (
    <div className="space-y-4">
      <div className="rounded-md bg-muted p-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="font-medium text-foreground">Current Plan: Free</p>
            <p className="text-sm text-muted-foreground">
              You are currently on the free plan
            </p>
          </div>
          <Button 
            variant="outline"
            size="md"
          >
            Upgrade
          </Button>
        </div>
      </div>

      <div className="space-y-4">
        <h4 className="text-sm font-medium text-foreground">Billing History</h4>
        <div className="text-sm text-muted-foreground">
          No billing history available.
        </div>
      </div>
    </div>
  )
} 