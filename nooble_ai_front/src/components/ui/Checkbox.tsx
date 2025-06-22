"use client"

import { InputHTMLAttributes, forwardRef, ReactNode } from 'react'
import { cn } from '@/utils/cn'

export interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type' | 'size'> {
  error?: string
  label?: ReactNode
  variant?: 'primary' | 'filled' | 'ghost'
  size?: 'sm' | 'md' | 'lg'
}

export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(
  ({ className, error, label, variant = 'primary', size = 'md', ...props }, ref) => {
    return (
      <div className="relative flex items-start">
        <div className="flex items-center">
          <input
            type="checkbox"
            ref={ref}
            data-checkbox-variant={variant}
            data-checkbox-size={size}
            className={cn(
              // Base styles
              "appearance-none",
              "inline-flex items-center justify-center",
              "transition-all",
              
              // Size variations
              size === 'sm' && "h-4 w-4",
              size === 'md' && "h-5 w-5",
              size === 'lg' && "h-6 w-6",
              
              // Checked state styling
              "checked:bg-[var(--checkbox-checked-bg)]",
              "checked:border-[var(--checkbox-checked-border)]",
              "checked:text-[var(--checkbox-checked-fg)]",
              
              // Focus and states
              "focus-visible:outline-none focus-visible:ring-2",
              "focus-visible:ring-[var(--checkbox-ring)]",
              "focus-visible:ring-offset-2",
              "disabled:cursor-not-allowed disabled:opacity-50",
              error && "border-destructive focus-visible:ring-destructive",
              
              // After element for checkmark
              "after:block after:opacity-0",
              "after:h-[50%] after:w-[50%]",
              "after:rotate-45 after:border-r-2 after:border-b-2",
              "after:border-current",
              "checked:after:opacity-100",
              
              className
            )}
            {...props}
          />
        </div>
        {label && (
          <div className="ml-3 text-sm leading-none">
            <label 
              htmlFor={props.id} 
              className={cn(
                "font-medium text-foreground",
                "select-none",
                props.disabled && "opacity-50 cursor-not-allowed"
              )}
            >
              {label}
            </label>
          </div>
        )}
        {error && (
          <span className="absolute left-0 top-full mt-1 text-xs text-destructive">
            {error}
          </span>
        )}
      </div>
    )
  }
)

Checkbox.displayName = 'Checkbox' 