import type { Json } from './supabase'

// Core system metrics types that might be used across features
export interface BaseMetrics {
  timestamp: string
  metadata?: Json
}

export interface SystemStatus {
  status: 'healthy' | 'warning' | 'error' | 'unknown'
  lastChecked: string
  metadata?: Json
}
