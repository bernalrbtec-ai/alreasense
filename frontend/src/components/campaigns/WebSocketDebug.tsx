import React, { useState } from 'react'
import { Bug, Eye, EyeOff, Copy, Trash2 } from 'lucide-react'
import { Button } from '../ui/Button'

interface WebSocketMessage {
  type: string
  data: any
  timestamp?: string
}

interface WebSocketDebugProps {
  isConnected: boolean
  connectionStatus: string
  reconnectAttempts: number
  lastUpdate: any
  messages: WebSocketMessage[]
  onClearMessages?: () => void
}

export function WebSocketDebug({ 
  isConnected, 
  connectionStatus, 
  reconnectAttempts, 
  lastUpdate, 
  messages,
  onClearMessages
}: WebSocketDebugProps) {
  const [isVisible, setIsVisible] = useState(false)
  const [autoScroll, setAutoScroll] = useState(true)

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
  }

  const clearMessages = () => {
    onClearMessages?.()
  }

  if (!isVisible) {
    return (
      <div className="fixed bottom-4 right-4 z-50">
        <Button
          onClick={() => setIsVisible(true)}
          className="bg-blue-600 hover:bg-blue-700 text-white p-2 rounded-full shadow-lg"
          title="Debug WebSocket"
        >
          <Bug className="w-4 h-4" />
        </Button>
      </div>
    )
  }

  return (
    <div className="fixed bottom-4 right-4 w-96 max-h-96 bg-white border border-gray-200 rounded-lg shadow-xl z-50">
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-gray-200">
        <div className="flex items-center gap-2">
          <Bug className="w-4 h-4 text-blue-600" />
          <h3 className="font-semibold text-sm">WebSocket Debug</h3>
        </div>
        <Button
          onClick={() => setIsVisible(false)}
          className="p-1 hover:bg-gray-100 rounded"
        >
          <EyeOff className="w-4 h-4" />
        </Button>
      </div>

      {/* Status */}
      <div className="p-3 border-b border-gray-200">
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div>
            <span className="font-medium">Status:</span>
            <span className={`ml-1 px-1 py-0.5 rounded text-xs ${
              isConnected ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
            }`}>
              {connectionStatus}
            </span>
          </div>
          <div>
            <span className="font-medium">Tentativas:</span>
            <span className="ml-1">{reconnectAttempts}</span>
          </div>
        </div>
      </div>

      {/* Last Update */}
      {lastUpdate && (
        <div className="p-3 border-b border-gray-200">
          <div className="flex items-center justify-between mb-2">
            <h4 className="font-medium text-xs">Última Atualização</h4>
            <Button
              onClick={() => copyToClipboard(JSON.stringify(lastUpdate, null, 2))}
              className="p-1 hover:bg-gray-100 rounded"
              title="Copiar"
            >
              <Copy className="w-3 h-3" />
            </Button>
          </div>
          <div className="text-xs text-gray-600 bg-gray-50 p-2 rounded max-h-20 overflow-y-auto">
            <div><strong>Campanha:</strong> {lastUpdate.campaign_name}</div>
            <div><strong>Evento:</strong> {lastUpdate.type}</div>
            <div><strong>Status:</strong> {lastUpdate.status}</div>
            <div><strong>Enviadas:</strong> {lastUpdate.messages_sent}/{lastUpdate.total_contacts}</div>
            <div><strong>Próximo:</strong> {lastUpdate.next_contact_name}</div>
          </div>
        </div>
      )}

      {/* Messages Log */}
      <div className="p-3">
        <div className="flex items-center justify-between mb-2">
          <h4 className="font-medium text-xs">Log de Mensagens</h4>
          <div className="flex gap-1">
            <Button
              onClick={() => setAutoScroll(!autoScroll)}
              className="p-1 hover:bg-gray-100 rounded"
              title={autoScroll ? "Auto-scroll ativo" : "Auto-scroll desativado"}
            >
              <Eye className={`w-3 h-3 ${autoScroll ? 'text-green-600' : 'text-gray-400'}`} />
            </Button>
            <Button
              onClick={clearMessages}
              className="p-1 hover:bg-gray-100 rounded"
              title="Limpar"
            >
              <Trash2 className="w-3 h-3" />
            </Button>
          </div>
        </div>
        
        <div className="max-h-32 overflow-y-auto bg-gray-50 p-2 rounded text-xs">
          {messages.length === 0 ? (
            <div className="text-gray-500 text-center">Nenhuma mensagem recebida</div>
          ) : (
            messages.slice(-10).map((msg, index) => (
              <div key={index} className="mb-1 p-1 bg-white rounded border">
                <div className="font-medium">{msg.type}</div>
                <div className="text-gray-600 text-xs">
                  {msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString() : 'Agora'}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
