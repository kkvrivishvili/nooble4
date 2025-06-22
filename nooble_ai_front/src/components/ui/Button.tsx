import { ButtonHTMLAttributes, forwardRef } from 'react'
import { Slot } from "@radix-ui/react-slot"
import { Loader2 } from "lucide-react"
import { cn } from '@/utils/cn'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'destructive' | 'glass'
  size?: 'sm' | 'md' | 'lg'
  isLoading?: boolean
  asChild?: boolean
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'primary', size = 'md', isLoading, asChild = false, children, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    
    return (
      <Comp
        ref={ref}
        data-button-variant={variant}
        className={cn(
          // Base styles
          'inline-flex items-center justify-center font-medium transition-all',
          'rounded-[var(--button-radius)] shadow-[var(--button-shadow)]',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2',
          'disabled:pointer-events-none disabled:opacity-50',
          
          // Size variations
          size === 'sm' && 'h-8 px-3 text-sm',
          size === 'md' && 'h-10 px-4 py-2',
          size === 'lg' && 'h-11 px-8',
          
          className
        )}
        {...props}
      >
        {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
        {children}
      </Comp>
    )
  }
)

Button.displayName = 'Button'
