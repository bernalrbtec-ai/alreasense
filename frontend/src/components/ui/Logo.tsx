import React, { useState } from 'react'

interface LogoProps {
  className?: string
  showText?: boolean
  size?: 'sm' | 'md' | 'lg'
}

export default function Logo({ className = '', showText = true, size = 'md' }: LogoProps) {
  const [imageError, setImageError] = useState(false)

  const getSizeClasses = () => {
    switch (size) {
      case 'sm':
        return {
          container: 'h-8',
          image: 'h-6',
          waves: 'h-4',
          text: 'text-lg'
        }
      case 'lg':
        return {
          container: 'h-16',
          image: 'h-12',
          waves: 'h-8',
          text: 'text-2xl'
        }
      default: // md
        return {
          container: 'h-12',
          image: 'h-8',
          waves: 'h-6',
          text: 'text-xl'
        }
    }
  }

  const sizeClasses = getSizeClasses()

  // ✅ NOVO: Tentar carregar logo personalizado, fallback para SVG gerado
  const logoPath = '/assets/logo/logo.png'
  const logoWithTextPath = '/assets/logo/logo-with-text.png'
  
  // Se showText, usar logo com texto, senão usar logo apenas
  const imagePath = showText ? logoWithTextPath : logoPath

  // Se imagem não carregou, mostrar SVG fallback
  if (imageError) {
    return (
      <div className={`flex flex-col items-center justify-center ${sizeClasses.container} ${className}`}>
        <div className={`relative ${sizeClasses.waves} w-24 mb-2`}>
          <svg 
            className="w-full h-full" 
            viewBox="0 0 96 20" 
            fill="none" 
            xmlns="http://www.w3.org/2000/svg"
          >
            <path 
              d="M0 15C12 5 24 5 36 15C48 5 60 5 72 15C84 5 96 5 96 15V20H0V15Z" 
              fill="#1e40af" 
            />
            <path 
              d="M0 10C12 2 24 2 36 10C48 2 60 2 72 10C84 2 96 2 96 10V15H0V10Z" 
              fill="#3C82F6" 
            />
            <path 
              d="M0 6C12 0 24 0 36 6C48 0 60 0 72 6C84 0 96 0 96 6V10H0V6Z" 
              fill="#60a5fa" 
            />
          </svg>
        </div>
        {showText && (
          <div className={`font-sans font-semibold text-gray-900 ${sizeClasses.text} tracking-wide`}>
            Alrea Flow
          </div>
        )}
      </div>
    )
  }

  // Tentar carregar imagem do logo
  return (
    <div className={`flex items-center justify-center ${sizeClasses.container} ${className}`}>
      <img 
        src={imagePath}
        alt="Alrea Flow"
        className={`${sizeClasses.image} object-contain`}
        onError={() => setImageError(true)}
      />
    </div>
  )
}
