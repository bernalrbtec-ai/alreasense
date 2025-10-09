import { useState, useRef, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { User, LogOut, Lock, ChevronDown } from 'lucide-react'
import { useAuthStore } from '../stores/authStore'
import Avatar from './ui/Avatar'

export default function UserDropdown() {
  const [isOpen, setIsOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)
  const { user, logout } = useAuthStore()

  // Fechar dropdown quando clicar fora
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [])

  const handleLogout = () => {
    setIsOpen(false)
    logout()
  }

  const getUserDisplayName = () => {
    const firstName = user?.first_name || ''
    const lastName = user?.last_name || ''
    if (firstName && lastName) {
      return `${firstName} ${lastName}`.trim()
    }
    return user?.username || 'Usuário'
  }

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Botão do usuário */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-x-2 hover:bg-brand-50 rounded-md px-2 py-1 transition-colors focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2"
      >
        <Avatar 
          name={getUserDisplayName()} 
          size="md" 
        />
        <div className="hidden lg:block text-left">
          <p className="text-sm font-medium text-gray-700">
            {`${user?.first_name || ''} ${user?.last_name || ''}`.trim() || user?.username}
          </p>
          <p className="text-xs text-gray-500">{user?.email}</p>
        </div>
        <ChevronDown className={`h-4 w-4 text-gray-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {/* Dropdown menu */}
      {isOpen && (
        <div className="absolute right-0 mt-2 w-56 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-50">
          {/* Meu Perfil */}
          <Link
            to="/profile"
            className="flex items-center px-4 py-2 text-sm text-gray-700 hover:bg-brand-50 transition-colors"
            onClick={() => setIsOpen(false)}
          >
            <User className="h-4 w-4 mr-3 text-gray-400" />
            Meu Perfil
          </Link>

          {/* Alterar Senha */}
          <Link
            to="/change-password"
            className="flex items-center px-4 py-2 text-sm text-gray-700 hover:bg-brand-50 transition-colors"
            onClick={() => setIsOpen(false)}
          >
            <Lock className="h-4 w-4 mr-3 text-gray-400" />
            Alterar Senha
          </Link>

          {/* Divisor */}
          <div className="border-t border-gray-100 my-1" />

          {/* Sair */}
          <button
            onClick={handleLogout}
            className="flex items-center w-full px-4 py-2 text-sm text-gray-700 hover:bg-red-50 transition-colors"
          >
            <LogOut className="h-4 w-4 mr-3 text-red-500" />
            <span className="text-gray-700">Sair</span>
          </button>
        </div>
      )}
    </div>
  )
}
