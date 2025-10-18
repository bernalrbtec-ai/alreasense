import { useEffect, useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/Card'
import { api } from '../lib/api'
import { useAuthStore } from '../stores/authStore'
import { formatDate } from '../lib/utils'
import { 
  MessageSquare, 
  TrendingUp, 
  Users, 
  Smile,
  Frown,
  Meh,
  Send,
  Play,
  Pause,
  MapPin,
  CheckCircle,
  XCircle
} from 'lucide-react'

// ==================== INTERFACES ====================

interface DashboardMetrics {
  // Mensagens
  total_messages: number
  messages_today: number
  messages_last_30_days: number
  
  // Sentimento (manter)
  avg_sentiment: number
  avg_satisfaction: number
  positive_messages_pct: number
  
  // Conexões (manter)
  active_connections: number
  avg_latency_ms: number
}

interface Campaign {
  id: string
  name: string
  status: 'draft' | 'active' | 'paused' | 'completed' | 'cancelled'
  total_contacts: number
  sent_count: number
  scheduled_date?: string
}

interface Contact {
  id: string
  name: string
  state?: string
  opted_out: boolean
  is_active: boolean
}

interface DashboardData {
  metrics: DashboardMetrics
  campaigns: Campaign[]
  contacts: Contact[]
  contactsStats?: {
    total: number
    active: number
    opted_out: number
    leads: number
    customers: number
    delivery_problems: number
  }
}

// ==================== COMPONENTE PRINCIPAL ====================

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isFirstLoad, setIsFirstLoad] = useState(true)
  const { user } = useAuthStore()

  // ==================== FETCH DATA ====================

  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        if (isFirstLoad) {
          setIsLoading(true)
        }
        
        // Fetch paralelo de todas as APIs
        const tenantId = user?.tenant_id || user?.tenant?.id;
        const [metricsRes, campaignsRes, contactsStatsRes] = await Promise.all([
          api.get(`/tenants/tenants/${tenantId}/metrics/`),
          api.get('/campaigns/?status=active,paused'),
          api.get('/contacts/contacts/stats/') // Usar endpoint de stats em vez de buscar todos
        ])

        setData({
          metrics: metricsRes.data,
          campaigns: Array.isArray(campaignsRes.data.results) ? campaignsRes.data.results : 
                    Array.isArray(campaignsRes.data) ? campaignsRes.data : [],
          contacts: [], // Não precisamos mais dos contatos individuais
          contactsStats: contactsStatsRes.data // Usar stats do backend
        })
        
        if (isFirstLoad) {
          setIsFirstLoad(false)
        }
      } catch (error) {
        console.error('Failed to fetch dashboard data:', error)
      } finally {
        if (isFirstLoad) {
          setIsLoading(false)
        }
      }
    }

    const tenantId = user?.tenant_id || user?.tenant?.id;
    if (tenantId) {
      fetchDashboardData()
      // Removido auto-refresh para evitar refresh visual
    }
  }, [user?.tenant_id, user?.tenant?.id])

  // ==================== HELPER FUNCTIONS ====================

  // Estados - TODO: Implementar endpoint de distribuição geográfica
  const getTopStates = (limit: number = 6): [string, number][] => {
    // Por enquanto, retornar dados mockados até implementar endpoint específico
    // TODO: Criar endpoint /contacts/contacts/geographic_distribution/
    return [
      ['RS', 33],
      ['GO', 17]
    ]
  }

  const getUniqueStatesCount = (): number => {
    // Por enquanto, retornar contagem mockada
    return 2
  }

  // Opt-in/Out - Usar stats do backend
  const getOptInContacts = (): number => {
    return data?.contactsStats?.active || 0
  }

  const getOptOutContacts = (): number => {
    return data?.contactsStats?.opted_out || 0
  }
  
  const getDeliveryFailureContacts = (): number => {
    return data?.contactsStats?.delivery_problems || 0
  }
  
  const getExitRateContacts = (): number => {
    return (data?.contactsStats?.opted_out || 0) + (data?.contactsStats?.delivery_problems || 0)
  }

  const getOptInRate = (): string => {
    const total = data?.contactsStats?.total || 0
    const active = data?.contactsStats?.active || 0
    if (total === 0) return "0.0"
    return ((active / total) * 100).toFixed(1)
  }

  const getTotalContacts = (): number => {
    return data?.contactsStats?.total || 0
  }

  // Campanhas
  const getActiveCampaigns = (): number => {
    if (!data?.campaigns || !Array.isArray(data.campaigns)) return 0
    return data.campaigns.filter(c => c.status === 'active').length
  }

  const getPausedCampaigns = (): number => {
    if (!data?.campaigns || !Array.isArray(data.campaigns)) return 0
    return data.campaigns.filter(c => c.status === 'paused').length
  }

  // Sentimento
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

  // ==================== LOADING & ERROR STATES ====================

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">Não foi possível carregar o dashboard</p>
      </div>
    )
  }

  // ==================== RENDER ====================

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl sm:text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-sm sm:text-base text-gray-600">
          Visão geral das métricas de {user?.tenant?.name}
        </p>
      </div>

      {/* ==================== LINHA 1: CARDS PRINCIPAIS ==================== */}
      <div className="grid grid-cols-1 gap-4 sm:gap-6 sm:grid-cols-2 lg:grid-cols-3">
        
        {/* 🆕 CARD 1: Mensagens (Modificado) */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Mensagens</CardTitle>
            <MessageSquare className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {data.metrics.messages_last_30_days?.toLocaleString() || 0}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Últimos 30 dias
            </p>
            <div className="flex items-center gap-2 mt-2 pt-2 border-t">
              <Send className="h-3 w-3 text-blue-600" />
              <span className="text-sm font-medium text-blue-600">
                {data.metrics.messages_today || 0} hoje
              </span>
            </div>
          </CardContent>
        </Card>

        {/* 🆕 CARD 2: Campanhas Ativas (Novo) */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Campanhas</CardTitle>
            <Play className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {getActiveCampaigns()}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {getActiveCampaigns() === 1 ? 'campanha ativa' : 'campanhas ativas'}
            </p>
            {getPausedCampaigns() > 0 && (
              <div className="flex items-center gap-2 mt-2 pt-2 border-t">
                <Pause className="h-3 w-3 text-amber-600" />
                <span className="text-sm text-amber-600">
                  {getPausedCampaigns()} pausadas
                </span>
              </div>
            )}
          </CardContent>
        </Card>

        {/* 🆕 CARD 3: Taxa de Saída (Novo) */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Taxa de Saída</CardTitle>
            <XCircle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="flex items-end gap-4">
              <div className="text-2xl font-bold text-red-600">
                {getExitRateContacts()}
              </div>
              <div className="flex flex-col gap-1 text-xs pb-1">
                <div className="text-gray-600">
                  <span className="font-medium">Opt-out:</span>{' '}
                  <span className="text-red-600 font-semibold">
                    {getOptOutContacts()}
                  </span>
                </div>
                <div className="text-gray-600">
                  <span className="font-medium">Falha:</span>{' '}
                  <span className="text-red-600 font-semibold">
                    {getDeliveryFailureContacts()}
                  </span>
                </div>
              </div>
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              de {getTotalContacts()} contatos totais
            </p>
          </CardContent>
        </Card>
      </div>

      {/* ==================== LINHA 2: MÉTRICAS SECUNDÁRIAS ==================== */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
        
        {/* CARD: Sentimento */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Sentimento Médio</CardTitle>
            <Smile className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-gray-400">
              --
            </div>
            <p className="text-xs text-muted-foreground">
              Em breve
            </p>
          </CardContent>
        </Card>

        {/* CARD: Satisfação */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Satisfação Média</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-gray-400">
              --
            </div>
            <p className="text-xs text-muted-foreground">
              Em breve
            </p>
          </CardContent>
        </Card>

        {/* CARD: Instâncias Conectadas */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Instâncias Conectadas</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {data.metrics.active_connections}
            </div>
            <p className="text-xs text-muted-foreground">
              Instâncias WhatsApp ativas
            </p>
          </CardContent>
        </Card>
      </div>

      {/* ==================== LINHA 3: INDICADORES AVANÇADOS ==================== */}
      {data.contacts.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          
          {/* 🆕 CARD: Distribuição Geográfica */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <MapPin className="h-5 w-5 text-blue-600" />
                  <CardTitle>Distribuição Geográfica</CardTitle>
                </div>
                <span className="text-xs text-gray-500">
                  {getUniqueStatesCount()} estados
                </span>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {getTopStates(6).map(([state, count]) => {
                  const percentage = (count / data.contacts.length) * 100
                  return (
                    <div key={state}>
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-sm font-medium text-gray-700">
                          {state || 'Não informado'}
                        </span>
                        <span className="text-xs text-gray-500">
                          {count} ({percentage.toFixed(1)}%)
                        </span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                          className={`h-2 rounded-full transition-all ${
                            state && state !== 'N/A' ? 'bg-blue-500' : 'bg-gray-400'
                          }`}
                          style={{ width: `${percentage}%` }}
                        />
                      </div>
                    </div>
                  )
                })}
              </div>
              
              {getUniqueStatesCount() > 6 && (
                <div className="mt-3 text-center text-xs text-gray-400">
                  +{getUniqueStatesCount() - 6} outros estados
                </div>
              )}
            </CardContent>
          </Card>

          {/* 🆕 CARD: Status de Consentimento (Opt-in/Out) */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <CheckCircle className="h-5 w-5 text-green-600" />
                  <CardTitle>Status de Consentimento</CardTitle>
                </div>
                <span className="text-xs text-gray-500">LGPD</span>
              </div>
            </CardHeader>
            <CardContent>
              {/* Gráfico Pizza */}
              <div className="flex items-center justify-center mb-4">
                <div className="relative w-32 h-32">
                  <svg className="w-32 h-32 transform -rotate-90">
                    {/* Círculo base (opt-out) */}
                    <circle
                      cx="64"
                      cy="64"
                      r="56"
                      fill="none"
                      stroke="#FEE2E2"
                      strokeWidth="16"
                    />
                    {/* Círculo principal (opt-in) */}
                    <circle
                      cx="64"
                      cy="64"
                      r="56"
                      fill="none"
                      stroke="#10B981"
                      strokeWidth="16"
                      strokeDasharray={`${(Number(getOptInRate()) / 100) * 352} 352`}
                      className="transition-all duration-500"
                    />
                  </svg>
                  {/* Texto central */}
                  <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <div className="text-2xl font-bold text-green-600">
                      {getOptInRate()}%
                    </div>
                    <div className="text-xs text-gray-500">opt-in</div>
                  </div>
                </div>
              </div>

              {/* Estatísticas */}
              <div className="space-y-2.5">
                <div className="flex items-center justify-between p-2.5 bg-green-50 rounded-lg">
                  <div className="flex items-center gap-2">
                    <CheckCircle className="h-4 w-4 text-green-600" />
                    <span className="text-sm font-medium text-gray-700">
                      Opt-in (Aptos)
                    </span>
                  </div>
                  <span className="text-sm font-bold text-green-600">
                    {getOptInContacts()}
                  </span>
                </div>

                <div className="flex items-center justify-between p-2.5 bg-red-50 rounded-lg">
                  <div className="flex items-center gap-2">
                    <XCircle className="h-4 w-4 text-red-600" />
                    <span className="text-sm font-medium text-gray-700">
                      Opt-out (Bloqueados)
                    </span>
                  </div>
                  <span className="text-sm font-bold text-red-600">
                    {getOptOutContacts()}
                  </span>
                </div>
              </div>

              {/* Alerta */}
              <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                <div className="flex items-start gap-2">
                  <Send className="h-4 w-4 text-blue-600 mt-0.5" />
                  <div className="flex-1">
                    <div className="text-xs font-medium text-blue-900 mb-0.5">
                      Audiência disponível
                    </div>
                    <div className="text-xs text-blue-700">
                      <span className="font-bold">{getOptInContacts()}</span> contatos 
                      podem receber campanhas
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* ==================== CARD: INFO DO PLANO (Manter) ==================== */}
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
