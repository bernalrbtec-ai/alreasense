import { Moon, Sun } from 'lucide-react'
import { useTheme } from '../hooks/useTheme'
import { Button } from './ui/Button'
import { cn } from '../lib/utils'

interface ThemeToggleProps {
  className?: string
  size?: 'sm' | 'md' | 'lg'
  variant?: 'default' | 'ghost' | 'icon'
}

/**
 * Componente para alternar entre tema claro e escuro.
 * ✅ UX: Animações suaves e feedback visual
 * ✅ Acessibilidade: ARIA labels e keyboard navigation
 */
export function ThemeToggle({ className, size = 'md', variant = 'icon' }: ThemeToggleProps) {
  const { theme, toggleTheme, isDark } = useTheme()

  const iconSize = {
    sm: 'h-4 w-4',
    md: 'h-5 w-5',
    lg: 'h-6 w-6',
  }[size]

  if (variant === 'icon') {
    return (
      <Button
        variant="ghost"
        size="icon"
        onClick={toggleTheme}
        className={cn(
          "relative transition-all duration-300 hover:scale-110 active:scale-95",
          className
        )}
        title={isDark ? 'Alternar para modo claro' : 'Alternar para modo escuro'}
        aria-label={isDark ? 'Alternar para modo claro' : 'Alternar para modo escuro'}
      >
        {/* ✅ UX: Animação de rotação suave */}
        <div className="relative">
          {isDark ? (
            <Sun className={cn(
              iconSize, 
              "text-yellow-500 dark:text-yellow-400",
              "transition-all duration-300 rotate-0"
            )} />
          ) : (
            <Moon className={cn(
              iconSize, 
              "text-gray-600 dark:text-gray-300",
              "transition-all duration-300 rotate-0"
            )} />
          )}
        </div>
      </Button>
    )
  }

  return (
    <Button
      variant={variant}
      onClick={toggleTheme}
      className={cn(
        "flex items-center gap-2 transition-all duration-200",
        className
      )}
      aria-label={isDark ? 'Alternar para modo claro' : 'Alternar para modo escuro'}
    >
      {isDark ? (
        <>
          <Sun className={cn(iconSize, "text-yellow-500")} />
          <span>Modo Claro</span>
        </>
      ) : (
        <>
          <Moon className={cn(iconSize)} />
          <span>Modo Escuro</span>
        </>
      )}
    </Button>
  )
}

