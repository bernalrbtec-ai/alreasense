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
        console.log('🔐 [AUTH] Iniciando login e limpeza de cache anterior...')
        
        // Limpar caches antes do login para garantir que não há dados de usuário anterior
        try {
          // Limpar chat store
          const { useChatStore } = await import('../modules/chat/store/chatStore')
          useChatStore.getState().reset()
          console.log('✅ [AUTH] Chat store limpo antes do login')
        } catch (error) {
          console.error('❌ [AUTH] Erro ao limpar chat store antes do login:', error)
        }
        
        // Desconectar WebSocket anterior se existir
        try {
          const { chatWebSocketManager } = await import('../modules/chat/services/ChatWebSocketManager')
          if (chatWebSocketManager && typeof chatWebSocketManager.disconnect === 'function') {
            chatWebSocketManager.disconnect()
            console.log('✅ [AUTH] WebSocket anterior desconectado')
          }
        } catch (error) {
          // Não é crítico se não conseguir desconectar - apenas log
          console.warn('⚠️ [AUTH] Não foi possível desconectar WebSocket anterior (não crítico):', error)
        }
        
        // Limpar localStorage de caches relacionados ao chat
        try {
          const keysToRemove: string[] = []
          for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i)
            if (key && (key.includes('chat') || key.includes('conversation') || key.includes('quick_replies'))) {
              keysToRemove.push(key)
            }
          }
          keysToRemove.forEach(key => localStorage.removeItem(key))
          if (keysToRemove.length > 0) {
            console.log('✅ [AUTH] Caches de chat limpos do localStorage:', keysToRemove)
          }
        } catch (error) {
          console.error('❌ [AUTH] Erro ao limpar localStorage de chat:', error)
        }
        
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
          
          console.log('✅ [AUTH] Login realizado com sucesso')
        } catch (error) {
          set({ isLoading: false })
          throw error
        }
      },

      logout: () => {
        console.log('🔐 [AUTH] Iniciando logout e limpeza de cache...')
        
        // 1. Limpar token da API
        delete api.defaults.headers.common['Authorization']
        
        // 2. Limpar estado do auth store
        set({ user: null, token: null })
        
        // 3. Limpar localStorage (auth-storage e outros possíveis caches)
        try {
          localStorage.removeItem('auth-storage')
          // Limpar outros possíveis caches relacionados
          const keysToRemove: string[] = []
          for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i)
            if (key && (key.includes('auth') || key.includes('chat') || key.includes('conversation') || key.includes('quick_replies'))) {
              keysToRemove.push(key)
            }
          }
          keysToRemove.forEach(key => localStorage.removeItem(key))
          console.log('✅ [AUTH] localStorage limpo:', keysToRemove)
        } catch (error) {
          console.error('❌ [AUTH] Erro ao limpar localStorage:', error)
        }
        
        // 4. Limpar sessionStorage
        try {
          sessionStorage.clear()
          console.log('✅ [AUTH] sessionStorage limpo')
        } catch (error) {
          console.error('❌ [AUTH] Erro ao limpar sessionStorage:', error)
        }
        
        // 5. Limpar chat store (conversas, mensagens, etc)
        try {
          import('../modules/chat/store/chatStore').then(({ useChatStore }) => {
            useChatStore.getState().reset()
            console.log('✅ [AUTH] Chat store resetado')
          }).catch((error) => {
            console.error('❌ [AUTH] Erro ao resetar chat store:', error)
          })
        } catch (error) {
          console.error('❌ [AUTH] Erro ao importar chat store:', error)
        }
        
        // 6. Desconectar WebSocket
        try {
          import('../modules/chat/services/ChatWebSocketManager').then(({ ChatWebSocketManager }) => {
            ChatWebSocketManager.getInstance().disconnect()
            console.log('✅ [AUTH] WebSocket desconectado')
          }).catch((error) => {
            console.error('❌ [AUTH] Erro ao desconectar WebSocket:', error)
          })
        } catch (error) {
          console.error('❌ [AUTH] Erro ao importar WebSocket manager:', error)
        }
        
        console.log('✅ [AUTH] Logout completo - todos os caches foram limpos')
      },

      checkAuth: async () => {
        const { token, user } = get()
        
        // ✅ FIX: Se não tem token, limpar estado e retornar
        if (!token) {
          // Se tinha user mas não tem token, limpar tudo (token expirou ou foi removido)
          if (user) {
            set({ user: null, token: null, isLoading: false })
            delete api.defaults.headers.common['Authorization']
          } else {
            set({ isLoading: false })
          }
          return
        }

        // ✅ FIX: Sempre configurar token no axios antes de verificar
        // Isso garante que mesmo após F5, o token está configurado
        api.defaults.headers.common['Authorization'] = `Bearer ${token}`

        // ✅ FIX: Se já tem user, ainda assim verificar se token é válido
        // Mas não mostrar loading se já tem user (melhor UX)
        const wasLoading = get().isLoading
        if (!wasLoading) {
          set({ isLoading: true })
        }

        try {
          // ✅ FIX: Adicionar timeout para evitar travamento
          const controller = new AbortController()
          const timeoutId = setTimeout(() => controller.abort(), 10000) // 10 segundos
          
          const response = await api.get('/auth/me/', {
            signal: controller.signal
          })
          
          clearTimeout(timeoutId)
          
          // ✅ FIX: Sempre atualizar user (pode ter mudado no backend)
          set({ user: response.data, isLoading: false })
          console.log('✅ [AUTH] Token válido, usuário autenticado')
        } catch (error: any) {
          // ✅ FIX: Verificar se foi abortado ou erro de rede
          if (error.name === 'AbortError' || error.code === 'ECONNABORTED') {
            console.error('❌ [AUTH] Auth check timeout:', error)
            set({ isLoading: false })
            return
          }
          
          // ✅ FIX: Se erro 401, token inválido - limpar tudo
          if (error.response?.status === 401) {
            console.error('❌ [AUTH] Token inválido ou expirado:', error)
            delete api.defaults.headers.common['Authorization']
            set({ user: null, token: null, isLoading: false })
            
            // Redirect to login if not already there
            if (window.location.pathname !== '/login') {
              window.location.href = '/login'
            }
          } else {
            // ✅ FIX: Outros erros (rede, etc) - manter estado atual mas parar loading
            console.error('❌ [AUTH] Erro ao verificar autenticação:', error)
            set({ isLoading: false })
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
