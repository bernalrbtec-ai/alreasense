import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { api } from '../lib/api'
import { formatDate } from '../lib/utils'
import { Plus, Wifi, WifiOff, Settings, TestTube } from 'lucide-react'

interface Connection {
  id: number
  name: string
  evo_ws_url: string
  is_active: boolean
  status: string
  created_at: string
  updated_at: string
}

export default function ConnectionsPage() {
  const [connections, setConnections] = useState<Connection[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [showAddForm, setShowAddForm] = useState(false)

  useEffect(() => {
    fetchConnections()
  }, [])

  const fetchConnections = async () => {
    try {
      setIsLoading(true)
      const response = await api.get('/connections/')
      setConnections(response.data)
    } catch (error) {
      console.error('Failed to fetch connections:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const toggleConnection = async (id: number) => {
    try {
      await api.post(`/connections/${id}/toggle/`)
      fetchConnections() // Refresh list
    } catch (error) {
      console.error('Failed to toggle connection:', error)
    }
  }

  const testConnection = async (id: number) => {
    try {
      await api.post(`/connections/${id}/test/`)
      // Show success message
    } catch (error) {
      console.error('Failed to test connection:', error)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Conexões</h1>
          <p className="text-gray-600">
            Gerencie suas conexões com a Evolution API
          </p>
        </div>
        <Button onClick={() => setShowAddForm(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Nova Conexão
        </Button>
      </div>

      {/* Connections List */}
      <div className="grid gap-6">
        {isLoading ? (
          <div className="flex items-center justify-center h-32">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          </div>
        ) : connections.length === 0 ? (
          <Card>
            <CardContent className="text-center py-12">
              <WifiOff className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-500 mb-4">Nenhuma conexão configurada</p>
              <Button onClick={() => setShowAddForm(true)}>
                <Plus className="h-4 w-4 mr-2" />
                Adicionar Primeira Conexão
              </Button>
            </CardContent>
          </Card>
        ) : (
          connections.map((connection) => (
            <Card key={connection.id}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    {connection.is_active ? (
                      <Wifi className="h-5 w-5 text-green-600" />
                    ) : (
                      <WifiOff className="h-5 w-5 text-red-600" />
                    )}
                    <div>
                      <CardTitle>{connection.name}</CardTitle>
                      <CardDescription>
                        Criada em {formatDate(connection.created_at)}
                      </CardDescription>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => testConnection(connection.id)}
                    >
                      <TestTube className="h-4 w-4 mr-2" />
                      Testar
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => toggleConnection(connection.id)}
                    >
                      {connection.is_active ? 'Desativar' : 'Ativar'}
                    </Button>
                    <Button variant="outline" size="sm">
                      <Settings className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <div>
                    <span className="text-sm font-medium text-gray-500">URL:</span>
                    <p className="text-sm text-gray-900 font-mono">{connection.evo_ws_url}</p>
                  </div>
                  <div>
                    <span className="text-sm font-medium text-gray-500">Status:</span>
                    <span className={`ml-2 inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                      connection.is_active 
                        ? 'bg-green-100 text-green-800' 
                        : 'bg-red-100 text-red-800'
                    }`}>
                      {connection.is_active ? 'Ativa' : 'Inativa'}
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))
        )}
      </div>

      {/* Add Connection Form */}
      {showAddForm && (
        <Card>
          <CardHeader>
            <CardTitle>Nova Conexão</CardTitle>
            <CardDescription>
              Configure uma nova conexão com a Evolution API
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Nome da Conexão
                </label>
                <input
                  type="text"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Ex: WhatsApp Principal"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  URL WebSocket
                </label>
                <input
                  type="url"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="wss://sua-evolution-api.com/ws"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Token de Acesso
                </label>
                <input
                  type="password"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Seu token da Evolution API"
                />
              </div>
              
              <div className="flex gap-2">
                <Button type="submit">
                  <Plus className="h-4 w-4 mr-2" />
                  Criar Conexão
                </Button>
                <Button 
                  type="button" 
                  variant="outline"
                  onClick={() => setShowAddForm(false)}
                >
                  Cancelar
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
