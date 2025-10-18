import { useEffect, useRef, useState, useCallback } from 'react'
import { useAuthStore } from '../stores/authStore'

interface CampaignUpdate {
  type: string
  campaign_id: string
  campaign_name: string
  status: string
  messages_sent: number
  messages_delivered: number
  messages_read: number
  messages_failed: number
  total_contacts: number
  progress_percentage: number
  last_message_sent_at?: string
  next_message_scheduled_at?: string
  next_contact_name?: string
  next_contact_phone?: string
  last_contact_name?: string
  last_contact_phone?: string
  updated_at: string
  timestamp: string
  event?: string
}

interface WebSocketMessage {
  type: string
  data: CampaignUpdate
  timestamp?: string
}

interface UseCampaignWebSocketReturn {
  isConnected: boolean
  lastUpdate: CampaignUpdate | null
  connectionStatus: 'connecting' | 'connected' | 'disconnected' | 'error'
  reconnectAttempts: number
  messages: WebSocketMessage[]
  clearMessages: () => void
}

export function useCampaignWebSocket(
  onCampaignUpdate?: (update: CampaignUpdate) => void,
  onConnectionChange?: (status: string) => void
): UseCampaignWebSocketReturn {
  const { user } = useAuthStore()
  const [isConnected, setIsConnected] = useState(false)
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected' | 'error'>('disconnected')
  const [lastUpdate, setLastUpdate] = useState<CampaignUpdate | null>(null)
  const [reconnectAttempts, setReconnectAttempts] = useState(0)
  const [messages, setMessages] = useState<WebSocketMessage[]>([])
  
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const heartbeatIntervalRef = useRef<NodeJS.Timeout | null>(null)
  const maxReconnectAttempts = 10
  const reconnectDelay = 3000 // 3 segundos

  const connect = useCallback(() => {
    const tenantId = user?.tenant_id || user?.tenant?.id
    if (!tenantId || wsRef.current?.readyState === WebSocket.CONNECTING || wsRef.current?.readyState === WebSocket.OPEN) {
      return
    }

    // Detectar URL base do WebSocket baseado no ambiente
    const isProduction = window.location.hostname !== 'localhost'
    const WS_BASE_URL = isProduction 
      ? `wss://${window.location.hostname.replace('alreasense-production', 'alreasense-backend-production')}`
      : (import.meta as any).env.VITE_WS_BASE_URL || 'ws://localhost:8000'
    const tenantId = user.tenant_id || user.tenant?.id
    const wsUrl = `${WS_BASE_URL}/ws/tenant/${tenantId}/`
    
    console.log('🔌 [CAMPAIGN-WS] Conectando em:', wsUrl)
    setConnectionStatus('connecting')

    try {
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        console.log('✅ [CAMPAIGN-WS] Conectado com sucesso')
        setIsConnected(true)
        setConnectionStatus('connected')
        setReconnectAttempts(0)
        onConnectionChange?.('connected')

        // Iniciar heartbeat
        heartbeatIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping' }))
          }
        }, 30000) // 30 segundos
      }

      ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data)
          
          // Lidar com diferentes tipos de mensagem
          if (message.type === 'pong') {
            // Resposta do heartbeat
            return
          }
          
          if (message.type === 'campaign_update' && message.data) {
            console.log('📡 [CAMPAIGN-WS] Recebido update:', message.data.campaign_name, message.data.type)
            setLastUpdate(message.data)
            onCampaignUpdate?.(message.data)
          }
          
          // Adicionar mensagem ao histórico (máximo 50 mensagens)
          setMessages(prev => {
            const newMessages = [...prev, message]
            return newMessages.slice(-50)
          })
          
          if (message.type === 'connection_established') {
            console.log('🎯 [CAMPAIGN-WS] Conexão estabelecida')
          }
        } catch (error) {
          console.error('❌ [CAMPAIGN-WS] Erro ao processar mensagem:', error)
        }
      }

      ws.onclose = (event) => {
        console.log('🔌 [CAMPAIGN-WS] Conexão fechada:', event.code, event.reason)
        setIsConnected(false)
        setConnectionStatus('disconnected')
        onConnectionChange?.('disconnected')
        
        // Limpar heartbeat
        if (heartbeatIntervalRef.current) {
          clearInterval(heartbeatIntervalRef.current)
          heartbeatIntervalRef.current = null
        }
        
        // Tentar reconectar se não foi fechamento intencional
        if (event.code !== 1000 && reconnectAttempts < maxReconnectAttempts) {
          const delay = Math.min(reconnectDelay * Math.pow(1.5, reconnectAttempts), 30000)
          console.log(`🔄 [CAMPAIGN-WS] Tentando reconectar em ${delay}ms (tentativa ${reconnectAttempts + 1}/${maxReconnectAttempts})`)
          
          setReconnectAttempts(prev => prev + 1)
          reconnectTimeoutRef.current = setTimeout(() => {
            connect()
          }, delay)
        } else if (reconnectAttempts >= maxReconnectAttempts) {
          console.error('❌ [CAMPAIGN-WS] Máximo de tentativas de reconexão atingido')
          setConnectionStatus('error')
          onConnectionChange?.('error')
        }
      }

      ws.onerror = (error) => {
        console.error('❌ [CAMPAIGN-WS] Erro na conexão:', error)
        setConnectionStatus('error')
        onConnectionChange?.('error')
      }
    } catch (error) {
      console.error('❌ [CAMPAIGN-WS] Erro ao criar conexão:', error)
      setConnectionStatus('error')
      onConnectionChange?.('error')
    }
  }, [user?.tenant?.id, onCampaignUpdate, onConnectionChange, reconnectAttempts])

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current)
      heartbeatIntervalRef.current = null
    }
    
    if (wsRef.current) {
      wsRef.current.close(1000, 'Intentional disconnect')
      wsRef.current = null
    }
    
    setIsConnected(false)
    setConnectionStatus('disconnected')
    setReconnectAttempts(0)
  }, [])

  useEffect(() => {
    if (user?.tenant?.id) {
      connect()
    } else {
      disconnect()
    }

    return () => {
      disconnect()
    }
  }, [user?.tenant?.id, connect, disconnect])

  const clearMessages = useCallback(() => {
    setMessages([])
  }, [])

  return {
    isConnected,
    lastUpdate,
    connectionStatus,
    reconnectAttempts,
    messages,
    clearMessages
  }
}
