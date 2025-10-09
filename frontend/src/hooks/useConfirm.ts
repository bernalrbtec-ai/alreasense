import { useState, useCallback } from 'react'

interface ConfirmState {
  show: boolean
  title: string
  message: string
  confirmText?: string
  cancelText?: string
  variant?: 'danger' | 'warning' | 'info'
  onConfirm?: () => void
}

export function useConfirm() {
  const [confirm, setConfirm] = useState<ConfirmState>({
    show: false,
    title: '',
    message: '',
    confirmText: 'Confirmar',
    cancelText: 'Cancelar',
    variant: 'danger'
  })

  const showConfirm = useCallback((
    title: string,
    message: string,
    onConfirm: () => void,
    options?: {
      confirmText?: string
      cancelText?: string
      variant?: 'danger' | 'warning' | 'info'
    }
  ) => {
    setConfirm({
      show: true,
      title,
      message,
      onConfirm,
      confirmText: options?.confirmText || 'Confirmar',
      cancelText: options?.cancelText || 'Cancelar',
      variant: options?.variant || 'danger'
    })
  }, [])

  const hideConfirm = useCallback(() => {
    setConfirm(prev => ({ ...prev, show: false }))
  }, [])

  const handleConfirm = useCallback(() => {
    if (confirm.onConfirm) {
      confirm.onConfirm()
    }
    hideConfirm()
  }, [confirm.onConfirm, hideConfirm])

  return {
    confirm,
    showConfirm,
    hideConfirm,
    handleConfirm
  }
}
