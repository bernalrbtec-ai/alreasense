/**
 * Página principal da Billing API
 * Dashboard com visão geral e acesso rápido às funcionalidades
 */
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { 
  Key, 
  FileText, 
  Send, 
  BarChart3, 
  Settings,
  Plus,
  ArrowRight,
  CheckCircle,
  Clock,
  AlertCircle
} from 'lucide-react'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import { api } from '../lib/api'

interface Stats {
  total_campaigns: number
  total_sent: number
  total_failed: number
  active_queues: number
}

export default function BillingApiPage() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [loading, setLoading] = useState(true)

  // TODO: Buscar stats da API quando endpoint estiver disponível
  // useEffect(() => {
  //   fetchStats()
  // }, [])

  // const fetchStats = async () => {
  //   try {
  //     const response = await api.get('/billing/v1/billing/stats/')
  //     setStats(response.data)
  //   } catch (error) {
  //     console.error('Erro ao buscar stats:', error)
  //   } finally {
  //     setLoading(false)
  //   }
  // }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
          Billing API
        </h1>
        <p className="mt-2 text-gray-600 dark:text-gray-400">
          Sistema de cobrança e notificações via WhatsApp
        </p>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <div className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600 dark:text-gray-400">Campanhas</p>
                  <p className="text-2xl font-bold text-gray-900 dark:text-white">
                    {stats.total_campaigns}
                  </p>
                </div>
                <BarChart3 className="h-8 w-8 text-brand-500" />
              </div>
            </div>
          </Card>

          <Card>
            <div className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600 dark:text-gray-400">Enviadas</p>
                  <p className="text-2xl font-bold text-green-600">
                    {stats.total_sent}
                  </p>
                </div>
                <CheckCircle className="h-8 w-8 text-green-500" />
              </div>
            </div>
          </Card>

          <Card>
            <div className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600 dark:text-gray-400">Falhas</p>
                  <p className="text-2xl font-bold text-red-600">
                    {stats.total_failed}
                  </p>
                </div>
                <AlertCircle className="h-8 w-8 text-red-500" />
              </div>
            </div>
          </Card>

          <Card>
            <div className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600 dark:text-gray-400">Filas Ativas</p>
                  <p className="text-2xl font-bold text-brand-600">
                    {stats.active_queues}
                  </p>
                </div>
                <Clock className="h-8 w-8 text-brand-500" />
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="hover:shadow-lg transition-shadow">
          <Link to="/billing-api/keys" className="block p-6">
            <div className="flex items-center justify-between mb-4">
              <Key className="h-8 w-8 text-brand-500" />
              <ArrowRight className="h-5 w-5 text-gray-400" />
            </div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
              API Keys
            </h3>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Gerencie suas chaves de API para integração
            </p>
          </Link>
        </Card>

        <Card className="hover:shadow-lg transition-shadow">
          <Link to="/billing-api/templates" className="block p-6">
            <div className="flex items-center justify-between mb-4">
              <FileText className="h-8 w-8 text-brand-500" />
              <ArrowRight className="h-5 w-5 text-gray-400" />
            </div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
              Templates
            </h3>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Configure templates de mensagens de cobrança
            </p>
          </Link>
        </Card>

        <Card className="hover:shadow-lg transition-shadow">
          <Link to="/billing-api/campaigns" className="block p-6">
            <div className="flex items-center justify-between mb-4">
              <Send className="h-8 w-8 text-brand-500" />
              <ArrowRight className="h-5 w-5 text-gray-400" />
            </div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
              Campanhas
            </h3>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Crie e monitore campanhas de billing
            </p>
          </Link>
        </Card>

        <Card className="hover:shadow-lg transition-shadow">
          <Link to="/billing-api/settings" className="block p-6">
            <div className="flex items-center justify-between mb-4">
              <Settings className="h-8 w-8 text-brand-500" />
              <ArrowRight className="h-5 w-5 text-gray-400" />
            </div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
              Configurações
            </h3>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Configure limites e comportamentos
            </p>
          </Link>
        </Card>
      </div>

      {/* API Documentation */}
      <Card>
        <div className="p-6">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
            Documentação da API
          </h2>
          <p className="text-gray-600 dark:text-gray-400 mb-4">
            Use os endpoints abaixo para integrar seu sistema com a Billing API:
          </p>
          <div className="space-y-2 font-mono text-sm">
            <div className="bg-gray-100 dark:bg-gray-800 p-3 rounded">
              <span className="text-green-600">POST</span> /api/billing/v1/billing/send/overdue
            </div>
            <div className="bg-gray-100 dark:bg-gray-800 p-3 rounded">
              <span className="text-green-600">POST</span> /api/billing/v1/billing/send/upcoming
            </div>
            <div className="bg-gray-100 dark:bg-gray-800 p-3 rounded">
              <span className="text-green-600">POST</span> /api/billing/v1/billing/send/notification
            </div>
            <div className="bg-gray-100 dark:bg-gray-800 p-3 rounded">
              <span className="text-blue-600">GET</span> /api/billing/v1/billing/queue/{'{queue_id}'}/status
            </div>
            <div className="bg-gray-100 dark:bg-gray-800 p-3 rounded">
              <span className="text-blue-600">GET</span> /api/billing/v1/billing/campaign/{'{campaign_id}'}/contacts
            </div>
          </div>
          <p className="mt-4 text-sm text-gray-500 dark:text-gray-400">
            Todas as requisições requerem o header: <code className="bg-gray-100 dark:bg-gray-800 px-2 py-1 rounded">X-Billing-API-Key</code>
          </p>
        </div>
      </Card>
    </div>
  )
}

