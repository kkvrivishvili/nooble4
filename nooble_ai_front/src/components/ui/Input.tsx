"use client"

import { InputHTMLAttributes, forwardRef } from 'react'
import { cn } from '@/utils/cn'

// Omit the native 'size' attribute to avoid type conflicts
export interface InputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'size'> {
  error?: string
  variant?: 'primary' | 'filled' | 'ghost'
  size?: 'sm' | 'md' | 'lg'
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, error, variant = 'primary', size = 'md', ...props }, ref) => {
    return (
      <div className="relative">
        <input
          ref={ref}
          data-input-variant={variant}
          data-input-size={size}
          className={cn(
            // Base styles from CSS variables
            "flex w-full",
            "rounded-[var(--input-radius)]",
            "border border-[var(--input-border)]",
            "bg-[var(--input-bg)]",
            "shadow-[var(--input-shadow)]",
            
            // Size variations
            size === 'sm' && [
              "h-[var(--input-height-sm)]",
              "text-[var(--input-font-size-sm)]",
            ],
            size === 'md' && [
              "h-[var(--input-height)]",
              "text-[var(--input-font-size)]",
            ],
            size === 'lg' && [
              "h-[var(--input-height-lg)]",
              "text-[var(--input-font-size-lg)]",
            ],
            
            // Placeholder
            "placeholder:text-muted-foreground/60",
            
            // Focus styles
            "focus-visible:outline-none focus-visible:ring-2",
            "focus-visible:ring-[var(--input-ring)]",
            "focus-visible:ring-offset-2",
            
            // States
            "disabled:cursor-not-allowed disabled:opacity-50",
            error && "border-destructive focus-visible:ring-destructive",
            
            className
          )}
          style={{
            paddingLeft: 'var(--input-padding-x)',
            paddingRight: 'var(--input-padding-x)',
            paddingTop: 'var(--input-padding-y)',
            paddingBottom: 'var(--input-padding-y)',
          }}
          {...props}
        />
        {error && (
          <span className="mt-1 text-xs text-destructive">{error}</span>
        )}
      </div>
    )
  }
)

Input.displayName = 'Input' 