import { createContext } from 'react'

export type Theme = 'default' | 'ios' | 'minimal' | 'cyberpunk'
export type Mode = 'light' | 'dark' | 'system'

export interface ThemeContextType {
  theme: Theme
  mode: Mode
  setTheme: (theme: Theme) => void
  setMode: (mode: Mode) => void
}

export const ThemeContext = createContext<ThemeContextType | undefined>(undefined)
ThemeContext.displayName = 'ThemeContext'