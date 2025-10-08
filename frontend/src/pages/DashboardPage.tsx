import { useEffect, useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/Card'
import { api } from '../lib/api'
import { useAuthStore } from '../stores/authStore'
import { formatCurrency, formatDate } from '../lib/utils'
import { 
  MessageSquare, 
  TrendingUp, 
  Users, 
  Clock,
  Smile,
  Frown,
  Meh
} from 'lucide-react'

interface DashboardMetrics {
  total_messages: number
  avg_sentiment: number
  avg_satisfaction: number
  positive_messages_pct: number
  messages_today: number
  active_connections: number
  avg_latency_ms: number
}

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const { user } = useAuthStore()

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const response = await api.get(`/tenants/${user?.tenant?.id}/metrics/`)
        setMetrics(response.data)
      } catch (error) {
        console.error('Failed to fetch metrics:', error)
      } finally {
        setIsLoading(false)
      }
    }

    if (user?.tenant?.id) {
      fetchMetrics()
    }
  }, [user?.tenant?.id])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  if (!metrics) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">Não foi possível carregar as métricas</p>
      </div>
    )
  }

  const getSentimentIcon = (sentiment: number) => {
    if (sentiment >= 0.3) return <Smile className="h-5 w-5 text-green-600" />
    if (sentiment <= -0.3) return <Frown className="h-5 w-5 text-red-600" />
    return <Meh className="h-5 w-5 text-yellow-600" />
  }

  const getSentimentColor = (sentiment: number) => {
    if (sentiment >= 0.3) return 'text-green-600'
    if (sentiment <= -0.3) return 'text-red-600'
    return 'text-yellow-600'
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-600">
          Visão geral das métricas de {user?.tenant?.name}
        </p>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total de Mensagens</CardTitle>
            <MessageSquare className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics.total_messages.toLocaleString()}</div>
            <p className="text-xs text-muted-foreground">
              {metrics.messages_today} hoje
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Sentimento Médio</CardTitle>
            {getSentimentIcon(metrics.avg_sentiment)}
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${getSentimentColor(metrics.avg_sentiment)}`}>
              {metrics.avg_sentiment.toFixed(2)}
            </div>
            <p className="text-xs text-muted-foreground">
              {metrics.positive_messages_pct.toFixed(1)}% positivas
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Satisfação Média</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics.avg_satisfaction.toFixed(0)}%</div>
            <p className="text-xs text-muted-foreground">
              Baseado em {metrics.total_messages} mensagens
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Conexões Ativas</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics.active_connections}</div>
            <p className="text-xs text-muted-foreground">
              Latência média: {metrics.avg_latency_ms.toFixed(0)}ms
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Plan Info */}
      <Card>
        <CardHeader>
          <CardTitle>Informações do Plano</CardTitle>
          <CardDescription>
            Detalhes do seu plano atual
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div>
              <p className="text-sm font-medium text-gray-500">Plano</p>
              <p className="text-lg font-semibold capitalize">{user?.tenant?.plan}</p>
            </div>
            <div>
              <p className="text-sm font-medium text-gray-500">Status</p>
              <p className="text-lg font-semibold capitalize">{user?.tenant?.status}</p>
            </div>
            <div>
              <p className="text-sm font-medium text-gray-500">Próxima Cobrança</p>
              <p className="text-lg font-semibold">
                {user?.tenant?.next_billing_date 
                  ? formatDate(user.tenant.next_billing_date)
                  : 'N/A'
                }
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
