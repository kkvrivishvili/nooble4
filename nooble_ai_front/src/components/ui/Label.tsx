"use client"

import * as React from "react"
import * as LabelPrimitive from "@radix-ui/react-label"
import { cn } from "@/utils/cn"

export interface LabelProps extends React.ComponentPropsWithoutRef<typeof LabelPrimitive.Root> {
  error?: boolean
  variant?: 'primary' | 'secondary' | 'ghost'
  size?: 'sm' | 'md' | 'lg'
  children?: React.ReactNode
}

const Label = React.forwardRef<
  React.ComponentRef<typeof LabelPrimitive.Root>,
  LabelProps
>(({ className, error, variant = 'primary', size = 'md', ...props }, ref) => (
  <LabelPrimitive.Root
    ref={ref}
    data-label-variant={variant}
    data-label-size={size}
    className={cn(
      // Base styles from our CSS variables
      "leading-[var(--label-line-height)]",
      "font-[var(--label-font-weight)]",
      "tracking-[var(--label-letter-spacing)]",
      "mb-[var(--label-margin-bottom)]",
      
      // Size variations
      size === 'sm' && 'text-[var(--label-font-size-sm)]',
      size === 'md' && 'text-[var(--label-font-size)]',
      size === 'lg' && 'text-[var(--label-font-size-lg)]',
      
      // State styles
      "peer-disabled:cursor-not-allowed peer-disabled:opacity-70",
      error && "text-destructive",
      
      className
    )}
    {...props}
  />
))

Label.displayName = LabelPrimitive.Root.displayName

export { Label }