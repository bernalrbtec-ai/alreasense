import { useState, useEffect, useCallback, useMemo } from 'react'

type Theme = 'light' | 'dark'

/**
 * Hook para gerenciar tema escuro/claro com:
 * - Persistência no localStorage
 * - Suporte a preferência do sistema
 * - Transições suaves
 * - Performance otimizada
 */
export function useTheme() {
  const [theme, setTheme] = useState<Theme>(() => {
    // ✅ PERFORMANCE: Inicialização síncrona para evitar flash
    if (typeof window === 'undefined') return 'dark' // SSR fallback
    
    // Verificar localStorage primeiro (prioridade)
    const saved = localStorage.getItem('theme') as Theme
    if (saved === 'light' || saved === 'dark') {
      return saved
    }
    
    // Verificar preferência do sistema
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      return 'dark'
    }
    
    // ✅ PADRÃO: dark (tema escuro)
    return 'dark'
  })

  // ✅ PERFORMANCE: Aplicar tema imediatamente no mount (evita flash)
  useEffect(() => {
    const root = document.documentElement
    
    // Remover classes anteriores
    root.classList.remove('light', 'dark')
    
    // Adicionar classe atual
    root.classList.add(theme)
    
    // ✅ UX: Adicionar transição suave
    root.style.transition = 'background-color 0.3s ease, color 0.3s ease'
    
    // Salvar no localStorage
    try {
      localStorage.setItem('theme', theme)
    } catch (e) {
      console.warn('⚠️ [THEME] Erro ao salvar no localStorage:', e)
    }
  }, [theme])

  // ✅ PERFORMANCE: Listener para mudanças na preferência do sistema (opcional)
  useEffect(() => {
    if (!window.matchMedia) return

    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    
    const handleChange = (e: MediaQueryListEvent) => {
      // Só atualizar se não houver preferência salva
      const saved = localStorage.getItem('theme')
      if (!saved) {
        setTheme(e.matches ? 'dark' : 'light')
      }
    }

    // ✅ MODERN: addEventListener ao invés de addListener (deprecated)
    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener('change', handleChange)
      return () => mediaQuery.removeEventListener('change', handleChange)
    } else {
      // Fallback para navegadores antigos
      mediaQuery.addListener(handleChange)
      return () => mediaQuery.removeListener(handleChange)
    }
  }, [])

  // ✅ PERFORMANCE: useCallback para evitar re-renders
  const toggleTheme = useCallback(() => {
    setTheme(prev => prev === 'light' ? 'dark' : 'light')
  }, [])

  const setLightTheme = useCallback(() => {
    setTheme('light')
  }, [])

  const setDarkTheme = useCallback(() => {
    setTheme('dark')
  }, [])

  // ✅ PERFORMANCE: useMemo para evitar recálculos
  const isDark = useMemo(() => theme === 'dark', [theme])

  return {
    theme,
    toggleTheme,
    setLightTheme,
    setDarkTheme,
    isDark,
  }
}

