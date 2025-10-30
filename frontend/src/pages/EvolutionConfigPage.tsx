import { useState, useEffect } from 'react'
import { RefreshCw, Server, CheckCircle, XCircle, AlertCircle, Copy, Check } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import Toast from '../components/ui/Toast'
import { useToast } from '../hooks/useToast'
import { api } from '../lib/api'
import { useAuthStore } from '../stores/authStore'

interface InstanceData {
  name: string
  status: 'connected' | 'disconnected'
  raw_status: string
}

interface EvolutionStats {
  status: 'active' | 'inactive' | 'error'
  last_check: string
  last_error?: string | null
  webhook_url: string
  statistics: {
    total: number
    connected: number
    disconnected: number
  }
  instances: InstanceData[]
}

export default function EvolutionConfigPage() {
  const { user } = useAuthStore()
  const [stats, setStats] = useState<EvolutionStats | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [copied, setCopied] = useState(false)
  const { toast, showToast, hideToast } = useToast()

  // ✅ Apenas superuser pode acessar esta página
  if (!user?.is_superuser) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <AlertCircle className="h-16 w-16 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Acesso Negado</h2>
          <p className="text-gray-600">
            Apenas administradores podem visualizar o servidor Evolution API.
          </p>
        </div>
      </div>
    )
  }

  useEffect(() => {
    fetchStats()
  }, [])

  const fetchStats = async () => {
    try {
      setIsLoading(true)
      const response = await api.get('/connections/evolution/config/')
      setStats(response.data)
    } catch (error) {
      console.error('Error fetching stats:', error)
      showToast('Erro ao buscar estatísticas', 'error')
    } finally {
      setIsLoading(false)
    }
  }

  const handleRefresh = async () => {
    try {
      setIsRefreshing(true)
      await fetchStats()
      showToast('Estatísticas atualizadas!', 'success')
    } catch (error) {
      showToast('Erro ao atualizar', 'error')
    } finally {
      setIsRefreshing(false)
    }
  }

  const handleCopyWebhook = async () => {
    if (stats?.webhook_url) {
      await navigator.clipboard.writeText(stats.webhook_url)
      setCopied(true)
      showToast('Webhook URL copiada!', 'success')
      setTimeout(() => setCopied(false), 2000)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (!stats) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <AlertCircle className="h-16 w-16 text-yellow-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Sem Dados</h2>
          <p className="text-gray-600 mb-4">
            Não foi possível carregar as estatísticas.
          </p>
          <Button onClick={fetchStats}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Tentar Novamente
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Servidor de Instância Evolution</h1>
          <p className="mt-1 text-sm text-gray-500">
            Monitoramento e estatísticas das instâncias WhatsApp conectadas
          </p>
        </div>
        <Button
          onClick={handleRefresh}
          disabled={isRefreshing}
          variant="outline"
        >
          <RefreshCw className={`h-4 w-4 mr-2 ${isRefreshing ? 'animate-spin' : ''}`} />
          {isRefreshing ? 'Atualizando...' : 'Atualizar'}
        </Button>
      </div>

      {/* Status Card */}
      <Card className={`p-6 border-l-4 ${
        stats.status === 'active' ? 'border-l-green-500 bg-green-50' :
        stats.status === 'inactive' ? 'border-l-gray-400 bg-gray-50' :
        'border-l-red-500 bg-red-50'
      }`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`h-3 w-3 rounded-full animate-pulse ${
              stats.status === 'active' ? 'bg-green-500' :
              stats.status === 'inactive' ? 'bg-gray-400' :
              'bg-red-500'
            }`} />
            <div>
              <h3 className="text-lg font-semibold text-gray-900">
                {stats.status === 'active' ? '🟢 Conectado' :
                 stats.status === 'inactive' ? '⚪ Desconectado' :
                 '🔴 Erro de Conexão'}
              </h3>
              <p className="text-sm text-gray-500">
                Verificado em: {new Date(stats.last_check).toLocaleString('pt-BR')}
              </p>
            </div>
          </div>
          <Server className="h-8 w-8 text-gray-400" />
        </div>

        {/* Error Message */}
        {stats.status === 'error' && stats.last_error && (
          <div className="mt-4 p-3 bg-red-100 border border-red-300 rounded-md">
            <div className="flex items-start gap-2">
              <XCircle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-red-800">Erro</p>
                <p className="text-sm text-red-700 mt-1">{stats.last_error}</p>
              </div>
            </div>
          </div>
        )}
      </Card>

      {/* Statistics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Total Instances */}
        <Card className="p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Total de Instâncias</p>
              <p className="text-3xl font-bold text-gray-900 mt-2">
                {stats.statistics.total}
              </p>
            </div>
            <div className="h-12 w-12 bg-blue-100 rounded-lg flex items-center justify-center">
              <Server className="h-6 w-6 text-blue-600" />
            </div>
          </div>
        </Card>

        {/* Connected */}
        <Card className="p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Conectadas</p>
              <p className="text-3xl font-bold text-green-600 mt-2">
                {stats.statistics.connected}
              </p>
            </div>
            <div className="h-12 w-12 bg-green-100 rounded-lg flex items-center justify-center">
              <CheckCircle className="h-6 w-6 text-green-600" />
            </div>
          </div>
          <div className="mt-2">
            <div className="h-2 w-full bg-gray-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-green-500 transition-all duration-300"
                style={{
                  width: `${stats.statistics.total > 0 
                    ? (stats.statistics.connected / stats.statistics.total) * 100 
                    : 0}%`
                }}
              />
            </div>
          </div>
        </Card>

        {/* Disconnected */}
        <Card className="p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Desconectadas</p>
              <p className="text-3xl font-bold text-red-600 mt-2">
                {stats.statistics.disconnected}
              </p>
            </div>
            <div className="h-12 w-12 bg-red-100 rounded-lg flex items-center justify-center">
              <XCircle className="h-6 w-6 text-red-600" />
            </div>
          </div>
          <div className="mt-2">
            <div className="h-2 w-full bg-gray-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-red-500 transition-all duration-300"
                style={{
                  width: `${stats.statistics.total > 0 
                    ? (stats.statistics.disconnected / stats.statistics.total) * 100 
                    : 0}%`
                }}
              />
            </div>
          </div>
        </Card>
      </div>

      {/* Webhook URL Card */}
      <Card className="p-6">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Webhook URL
            </label>
            <div className="flex items-center gap-2">
              <input
                type="text"
                readOnly
                value={stats.webhook_url}
                className="flex-1 px-4 py-2 text-sm bg-gray-50 border border-gray-300 rounded-md font-mono"
              />
              <Button
                onClick={handleCopyWebhook}
                variant="outline"
                size="sm"
              >
                {copied ? (
                  <Check className="h-4 w-4" />
                ) : (
                  <Copy className="h-4 w-4" />
                )}
              </Button>
            </div>
            <p className="mt-2 text-sm text-gray-500">
              Configure esta URL no servidor Evolution API para receber eventos de mensagens
            </p>
          </div>
        </div>
      </Card>

      {/* Instances List */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Instâncias ({stats.instances.length})
        </h2>

        {stats.instances.length === 0 ? (
          <Card className="p-8">
            <div className="text-center">
              <Server className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-600">Nenhuma instância encontrada</p>
              <p className="text-sm text-gray-500 mt-1">
                As instâncias aparecerão aqui quando forem configuradas no Evolution API
              </p>
            </div>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {stats.instances.map((instance, index) => (
              <Card
                key={index}
                className={`p-4 border-l-4 ${
                  instance.status === 'connected'
                    ? 'border-l-green-500 bg-green-50'
                    : 'border-l-red-500 bg-red-50'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      {instance.status === 'connected' ? (
                        <CheckCircle className="h-5 w-5 text-green-600" />
                      ) : (
                        <XCircle className="h-5 w-5 text-red-600" />
                      )}
                      <h3 className="font-semibold text-gray-900">
                        {instance.name}
                      </h3>
                    </div>
                    <p className="text-sm text-gray-600 mt-1">
                      Status: {instance.status === 'connected' ? 'Conectada' : 'Desconectada'}
                    </p>
                    <p className="text-xs text-gray-500 mt-1">
                      Raw: {instance.raw_status}
                    </p>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Configuration Note */}
      <Card className="p-4 bg-blue-50 border border-blue-200">
        <div className="flex items-start gap-3">
          <AlertCircle className="h-5 w-5 text-blue-600 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-blue-800">
            <p className="font-medium mb-1">ℹ️ Configuração via Variáveis de Ambiente</p>
            <p>
              A URL e API Key da Evolution API são configuradas via variáveis de ambiente (<code className="bg-blue-100 px-1 rounded">EVO_BASE_URL</code> e <code className="bg-blue-100 px-1 rounded">EVO_API_KEY</code>).
              Entre em contato com o administrador do sistema para alterações.
            </p>
          </div>
        </div>
      </Card>

      {/* Toast Notification */}
      <Toast
        show={toast.show}
        message={toast.message}
        type={toast.type}
        onClose={hideToast}
      />
    </div>
  )
}
