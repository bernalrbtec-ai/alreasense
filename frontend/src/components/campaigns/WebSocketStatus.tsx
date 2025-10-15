import React from 'react'
import { Wifi, WifiOff, Loader2, AlertCircle } from 'lucide-react'

interface WebSocketStatusProps {
  isConnected: boolean
  connectionStatus: 'connecting' | 'connected' | 'disconnected' | 'error'
  reconnectAttempts: number
  className?: string
}

export function WebSocketStatus({ 
  isConnected, 
  connectionStatus, 
  reconnectAttempts, 
  className = '' 
}: WebSocketStatusProps) {
  const getStatusConfig = () => {
    switch (connectionStatus) {
      case 'connecting':
        return {
          icon: Loader2,
          text: 'Conectando...',
          bgColor: 'bg-yellow-100',
          textColor: 'text-yellow-800',
          borderColor: 'border-yellow-200',
          dotColor: 'bg-yellow-500',
          animate: true
        }
      case 'connected':
        return {
          icon: Wifi,
          text: 'Tempo Real',
          bgColor: 'bg-green-100',
          textColor: 'text-green-800',
          borderColor: 'border-green-200',
          dotColor: 'bg-green-500',
          animate: false
        }
      case 'error':
        return {
          icon: AlertCircle,
          text: `Erro - Polling (${reconnectAttempts} tentativas)`,
          bgColor: 'bg-red-100',
          textColor: 'text-red-800',
          borderColor: 'border-red-200',
          dotColor: 'bg-red-500',
          animate: false
        }
      default:
        return {
          icon: WifiOff,
          text: 'Polling',
          bgColor: 'bg-gray-100',
          textColor: 'text-gray-800',
          borderColor: 'border-gray-200',
          dotColor: 'bg-gray-500',
          animate: false
        }
    }
  }

  const config = getStatusConfig()
  const Icon = config.icon

  return (
    <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-sm font-medium border ${config.bgColor} ${config.textColor} ${config.borderColor} ${className}`}>
      <div className={`w-2 h-2 rounded-full ${config.dotColor} ${config.animate ? 'animate-pulse' : ''}`}></div>
      <Icon className={`w-3 h-3 ${config.animate ? 'animate-spin' : ''}`} />
      <span>{config.text}</span>
    </div>
  )
}
