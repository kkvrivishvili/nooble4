"use client"

import { useState, useEffect } from 'react'

export function useMediaQuery(query: string): boolean {
  // Default to false for SSR
  const [matches, setMatches] = useState(false)

  useEffect(() => {
    // Create media query list
    const mediaQuery = window.matchMedia(query)
    
    // Set initial value
    setMatches(mediaQuery.matches)

    // Create event listener function
    const handler = (event: MediaQueryListEvent) => {
      setMatches(event.matches)
    }

    // Add listener
    mediaQuery.addEventListener('change', handler)

    // Cleanup
    return () => {
      mediaQuery.removeEventListener('change', handler)
    }
  }, [query]) // Re-run effect if query changes

  return matches
}