# 🎯 PROMPT: Dashboard Inicial Completo

## 📋 **REQUISITOS**

Implementar dashboard inicial do cliente com os seguintes cards:

1. **📊 Total de Mensagens** - Modificado para mostrar últimos 30 dias + hoje
2. **📢 Campanhas Ativas** - Novo card
3. **📍 Estados x Contatos** - Novo card (distribuição geográfica)
4. **✅ Status de Consentimento** - Novo card (opt-in/opt-out)
5. **Manter cards existentes:** Sentimento, Satisfação, Conexões

---

## 🎨 **LAYOUT PROPOSTO**

```
┌─────────────────────────────────────────────────────────────┐
│  DASHBOARD                                                   │
│  Visão geral das métricas de {Tenant}                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │ Mensagens   │ │ Campanhas   │ │ Contatos    │           │
│  │ 30d: 5.2k   │ │ 3 ativas    │ │ 350 totais  │           │
│  │ Hoje: 180   │ │ 2 pausadas  │ │ 320 opt-in  │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
│                                                              │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │ Sentimento  │ │ Satisfação  │ │ Conexões    │           │
│  │ 0.72 😊     │ │ 85%         │ │ 2 ativas    │           │
│  │ 80% positivo│ │ 5.2k msgs   │ │ 120ms       │           │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ 📍 DISTRIBUIÇÃO GEOGRÁFICA                            │  │
│  │ SP: 150 (43%)  ████████░░  RJ: 100 (29%)  █████░░░   │  │
│  │ MG: 50 (14%)   ██░░░░░░░░  PR: 30 (9%)    █░░░░░░░░  │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ ✅ STATUS DE CONSENTIMENTO (LGPD)                     │  │
│  │ [Gráfico Pizza 91%] 320 opt-in / 30 opt-out          │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 📝 **IMPLEMENTAÇÃO COMPLETA**

### **Arquivo:** `frontend/src/pages/DashboardPage.tsx`

```tsx
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
}

