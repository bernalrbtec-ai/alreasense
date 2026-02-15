import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { RefreshCw, Database, Server, Activity, MessageSquare, Rabbit, Box, ExternalLink } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import { api } from '../lib/api'

interface SystemStatus {
  status: string
  database: {
    status: string
    connection_count?: number
    database_size?: string
  }
  redis: {
    status: string
    memory_usage?: string
    connected_clients?: number
  }
  rabbitmq: {
    status: string
    connection?: boolean
    channel?: boolean
    consumer_running?: boolean
    active_campaign_threads?: number
  }
  evolution_api?: {
    status: string
    registered_instances?: { total: number; active: number; inactive: number }
    external_api_instances?: number
  }
  minio?: {
    status: string
    bucket?: string
    error?: string
  }
  memory?: {
    total?: string
    used?: string
    free?: string
    percent?: number
  }
}

export default function SystemStatusPage() {
  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date())

  useEffect(() => {
    fetchStatus()
    const interval = setInterval(fetchStatus, 60000) // Update every 60 seconds (reduced frequency)
    return () => clearInterval(interval)
  }, [])

  const fetchStatus = async () => {
    try {
      setIsLoading(true)
      console.log('🔍 Fetching system status from /health/')
      const response = await api.get('/health/')
      console.log('✅ Health check response:', response.data)
      setStatus(response.data)
      setLastUpdate(new Date())
    } catch (error: any) {
      console.error('❌ Error fetching system status:', error)
      console.error('Error details:', {
        message: error.message,
        response: error.response?.data,
        status: error.response?.status,
      })
      setStatus({
        status: 'degraded',
        database: { status: 'unhealthy' },
        redis: { status: 'unhealthy' },
        rabbitmq: { status: 'unhealthy' },
      })
    } finally {
      setIsLoading(false)
    }
  }

  const getStatusColor = (s: string) => {
    if (s === 'healthy') return 'text-green-600'
    if (s === 'not_configured') return 'text-gray-500'
    if (s === 'degraded') return 'text-yellow-600'
    return 'text-red-600'
  }

  const getStatusBadge = (s: string) => {
    if (s === 'healthy') return 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
    if (s === 'not_configured') return 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300'
    if (s === 'degraded') return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400'
    return 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'
  }

  const getStatusLabel = (s: string) => {
    if (s === 'healthy') return 'Online'
    if (s === 'not_configured') return 'Não configurado'
    if (s === 'degraded') return 'Degradado'
    return 'Offline'
  }

  const evolutionStatusDisplay = status?.evolution_api?.status
  const evolutionLabel =
    evolutionStatusDisplay === 'connected' ? 'Conectado' :
    evolutionStatusDisplay === 'no_active_connection' ? 'Inativo' :
    evolutionStatusDisplay === 'error' || evolutionStatusDisplay === 'disconnected' ? 'Erro' : 'Erro'

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
          <span className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-medium ${getStatusBadge(status?.status || 'degraded')}`}>
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
              {getStatusLabel(status?.database?.status || 'unhealthy')}
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
              {getStatusLabel(status?.redis?.status || 'unhealthy')}
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

        {/* RabbitMQ */}
        <Card className="p-6">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <Rabbit className={`h-8 w-8 ${getStatusColor(status?.rabbitmq?.status || 'unhealthy')}`} />
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">RabbitMQ</h3>
                <p className="text-sm text-gray-500">Message Broker / Campanhas</p>
              </div>
            </div>
            <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${getStatusBadge(status?.rabbitmq?.status || 'unhealthy')}`}>
              {getStatusLabel(status?.rabbitmq?.status || 'unhealthy')}
            </span>
          </div>
          {status?.rabbitmq && status.rabbitmq.status !== 'not_configured' && (
            <div className="mt-4 space-y-2 text-sm text-gray-600 dark:text-gray-400">
              {status.rabbitmq.connection !== undefined && <p>Conexão: {status.rabbitmq.connection ? 'Sim' : 'Não'}</p>}
              {status.rabbitmq.channel !== undefined && <p>Canal: {status.rabbitmq.channel ? 'Ok' : 'Não'}</p>}
              {status.rabbitmq.consumer_running !== undefined && <p>Consumer: {status.rabbitmq.consumer_running ? 'Rodando' : 'Parado'}</p>}
              {status.rabbitmq.active_campaign_threads !== undefined && <p>Threads de campanha: {status.rabbitmq.active_campaign_threads}</p>}
            </div>
          )}
        </Card>

        {/* Evolution API */}
        <Card className="p-6">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <MessageSquare className={`h-8 w-8 ${
                evolutionStatusDisplay === 'connected' ? 'text-green-600' :
                evolutionStatusDisplay === 'no_active_connection' ? 'text-gray-400' :
                'text-red-600'
              }`} />
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Evolution API</h3>
                <p className="text-sm text-gray-500">WhatsApp Integration</p>
              </div>
            </div>
            <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
              evolutionStatusDisplay === 'connected' ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400' :
              evolutionStatusDisplay === 'no_active_connection' ? 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300' :
              'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'
            }`}>
              {evolutionLabel}
            </span>
          </div>
          {status?.evolution_api && (
            <div className="mt-4 space-y-2 text-sm text-gray-600 dark:text-gray-400">
              {status.evolution_api.registered_instances && (
                <>
                  <p className="font-medium text-gray-700 dark:text-gray-300">Instâncias cadastradas no Sense (WhatsAppInstance):</p>
                  <div className="ml-4 space-y-1">
                    <p>Total: {status.evolution_api.registered_instances.total}</p>
                    <p>Ativas: {status.evolution_api.registered_instances.active}</p>
                    <p>Inativas: {status.evolution_api.registered_instances.inactive}</p>
                  </div>
                </>
              )}
              {status.evolution_api.external_api_instances !== undefined && (
                <p className="font-medium text-gray-700 dark:text-gray-300 mt-2">Instâncias na Evolution API: {status.evolution_api.external_api_instances}</p>
              )}
              <Link to="/admin/evolution" className="inline-flex items-center gap-1 text-accent-600 hover:text-accent-700 text-sm font-medium mt-2">
                Ver instâncias <ExternalLink className="h-3.5 w-3.5" />
              </Link>
            </div>
          )}
        </Card>

        {/* MinIO */}
        <Card className="p-6">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <Box className={`h-8 w-8 ${getStatusColor(status?.minio?.status || 'unhealthy')}`} />
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">MinIO</h3>
                <p className="text-sm text-gray-500">Object Storage (S3)</p>
              </div>
            </div>
            <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${getStatusBadge(status?.minio?.status || 'unhealthy')}`}>
              {getStatusLabel(status?.minio?.status || 'unhealthy')}
            </span>
          </div>
          {status?.minio && status.minio.status === 'healthy' && status.minio.bucket && (
            <div className="mt-4 space-y-2 text-sm text-gray-600 dark:text-gray-400">
              <p>Bucket: {status.minio.bucket}</p>
            </div>
          )}
          {status?.minio && status.minio.status === 'unhealthy' && status.minio.error && (
            <p className="mt-4 text-sm text-red-600 dark:text-red-400">{status.minio.error}</p>
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

