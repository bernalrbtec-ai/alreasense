import axios from 'axios'

const API_BASE_URL = (import.meta as any).env.VITE_API_BASE_URL || 'http://localhost:8000'
const isDevelopment = (import.meta as any).env.DEV

// Logger helper - só loga em desenvolvimento
const log = {
  info: (...args: any[]) => {
    if (isDevelopment) console.log(...args)
  },
  error: (...args: any[]) => {
    if (isDevelopment) console.error(...args)
  }
}

export const api = axios.create({
  baseURL: `${API_BASE_URL}/api`,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor
api.interceptors.request.use(
  (config) => {
    log.info('🔍 API Request:', config.method?.toUpperCase(), config.url, config.data)
    return config
  },
  (error) => {
    log.error('❌ Request interceptor error:', error)
    return Promise.reject(error)
  }
)

// Response interceptor
api.interceptors.response.use(
  (response) => {
    log.info('✅ API Response:', response.status, response.config.url, response.data)
    return response
  },
  (error) => {
    log.error('❌ API Error:', error.config?.method?.toUpperCase(), error.config?.url, error.response?.status, error.response?.data)
    if (error.response?.status === 401) {
      // Token expired or invalid - redirect to login
      log.info('401 Unauthorized - token expired, redirecting to login')
      delete api.defaults.headers.common['Authorization']
      
      // Clear localStorage
      localStorage.removeItem('auth-storage')
      
      // Redirect to login if not already there
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)
