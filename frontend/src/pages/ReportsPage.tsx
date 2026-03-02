import { useEffect, useMemo, useState } from 'react'
import {
  BarChart3,
  Clock,
  Mic,
  RefreshCcw,
  XCircle,
  CheckCircle,
  Database,
  TrendingUp,
  Zap,
  Cpu,
  MessageSquare,
  FileText,
  Send,
  Inbox,
} from 'lucide-react'
import { toast } from 'sonner'
import {
  ResponsiveContainer,
  LineChart,
  Line,
  Area,
  AreaChart,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
  PieChart,
  Pie,
  Cell,
} from 'recharts'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { api } from '../lib/api'
import { PermissionGuard } from '../components/PermissionGuard'

interface MetricSeriesItem {
  date: string
  minutes_total: number
  audio_count: number
  success_count: number
  failed_count: number
  quality_correct_count: number
  quality_incorrect_count: number
  quality_unrated_count: number
  avg_latency_ms: number | null
  models_used: Record<string, number>
}

interface MetricsResponse {
  range: {
    from: string
    to: string
    timezone: string
  }
  totals: {
    minutes_total: number
    avg_minutes_per_day: number
    audio_count: number
    success_count: number
    failed_count: number
    quality_correct_count: number
    quality_incorrect_count: number
    quality_unrated_count: number
    avg_latency_ms: number | null
    models_used: Record<string, number>
  }
  series: MetricSeriesItem[]
}

interface DepartmentUserMetric {
  department_id: string | null
  department_name: string
  user_id: string
  user_name: string
  total_sent: number
  by_date: Array<{ date: string; sent: number }>
}

interface MessageMetricsResponse {
  range: { from: string; to: string; timezone: string }
  totals: { total: number; sent: number; received: number }
  series_by_hour: Array<{ hour: number; total: number; sent: number; received: number }>
  series_by_date: Array<{ date: string; total: number; sent: number; received: number }>
  avg_first_response_seconds: number | null
  by_user: Array<{
    user_id: string
    email: string
    first_name: string
    last_name: string
    total_sent: number
    avg_first_response_seconds: number | null
  }>
  by_department_user?: DepartmentUserMetric[]
  series_by_hour_by_department?: Array<{
    department_id: string | null
    department_name: string
    by_hour: Array<{ hour: number; total: number; avg: number }>
  }>
  by_department_summary?: Array<{
    department_id: string | null
    department_name: string
    total_period: number
    avg_per_day: number
    peak_hour: number
    peak_count: number
    quiet_hour: number
    quiet_count: number
    sent: number
    received: number
  }>
  secretary_metrics?: {
    total_period: number
    avg_per_day: number
    peak_hour: number
    peak_count: number
    quiet_hour: number
    quiet_count: number
    sent: number
    by_hour: Array<{ hour: number; total: number; avg: number }>
  }
  num_days?: number
}

const getDefaultRange = () => {
  const to = new Date()
  const from = new Date()
  from.setDate(to.getDate() - 30)
  return {
    from: from.toISOString().slice(0, 10),
    to: to.toISOString().slice(0, 10),
  }
}

function formatFirstResponse(seconds: number | null): string {
  if (seconds == null) return '—'
  if (seconds < 60) return `${Math.round(seconds)} s`
  const min = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return s ? `${min} min ${s} s` : `${min} min`
}

