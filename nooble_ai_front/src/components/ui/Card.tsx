import { HTMLAttributes, forwardRef } from 'react'
import { cn } from '@/utils/cn'

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'bordered'
}

export const Card = forwardRef<HTMLDivElement, CardProps>(
  ({ className, variant = 'default', children, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          'rounded-[var(--card-radius)] shadow-[var(--card-shadow)]',
          'bg-card text-card-foreground',
          {
            'border border-border': variant === 'bordered',
            'border border-border/50 backdrop-blur-[var(--card-blur)]': variant === 'default',
          },
          className
        )}
        {...props}
      >
        {children}
      </div>
    )
  }
)

Card.displayName = 'Card'

// Card subcomponents for better organization
export const CardHeader = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div 
      ref={ref} 
      className={cn(
        'flex flex-col space-y-1.5 p-6',
        'border-b border-border/10',
        className
      )} 
      {...props} 
    />
  )
)
CardHeader.displayName = 'CardHeader'

export const CardTitle = forwardRef<HTMLParagraphElement, HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => (
    <h3 
      ref={ref} 
      className={cn(
        'text-xl font-semibold leading-none tracking-tight',
        'text-card-foreground',
        className
      )} 
      {...props} 
    />
  )
)
CardTitle.displayName = 'CardTitle'

export const CardDescription = forwardRef<HTMLParagraphElement, HTMLAttributes<HTMLParagraphElement>>(
  ({ className, ...props }, ref) => (
    <p 
      ref={ref} 
      className={cn(
        'text-sm',
        'text-muted-foreground/75',
        className
      )} 
      {...props} 
    />
  )
)
CardDescription.displayName = 'CardDescription'

export const CardContent = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div 
      ref={ref} 
      className={cn(
        'p-6 pt-0',
        className
      )} 
      {...props} 
    />
  )
)
CardContent.displayName = 'CardContent'