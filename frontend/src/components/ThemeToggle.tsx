import { Moon, Sun } from 'lucide-react'
import { useTheme } from '../hooks/useTheme'
import { Button } from './ui/Button'
import { cn } from '../lib/utils'

interface ThemeToggleProps {
  className?: string
  size?: 'sm' | 'md' | 'lg'
  variant?: 'default' | 'ghost' | 'icon'
}

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
        className={cn(className)}
        title={isDark ? 'Alternar para modo claro' : 'Alternar para modo escuro'}
      >
        {isDark ? (
          <Sun className={cn(iconSize, "text-yellow-500")} />
        ) : (
          <Moon className={cn(iconSize, "text-gray-600 dark:text-gray-300")} />
        )}
      </Button>
    )
  }

  return (
    <Button
      variant={variant}
      onClick={toggleTheme}
      className={cn("flex items-center gap-2", className)}
    >
      {isDark ? (
        <>
          <Sun className={iconSize} />
          <span>Modo Claro</span>
        </>
      ) : (
        <>
          <Moon className={iconSize} />
          <span>Modo Escuro</span>
        </>
      )}
    </Button>
  )
}

