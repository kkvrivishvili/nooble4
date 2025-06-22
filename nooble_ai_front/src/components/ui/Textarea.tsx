import { TextareaHTMLAttributes, forwardRef } from 'react'
import { cn } from '@/utils/cn'

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  error?: string
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, error, ...props }, ref) => {
    return (
      <div className="relative">
        <textarea
          ref={ref}
          className={cn(
            'flex min-h-[80px] w-full',
            'rounded-[var(--textarea-radius)] border border-input',
            'bg-background px-3 py-2 text-sm',
            'ring-offset-background',
            'placeholder:text-muted-foreground/60',
            'focus-visible:outline-none focus-visible:ring-2',
            'focus-visible:ring-ring focus-visible:ring-offset-2',
            'disabled:cursor-not-allowed disabled:opacity-50',
            error && 'border-destructive focus-visible:ring-destructive',
            className
          )}
          {...props}
        />
        {error && (
          <span className="mt-1 text-xs text-destructive">{error}</span>
        )}
      </div>
    )
  }
)

Textarea.displayName = 'Textarea' 