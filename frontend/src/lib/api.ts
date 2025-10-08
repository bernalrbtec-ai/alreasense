import axios from 'axios'

const API_BASE_URL = (import.meta as any).env.VITE_API_BASE_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL: `${API_BASE_URL}/api`,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor
api.interceptors.request.use(
  (config) => {
    console.log('🔍 API Request:', config.method?.toUpperCase(), config.url, config.data)
    return config
  },
  (error) => {
    console.error('❌ Request interceptor error:', error)
    return Promise.reject(error)
  }
)

// Response interceptor
api.interceptors.response.use(
  (response) => {
    console.log('✅ API Response:', response.status, response.config.url, response.data)
    return response
  },
  (error) => {
    console.error('❌ API Error:', error.config?.method?.toUpperCase(), error.config?.url, error.response?.status, error.response?.data)
    if (error.response?.status === 401) {
      // Token expired or invalid - we'll handle this in the auth store
      console.log('401 Unauthorized - token expired')
    }
    return Promise.reject(error)
  }
)
