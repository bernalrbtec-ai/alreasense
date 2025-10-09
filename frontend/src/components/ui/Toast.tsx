import { useEffect } from 'react'
import { Check, X, AlertCircle, Info } from 'lucide-react'

interface ToastProps {
  show: boolean
  message: string
  type: 'success' | 'error' | 'warning' | 'info'
  onClose: () => void
  duration?: number
}

export default function Toast({ show, message, type, onClose, duration = 5000 }: ToastProps) {
  useEffect(() => {
    if (show) {
      const timer = setTimeout(() => {
        onClose()
      }, duration)
      return () => clearTimeout(timer)
    }
  }, [show, duration, onClose])

  if (!show) return null

  const getIcon = () => {
    switch (type) {
      case 'success':
        return <Check className="h-5 w-5 text-green-500" />
      case 'error':
        return <X className="h-5 w-5 text-red-500" />
      case 'warning':
        return <AlertCircle className="h-5 w-5 text-yellow-500" />
      case 'info':
        return <Info className="h-5 w-5 text-blue-500" />
    }
  }

  const getBackgroundColor = () => {
    switch (type) {
      case 'success':
        return 'bg-green-50 border-green-200'
      case 'error':
        return 'bg-red-50 border-red-200'
      case 'warning':
        return 'bg-yellow-50 border-yellow-200'
      case 'info':
        return 'bg-blue-50 border-blue-200'
    }
  }

  return (
    <div className="fixed top-4 right-4 z-50 max-w-sm w-full">
      <div className={`bg-white rounded-lg shadow-lg border-l-4 ${getBackgroundColor()} animate-in slide-in-from-right-full duration-300`}>
        <div className="p-4">
          <div className="flex items-start">
            <div className="flex-shrink-0">
              {getIcon()}
            </div>
            <div className="ml-3 w-0 flex-1">
              <p className="text-sm font-medium text-gray-900">
                {message}
              </p>
            </div>
            <div className="ml-4 flex-shrink-0 flex">
              <button
                className="bg-white rounded-md inline-flex text-gray-400 hover:text-gray-500 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                onClick={onClose}
              >
                <span className="sr-only">Fechar</span>
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