export default function ReportsPage() {
  const defaultRange = useMemo(() => getDefaultRange(), [])
  const [activeReportTab, setActiveReportTab] = useState<'messages' | 'transcriptions'>('transcriptions')
  const [createdFrom, setCreatedFrom] = useState(defaultRange.from)
  const [createdTo, setCreatedTo] = useState(defaultRange.to)
  const [departmentId, setDepartmentId] = useState('')
  const [agentId, setAgentId] = useState('')
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [isRebuilding, setIsRebuilding] = useState(false)

  const [msgFrom, setMsgFrom] = useState(defaultRange.from)
  const [msgTo, setMsgTo] = useState(defaultRange.to)
  const [messageMetrics, setMessageMetrics] = useState<MessageMetricsResponse | null>(null)
  const [messageMetricsLoading, setMessageMetricsLoading] = useState(false)
  const [messageMetricsError, setMessageMetricsError] = useState('')
  const [messageMetricsRebuilding, setMessageMetricsRebuilding] = useState(false)

  const fetchMetrics = async () => {
    setIsLoading(true)
    setError('')
    try {
      const params: Record<string, string> = {}
      if (createdFrom) params.created_from = createdFrom
      if (createdTo) params.created_to = createdTo
      if (departmentId) params.department_id = departmentId
      if (agentId) params.agent_id = agentId

      const response = await api.get('/ai/transcription/metrics/', { params })
      setMetrics(response.data)
    } catch (err) {
      setError('Não foi possível carregar o relatório de transcrição.')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchMetrics()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const fetchMessageMetrics = async () => {
    setMessageMetricsLoading(true)
    setMessageMetricsError('')
    try {
      const params: Record<string, string> = {}
      if (msgFrom) params.created_from = msgFrom
      if (msgTo) params.created_to = msgTo
      const response = await api.get<MessageMetricsResponse>('/chat/metrics/messages/', { params })
      setMessageMetrics(response.data)
    } catch {
      setMessageMetricsError('Não foi possível carregar as métricas de mensagens.')
    } finally {
      setMessageMetricsLoading(false)
    }
  }

  useEffect(() => {
    if (activeReportTab === 'messages') fetchMessageMetrics()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeReportTab])

  const handleMessageRebuild = async () => {
    if (!msgFrom || !msgTo) {
      toast.error('Selecione um período para rebuild')
      return
    }
    setMessageMetricsRebuilding(true)
    try {
      const response = await api.post<{
        status: string
        message: string
        days_processed: number
        totals: { total: number; sent: number; received: number }
      }>('/chat/metrics/messages/rebuild/', { from: msgFrom, to: msgTo })
      toast.success(response.data.message, {
        description: `${response.data.days_processed} dia(s) processado(s). ${response.data.totals.total} mensagens no total.`,
      })
      await fetchMessageMetrics()
    } catch (err: any) {
      toast.error('Erro ao executar rebuild', {
        description: err.response?.data?.error || 'Tente novamente',
      })
    } finally {
      setMessageMetricsRebuilding(false)
    }
  }

  const handleRebuild = async () => {
    if (!createdFrom || !createdTo) {
      toast.error('Selecione um período para rebuild')
      return
    }

    setIsRebuilding(true)
    try {
      const response = await api.post('/ai/transcription/metrics/rebuild/', {
        from: createdFrom,
        to: createdTo,
      })
      
      toast.success(
        `Rebuild concluído! ${response.data.days_processed} dias processados.`,
        {
          description: `${response.data.totals.audio_count} áudios processados`,
        }
      )
      
      // Recarrega as métricas após rebuild
      await fetchMetrics()
    } catch (err: any) {
      toast.error('Erro ao executar rebuild', {
        description: err.response?.data?.error || 'Tente novamente',
      })
    } finally {
      setIsRebuilding(false)
    }
  }

  const chartData = metrics?.series || []

  return (
    <PermissionGuard require="admin">
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Relatórios</h1>
          <p className="mt-2 text-gray-600 dark:text-gray-400">
            KPIs e métricas de mensagens e transcrição
          </p>
        </div>

        <div className="border-b border-gray-200 dark:border-gray-700">
          <nav className="-mb-px flex space-x-8">
            <button
              type="button"
              onClick={() => setActiveReportTab('messages')}
              className={`py-2 px-1 border-b-2 font-medium text-sm flex items-center gap-2 ${
                activeReportTab === 'messages'
                  ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-300'
              }`}
            >
              <MessageSquare className="h-4 w-4" />
              Mensagens
            </button>
            <button
              type="button"
              onClick={() => setActiveReportTab('transcriptions')}
              className={`py-2 px-1 border-b-2 font-medium text-sm flex items-center gap-2 ${
                activeReportTab === 'transcriptions'
                  ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-300'
              }`}
            >
              <FileText className="h-4 w-4" />
              Transcrições
            </button>
          </nav>
        </div>

        {activeReportTab === 'messages' && (
          <>
            <Card>
              <div className="p-6 space-y-4">
                <div className="flex flex-wrap items-end gap-4">
                  <div className="flex flex-col gap-1">
                    <label className="text-sm text-gray-600 dark:text-gray-400">De</label>
                    <input
                      type="date"
                      value={msgFrom}
                      onChange={(e) => setMsgFrom(e.target.value)}
                      className="rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm"
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className="text-sm text-gray-600 dark:text-gray-400">Até</label>
                    <input
                      type="date"
                      value={msgTo}
                      onChange={(e) => setMsgTo(e.target.value)}
                      className="rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm"
                    />
                  </div>
                  <Button onClick={fetchMessageMetrics} disabled={messageMetricsLoading}>
                    <RefreshCcw className="h-4 w-4 mr-2" />
                    Atualizar
                  </Button>
                  <Button
                    onClick={handleMessageRebuild}
                    disabled={messageMetricsRebuilding || messageMetricsLoading}
                    variant="outline"
                    className="border-orange-200 dark:border-orange-800 text-orange-600 dark:text-orange-400 hover:bg-orange-50 dark:hover:bg-orange-900/20"
                  >
                    <Database className="h-4 w-4 mr-2" />
                    {messageMetricsRebuilding ? 'Processando...' : 'Rebuild Métricas'}
                  </Button>
                </div>
                {messageMetricsError && (
                  <p className="text-sm text-red-600 dark:text-red-400">{messageMetricsError}</p>
                )}
              </div>
            </Card>

            {messageMetricsLoading && (
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                {[1, 2, 3, 4].map((i) => (
                  <Card key={i}>
                    <div className="p-4 h-20 animate-pulse bg-gray-100 dark:bg-gray-800 rounded" />
                  </Card>
                ))}
              </div>
            )}

            {!messageMetricsLoading && messageMetrics && (
              <>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <Card>
                    <div className="p-4 flex items-center justify-between">
                      <div>
                        <p className="text-sm text-gray-600 dark:text-gray-400">Total de mensagens</p>
                        <p className="text-2xl font-bold text-gray-900 dark:text-white">
                          {messageMetrics.totals.total}
                        </p>
                      </div>
                      <MessageSquare className="h-8 w-8 text-brand-500" />
                    </div>
                  </Card>
                  <Card>
                    <div className="p-4 flex items-center justify-between">
                      <div>
                        <p className="text-sm text-gray-600 dark:text-gray-400">Enviadas</p>
                        <p className="text-2xl font-bold text-green-600">
                          {messageMetrics.totals.sent}
                        </p>
                      </div>
                      <Send className="h-8 w-8 text-green-500" />
                    </div>
                  </Card>
                  <Card>
                    <div className="p-4 flex items-center justify-between">
                      <div>
                        <p className="text-sm text-gray-600 dark:text-gray-400">Recebidas</p>
                        <p className="text-2xl font-bold text-blue-600">
                          {messageMetrics.totals.received}
                        </p>
                      </div>
                      <Inbox className="h-8 w-8 text-blue-500" />
                    </div>
                  </Card>
                  <Card>
                    <div className="p-4 flex items-center justify-between">
                      <div>
                        <p className="text-sm text-gray-600 dark:text-gray-400">Tempo médio de 1ª resposta</p>
                        <p className="text-2xl font-bold text-gray-900 dark:text-white">
                          {formatFirstResponse(messageMetrics.avg_first_response_seconds)}
                        </p>
                      </div>
                      <Clock className="h-8 w-8 text-brand-500" />
                    </div>
                  </Card>
                </div>

                <div className="space-y-6">
                  {/* Cards por departamento + BIA (quando secretary_enabled) */}
                  {((messageMetrics.by_department_summary?.length ?? 0) > 0 || messageMetrics.secretary_metrics) && (
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                      {messageMetrics.secretary_metrics && (
                        <Card key="bia" className="p-5 border-l-4 border-l-violet-500">
                          <div className="flex items-center gap-2 mb-4">
                            <div className="w-3 h-3 rounded-sm shrink-0 bg-violet-500" />
                            <h3 className="font-semibold text-gray-900 dark:text-white">
                              BIA (Secretária IA)
                            </h3>
                          </div>
                          <div className="space-y-3 text-sm">
                            <div className="flex justify-between">
                              <span className="text-gray-600 dark:text-gray-400">Total no período</span>
                              <span className="font-medium tabular-nums">{messageMetrics.secretary_metrics.total_period.toLocaleString('pt-BR')}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-600 dark:text-gray-400">Média por dia</span>
                              <span className="font-medium tabular-nums">{messageMetrics.secretary_metrics.avg_per_day.toLocaleString('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: 3 })}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-600 dark:text-gray-400">Horário de pico</span>
                              <span className="font-medium tabular-nums">{messageMetrics.secretary_metrics.peak_hour}h ({messageMetrics.secretary_metrics.peak_count.toLocaleString('pt-BR')} msg)</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-600 dark:text-gray-400">Horário tranquilo</span>
                              <span className="font-medium tabular-nums">{messageMetrics.secretary_metrics.quiet_hour}h ({messageMetrics.secretary_metrics.quiet_count.toLocaleString('pt-BR')} msg)</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-600 dark:text-gray-400">Enviadas</span>
                              <span className="font-medium tabular-nums text-green-600 dark:text-green-400">{messageMetrics.secretary_metrics.sent.toLocaleString('pt-BR')}</span>
                            </div>
                          </div>
                        </Card>
                      )}
                      {(messageMetrics.by_department_summary ?? []).map((dept, i) => {
                        const colors = ['#3b82f6', '#10b981', '#a855f7', '#f59e0b', '#06b6d4', '#ec4899']
                        const color = colors[i % colors.length]
                        return (
                          <Card key={dept.department_id ?? 'inbox'} className="p-5">
                            <div className="flex items-center gap-2 mb-4">
                              <div
                                className="w-3 h-3 rounded-sm shrink-0"
                                style={{ backgroundColor: color }}
                              />
                              <h3 className="font-semibold text-gray-900 dark:text-white truncate">
                                {dept.department_name}
                              </h3>
                            </div>
                            <div className="space-y-3 text-sm">
                              <div className="flex justify-between">
                                <span className="text-gray-600 dark:text-gray-400">Total no período</span>
                                <span className="font-medium tabular-nums">{dept.total_period.toLocaleString('pt-BR')}</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-gray-600 dark:text-gray-400">Média por dia</span>
                                <span className="font-medium tabular-nums">{dept.avg_per_day.toLocaleString('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: 3 })}</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-gray-600 dark:text-gray-400">Horário de pico</span>
                                <span className="font-medium tabular-nums">{dept.peak_hour}h ({dept.peak_count.toLocaleString('pt-BR')} msg)</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-gray-600 dark:text-gray-400">Horário tranquilo</span>
                                <span className="font-medium tabular-nums">{dept.quiet_hour}h ({dept.quiet_count.toLocaleString('pt-BR')} msg)</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-gray-600 dark:text-gray-400">Enviadas</span>
                                <span className="font-medium tabular-nums text-green-600 dark:text-green-400">{dept.sent.toLocaleString('pt-BR')}</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-gray-600 dark:text-gray-400">Recebidas</span>
                                <span className="font-medium tabular-nums text-blue-600 dark:text-blue-400">{dept.received.toLocaleString('pt-BR')}</span>
                              </div>
                            </div>
                          </Card>
                        )
                      })}
                    </div>
                  )}

                  {/* Gráfico: Média de Mensagens por Hora do Dia */}
                  {((messageMetrics.series_by_hour_by_department?.length ?? 0) > 0 || messageMetrics.secretary_metrics) ? (
                    <Card>
                      <div className="p-6">
                        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-1">
                          Média de Mensagens por Hora do Dia
                        </h2>
                        <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
                          Por departamento{messageMetrics.secretary_metrics ? ' e BIA' : ''} ({messageMetrics.range.from} a {messageMetrics.range.to} — {messageMetrics.num_days ?? 1} dia(s))
                        </p>
                        <div className="h-80">
                          <ResponsiveContainer width="100%" height="100%">
                            <AreaChart
                              data={Array.from({ length: 24 }, (_, h) => {
                                const row: Record<string, string | number> = { hour: h, hourLabel: `${h}h` }
                                ;(messageMetrics.series_by_hour_by_department ?? []).forEach((d) => {
                                  const bh = d.by_hour.find((b) => b.hour === h)
                                  row[d.department_name] = bh ? Math.round(bh.avg * 100) / 100 : 0
                                })
                                if (messageMetrics.secretary_metrics) {
                                  const bh = messageMetrics.secretary_metrics.by_hour.find((b) => b.hour === h)
                                  row['BIA'] = bh ? Math.round(bh.avg * 100) / 100 : 0
                                }
                                return row
                              })}
                              margin={{ top: 10, right: 20, left: 10, bottom: 10 }}
                            >
                              <defs>
                                <linearGradient id="grad-hour-bia" x1="0" y1="0" x2="0" y2="1">
                                  <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.25} />
                                  <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0} />
                                </linearGradient>
                                {['#3b82f6', '#10b981', '#a855f7', '#f59e0b', '#06b6d4', '#ec4899'].map((color, i) => (
                                  <linearGradient key={i} id={`grad-hour-${i}`} x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="0%" stopColor={color} stopOpacity={0.25} />
                                    <stop offset="100%" stopColor={color} stopOpacity={0} />
                                  </linearGradient>
                                ))}
                              </defs>
                              <CartesianGrid strokeDasharray="3 3" className="stroke-gray-200 dark:stroke-gray-700" />
                              <XAxis
                                dataKey="hourLabel"
                                tick={{ fill: 'currentColor', fontSize: 11 }}
                              />
                              <YAxis
                                tick={{ fill: 'currentColor', fontSize: 11 }}
                                label={{
                                  value: 'Média de Mensagens',
                                  angle: -90,
                                  position: 'insideLeft',
                                  style: { fontSize: 11 },
                                }}
                              />
                              <Tooltip
                                contentStyle={{ borderRadius: 8 }}
                                labelFormatter={(label) => label}
                                formatter={(value: number) => [`${Math.round(value * 10) / 10} msg`, '']}
                              />
                              <Legend wrapperStyle={{ paddingTop: 8 }} />
                              {messageMetrics.secretary_metrics && (
                                <Area
                                  key="bia"
                                  type="monotone"
                                  dataKey="BIA"
                                  stroke="#8b5cf6"
                                  strokeWidth={2}
                                  fill="url(#grad-hour-bia)"
                                  dot={{ r: 3, fill: '#8b5cf6' }}
                                  activeDot={{ r: 5 }}
                                  isAnimationActive
                                />
                              )}
                              {(messageMetrics.series_by_hour_by_department ?? []).map((d, i) => {
                                const colors = ['#3b82f6', '#10b981', '#a855f7', '#f59e0b', '#06b6d4']
                                const c = colors[i % colors.length]
                                return (
                                  <Area
                                    key={d.department_id ?? 'inbox'}
                                    type="monotone"
                                    dataKey={d.department_name}
                                    stroke={c}
                                    strokeWidth={2}
                                    fill={`url(#grad-hour-${i})`}
                                    dot={{ r: 3, fill: c }}
                                    activeDot={{ r: 5 }}
                                    isAnimationActive
                                  />
                                )
                              })}
                            </AreaChart>
                          </ResponsiveContainer>
                        </div>
                      </div>
                    </Card>
                  ) : (
                    <Card>
                      <div className="p-6 flex items-center justify-center h-80 text-gray-500 dark:text-gray-400 text-sm">
                        Sem dados por departamento para exibir gráfico.
                      </div>
                    </Card>
                  )}
                </div>

                {(messageMetrics.by_department_user?.length ?? 0) > 0 && (
                  <Card>
                    <div className="p-6">
                      <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                        Departamento × Usuário × Mensagens × Dia
                      </h2>
                      <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
                        Quem conversa mais ou menos por departamento (mensagens enviadas) — {messageMetrics.range.from} a {messageMetrics.range.to}
                      </p>
                      <div className="h-96">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart
                            data={messageMetrics.by_department_user!.map((d) => ({
                              name: `${d.department_name} – ${d.user_name}`,
                              department_name: d.department_name,
                              user_name: d.user_name,
                              total_sent: d.total_sent,
                              by_date: d.by_date,
                            }))}
                            layout="vertical"
                            margin={{ left: 100 }}
                            animationDuration={600}
                            animationEasing="ease-out"
                          >
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis type="number" />
                            <YAxis type="category" dataKey="name" width={100} tick={{ fontSize: 11 }} />
                            <Tooltip
                              formatter={(value: number) => [`${value} mensagens`, 'Enviadas']}
                              content={({ active, payload }) => {
                                if (!active || !payload?.length) return null
                                const p = payload[0].payload
                                const daily =
                                  p.by_date?.length > 0
                                    ? p.by_date
                                        .slice(-7)
                                        .map((d) => `${d.date.slice(8, 10)}/${d.date.slice(5, 7)}: ${d.sent}`)
                                        .join(', ')
                                    : null
                                return (
                                  <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded shadow-lg px-3 py-2 text-sm max-w-xs">
                                    <p className="font-medium">{p.department_name} – {p.user_name}</p>
                                    <p>{p.total_sent} mensagens enviadas (total)</p>
                                    {daily && <p className="text-xs mt-1 text-gray-500 dark:text-gray-400">Últimos dias: {daily}</p>}
                                  </div>
                                )
                              }}
                            />
                            <Bar dataKey="total_sent" name="Enviadas" fill="#8b5cf6" isAnimationActive />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </div>
                  </Card>
                )}

                {(messageMetrics.by_department_user?.length ?? 0) > 0 && (() => {
                  const topDeptUsers = messageMetrics.by_department_user!.slice(0, 6)
                  const dates = messageMetrics.series_by_date?.map((s) => s.date) ?? []
                  const colors = ['#6366f1', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4']
                  const dailyChartData = dates.map((date) => {
                    const row: Record<string, string | number> = { date }
                    topDeptUsers.forEach((d, i) => {
                      const dayEntry = d.by_date?.find((b) => b.date === date)
                      row[d.department_name + ' – ' + d.user_name] = dayEntry?.sent ?? 0
                    })
                    return row
                  })
                  return (
                    <Card>
                      <div className="p-6">
                        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-1">
                          Mensagens por dia (top atendentes por departamento)
                        </h2>
                        <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
                          Período: {messageMetrics.range.from} a {messageMetrics.range.to}
                        </p>
                        <div className="h-96">
                          <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={dailyChartData} margin={{ left: 20 }}>
                              <CartesianGrid strokeDasharray="3 3" />
                              <XAxis
                                dataKey="date"
                                tickFormatter={(d) => {
                                  const [y, m, day] = d.split('-')
                                  return `${day}/${m}`
                                }}
                              />
                              <YAxis />
                              <Tooltip
                                labelFormatter={(label) => {
                                  const [y, m, d] = label.split('-')
                                  return `${d}/${m}/${y}`
                                }}
                              />
                              <Legend />
                              {topDeptUsers.map((d, i) => (
                                <Line
                                  key={d.user_id + (d.department_id ?? '')}
                                  type="monotone"
                                  dataKey={d.department_name + ' – ' + d.user_name}
                                  stroke={colors[i % colors.length]}
                                  strokeWidth={2}
                                  dot={false}
                                  connectNulls
                                />
                              ))}
                            </LineChart>
                          </ResponsiveContainer>
                        </div>
                      </div>
                    </Card>
                  )
                })()}
              </>
            )}

            {!messageMetricsLoading && !messageMetrics && !messageMetricsError && (
              <Card>
                <div className="p-8 text-center text-gray-500 dark:text-gray-400">
                  <MessageSquare className="h-12 w-12 mx-auto mb-2 opacity-50" />
                  <p>Nenhuma mensagem no período.</p>
                  <p className="text-sm mt-1">Amplie o período ou altere os filtros.</p>
                </div>
              </Card>
            )}
          </>
        )}

        {activeReportTab === 'transcriptions' && (
        <>
        <Card>
          <div className="p-6 space-y-4">
            <div className="flex flex-wrap items-end gap-4">
              <div className="flex flex-col gap-1">
                <label className="text-sm text-gray-600 dark:text-gray-400">De</label>
                <input
                  type="date"
                  value={createdFrom}
                  onChange={(event) => setCreatedFrom(event.target.value)}
                  className="rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-sm text-gray-600 dark:text-gray-400">Até</label>
                <input
                  type="date"
                  value={createdTo}
                  onChange={(event) => setCreatedTo(event.target.value)}
                  className="rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-sm text-gray-600 dark:text-gray-400">Departamento</label>
                <input
                  type="text"
                  placeholder="UUID do departamento"
                  value={departmentId}
                  onChange={(event) => setDepartmentId(event.target.value)}
                  className="w-64 rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm"
                />
              </div>
              <div className="flex flex-col gap-1">
                <label className="text-sm text-gray-600 dark:text-gray-400">Agente</label>
                <input
                  type="text"
                  placeholder="UUID do agente"
                  value={agentId}
                  onChange={(event) => setAgentId(event.target.value)}
                  className="w-64 rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm"
                />
              </div>
              <Button onClick={fetchMetrics} disabled={isLoading}>
                <RefreshCcw className="h-4 w-4 mr-2" />
                Atualizar
              </Button>
              <Button
                onClick={handleRebuild}
                disabled={isRebuilding || isLoading}
                variant="outline"
                className="border-orange-200 dark:border-orange-800 text-orange-600 dark:text-orange-400 hover:bg-orange-50 dark:hover:bg-orange-900/20"
              >
                <Database className="h-4 w-4 mr-2" />
                {isRebuilding ? 'Processando...' : 'Rebuild Métricas'}
              </Button>
            </div>
            {metrics?.range && (
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Período: {metrics.range.from} até {metrics.range.to} ({metrics.range.timezone})
              </p>
            )}
            {error && <p className="text-sm text-red-600">{error}</p>}
          </div>
        </Card>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          <Card>
            <div className="p-4 flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600 dark:text-gray-400">Minutos transcritos</p>
                <p className="text-2xl font-bold text-gray-900 dark:text-white">
                  {metrics?.totals.minutes_total ?? 0}
                </p>
              </div>
              <BarChart3 className="h-8 w-8 text-brand-500" />
            </div>
          </Card>
          <Card>
            <div className="p-4 flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600 dark:text-gray-400">Média diária</p>
                <p className="text-2xl font-bold text-gray-900 dark:text-white">
                  {metrics?.totals.avg_minutes_per_day ?? 0}
                </p>
              </div>
              <Clock className="h-8 w-8 text-brand-500" />
            </div>
          </Card>
          <Card>
            <div className="p-4 flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600 dark:text-gray-400">Áudios</p>
                <p className="text-2xl font-bold text-gray-900 dark:text-white">
                  {metrics?.totals.audio_count ?? 0}
                </p>
              </div>
              <Mic className="h-8 w-8 text-brand-500" />
            </div>
          </Card>
          <Card>
            <div className="p-4 flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600 dark:text-gray-400">Sucessos</p>
                <p className="text-2xl font-bold text-green-600">
                  {metrics?.totals.success_count ?? 0}
                </p>
              </div>
              <CheckCircle className="h-8 w-8 text-green-500" />
            </div>
          </Card>
          <Card>
            <div className="p-4 flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600 dark:text-gray-400">Falhas</p>
                <p className="text-2xl font-bold text-red-600">
                  {metrics?.totals.failed_count ?? 0}
                </p>
              </div>
              <XCircle className="h-8 w-8 text-red-500" />
            </div>
          </Card>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <div className="p-4 flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600 dark:text-gray-400">% Correta</p>
                <p className="text-2xl font-bold text-green-600">
                  {metrics?.totals
                    ? (() => {
                        const total = metrics.totals.quality_correct_count + 
                                     metrics.totals.quality_incorrect_count + 
                                     metrics.totals.quality_unrated_count
                        if (total === 0) return '0%'
                        const percent = (metrics.totals.quality_correct_count / total) * 100
                        return `${percent.toFixed(1)}%`
                      })()
                    : '0%'}
                </p>
              </div>
              <TrendingUp className="h-8 w-8 text-green-500" />
            </div>
          </Card>
          <Card>
            <div className="p-4 flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600 dark:text-gray-400">% Não avaliada</p>
                <p className="text-2xl font-bold text-yellow-600">
                  {metrics?.totals
                    ? (() => {
                        const total = metrics.totals.quality_correct_count + 
                                     metrics.totals.quality_incorrect_count + 
                                     metrics.totals.quality_unrated_count
                        if (total === 0) return '0%'
                        const percent = (metrics.totals.quality_unrated_count / total) * 100
                        return `${percent.toFixed(1)}%`
                      })()
                    : '0%'}
                </p>
              </div>
              <Clock className="h-8 w-8 text-yellow-500" />
            </div>
          </Card>
          <Card>
            <div className="p-4 flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600 dark:text-gray-400">Latência média</p>
                <p className={`text-2xl font-bold ${
                  metrics?.totals.avg_latency_ms 
                    ? (metrics.totals.avg_latency_ms > 10000 
                        ? 'text-red-600' 
                        : metrics.totals.avg_latency_ms > 5000 
                        ? 'text-yellow-600' 
                        : 'text-gray-900 dark:text-white')
                    : 'text-gray-900 dark:text-white'
                }`}>
                  {metrics?.totals.avg_latency_ms 
                    ? (() => {
                        const seconds = metrics.totals.avg_latency_ms / 1000
                        if (seconds >= 1) {
                          return `${seconds.toFixed(1)}s`
                        }
                        return `${metrics.totals.avg_latency_ms.toFixed(0)}ms`
                      })()
                    : 'N/A'}
                </p>
                {metrics?.totals.avg_latency_ms && metrics.totals.avg_latency_ms > 10000 && (
                  <p className="text-xs text-red-500 mt-1">⚠️ Alta latência</p>
                )}
              </div>
              <Zap className="h-8 w-8 text-blue-500" />
            </div>
          </Card>
          <Card>
            <div className="p-4 flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600 dark:text-gray-400">Modelos usados</p>
                <p className="text-2xl font-bold text-gray-900 dark:text-white">
                  {metrics?.totals.models_used 
                    ? Object.keys(metrics.totals.models_used).length
                    : 0}
                </p>
                {metrics?.totals.models_used && Object.keys(metrics.totals.models_used).length > 0 && (
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                    {Object.entries(metrics.totals.models_used)
                      .sort(([, a], [, b]) => b - a)
                      .slice(0, 2)
                      .map(([model]) => model)
                      .join(', ')}
                  </p>
                )}
              </div>
              <Cpu className="h-8 w-8 text-purple-500" />
            </div>
          </Card>
        </div>

        <Card>
          <div className="p-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
              Minutos transcritos por dia
            </h2>
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" />
                  <YAxis />
                  <Tooltip />
                  <Line
                    type="monotone"
                    dataKey="minutes_total"
                    stroke="#6366f1"
                    strokeWidth={2}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </Card>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card>
            <div className="p-6">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                Qualidade da transcrição por dia
              </h2>
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="quality_correct_count" stackId="quality" fill="#10b981" name="Correta" />
                    <Bar dataKey="quality_incorrect_count" stackId="quality" fill="#ef4444" name="Incorreta" />
                    <Bar dataKey="quality_unrated_count" stackId="quality" fill="#f59e0b" name="Não avaliada" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </Card>

          <Card>
            <div className="p-6">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                Latência média por dia
              </h2>
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData.filter(d => d.avg_latency_ms !== null)}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" />
                    <YAxis 
                      label={{ value: 'Latência (s)', angle: -90, position: 'insideLeft' }}
                      tickFormatter={(value) => `${(value / 1000).toFixed(1)}s`}
                    />
                    <Tooltip 
                      formatter={(value: number) => {
                        const seconds = value / 1000
                        return seconds >= 1 ? `${seconds.toFixed(2)}s` : `${value.toFixed(0)}ms`
                      }}
                      labelFormatter={(label) => `Data: ${label}`}
                    />
                    <Line
                      type="monotone"
                      dataKey="avg_latency_ms"
                      stroke="#3b82f6"
                      strokeWidth={2}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              {metrics?.totals.avg_latency_ms && metrics.totals.avg_latency_ms > 10000 && (
                <div className="mt-4 p-3 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded">
                  <p className="text-sm text-yellow-800 dark:text-yellow-200">
                    ⚠️ <strong>Alta latência detectada:</strong> A latência média está acima de 10 segundos. 
                    Isso pode indicar problemas de rede ou processamento no N8N.
                  </p>
                </div>
              )}
            </div>
          </Card>
        </div>
        </>
        )}
      </div>
    </PermissionGuard>
  )
}
