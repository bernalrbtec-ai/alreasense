import { useState, useEffect } from 'react'

type Theme = 'light' | 'dark'

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(() => {
    // Verificar localStorage primeiro
    const saved = localStorage.getItem('theme') as Theme
    if (saved === 'light' || saved === 'dark') {
      return saved
    }
    
    // Verificar preferência do sistema
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      return 'dark'
    }
    
    // Padrão: light
    return 'light'
  })

  useEffect(() => {
    const root = document.documentElement
    
    // Remover classes anteriores
    root.classList.remove('light', 'dark')
    
    // Adicionar classe atual
    root.classList.add(theme)
    
    // Salvar no localStorage
    localStorage.setItem('theme', theme)
  }, [theme])

  const toggleTheme = () => {
    setTheme(prev => prev === 'light' ? 'dark' : 'light')
  }

  const setLightTheme = () => {
    setTheme('light')
  }

  const setDarkTheme = () => {
    setTheme('dark')
  }

  return {
    theme,
    toggleTheme,
    setLightTheme,
    setDarkTheme,
    isDark: theme === 'dark',
  }
}

