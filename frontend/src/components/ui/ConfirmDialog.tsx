import { AlertTriangle, X } from 'lucide-react'
import { Button } from './Button'

interface ConfirmDialogProps {
  show: boolean
  title: string
  message: string
  confirmText?: string
  cancelText?: string
  variant?: 'danger' | 'warning' | 'info'
  confirmLoading?: boolean
  confirmLoadingText?: string
  onConfirm: () => void
  onCancel: () => void
}

export default function ConfirmDialog({
  show,
  title,
  message,
  confirmText = 'Confirmar',
  cancelText = 'Cancelar',
  variant = 'danger',
  confirmLoading = false,
  confirmLoadingText,
  onConfirm,
  onCancel
}: ConfirmDialogProps) {
  if (!show) return null

  const getVariantStyles = () => {
    switch (variant) {
      case 'danger':
        return {
          icon: 'text-red-500',
          confirmButton: 'bg-red-600 hover:bg-red-700 text-white',
          border: 'border-red-200 dark:border-red-800'
        }
      case 'warning':
        return {
          icon: 'text-yellow-500',
          confirmButton: 'bg-yellow-600 hover:bg-yellow-700 text-white',
          border: 'border-yellow-200 dark:border-yellow-800'
        }
      case 'info':
        return {
          icon: 'text-blue-500',
          confirmButton: 'bg-blue-600 hover:bg-blue-700 text-white',
          border: 'border-blue-200 dark:border-blue-800'
        }
      default:
        return {
          icon: 'text-red-500',
          confirmButton: 'bg-red-600 hover:bg-red-700 text-white',
          border: 'border-red-200 dark:border-red-800'
        }
    }
  }

  const styles = getVariantStyles()

  return (
    <div className="fixed inset-0 bg-black/50 dark:bg-black/60 flex items-center justify-center z-50 p-4 animate-fade-in">
      <div className={`bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-md border-l-4 ${styles.border} animate-scale-in`}>
        <div className="p-6">
          <div className="flex items-start">
            <div className="flex-shrink-0">
              <AlertTriangle className={`h-6 w-6 ${styles.icon}`} />
            </div>
            <div className="ml-3 w-0 flex-1">
              <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100">
                {title}
              </h3>
              <div className="mt-2">
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  {message}
                </p>
              </div>
            </div>
            <div className="ml-4 flex-shrink-0 flex">
              <button
                className="bg-white dark:bg-gray-800 rounded-md inline-flex text-gray-400 dark:text-gray-500 hover:text-gray-500 dark:hover:text-gray-400 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-ring ring-offset-background disabled:opacity-50 disabled:pointer-events-none"
                onClick={onCancel}
                disabled={confirmLoading}
              >
                <span className="sr-only">Fechar</span>
                <X className="h-5 w-5" />
              </button>
            </div>
          </div>
          <div className="mt-6 flex justify-end gap-3">
            <Button
              variant="outline"
              onClick={onCancel}
              disabled={confirmLoading}
            >
              {cancelText}
            </Button>
            <Button
              className={styles.confirmButton}
              onClick={onConfirm}
              disabled={confirmLoading}
            >
              {confirmLoading ? (confirmLoadingText ?? confirmText) : confirmText}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
