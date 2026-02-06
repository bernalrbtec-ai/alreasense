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
} from 'lucide-react'
import { toast } from 'sonner'
import {
  ResponsiveContainer,
  LineChart,
  Line,
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

const getDefaultRange = () => {
  const to = new Date()
  const from = new Date()
  from.setDate(to.getDate() - 30)
  return {
    from: from.toISOString().slice(0, 10),
    to: to.toISOString().slice(0, 10),
  }
}

export default function ReportsPage() {
  const defaultRange = useMemo(() => getDefaultRange(), [])
  const [createdFrom, setCreatedFrom] = useState(defaultRange.from)
  const [createdTo, setCreatedTo] = useState(defaultRange.to)
  const [departmentId, setDepartmentId] = useState('')
  const [agentId, setAgentId] = useState('')
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [isRebuilding, setIsRebuilding] = useState(false)

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
            KPIs e métricas diárias de transcrição
          </p>
        </div>

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
      </div>
    </PermissionGuard>
  )
}
