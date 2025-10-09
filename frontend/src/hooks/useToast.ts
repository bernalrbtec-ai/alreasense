import { useState, useCallback } from 'react'

interface ToastState {
  show: boolean
  message: string
  type: 'success' | 'error' | 'warning' | 'info'
}

export function useToast() {
  const [toast, setToast] = useState<ToastState>({
    show: false,
    message: '',
    type: 'success'
  })

  const showToast = useCallback((message: string, type: 'success' | 'error' | 'warning' | 'info' = 'success') => {
    setToast({
      show: true,
      message,
      type
    })
  }, [])

  const hideToast = useCallback(() => {
    setToast(prev => ({ ...prev, show: false }))
  }, [])

  return {
    toast,
    showToast,
    hideToast
  }
}
