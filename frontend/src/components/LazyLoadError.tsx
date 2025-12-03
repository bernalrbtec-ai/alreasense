import { useState } from 'react'
import { Button } from './ui/Button'
import { AlertCircle, RefreshCw } from 'lucide-react'

interface LazyLoadErrorProps {
  error: Error
  onRetry?: () => void
}

export function LazyLoadError({ error, onRetry }: LazyLoadErrorProps) {
  const [isRetrying, setIsRetrying] = useState(false)

  const handleRetry = async () => {
    if (onRetry) {
      setIsRetrying(true)
      try {
        await onRetry()
      } finally {
        setIsRetrying(false)
      }
    } else {
      window.location.reload()
    }
  }

  return (
    <div className="min-h-[400px] flex items-center justify-center p-6">
      <div className="max-w-md w-full text-center space-y-4">
        <div className="mx-auto flex items-center justify-center h-16 w-16 rounded-full bg-red-100">
          <AlertCircle className="h-8 w-8 text-red-600" />
        </div>
        
        <div>
          <h3 className="text-lg font-semibold text-gray-900">
            Erro ao carregar página
          </h3>
          <p className="mt-2 text-sm text-gray-600">
            Não foi possível carregar o módulo necessário. Isso pode acontecer após um deploy recente.
          </p>
        </div>

        <div className="rounded-md bg-red-50 p-4 text-left">
          <p className="text-xs font-mono text-red-800 break-all">
            {error.message}
          </p>
        </div>

        <div className="flex flex-col gap-2">
          <Button 
            onClick={handleRetry} 
            disabled={isRetrying}
            className="w-full"
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${isRetrying ? 'animate-spin' : ''}`} />
            {isRetrying ? 'Tentando novamente...' : 'Tentar Novamente'}
          </Button>
          
          <Button
            variant="outline"
            onClick={() => window.location.href = '/dashboard'}
            className="w-full"
          >
            Voltar ao Dashboard
          </Button>
        </div>
      </div>
    </div>
  )
}

