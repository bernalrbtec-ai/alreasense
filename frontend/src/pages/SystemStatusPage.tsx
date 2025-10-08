import { useState, useEffect } from 'react'
import { RefreshCw, Database, Server, Activity, HardDrive, MessageSquare } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import { api } from '../lib/api'

interface SystemStatus {
  status: string
  database: {
    status: 'healthy' | 'unhealthy'
    connection_count?: number
    database_size?: string
  }
  redis: {
    status: 'healthy' | 'unhealthy'
    memory_usage?: string
    connected_clients?: number
  }
  celery: {
    status: 'healthy' | 'unhealthy'
    active_tasks?: number
    processed_tasks?: number
  }
  disk: {
    total?: string
    used?: string
    free?: string
    percent?: number
  }
  memory: {
    total?: string
    used?: string
    free?: string
    percent?: number
  }
  evolution_api?: {
    status: 'active' | 'inactive' | 'error'
    instance_count?: number
    registered_instances?: {
      total: number
      active: number
      inactive: number
    }
  }
}

export default function SystemStatusPage() {
  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date())

  useEffect(() => {
    fetchStatus()
    const interval = setInterval(fetchStatus, 30000) // Update every 30 seconds
    return () => clearInterval(interval)
  }, [])

  const fetchStatus = async () => {
    try {
      setIsLoading(true)
      const response = await api.get('/api/health/')
      setStatus(response.data)
      setLastUpdate(new Date())
    } catch (error) {
      console.error('Error fetching system status:', error)
      // Set default error status
      setStatus({
        status: 'error',
        database: { status: 'unhealthy' },
        redis: { status: 'unhealthy' },
        celery: { status: 'unhealthy' },
      })
    } finally {
      setIsLoading(false)
    }
  }

  const getStatusColor = (status: string) => {
    return status === 'healthy' ? 'text-green-600' : 'text-red-600'
  }

  const getStatusBadge = (status: string) => {
    return status === 'healthy' 
      ? 'bg-green-100 text-green-800' 
      : 'bg-red-100 text-red-800'
  }

  if (isLoading && !status) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Status do Sistema</h1>
          <p className="mt-1 text-sm text-gray-500">
            Monitore a saúde e performance da plataforma
          </p>
          <p className="mt-1 text-xs text-gray-400">
            Última atualização: {lastUpdate.toLocaleTimeString()}
          </p>
        </div>
        <Button onClick={fetchStatus} disabled={isLoading}>
          <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
          Atualizar
        </Button>
      </div>

      {/* Overall Status */}
      <Card className="p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Activity className="h-8 w-8 text-blue-600" />
            <div>
              <h3 className="text-lg font-semibold text-gray-900">Status Geral</h3>
              <p className="text-sm text-gray-500">Alrea Sense Platform</p>
            </div>
          </div>
          <span className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-medium ${getStatusBadge(status?.status || 'unhealthy')}`}>
            {status?.status === 'healthy' ? 'Saudável' : 'Com problemas'}
          </span>
        </div>
      </Card>

      {/* Services Status */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
        {/* Database */}
        <Card className="p-6">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <Database className={`h-8 w-8 ${getStatusColor(status?.database?.status || 'unhealthy')}`} />
              <div>
                <h3 className="text-lg font-semibold text-gray-900">PostgreSQL</h3>
                <p className="text-sm text-gray-500">Banco de Dados</p>
              </div>
            </div>
            <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${getStatusBadge(status?.database?.status || 'unhealthy')}`}>
              {status?.database?.status === 'healthy' ? 'Online' : 'Offline'}
            </span>
          </div>
          {status?.database && (
            <div className="mt-4 space-y-2 text-sm text-gray-600">
              {status.database.connection_count !== undefined && (
                <p>Conexões ativas: {status.database.connection_count}</p>
              )}
              {status.database.database_size && (
                <p>Tamanho do banco: {status.database.database_size}</p>
              )}
            </div>
          )}
        </Card>

        {/* Redis */}
        <Card className="p-6">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <Server className={`h-8 w-8 ${getStatusColor(status?.redis?.status || 'unhealthy')}`} />
              <div>
                <h3 className="text-lg font-semibold text-gray-900">Redis</h3>
                <p className="text-sm text-gray-500">Cache & Message Broker</p>
              </div>
            </div>
            <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${getStatusBadge(status?.redis?.status || 'unhealthy')}`}>
              {status?.redis?.status === 'healthy' ? 'Online' : 'Offline'}
            </span>
          </div>
          {status?.redis && (
            <div className="mt-4 space-y-2 text-sm text-gray-600">
              {status.redis.memory_usage && (
                <p>Uso de memória: {status.redis.memory_usage}</p>
              )}
              {status.redis.connected_clients !== undefined && (
                <p>Clientes conectados: {status.redis.connected_clients}</p>
              )}
            </div>
          )}
        </Card>

        {/* Celery */}
        <Card className="p-6">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <Activity className={`h-8 w-8 ${getStatusColor(status?.celery?.status || 'unhealthy')}`} />
              <div>
                <h3 className="text-lg font-semibold text-gray-900">Celery</h3>
                <p className="text-sm text-gray-500">Task Queue</p>
              </div>
            </div>
            <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${getStatusBadge(status?.celery?.status || 'unhealthy')}`}>
              {status?.celery?.status === 'healthy' ? 'Online' : 'Offline'}
            </span>
          </div>
          {status?.celery && (
            <div className="mt-4 space-y-2 text-sm text-gray-600">
              {status.celery.active_tasks !== undefined && (
                <p>Tarefas ativas: {status.celery.active_tasks}</p>
              )}
              {status.celery.processed_tasks !== undefined && (
                <p>Tarefas processadas: {status.celery.processed_tasks}</p>
              )}
            </div>
          )}
        </Card>

        {/* Evolution API */}
        <Card className="p-6">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <MessageSquare className={`h-8 w-8 ${
                status?.evolution_api?.status === 'active' ? 'text-green-600' : 
                status?.evolution_api?.status === 'inactive' ? 'text-gray-400' : 
                'text-red-600'
              }`} />
              <div>
                <h3 className="text-lg font-semibold text-gray-900">Evolution API</h3>
                <p className="text-sm text-gray-500">WhatsApp Integration</p>
              </div>
            </div>
            <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
              status?.evolution_api?.status === 'active' ? 'bg-green-100 text-green-800' : 
              status?.evolution_api?.status === 'inactive' ? 'bg-gray-100 text-gray-800' : 
              'bg-red-100 text-red-800'
            }`}>
              {status?.evolution_api?.status === 'active' ? 'Conectado' : 
               status?.evolution_api?.status === 'inactive' ? 'Inativo' : 
               'Erro'}
            </span>
          </div>
          {status?.evolution_api && (
            <div className="mt-4 space-y-2 text-sm text-gray-600">
              {status.evolution_api.instance_count !== undefined && (
                <p>Total de instâncias no Evo: {status.evolution_api.instance_count}</p>
              )}
              {status.evolution_api.registered_instances && (
                <>
                  <p className="font-medium text-blue-700">Instâncias cadastradas no Sense:</p>
                  <div className="ml-4 space-y-1">
                    <p>📊 Total: {status.evolution_api.registered_instances.total}</p>
                    <p>🟢 Ativas: {status.evolution_api.registered_instances.active}</p>
                    <p>⚪ Inativas: {status.evolution_api.registered_instances.inactive}</p>
                  </div>
                </>
              )}
            </div>
          )}
        </Card>

        {/* Disk */}
        <Card className="p-6">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <HardDrive className="h-8 w-8 text-blue-600" />
              <div>
                <h3 className="text-lg font-semibold text-gray-900">Disco</h3>
                <p className="text-sm text-gray-500">Armazenamento</p>
              </div>
            </div>
          </div>
          {status?.disk && (
            <div className="mt-4 space-y-2">
              <div className="flex justify-between text-sm text-gray-600">
                <span>Total: {status.disk.total || 'N/A'}</span>
                <span>Usado: {status.disk.used || 'N/A'}</span>
              </div>
              {status.disk.percent !== undefined && (
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div 
                    className={`h-2 rounded-full ${status.disk.percent > 90 ? 'bg-red-600' : status.disk.percent > 70 ? 'bg-yellow-600' : 'bg-green-600'}`}
                    style={{ width: `${status.disk.percent}%` }}
                  />
                </div>
              )}
            </div>
          )}
        </Card>
      </div>

      {/* Memory Usage */}
      {status?.memory && (
        <Card className="p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Uso de Memória</h3>
          <div className="space-y-2">
            <div className="flex justify-between text-sm text-gray-600">
              <span>Total: {status.memory.total || 'N/A'}</span>
              <span>Usado: {status.memory.used || 'N/A'}</span>
              <span>Livre: {status.memory.free || 'N/A'}</span>
            </div>
            {status.memory.percent !== undefined && (
              <div className="w-full bg-gray-200 rounded-full h-3">
                <div 
                  className={`h-3 rounded-full ${status.memory.percent > 90 ? 'bg-red-600' : status.memory.percent > 70 ? 'bg-yellow-600' : 'bg-green-600'}`}
                  style={{ width: `${status.memory.percent}%` }}
                />
              </div>
            )}
          </div>
        </Card>
      )}
    </div>
  )
}

