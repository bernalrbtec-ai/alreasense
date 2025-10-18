import { useEffect, useRef, useState } from 'react'
import { useAuthStore } from '../stores/authStore'

interface WebSocketMessage {
  type: string
  data?: any
  payload?: any
}

export function useWebSocket() {
  const { user } = useAuthStore()
  const [isConnected, setIsConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    const tenantId = user?.tenant_id || user?.tenant?.id
    if (!tenantId) return

    // Detectar URL base do WebSocket baseado no ambiente
    const isProduction = window.location.hostname !== 'localhost'
    const WS_BASE_URL = isProduction 
      ? `wss://${window.location.hostname.replace('alreasense-production', 'alreasense-backend-production')}`
      : (import.meta as any).env.VITE_WS_BASE_URL || 'ws://localhost:8000'
    const wsUrl = `${WS_BASE_URL}/ws/tenant/${tenantId}/`
    
    console.log('🔌 [WEBSOCKET] Conectando em:', wsUrl)

    const connect = () => {
      try {
        const ws = new WebSocket(wsUrl)
        wsRef.current = ws

        ws.onopen = () => {
          console.log('WebSocket connected')
          setIsConnected(true)
        }

        ws.onmessage = (event) => {
          try {
            const message: WebSocketMessage = JSON.parse(event.data)
            setLastMessage(message)
          } catch (error) {
            console.error('Failed to parse WebSocket message:', error)
          }
        }

        ws.onclose = () => {
          console.log('WebSocket disconnected')
          setIsConnected(false)
          
          // Reconnect after 5 seconds
          setTimeout(connect, 5000)
        }

        ws.onerror = (error) => {
          console.error('WebSocket error:', error)
          setIsConnected(false)
        }
      } catch (error) {
        console.error('Failed to connect WebSocket:', error)
        setIsConnected(false)
      }
    }

    connect()

    return () => {
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [user?.tenant_id, user?.tenant?.id])

  const sendMessage = (message: any) => {
    if (wsRef.current && isConnected) {
      wsRef.current.send(JSON.stringify(message))
    }
  }

  const subscribeToChat = (chatId: string) => {
    sendMessage({
      type: 'subscribe_chat',
      chat_id: chatId,
    })
  }

  const unsubscribeFromChat = (chatId: string) => {
    sendMessage({
      type: 'unsubscribe_chat',
      chat_id: chatId,
    })
  }

  return {
    isConnected,
    lastMessage,
    sendMessage,
    subscribeToChat,
    unsubscribeFromChat,
  }
}
