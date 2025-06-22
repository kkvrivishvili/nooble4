"use client"

import * as React from "react"
import * as TooltipPrimitive from "@radix-ui/react-tooltip"
import { cn } from "@/utils/cn"

const TooltipProvider = TooltipPrimitive.Provider
const TooltipTrigger = TooltipPrimitive.Trigger

interface TooltipContentProps 
  extends React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Content> {
  variant?: 'primary' | 'destructive' | 'warning'
  size?: 'sm' | 'md' | 'lg'
  theme?: 'default' | 'ios' | 'minimal'
}

const TooltipContent = React.forwardRef<
  React.ElementRef<typeof TooltipPrimitive.Content>,
  TooltipContentProps
>(({ className, variant = 'primary', size = 'md', theme, sideOffset = 4, ...props }, ref) => (
  <TooltipPrimitive.Content
    ref={ref}
    sideOffset={sideOffset}
    data-tooltip-variant={variant}
    data-tooltip-size={size}
    data-theme={theme}
    className={cn(
      // Only structural styles here
      "z-50 overflow-hidden",
      "animate-in fade-in-0 zoom-in-95",
      "data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95",
      "data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2",
      "data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2",
      className
    )}
    {...props}
  />
))
TooltipContent.displayName = TooltipPrimitive.Content.displayName

const Tooltip = ({ children }: { children: React.ReactNode }) => (
  <TooltipPrimitive.Root>
    {children}
  </TooltipPrimitive.Root>
)

export { 
  Tooltip, 
  TooltipTrigger, 
  TooltipContent,
  TooltipProvider
} 