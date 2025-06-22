'use client'

interface PasswordStrengthIndicatorProps {
  password: string
}

export function PasswordStrengthIndicator({ password }: PasswordStrengthIndicatorProps) {
  const getStrength = (password: string) => {
    let strength = 0
    if (password.length >= 8) strength++
    if (password.match(/[a-z]/)) strength++
    if (password.match(/[A-Z]/)) strength++
    if (password.match(/[0-9]/)) strength++
    if (password.match(/[^a-zA-Z0-9]/)) strength++
    return strength
  }

  const strength = getStrength(password)

  return (
    <div className="space-y-2">
      <div className="flex gap-1">
        {[...Array(5)].map((_, i) => (
          <div
            key={i}
            className={`h-2 flex-1 rounded-full transition-colors ${
              i < strength ? 
                strength <= 2 ? 'bg-destructive' : 
                strength <= 3 ? 'bg-warning' : 
                'bg-success'
              : 'bg-muted'
            }`}
          />
        ))}
      </div>
      <ul className="text-xs space-y-1 text-muted-foreground">
        <li className={password.length >= 8 ? 'text-success' : ''}>
          • At least 8 characters
        </li>
        <li className={password.match(/[a-z]/) ? 'text-success' : ''}>
          • One lowercase letter
        </li>
        <li className={password.match(/[A-Z]/) ? 'text-success' : ''}>
          • One uppercase letter
        </li>
        <li className={password.match(/[0-9]/) ? 'text-success' : ''}>
          • One number
        </li>
        <li className={password.match(/[^a-zA-Z0-9]/) ? 'text-success' : ''}>
          • One special character
        </li>
      </ul>
    </div>
  )
}