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
      {/* Elemento gráfico das ondas - posicionado acima do texto */}
      <div className={`relative ${sizeClasses.waves} w-24 mb-2`}>
        {/* Ondas principais - mais suaves e bem posicionadas */}
        <svg 
          className="w-full h-full" 
          viewBox="0 0 96 20" 
          fill="none" 
          xmlns="http://www.w3.org/2000/svg"
        >
          {/* Onda inferior (verde escuro) */}
          <path 
            d="M0 15C12 5 24 5 36 15C48 5 60 5 72 15C84 5 96 5 96 15V20H0V15Z" 
            fill="#15803d" 
          />
          {/* Onda superior (verde vibrante) */}
          <path 
            d="M0 10C12 2 24 2 36 10C48 2 60 2 72 10C84 2 96 2 96 10V15H0V10Z" 
            fill="#26BC6D" 
          />
          {/* Onda mais clara (azul claro) */}
          <path 
            d="M0 6C12 0 24 0 36 6C48 0 60 0 72 6C84 0 96 0 96 6V10H0V6Z" 
            fill="#3C82F6" 
          />
        </svg>
        
        {/* Ondas menores (eco, à direita) - mais sutis */}
        <div className="absolute right-2 top-1">
          <svg 
            className="w-6 h-3 opacity-70" 
            viewBox="0 0 24 12" 
            fill="none" 
            xmlns="http://www.w3.org/2000/svg"
          >
            <path 
              d="M0 8C3 4 6 4 9 8C12 4 15 4 18 8C21 4 24 4 24 8V12H0V8Z" 
              fill="#4ade80" 
            />
            <path 
              d="M0 5C3 2 6 2 9 5C12 2 15 2 18 5C21 2 24 2 24 5V8H0V5Z" 
              fill="#3C82F6" 
            />
          </svg>
        </div>
      </div>
      
      {/* Texto "Alrea Flow" - bem separado das ondas */}
      {showText && (
        <div className={`font-sans font-semibold text-gray-900 ${sizeClasses.text} tracking-wide`}>
          Alrea Flow
        </div>
      )}
    </div>
  )
}
