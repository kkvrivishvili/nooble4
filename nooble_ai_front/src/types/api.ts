import type { Database } from './supabase'

export type Tables = Database['public']['Tables']
export type UserRow = Tables['users']['Row']
export type ProfileRow = Tables['profiles']['Row']

export type ApiResponse<T = unknown> = {
  data?: T
  error?: {
    message: string
    code?: string
    status?: number
  }
}

export type ApiErrorResponse = {
  error: {
    message: string
    code: string
    status: number
  }
}

export type ApiHandler<T = unknown> = (
  req: Request,
  params: Record<string, string | string[]>
) => Promise<ApiResponse<T>>

export interface AuthApiResponse extends ApiResponse {
  data?: {
    user: UserRow
    session?: Record<string, unknown>
  }
}
