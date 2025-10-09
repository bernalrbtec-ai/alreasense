interface AvatarProps {
  name: string
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

export default function Avatar({ name, size = 'md', className = '' }: AvatarProps) {
  const getInitials = () => {
    const words = name.trim().split(' ')
    if (words.length >= 2) {
      return `${words[0].charAt(0)}${words[1].charAt(0)}`.toUpperCase()
    }
    return name.charAt(0).toUpperCase()
  }

  const getSizeClasses = () => {
    switch (size) {
      case 'sm':
        return 'h-6 w-6 text-xs'
      case 'md':
        return 'h-8 w-8 text-sm'
      case 'lg':
        return 'h-12 w-12 text-lg'
      default:
        return 'h-8 w-8 text-sm'
    }
  }

  return (
    <div className={`${getSizeClasses()} rounded-full flex items-center justify-center shadow-lg ${className}`}>
      <div 
        className="w-full h-full rounded-full flex items-center justify-center bg-gradient-to-br from-brand-500 via-brand-400 to-accent-500"
        style={{
          background: `
            radial-gradient(circle at 30% 30%, #26BC6D 0%, transparent 50%),
            radial-gradient(circle at 70% 70%, #3C82F6 0%, transparent 50%),
            linear-gradient(135deg, #26BC6D 0%, #4ade80 25%, #3C82F6 75%, #2563eb 100%)
          `
        }}
      >
        <span className="font-bold text-white drop-shadow-sm">
          {getInitials()}
        </span>
      </div>
    </div>
  )
}