// ==================== COMPONENTE PRINCIPAL ====================

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const { user } = useAuthStore()

  // ==================== FETCH DATA ====================

  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        setIsLoading(true)
        
        // Fetch paralelo de todas as APIs
        const [metricsRes, campaignsRes, contactsRes] = await Promise.all([
          api.get(`/tenants/tenants/${user?.tenant?.id}/metrics/`),
          api.get('/campaigns/campaigns/?status=active,paused'),
          api.get('/contacts/contacts/')
        ])

        setData({
          metrics: metricsRes.data,
          campaigns: campaignsRes.data.results || campaignsRes.data,
          contacts: contactsRes.data.results || contactsRes.data
        })
      } catch (error) {
        console.error('Failed to fetch dashboard data:', error)
      } finally {
        setIsLoading(false)
      }
    }

    if (user?.tenant?.id) {
      fetchDashboardData()
    }
  }, [user?.tenant?.id])

  // ==================== HELPER FUNCTIONS ====================

  // Estados
  const getTopStates = (limit: number = 4): [string, number][] => {
    if (!data?.contacts) return []
    
    const stateCounts = data.contacts.reduce((acc, contact) => {
      const state = contact.state || 'N/A'
      acc[state] = (acc[state] || 0) + 1
      return acc
    }, {} as Record<string, number>)

    return Object.entries(stateCounts)
      .sort(([, a], [, b]) => b - a)
      .slice(0, limit)
  }

  const getUniqueStatesCount = (): number => {
    if (!data?.contacts) return 0
    const states = new Set(data.contacts.map(c => c.state).filter(Boolean))
    return states.size
  }

  // Opt-in/Out
  const getOptInContacts = (): number => {
    if (!data?.contacts) return 0
    return data.contacts.filter(c => !c.opted_out && c.is_active).length
  }

  const getOptOutContacts = (): number => {
    if (!data?.contacts) return 0
    return data.contacts.filter(c => c.opted_out).length
  }

  const getOptInRate = (): string => {
    if (!data?.contacts || data.contacts.length === 0) return "0.0"
    return ((getOptInContacts() / data.contacts.length) * 100).toFixed(1)
  }

  // Campanhas
  const getActiveCampaigns = (): number => {
    if (!data?.campaigns) return 0
    return data.campaigns.filter(c => c.status === 'active').length
  }

  const getPausedCampaigns = (): number => {
    if (!data?.campaigns) return 0
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
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-600">
          Visão geral das métricas de {user?.tenant?.name}
        </p>
      </div>

      {/* ==================== LINHA 1: CARDS PRINCIPAIS ==================== */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
        
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

        {/* 🆕 CARD 3: Contatos (Novo) */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Contatos</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {data.contacts.length}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {getUniqueStatesCount()} estados
            </p>
            <div className="flex items-center gap-2 mt-2 pt-2 border-t">
              <CheckCircle className="h-3 w-3 text-green-600" />
              <span className="text-sm text-green-600">
                {getOptInContacts()} aptos
              </span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* ==================== LINHA 2: MÉTRICAS SECUNDÁRIAS ==================== */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
        
        {/* CARD: Sentimento (Manter) */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Sentimento Médio</CardTitle>
            {getSentimentIcon(data.metrics.avg_sentiment)}
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${getSentimentColor(data.metrics.avg_sentiment)}`}>
              {Number(data.metrics.avg_sentiment).toFixed(2)}
            </div>
            <p className="text-xs text-muted-foreground">
              {Number(data.metrics.positive_messages_pct).toFixed(1)}% positivas
            </p>
          </CardContent>
        </Card>

        {/* CARD: Satisfação (Manter) */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Satisfação Média</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {Number(data.metrics.avg_satisfaction).toFixed(0)}%
            </div>
            <p className="text-xs text-muted-foreground">
              Baseado em {data.metrics.total_messages} mensagens
            </p>
          </CardContent>
        </Card>

        {/* CARD: Conexões (Manter) */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Conexões Ativas</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {data.metrics.active_connections}
            </div>
            <p className="text-xs text-muted-foreground">
              Latência média: {Number(data.metrics.avg_latency_ms).toFixed(0)}ms
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
```

---

## 📊 **BACKEND: ATUALIZAR API DE MÉTRICAS**

### **Arquivo:** `backend/apps/tenancy/views.py`

**Adicionar campo `messages_last_30_days` na API de métricas:**

```python
from datetime import datetime, timedelta
from django.utils import timezone

# No método que retorna as métricas
@action(detail=True, methods=['get'])
def metrics(self, request, pk=None):
    """Retorna métricas do tenant"""
    tenant = self.get_object()
    
    # Data de 30 dias atrás
    thirty_days_ago = timezone.now() - timedelta(days=30)
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Consultas
    total_messages = Message.objects.filter(tenant=tenant).count()
    messages_today = Message.objects.filter(
        tenant=tenant,
        created_at__gte=today_start
    ).count()
    
    # 🆕 NOVO: Mensagens dos últimos 30 dias
    messages_last_30_days = Message.objects.filter(
        tenant=tenant,
        created_at__gte=thirty_days_ago
    ).count()
    
    # ... resto das métricas ...
    
    return Response({
        'total_messages': total_messages,
        'messages_today': messages_today,
        'messages_last_30_days': messages_last_30_days,  # 🆕 NOVO
        'avg_sentiment': avg_sentiment,
        'avg_satisfaction': avg_satisfaction,
        'positive_messages_pct': positive_messages_pct,
        'active_connections': active_connections,
        'avg_latency_ms': avg_latency_ms,
    })
```

---

## ✅ **CHECKLIST DE IMPLEMENTAÇÃO**

### **Frontend**
- [ ] Atualizar `DashboardPage.tsx` com novo layout
- [ ] Adicionar imports de ícones (Play, Pause, MapPin, CheckCircle, XCircle, Send)
- [ ] Adicionar interfaces (Campaign, Contact, DashboardData)
- [ ] Implementar funções helper (getTopStates, getOptInContacts, etc)
- [ ] Adicionar fetch de campanhas e contatos em paralelo
- [ ] Implementar Card de Mensagens modificado
- [ ] Implementar Card de Campanhas Ativas
- [ ] Implementar Card de Contatos
- [ ] Implementar Card de Distribuição Geográfica
- [ ] Implementar Card de Status de Consentimento com gráfico pizza
- [ ] Manter cards existentes (Sentimento, Satisfação, Conexões, Plano)

### **Backend**
- [ ] Adicionar campo `messages_last_30_days` na API de métricas
- [ ] Testar retorno da API de métricas
- [ ] Verificar performance das queries (adicionar índices se necessário)

### **Testes**
- [ ] Testar dashboard com 0 contatos
- [ ] Testar dashboard com contatos mas sem estado
- [ ] Testar dashboard com campanhas ativas e pausadas
- [ ] Testar dashboard sem campanhas
- [ ] Testar responsividade mobile
- [ ] Testar loading states
- [ ] Testar cálculos de porcentagens

---

## 🎨 **CORES E ÍCONES UTILIZADOS**

```typescript
// Cores
const COLORS = {
  primary: 'blue-600',
  success: 'green-600',
  warning: 'amber-600',
  danger: 'red-600',
  muted: 'gray-500'
}

// Ícones (lucide-react)
import {
  MessageSquare,  // Mensagens
  Play,           // Campanhas ativas
  Pause,          // Campanhas pausadas
  Users,          // Contatos/Conexões
  MapPin,         // Geografia
  CheckCircle,    // Opt-in
  XCircle,        // Opt-out
  Send,           // Envio
  TrendingUp,     // Satisfação
  Smile, Frown, Meh // Sentimento
}
```

---

## 📱 **RESPONSIVIDADE**

```tsx
// Mobile: 1 coluna
// Tablet: 2 colunas
// Desktop: 3 colunas

<div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
  {/* Cards */}
</div>

// Cards grandes (Distribuição + Consentimento)
// Mobile: 1 coluna
// Desktop: 2 colunas lado a lado

<div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
  {/* Cards grandes */}
</div>
```

---

## 🚀 **FEATURES ADICIONAIS FUTURAS**

1. **Filtros de período:** Escolher 7, 15, 30, 90 dias
2. **Gráfico de linha:** Evolução de mensagens ao longo do tempo
3. **Click em estados:** Filtrar contatos daquele estado
4. **Export rápido:** Botão para exportar audiência disponível
5. **Alertas:** Avisar se opt-out subir muito
6. **Comparação:** Período atual vs período anterior

---

## 📚 **REFERÊNCIAS**

- **Frontend:** `frontend/src/pages/DashboardPage.tsx`
- **Backend:** `backend/apps/tenancy/views.py` (metrics endpoint)
- **Componentes UI:** `Card`, `CardHeader`, `CardTitle`, `CardContent`
- **Ícones:** lucide-react
- **APIs utilizadas:**
  - `/tenants/tenants/{id}/metrics/`
  - `/campaigns/campaigns/?status=active,paused`
  - `/contacts/contacts/`

---

**✅ PROMPT COMPLETO - DASHBOARD PRONTO PARA IMPLEMENTAR**




