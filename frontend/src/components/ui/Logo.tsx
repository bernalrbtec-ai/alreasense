import React from 'react'

interface LogoProps {
  className?: string
  showText?: boolean
  size?: 'sm' | 'md' | 'lg'
}

export default function Logo({ className = '', showText = true, size = 'md' }: LogoProps) {
  const getSizeClasses = () => {
    switch (size) {
      case 'sm':
        return {
          container: 'h-8',
          waves: 'h-4',
          text: 'text-lg'
        }
      case 'lg':
        return {
          container: 'h-16',
          waves: 'h-8',
          text: 'text-2xl'
        }
      default: // md
        return {
          container: 'h-12',
          waves: 'h-6',
          text: 'text-xl'
        }
    }
  }

  const sizeClasses = getSizeClasses()

  return (
    <div className={`flex flex-col items-center justify-center ${sizeClasses.container} ${className}`}>
      {/* Elemento gráfico das ondas */}
      <div className={`relative ${sizeClasses.waves} w-20 flex items-center justify-center`}>
        {/* Ondas principais */}
        <div className="absolute inset-0 flex flex-col justify-center">
          {/* Onda inferior (mais espessa, azul escuro) */}
          <svg 
            className="w-full h-full" 
            viewBox="0 0 80 24" 
            fill="none" 
            xmlns="http://www.w3.org/2000/svg"
          >
            <path 
              d="M0 18C10 6 20 6 30 18C40 6 50 6 60 18C70 6 80 6 80 18V24H0V18Z" 
              fill="#1e40af" 
            />
            {/* Onda superior (mais fina, azul claro) */}
            <path 
              d="M0 12C10 2 20 2 30 12C40 2 50 2 60 12C70 2 80 2 80 12V18H0V12Z" 
              fill="#3b82f6" 
            />
          </svg>
        </div>
        
        {/* Ondas menores (eco, à direita) */}
        <div className="absolute right-0 top-1">
          <svg 
            className="w-8 h-4" 
            viewBox="0 0 32 16" 
            fill="none" 
            xmlns="http://www.w3.org/2000/svg"
          >
            <path 
              d="M0 12C4 4 8 4 12 12C16 4 20 4 24 12C28 4 32 4 32 12V16H0V12Z" 
              fill="#60a5fa" 
            />
            <path 
              d="M0 8C4 2 8 2 12 8C16 2 20 2 24 8C28 2 32 2 32 8V12H0V8Z" 
              fill="#06b6d4" 
            />
          </svg>
        </div>
      </div>
      
      {/* Texto "Alrea Flow" */}
      {showText && (
        <div className={`font-sans font-medium text-gray-900 ${sizeClasses.text} tracking-tight`}>
          Alrea Flow
        </div>
      )}
    </div>
  )
}
