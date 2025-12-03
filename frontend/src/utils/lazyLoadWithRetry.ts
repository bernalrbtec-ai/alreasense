import { lazy, ComponentType, LazyExoticComponent } from 'react'

/**
 * Lazy loading com retry automático em caso de falha
 * Útil para resolver problemas de carregamento de módulos em produção
 */
export function lazyLoadWithRetry<T extends ComponentType<any>>(
  importFn: () => Promise<{ default: T }>,
  retries = 3,
  delay = 1000
): LazyExoticComponent<T> {
  return lazy(async () => {
    let lastError: Error | null = null
    
    for (let i = 0; i < retries; i++) {
      try {
        const module = await importFn()
        
        // Verificar se o módulo tem default export
        if (!module || !module.default) {
          throw new Error('Module does not have a default export')
        }
        
        return module
      } catch (error) {
        lastError = error instanceof Error ? error : new Error(String(error))
        console.warn(`Lazy load attempt ${i + 1} failed:`, lastError.message)
        
        // Aguardar antes de tentar novamente (exceto na última tentativa)
        if (i < retries - 1) {
          await new Promise(resolve => setTimeout(resolve, delay * (i + 1)))
        }
      }
    }
    
    // Se todas as tentativas falharam, relançar o erro
    console.error('All lazy load attempts failed:', lastError)
    throw lastError || new Error('Failed to load module after multiple attempts')
  })
}

