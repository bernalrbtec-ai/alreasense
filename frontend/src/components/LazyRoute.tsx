import { Suspense, ReactNode, Component, ErrorInfo } from 'react'
import LoadingSpinner from './ui/LoadingSpinner'
import { LazyLoadError } from './LazyLoadError'

interface LazyRouteProps {
  children: ReactNode
}

interface LazyRouteState {
  hasError: boolean
  error: Error | null
  retryCount: number
}

/**
 * Wrapper para rotas com lazy loading que captura erros de carregamento
 * e oferece retry automático
 */
class LazyRoute extends Component<LazyRouteProps, LazyRouteState> {
  private retryTimeout: NodeJS.Timeout | null = null

  constructor(props: LazyRouteProps) {
    super(props)
    this.state = {
      hasError: false,
      error: null,
      retryCount: 0,
    }
  }

  static getDerivedStateFromError(error: Error): Partial<LazyRouteState> {
    // Verificar se é erro de módulo não encontrado
    const isModuleError = 
      error.message.includes('Failed to fetch dynamically imported module') ||
      error.message.includes('Loading chunk') ||
      error.message.includes('ChunkLoadError') ||
      error.name === 'ChunkLoadError'

    return {
      hasError: true,
      error,
      retryCount: 0,
    }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('LazyRoute error:', error, errorInfo)
    
    // Se for erro de módulo não encontrado, tentar reload após delay
    const isModuleError = 
      error.message.includes('Failed to fetch dynamically imported module') ||
      error.message.includes('Loading chunk') ||
      error.message.includes('ChunkLoadError') ||
      error.name === 'ChunkLoadError'

    if (isModuleError && this.state.retryCount < 2) {
      // Aguardar 2 segundos e tentar reload
      this.retryTimeout = setTimeout(() => {
        this.setState(prev => ({ retryCount: prev.retryCount + 1 }))
        window.location.reload()
      }, 2000)
    }
  }

  componentWillUnmount() {
    if (this.retryTimeout) {
      clearTimeout(this.retryTimeout)
    }
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null })
    window.location.reload()
  }

  render() {
    if (this.state.hasError && this.state.error) {
      return (
        <LazyLoadError 
          error={this.state.error} 
          onRetry={this.handleRetry}
        />
      )
    }

    return (
      <Suspense fallback={<LoadingSpinner size="lg" />}>
        {this.props.children}
      </Suspense>
    )
  }
}

export default LazyRoute

