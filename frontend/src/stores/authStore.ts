import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { api } from '../lib/api'

interface User {
  id: number
  username: string
  email: string
  first_name: string
  last_name: string
  display_name?: string
  phone?: string
  birth_date?: string
  notify_email?: boolean
  notify_whatsapp?: boolean
  role: 'admin' | 'gerente' | 'agente'
  is_superuser?: boolean
  is_staff?: boolean
  is_admin?: boolean
  is_gerente?: boolean
  is_agente?: boolean
  avatar?: string
  // Novos campos retornados pelo backend (formato simplificado)
  tenant_id?: string
  tenant_name?: string
  department_ids?: string[]
  department_names?: string[]
  permissions?: {
    can_access_all_departments: boolean
    can_view_metrics: boolean
    can_access_chat: boolean
    can_manage_users: boolean
    can_manage_departments: boolean
    can_manage_campaigns: boolean
    can_view_all_contacts: boolean
  }
  // Campo legado (ainda pode ser retornado em alguns endpoints)
  tenant?: {
    id: string
    name: string
    plan?: string
    status?: string
  }
}

interface AuthState {
  user: User | null
  token: string | null
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  checkAuth: () => Promise<void>
  setUser: (user: any) => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      isLoading: false,

      login: async (email: string, password: string) => {
        set({ isLoading: true })
        try {
          const response = await api.post('/auth/login/', {
            email,
            password,
          })
          
          const { access, refresh } = response.data
          
          // Set token in API client
          api.defaults.headers.common['Authorization'] = `Bearer ${access}`
          
          // Get user info
          const userResponse = await api.get('/auth/me/')
          
          set({
            user: userResponse.data,
            token: access,
            isLoading: false,
          })
        } catch (error) {
          set({ isLoading: false })
          throw error
        }
      },

      logout: () => {
        delete api.defaults.headers.common['Authorization']
        set({ user: null, token: null })
      },

      checkAuth: async () => {
        const { token, user } = get()
        
        // If already have user, skip check
        if (user) {
          set({ isLoading: false })
          return
        }
        
        if (!token) {
          set({ isLoading: false })
          return
        }

        set({ isLoading: true })
        try {
          api.defaults.headers.common['Authorization'] = `Bearer ${token}`
          const response = await api.get('/auth/me/')
          set({ user: response.data, isLoading: false })
        } catch (error: any) {
          // Token is invalid, clear auth state
          console.error('Auth check failed:', error)
          delete api.defaults.headers.common['Authorization']
          set({ user: null, token: null, isLoading: false })
          
          // Redirect to login if not already there
          if (window.location.pathname !== '/login') {
            window.location.href = '/login'
          }
        }
      },

      setUser: (user: any) => {
        set({ user })
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({ 
        token: state.token,
        user: state.user 
      }),
    }
  )
)
