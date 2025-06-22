'use client'

import { useEffect, useState } from 'react'
import { ThemeContext, type Theme, type Mode } from './ThemeContext'
import { useMediaQuery } from '@/utils/useMediaQuery'

export function ThemeProvider({ 
  children,
  defaultTheme = 'default',
  defaultMode = 'dark'
}: { 
  children: React.ReactNode
  defaultTheme?: Theme
  defaultMode?: Mode 
}) {
  const [theme, setTheme] = useState<Theme>(defaultTheme)
  const [mode, setMode] = useState<Mode>(defaultMode)
  const prefersDark = useMediaQuery('(prefers-color-scheme: dark)')

  useEffect(() => {
    const root = document.documentElement
    root.setAttribute('data-theme', theme)
    
    const effectiveMode = mode === 'system' 
      ? prefersDark ? 'dark' : 'light'
      : mode
      
    root.classList.toggle('dark', effectiveMode === 'dark')
  }, [theme, mode, prefersDark])

  return (
    <ThemeContext.Provider value={{ theme, mode, setTheme, setMode }}>
      {children}
    </ThemeContext.Provider>
  )
}