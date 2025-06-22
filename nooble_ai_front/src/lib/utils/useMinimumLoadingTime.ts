import { useState, useEffect } from 'react'

interface UseMinimumLoadingTimeOptions {
  minimumLoadingTime?: number // in milliseconds
  initialLoadingState?: boolean
}

export function useMinimumLoadingTime({
  minimumLoadingTime = 2200,
  initialLoadingState = true
}: UseMinimumLoadingTimeOptions = {}) {
  const [isLoading, setIsLoading] = useState(initialLoadingState)
  const [shouldEndLoading, setShouldEndLoading] = useState(false)

  useEffect(() => {
    let minLoadingTimeout: NodeJS.Timeout

    if (shouldEndLoading) {
      minLoadingTimeout = setTimeout(() => {
        setIsLoading(false)
      }, minimumLoadingTime)
    }

    return () => {
      clearTimeout(minLoadingTimeout)
    }
  }, [shouldEndLoading, minimumLoadingTime])

  const endLoading = () => {
    setShouldEndLoading(true)
  }

  return {
    isLoading,
    endLoading
  }
} 