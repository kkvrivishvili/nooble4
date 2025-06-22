import type { Database } from './supabase'

declare global {
  type DBTables = Database['public']['Tables']
  
  namespace NodeJS {
    interface ProcessEnv {
      NEXT_PUBLIC_SUPABASE_URL: string
      NEXT_PUBLIC_SUPABASE_ANON_KEY: string
      // Add other env variables here
    }
  }
}

export {}
