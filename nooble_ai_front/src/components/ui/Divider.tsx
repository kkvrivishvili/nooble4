import { cn } from '@/utils/cn'

interface DividerProps {
  children?: React.ReactNode
  className?: string
  variant?: 'default' | 'muted'
}

export function Divider({ children, className, variant = 'default' }: DividerProps) {
  return (
    <div className={cn("relative", className)}>
      <div className="absolute inset-0 flex items-center">
        <span className={cn(
          "w-full border-t transition-colors",
          variant === 'default' ? 'border-border' : 'border-border/50'
        )} />
      </div>
      {children && (
        <div className="relative flex justify-center text-xs uppercase">
          <span className={cn(
            "bg-background px-2",
            "text-muted-foreground/75",
            "transition-colors"
          )}>
            {children}
          </span>
        </div>
      )}
    </div>
  )
} 