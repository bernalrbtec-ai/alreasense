import React, { useState, useEffect } from 'react'
import { RefreshCw, Settings, AlertCircle, CheckCircle2, Loader2, ChevronDown, ChevronRight, Database, MessageCircle, Server, Plus, Pencil, Trash2, CalendarClock, Cpu } from 'lucide-react'
import {
  AreaChart,
  Area,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import { api, getApiBaseUrl } from '../lib/api'
import { toast } from 'sonner'
import ConfirmDialog from '../components/ui/ConfirmDialog'

interface ProxyOverview {
  config_ok: boolean
  last_execution: {
    started_at: string
    finished_at: string | null
    status: string
    num_proxies: number
    num_instances: number
    num_updated: number
    num_errors?: number
  } | null
  last_errors: string[]
  is_running: boolean
  warnings: string[]
}

interface InstanceLog {
  id?: number
  instance_name: string
  proxy_host: string
  proxy_port: number
  success: boolean
  error_message: string | null
  created_at?: string
}

interface RotationLog {
  id: number
  started_at: string
  finished_at: string | null
  status: string
  num_proxies: number
  num_instances: number
  num_updated: number
  strategy: string
  triggered_by: string
  created_by_email: string | null
  created_at: string
  error_message?: string | null
  instance_logs?: InstanceLog[]
}

interface ProxyStats {
  last_7_days: { total: number; success: number; success_rate: number }
  last_30_days: { total: number; success: number; success_rate: number }
  avg_updated_per_run: number
}

interface ProxyRotationSchedule {
  id: number
  name: string
  is_active: boolean
  interval_minutes: number
  strategy: 'rotate' | 'prioritize' | 'random'
  last_run_at: string | null
  next_run_at: string | null
  created_by_email: string | null
  created_at: string
  updated_at: string
}

interface RedisOverview {
  config_ok: boolean
  error?: string | null
  used_memory: number | null
  used_memory_human: string | null
  keys_total: number | null
  keys_profile_pic: number | null
  keys_webhook: number | null
  last_cleanup: {
    started_at: string
    finished_at: string | null
    status: string
    keys_deleted_profile_pic: number
    keys_deleted_webhook: number
    bytes_freed_estimate: number | null
    duration_seconds?: number | null
  } | null
  growth_projection: { keys_per_day_estimate?: number; message: string } | null
  warnings: string[]
  persistence?: {
    aof_enabled: boolean
    aof_current_size: number | null
    rdb_last_save_time: number | null
  } | null
  usage_history?: {
    sampled_at: string
    used_memory: number
    aof_current_size: number | null
    keys_profile_pic?: number | null
    keys_webhook?: number | null
  }[]
}

interface RedisStats {
  last_7_days: {
    total_cleanups: number
    success_count: number
    success_rate: number
    total_keys_deleted: number
    total_bytes_freed_estimate: number
    avg_duration_seconds?: number
  }
  last_30_days: {
    total_cleanups: number
    success_count: number
    success_rate: number
    total_keys_deleted: number
    total_bytes_freed_estimate: number
    avg_duration_seconds?: number
  }
  avg_keys_deleted_per_run: number
  avg_bytes_freed_per_run: number
  avg_duration_seconds?: number
}

interface RedisCleanupLogEntry {
  id: number
  started_at: string
  finished_at: string | null
  status: string
  keys_deleted_profile_pic: number
  keys_deleted_webhook: number
  bytes_freed_estimate: number | null
  duration_seconds?: number | null
  triggered_by: string
  created_by_email: string | null
  error_message: string | null
}

interface RabbitMQOverview {
  config_ok: boolean
  error?: string | null
  connection_ok: boolean
  consumer_running: boolean
  active_campaign_threads: number
  queues: { name: string; messages_ready: number; consumers: number }[]
  warnings: string[]
  /** Filas não encontradas (404); opcionais como campaigns.dlq não entram aqui */
  warnings_queues_not_found?: string[]
}

interface PostgresOverview {
  config_ok: boolean
  error?: string | null
  connection_count: number | null
  database_size_bytes: number | null
  database_size_human: string | null
  top_tables: { name: string; size_bytes: number }[]
  warnings: string[]
  usage_history?: {
    sampled_at: string
    connection_count: number
    database_size_bytes: number
  }[]
  peak_24h_connections?: number | null
  peak_24h_size_bytes?: number | null
  /** Espaço total no disco (data_directory); null se banco remoto */
  disk_total_bytes?: number | null
  /** Espaço livre no disco; null se banco remoto */
  disk_free_bytes?: number | null
}

interface CeleryOverview {
  config_ok: boolean
  overview_api_path: string
  broker_url_masked: string
  broker_transport: string
  default_queue: string
  task_always_eager: boolean
  broker_reachable: boolean
  broker_error?: string | null
  workers_online: number | null
  workers_error?: string | null
  worker_start_command: string
  dify_debounce_task: string
  celery_queue?: {
    queue?: string
    messages_ready?: number | null
    consumers?: number | null
    note?: string
    error?: string
  } | null
  warnings: string[]
}

type TabId = 'proxy' | 'redis' | 'rabbitmq' | 'postgres' | 'celery'

export default function ServicosPage() {
  const [activeTab, setActiveTab] = useState<TabId>('proxy')
  const [overview, setOverview] = useState<ProxyOverview | null>(null)
  const [history, setHistory] = useState<{ results: RotationLog[]; count: number } | null>(null)
  const [stats, setStats] = useState<ProxyStats | null>(null)
  const [isLoadingOverview, setIsLoadingOverview] = useState(true)
  const [isLoadingHistory, setIsLoadingHistory] = useState(false)
  const [isLoadingStats, setIsLoadingStats] = useState(false)
  const [isRotating, setIsRotating] = useState(false)
  const [historyPage, setHistoryPage] = useState(1)
  const [expandedLogId, setExpandedLogId] = useState<number | null>(null)

  const [schedules, setSchedules] = useState<ProxyRotationSchedule[]>([])
  const [isLoadingSchedules, setIsLoadingSchedules] = useState(false)
  const [scheduleModalOpen, setScheduleModalOpen] = useState(false)
  const [scheduleEditingId, setScheduleEditingId] = useState<number | null>(null)
  const [scheduleForm, setScheduleForm] = useState({
    name: '',
    is_active: true,
    interval_minutes: 1440,
    strategy: 'rotate' as ProxyRotationSchedule['strategy'],
  })
  const [savingSchedule, setSavingSchedule] = useState(false)
  const [deleteScheduleId, setDeleteScheduleId] = useState<number | null>(null)
  const [deletingSchedule, setDeletingSchedule] = useState(false)

  const [redisOverview, setRedisOverview] = useState<RedisOverview | null>(null)
  const [redisStats, setRedisStats] = useState<RedisStats | null>(null)
  const [redisHistory, setRedisHistory] = useState<{ results: RedisCleanupLogEntry[]; count: number } | null>(null)
  const [isLoadingRedisOverview, setIsLoadingRedisOverview] = useState(false)
  const [isLoadingRedisStats, setIsLoadingRedisStats] = useState(false)
  const [isLoadingRedisHistory, setIsLoadingRedisHistory] = useState(false)
  const [isCleaningRedis, setIsCleaningRedis] = useState(false)
  const [redisHistoryPage, setRedisHistoryPage] = useState(1)
  const [redisCleanupProfilePic, setRedisCleanupProfilePic] = useState(true)
  const [redisCleanupWebhook, setRedisCleanupWebhook] = useState(false)
  const [isPersistRewriting, setIsPersistRewriting] = useState(false)

  const [rabbitmqOverview, setRabbitmqOverview] = useState<RabbitMQOverview | null>(null)
  const [postgresOverview, setPostgresOverview] = useState<PostgresOverview | null>(null)
  const [isLoadingRabbitmqOverview, setIsLoadingRabbitmqOverview] = useState(false)
  const [isLoadingPostgresOverview, setIsLoadingPostgresOverview] = useState(false)
  const [celeryOverview, setCeleryOverview] = useState<CeleryOverview | null>(null)
  const [isLoadingCeleryOverview, setIsLoadingCeleryOverview] = useState(false)

  const fetchOverview = async () => {
    try {
      setIsLoadingOverview(true)
      const res = await api.get<ProxyOverview>('/proxy/overview/')
      setOverview(res.data)
    } catch (err: any) {
      console.error('Erro ao carregar overview:', err)
      toast.error(err.response?.data?.error || 'Erro ao carregar overview')
    } finally {
      setIsLoadingOverview(false)
    }
  }

  const fetchHistory = async () => {
    try {
      setIsLoadingHistory(true)
      const res = await api.get<{ results: RotationLog[]; count: number }>(
        `/proxy/rotation-history/?page=${historyPage}&page_size=10`
      )
      setHistory(res.data)
    } catch (err: any) {
      console.error('Erro ao carregar histórico:', err)
      toast.error(err.response?.data?.error || 'Erro ao carregar histórico')
    } finally {
      setIsLoadingHistory(false)
    }
  }

  const fetchStats = async () => {
    try {
      setIsLoadingStats(true)
      const res = await api.get<ProxyStats>('/proxy/statistics/')
      setStats(res.data)
    } catch (err: any) {
      console.error('Erro ao carregar estatísticas:', err)
      toast.error(err.response?.data?.error || 'Erro ao carregar estatísticas')
    } finally {
      setIsLoadingStats(false)
    }
  }

  const fetchSchedules = async () => {
    try {
      setIsLoadingSchedules(true)
      const res = await api.get<ProxyRotationSchedule[]>('/proxy/rotation-schedules/')
      setSchedules(Array.isArray(res.data) ? res.data : [])
    } catch (err: any) {
      console.error('Erro ao carregar agendamentos:', err)
      toast.error(err.response?.data?.error || 'Erro ao carregar agendamentos')
      setSchedules([])
    } finally {
      setIsLoadingSchedules(false)
    }
  }

  useEffect(() => {
    fetchOverview()
  }, [])

  useEffect(() => {
    if (activeTab === 'proxy') {
      fetchHistory()
      fetchStats()
      fetchSchedules()
    }
  }, [activeTab, historyPage])

  const fetchRedisOverview = async () => {
    try {
      setIsLoadingRedisOverview(true)
      const res = await api.get<RedisOverview>('/servicos/redis/overview/')
      setRedisOverview(res.data)
    } catch (err: any) {
      console.error('Erro ao carregar overview Redis:', err)
      toast.error(err.response?.data?.error || 'Erro ao carregar overview Redis')
    } finally {
      setIsLoadingRedisOverview(false)
    }
  }

  const fetchRedisStats = async () => {
    try {
      setIsLoadingRedisStats(true)
      const res = await api.get<RedisStats>('/servicos/redis/statistics/')
      setRedisStats(res.data)
    } catch (err: any) {
      console.error('Erro ao carregar estatísticas Redis:', err)
      toast.error(err.response?.data?.error || 'Erro ao carregar estatísticas Redis')
    } finally {
      setIsLoadingRedisStats(false)
    }
  }

  const fetchRedisHistory = async () => {
    try {
      setIsLoadingRedisHistory(true)
      const res = await api.get<{ results: RedisCleanupLogEntry[]; count: number }>(
        `/servicos/redis/cleanup-history/?page=${redisHistoryPage}&page_size=10`
      )
      setRedisHistory(res.data)
    } catch (err: any) {
      console.error('Erro ao carregar histórico Redis:', err)
      toast.error(err.response?.data?.error || 'Erro ao carregar histórico Redis')
    } finally {
      setIsLoadingRedisHistory(false)
    }
  }

  useEffect(() => {
    if (activeTab === 'redis') {
      fetchRedisOverview()
      fetchRedisStats()
      fetchRedisHistory()
    }
  }, [activeTab, redisHistoryPage])

  const fetchRabbitmqOverview = async () => {
    try {
      setIsLoadingRabbitmqOverview(true)
      const res = await api.get<RabbitMQOverview>('/servicos/rabbitmq/overview/')
      setRabbitmqOverview(res.data)
    } catch (err: any) {
      console.error('Erro ao carregar overview RabbitMQ:', err)
      toast.error(err.response?.data?.error || 'Erro ao carregar overview RabbitMQ')
      setRabbitmqOverview(null)
    } finally {
      setIsLoadingRabbitmqOverview(false)
    }
  }

  const fetchPostgresOverview = async () => {
    try {
      setIsLoadingPostgresOverview(true)
      const res = await api.get<PostgresOverview>('/servicos/postgres/overview/')
      setPostgresOverview(res.data)
    } catch (err: any) {
      console.error('Erro ao carregar overview PostgreSQL:', err)
      toast.error(err.response?.data?.error || 'Erro ao carregar overview PostgreSQL')
      setPostgresOverview(null)
    } finally {
      setIsLoadingPostgresOverview(false)
    }
  }

  const fetchCeleryOverview = async () => {
    try {
      setIsLoadingCeleryOverview(true)
      const res = await api.get<CeleryOverview>('/servicos/celery/overview/')
      setCeleryOverview(res.data)
    } catch (err: any) {
      console.error('Erro ao carregar overview Celery:', err)
      toast.error(err.response?.data?.error || 'Erro ao carregar overview Celery')
      setCeleryOverview(null)
    } finally {
      setIsLoadingCeleryOverview(false)
    }
  }

  useEffect(() => {
    if (activeTab === 'rabbitmq') fetchRabbitmqOverview()
    if (activeTab === 'postgres') fetchPostgresOverview()
    if (activeTab === 'celery') fetchCeleryOverview()
  }, [activeTab])

  const handleRedisCleanup = async () => {
    if (!redisCleanupProfilePic && !redisCleanupWebhook) {
      toast.error('Selecione ao menos um tipo de cache para limpar.')
      return
    }
    try {
      setIsCleaningRedis(true)
      const { data } = await api.post<{ persist_rewrite?: { message: string } }>('/servicos/redis/cleanup/', {
        profile_pic: redisCleanupProfilePic,
        webhook: redisCleanupWebhook,
      })
      toast.success('Limpeza Redis concluída com sucesso.')
      if (data?.persist_rewrite?.message) {
        toast.info(data.persist_rewrite.message)
      }
      await fetchRedisOverview()
      await fetchRedisStats()
      await fetchRedisHistory()
    } catch (err: any) {
      const msg = err.response?.data?.error || 'Erro ao executar limpeza'
      if (err.response?.status === 409) {
        toast.error('Limpeza já em andamento. Aguarde a conclusão.')
      } else if (err.response?.status === 429) {
        toast.error('Aguarde 30 segundos entre limpezas.')
      } else {
        toast.error(msg)
      }
      await fetchRedisOverview()
    } finally {
      setIsCleaningRedis(false)
    }
  }

  const handleRedisPersistRewrite = async () => {
    try {
      setIsPersistRewriting(true)
      const { data } = await api.post<{ bgsave: string; bgrewriteaof: string; message: string }>(
        '/servicos/redis/persist-rewrite/'
      )
      const ok = data.bgsave === 'ok' || data.bgrewriteaof === 'ok'
      if (ok) {
        toast.success(data.message || 'Compactação de persistência iniciada.')
      } else if (data.bgsave === 'disabled' && data.bgrewriteaof === 'disabled') {
        toast.info(data.message || 'Comandos de disco desabilitados (comum em Redis gerenciado).')
      } else {
        toast.warning(data.message || 'Resultado parcial.')
      }
    } catch (err: any) {
      const msg = err.response?.data?.error || 'Erro ao solicitar compactação'
      if (err.response?.status === 429) {
        toast.error('Aguarde 1 minuto antes de tentar novamente.')
      } else {
        toast.error(msg)
      }
    } finally {
      setIsPersistRewriting(false)
    }
  }

  const handleRotate = async () => {
    try {
      setIsRotating(true)
      await api.post('/proxy/rotate/')
      toast.success('Rotação de proxies iniciada com sucesso')
      await fetchOverview()
      await fetchHistory()
      await fetchStats()
    } catch (err: any) {
      const msg = err.response?.data?.error || 'Erro ao executar rotação'
      toast.error(msg)
      await fetchOverview()
    } finally {
      setIsRotating(false)
    }
  }

  const openNewScheduleModal = () => {
    setScheduleEditingId(null)
    setScheduleForm({
      name: '',
      is_active: true,
      interval_minutes: 1440,
      strategy: 'rotate',
    })
    setScheduleModalOpen(true)
  }

  const openEditScheduleModal = (s: ProxyRotationSchedule) => {
    setScheduleEditingId(s.id)
    setScheduleForm({
      name: s.name || '',
      is_active: s.is_active,
      interval_minutes: s.interval_minutes,
      strategy: s.strategy,
    })
    setScheduleModalOpen(true)
  }

  const handleSaveSchedule = async () => {
    const mins = Number(scheduleForm.interval_minutes)
    if (!Number.isFinite(mins) || mins < 1 || mins > 10080) {
      toast.error('Intervalo deve ser entre 1 e 10080 minutos (7 dias).')
      return
    }
    try {
      setSavingSchedule(true)
      const body = {
        name: scheduleForm.name.trim(),
        is_active: scheduleForm.is_active,
        interval_minutes: mins,
        strategy: scheduleForm.strategy,
      }
      if (scheduleEditingId == null) {
        await api.post('/proxy/rotation-schedules/', body)
        toast.success('Agendamento criado')
      } else {
        await api.patch(`/proxy/rotation-schedules/${scheduleEditingId}/`, body)
        toast.success('Agendamento atualizado')
      }
      setScheduleModalOpen(false)
      await fetchSchedules()
    } catch (err: any) {
      const msg = err.response?.data?.error || err.response?.data?.detail || 'Erro ao salvar agendamento'
      if (typeof msg === 'object') {
        toast.error(JSON.stringify(msg))
      } else {
        toast.error(String(msg))
      }
    } finally {
      setSavingSchedule(false)
    }
  }

  const handleConfirmDeleteSchedule = async () => {
    if (deleteScheduleId == null) return
    try {
      setDeletingSchedule(true)
      await api.delete(`/proxy/rotation-schedules/${deleteScheduleId}/`)
      toast.success('Agendamento removido')
      setDeleteScheduleId(null)
      await fetchSchedules()
    } catch (err: any) {
      toast.error(err.response?.data?.error || 'Erro ao excluir')
    } finally {
      setDeletingSchedule(false)
    }
  }

  const strategyLabel = (s: string) =>
    ({ rotate: 'Rotacionar', prioritize: 'Priorizar', random: 'Aleatório' } as Record<string, string>)[s] || s

  const formatDate = (s: string | null) =>
    s ? new Date(s).toLocaleString('pt-BR') : '—'

  const getStatusBadge = (status: string) => {
    const map: Record<string, string> = {
      success: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
      partial: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
      failed: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
      running: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
    }
    return map[status] || 'bg-gray-100 text-gray-800'
  }

  const tabs = [
    { id: 'proxy' as TabId, name: 'Proxy', icon: Settings },
    { id: 'redis' as TabId, name: 'Redis', icon: Database },
    { id: 'rabbitmq' as TabId, name: 'RabbitMQ', icon: MessageCircle },
    { id: 'postgres' as TabId, name: 'PostgreSQL', icon: Server },
    { id: 'celery' as TabId, name: 'Celery', icon: Cpu },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Serviços</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Gerencie serviços da aplicação (rotação de proxies, etc.)
        </p>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 dark:border-gray-700">
        <nav className="-mb-px flex space-x-8">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 py-4 px-1 border-b-2 font-medium text-sm ${
                activeTab === tab.id
                  ? 'border-brand-500 text-brand-600 dark:text-brand-400'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <tab.icon className="h-4 w-4" />
              {tab.name}
            </button>
          ))}
        </nav>
      </div>

      {activeTab === 'proxy' && (
        <div className="space-y-6">
          {/* Overview Card */}
          <Card className="p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                Overview – Rotação de Proxies
              </h2>
              <div className="flex items-center gap-2">
                <Button
                  onClick={fetchOverview}
                  disabled={isLoadingOverview}
                  variant="outline"
                  size="sm"
                  className="border-gray-300 dark:border-gray-500 text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700"
                >
                  <RefreshCw className={`h-4 w-4 mr-1 ${isLoadingOverview ? 'animate-spin' : ''}`} />
                  Atualizar
                </Button>
                <Button
                  onClick={handleRotate}
                  disabled={isRotating || !overview?.config_ok || overview?.is_running}
                  size="sm"
                >
                  {isRotating ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                      Executando...
                    </>
                  ) : (
                    <>
                      <RefreshCw className="h-4 w-4 mr-1" />
                      Executar rotação
                    </>
                  )}
                </Button>
              </div>
            </div>

            {isLoadingOverview ? (
              <div className="flex justify-center py-8">
                <LoadingSpinner size="md" />
              </div>
            ) : overview ? (
              <div className="space-y-4">
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                    <p className="text-sm text-gray-500 dark:text-gray-400">Configuração</p>
                    <div className="mt-1 flex items-center gap-2">
                      {overview.config_ok ? (
                        <CheckCircle2 className="h-5 w-5 text-green-500" />
                      ) : (
                        <AlertCircle className="h-5 w-5 text-amber-500" />
                      )}
                      <span className="font-medium">
                        {overview.config_ok ? 'OK' : 'Credenciais ausentes'}
                      </span>
                    </div>
                  </div>
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                    <p className="text-sm text-gray-500 dark:text-gray-400">Instâncias × Proxies</p>
                    <p className="mt-1 font-medium">
                      {overview.last_execution
                        ? `${overview.last_execution.num_instances} / ${overview.last_execution.num_proxies}`
                        : '—'}
                    </p>
                  </div>
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                    <p className="text-sm text-gray-500 dark:text-gray-400">Última execução</p>
                    <p className="mt-1 text-sm">
                      {overview.last_execution
                        ? formatDate(overview.last_execution.finished_at || overview.last_execution.started_at)
                        : '—'}
                    </p>
                    {overview.last_execution && (
                      <span
                        className={`mt-1 inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${getStatusBadge(
                          overview.last_execution.status
                        )}`}
                      >
                        {overview.last_execution.status}
                      </span>
                    )}
                  </div>
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                    <p className="text-sm text-gray-500 dark:text-gray-400">Status</p>
                    {overview.is_running || isRotating ? (
                      <div className="mt-1 flex flex-col gap-1">
                        <div className="flex items-center gap-2">
                          <Loader2 className="h-5 w-5 animate-spin text-blue-500 flex-shrink-0" />
                          <span className="font-medium">Em execução</span>
                        </div>
                        <p className="text-xs text-gray-500 dark:text-gray-400">Aguarde a conclusão...</p>
                      </div>
                    ) : overview.last_execution ? (
                      <div className="mt-1 space-y-1">
                        <p className="font-medium">
                          {overview.last_execution.num_instances > 0
                            ? `${overview.last_execution.num_updated}/${overview.last_execution.num_instances} processadas`
                            : 'Ocioso'}
                        </p>
                        <div className="text-xs space-y-0.5">
                          <p className="text-green-600 dark:text-green-400">
                            Sucessos: {overview.last_execution.num_updated ?? 0}
                          </p>
                          <p className="text-red-600 dark:text-red-400">
                            Erros: {overview.last_execution.num_errors ?? overview.last_execution.num_instances - overview.last_execution.num_updated}
                          </p>
                        </div>
                      </div>
                    ) : (
                      <p className="mt-1 font-medium">Ocioso</p>
                    )}
                  </div>
                </div>

                {overview.warnings && overview.warnings.length > 0 && (
                  <div className="rounded-lg bg-amber-50 dark:bg-amber-900/20 p-4">
                    <p className="text-sm font-medium text-amber-800 dark:text-amber-200">Avisos</p>
                    <ul className="mt-1 list-disc list-inside text-sm text-amber-700 dark:text-amber-300">
                      {overview.warnings.map((w, i) => (
                        <li key={i}>{w}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {overview.last_errors && overview.last_errors.length > 0 && (
                  <div className="rounded-lg bg-red-50 dark:bg-red-900/20 p-4">
                    <p className="text-sm font-medium text-red-800 dark:text-red-200">Últimos erros</p>
                    <ul className="mt-1 list-disc list-inside text-sm text-red-700 dark:text-red-300">
                      {overview.last_errors.slice(0, 5).map((e, i) => (
                        <li key={i}>{e}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ) : null}
          </Card>

          {/* Agendamentos de rotação */}
          <Card className="p-6">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between mb-4">
              <div>
                <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
                  <CalendarClock className="h-5 w-5 text-brand-500" />
                  Agendamentos automáticos
                </h2>
                <p className="mt-1 text-sm text-gray-500 dark:text-gray-400 max-w-2xl">
                  Cadastre intervalos para rotação com a estratégia desejada. No servidor, rode periodicamente:{' '}
                  <code className="text-xs bg-gray-100 dark:bg-gray-800 px-1 py-0.5 rounded">
                    python manage.py process_proxy_rotation_schedules
                  </code>{' '}
                  (ex.: cron a cada minuto).
                </p>
              </div>
              <div className="flex gap-2 shrink-0">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={fetchSchedules}
                  disabled={isLoadingSchedules}
                  className="border-gray-300 dark:border-gray-500"
                >
                  <RefreshCw className={`h-4 w-4 mr-1 ${isLoadingSchedules ? 'animate-spin' : ''}`} />
                  Atualizar
                </Button>
                <Button type="button" size="sm" onClick={openNewScheduleModal}>
                  <Plus className="h-4 w-4 mr-1" />
                  Novo agendamento
                </Button>
              </div>
            </div>

            {isLoadingSchedules ? (
              <div className="flex justify-center py-8">
                <LoadingSpinner size="md" />
              </div>
            ) : schedules.length === 0 ? (
              <p className="text-sm text-gray-500 dark:text-gray-400 py-2">
                Nenhum agendamento cadastrado. Clique em &quot;Novo agendamento&quot; para criar.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                  <thead>
                    <tr>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                        Nome
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                        Ativo
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                        Intervalo (min)
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                        Estratégia
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                        Próxima execução
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                        Última execução
                      </th>
                      <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                        Ações
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {schedules.map((s) => (
                      <tr
                        key={s.id}
                        className="border-t border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800/50"
                      >
                        <td className="px-4 py-2 text-sm text-gray-900 dark:text-gray-100">
                          {s.name?.trim() ? s.name : <span className="text-gray-400">—</span>}
                        </td>
                        <td className="px-4 py-2 text-sm">
                          {s.is_active ? (
                            <span className="inline-flex rounded-full px-2 py-0.5 text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400">
                              Sim
                            </span>
                          ) : (
                            <span className="inline-flex rounded-full px-2 py-0.5 text-xs font-medium bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300">
                              Não
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-2 text-sm">{s.interval_minutes}</td>
                        <td className="px-4 py-2 text-sm">{strategyLabel(s.strategy)}</td>
                        <td className="px-4 py-2 text-sm">{formatDate(s.next_run_at)}</td>
                        <td className="px-4 py-2 text-sm">{formatDate(s.last_run_at)}</td>
                        <td className="px-4 py-2 text-sm text-right">
                          <button
                            type="button"
                            onClick={() => openEditScheduleModal(s)}
                            className="inline-flex items-center gap-1 px-2 py-1 rounded text-brand-600 dark:text-brand-400 hover:bg-brand-50 dark:hover:bg-brand-900/20 mr-1"
                          >
                            <Pencil className="h-4 w-4" />
                            Editar
                          </button>
                          <button
                            type="button"
                            onClick={() => setDeleteScheduleId(s.id)}
                            className="inline-flex items-center gap-1 px-2 py-1 rounded text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20"
                          >
                            <Trash2 className="h-4 w-4" />
                            Excluir
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          {scheduleModalOpen && (
            <div
              className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 dark:bg-black/60"
              role="dialog"
              aria-modal="true"
              aria-labelledby="schedule-modal-title"
              onClick={() => !savingSchedule && setScheduleModalOpen(false)}
            >
              <div
                className="bg-white dark:bg-gray-900 rounded-xl shadow-xl max-w-md w-full border border-gray-200 dark:border-gray-700 p-6"
                onClick={(e) => e.stopPropagation()}
              >
                <h3 id="schedule-modal-title" className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
                  {scheduleEditingId == null ? 'Novo agendamento' : 'Editar agendamento'}
                </h3>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Nome (opcional)</label>
                    <input
                      type="text"
                      value={scheduleForm.name}
                      onChange={(e) => setScheduleForm((f) => ({ ...f, name: e.target.value }))}
                      className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm"
                      placeholder="Ex.: Rotação diária"
                    />
                  </div>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={scheduleForm.is_active}
                      onChange={(e) => setScheduleForm((f) => ({ ...f, is_active: e.target.checked }))}
                      className="rounded border-gray-300 dark:border-gray-600"
                    />
                    <span className="text-sm text-gray-700 dark:text-gray-300">Agendamento ativo</span>
                  </label>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Intervalo entre execuções (minutos)
                    </label>
                    <input
                      type="number"
                      min={1}
                      max={10080}
                      value={scheduleForm.interval_minutes}
                      onChange={(e) =>
                        setScheduleForm((f) => ({ ...f, interval_minutes: Number(e.target.value) || 0 }))
                      }
                      className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm"
                    />
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">1440 = aprox. uma vez por dia.</p>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Estratégia</label>
                    <select
                      value={scheduleForm.strategy}
                      onChange={(e) =>
                        setScheduleForm((f) => ({
                          ...f,
                          strategy: e.target.value as ProxyRotationSchedule['strategy'],
                        }))
                      }
                      className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm"
                    >
                      <option value="rotate">Rotacionar</option>
                      <option value="prioritize">Priorizar</option>
                      <option value="random">Aleatório</option>
                    </select>
                  </div>
                </div>
                <div className="mt-6 flex justify-end gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setScheduleModalOpen(false)}
                    disabled={savingSchedule}
                  >
                    Cancelar
                  </Button>
                  <Button type="button" onClick={handleSaveSchedule} disabled={savingSchedule}>
                    {savingSchedule ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                        Salvando...
                      </>
                    ) : (
                      'Salvar'
                    )}
                  </Button>
                </div>
              </div>
            </div>
          )}

          <ConfirmDialog
            show={deleteScheduleId !== null}
            title="Excluir agendamento?"
            message="Esta ação não pode ser desfeita."
            confirmText="Excluir"
            variant="danger"
            confirmLoading={deletingSchedule}
            confirmLoadingText="Excluindo..."
            onConfirm={handleConfirmDeleteSchedule}
            onCancel={() => !deletingSchedule && setDeleteScheduleId(null)}
          />

          {/* Statistics */}
          {stats && (
            <Card className="p-6">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
                Estatísticas
              </h2>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Últimos 7 dias</p>
                  <p className="text-xl font-semibold">{stats.last_7_days.total} rotações</p>
                  <p className="text-sm text-green-600 dark:text-green-400">
                    {stats.last_7_days.success_rate.toFixed(1)}% sucesso
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Últimos 30 dias</p>
                  <p className="text-xl font-semibold">{stats.last_30_days.total} rotações</p>
                  <p className="text-sm text-green-600 dark:text-green-400">
                    {stats.last_30_days.success_rate.toFixed(1)}% sucesso
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Média por execução</p>
                  <p className="text-xl font-semibold">{stats.avg_updated_per_run} instâncias</p>
                </div>
              </div>
            </Card>
          )}

          {/* History */}
          <Card className="p-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
              Histórico
            </h2>
            {isLoadingHistory ? (
              <div className="flex justify-center py-8">
                <LoadingSpinner size="md" />
              </div>
            ) : history && history.results.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                  <thead>
                    <tr>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase w-8">
                        {' '}
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                        Data/Hora
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                        Status
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                        Proxies
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                        Instâncias
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                        Atualizadas
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                        Acionado por
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                        Erro
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.results.map((log) => (
                      <React.Fragment key={log.id}>
                        <tr
                          className="border-t border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800/50"
                        >
                          <td className="px-4 py-2 text-sm">
                            {log.instance_logs && log.instance_logs.length > 0 ? (
                              <button
                                type="button"
                                onClick={() => setExpandedLogId(expandedLogId === log.id ? null : log.id)}
                                className="p-0.5 rounded hover:bg-gray-200 dark:hover:bg-gray-700"
                                aria-label={expandedLogId === log.id ? 'Recolher detalhes' : 'Expandir detalhes'}
                              >
                                {expandedLogId === log.id ? (
                                  <ChevronDown className="h-4 w-4 text-gray-500 dark:text-gray-400" />
                                ) : (
                                  <ChevronRight className="h-4 w-4 text-gray-500 dark:text-gray-400" />
                                )}
                              </button>
                            ) : (
                              <span className="w-4 inline-block" />
                            )}
                          </td>
                          <td className="px-4 py-2 text-sm text-gray-900 dark:text-gray-100">
                            {formatDate(log.started_at)}
                          </td>
                          <td className="px-4 py-2">
                            <span
                              className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${getStatusBadge(
                                log.status
                              )}`}
                            >
                              {log.status}
                            </span>
                          </td>
                          <td className="px-4 py-2 text-sm">{log.num_proxies}</td>
                          <td className="px-4 py-2 text-sm">{log.num_instances}</td>
                          <td className="px-4 py-2 text-sm">{log.num_updated}</td>
                          <td className="px-4 py-2 text-sm">
                            {log.created_by_email || log.triggered_by}
                          </td>
                          <td className="px-4 py-2 text-sm max-w-[200px]">
                            {log.error_message ? (
                              <span
                                className="text-red-700 dark:text-red-300 truncate block"
                                title={log.error_message}
                              >
                                {log.error_message.length > 60
                                  ? `${log.error_message.slice(0, 60)}…`
                                  : log.error_message}
                              </span>
                            ) : (
                              '—'
                            )}
                          </td>
                        </tr>
                        {expandedLogId === log.id && log.instance_logs && log.instance_logs.length > 0 && (
                          <tr key={`${log.id}-detail`} className="border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/30">
                            <td colSpan={9} className="px-4 py-3">
                              <p className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-2">
                                Detalhe por instância
                              </p>
                              <ul className="space-y-1 text-sm">
                                {log.instance_logs.map((inst, idx) => (
                                  <li
                                    key={inst.instance_name + String(idx)}
                                    className={`flex flex-wrap gap-2 items-baseline ${
                                      inst.success ? 'text-gray-700 dark:text-gray-300' : 'text-red-700 dark:text-red-300'
                                    }`}
                                  >
                                    <span className="font-medium">{inst.instance_name}</span>
                                    <span className="text-xs">
                                      {inst.success ? 'OK' : `Erro: ${inst.error_message || '—'}`}
                                    </span>
                                  </li>
                                ))}
                              </ul>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm text-gray-500 dark:text-gray-400 py-4">
                Nenhuma execução registrada.
              </p>
            )}
          </Card>
        </div>
      )}

      {activeTab === 'redis' && (
        <div className="space-y-6">
          <Card className="p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                Overview – Redis
              </h2>
              <Button
                onClick={fetchRedisOverview}
                disabled={isLoadingRedisOverview}
                variant="outline"
                size="sm"
              >
                <RefreshCw className={`h-4 w-4 mr-1 ${isLoadingRedisOverview ? 'animate-spin' : ''}`} />
                Atualizar
              </Button>
            </div>

            {isLoadingRedisOverview ? (
              <div className="flex justify-center py-8">
                <LoadingSpinner size="md" />
              </div>
            ) : redisOverview ? (
              <div className="space-y-4">
                <p className="text-sm text-gray-600 dark:text-gray-300">
                  Libera espaço no Redis removendo cache. Fotos de perfil (7 dias) e/ou webhooks (24h) podem ser limpos; as fotos serão baixadas de novo quando necessário.
                </p>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                    <p className="text-sm text-gray-500 dark:text-gray-400">Configuração</p>
                    <div className="mt-1 flex items-center gap-2">
                      {redisOverview.config_ok ? (
                        <CheckCircle2 className="h-5 w-5 text-green-500" />
                      ) : (
                        <AlertCircle className="h-5 w-5 text-amber-500" />
                      )}
                      <span className="font-medium">
                        {redisOverview.config_ok ? 'OK' : (redisOverview.error || 'Erro')}
                      </span>
                    </div>
                  </div>
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                    <p className="text-sm text-gray-500 dark:text-gray-400">Uso de memória</p>
                    <p className="mt-1 font-medium">
                      {redisOverview.used_memory_human ?? '—'}
                    </p>
                  </div>
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                    <p className="text-sm text-gray-500 dark:text-gray-400">Volume (keys)</p>
                    <p className="mt-1 font-medium">
                      {redisOverview.keys_total != null
                        ? `${redisOverview.keys_total} total`
                        : '—'}
                    </p>
                    {(redisOverview.keys_profile_pic != null || redisOverview.keys_webhook != null) && (
                      <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
                        {[
                          redisOverview.keys_profile_pic != null && `fotos: ${redisOverview.keys_profile_pic}`,
                          redisOverview.keys_webhook != null && `webhook: ${redisOverview.keys_webhook}`,
                        ].filter(Boolean).join(' · ')}
                      </p>
                    )}
                  </div>
                  {redisOverview.persistence?.aof_enabled && redisOverview.persistence?.aof_current_size != null && (
                    <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                      <p className="text-sm text-gray-500 dark:text-gray-400">Espaço em disco (AOF)</p>
                      <p className="mt-1 font-medium">
                        {(redisOverview.persistence.aof_current_size / 1024 / 1024).toFixed(2)} MB
                      </p>
                    </div>
                  )}
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                    <p className="text-sm text-gray-500 dark:text-gray-400">Última limpeza</p>
                    <p className="mt-1 text-sm">
                      {redisOverview.last_cleanup
                        ? formatDate(redisOverview.last_cleanup.finished_at || redisOverview.last_cleanup.started_at)
                        : '—'}
                    </p>
                    {redisOverview.last_cleanup && (
                      <>
                        <span
                          className={`mt-1 inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${getStatusBadge(
                            redisOverview.last_cleanup.status
                          )}`}
                        >
                          {redisOverview.last_cleanup.status}
                        </span>
                        <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                          Keys: {(redisOverview.last_cleanup.keys_deleted_profile_pic ?? 0) + (redisOverview.last_cleanup.keys_deleted_webhook ?? 0)}
                          {redisOverview.last_cleanup.bytes_freed_estimate != null
                            ? ` · ${(redisOverview.last_cleanup.bytes_freed_estimate / 1024 / 1024).toFixed(2)} MB liberados`
                            : ''}
                          {redisOverview.last_cleanup.duration_seconds != null && redisOverview.last_cleanup.duration_seconds > 0
                            ? ` · ${Number(redisOverview.last_cleanup.duration_seconds).toFixed(1)}s`
                            : ''}
                        </p>
                      </>
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                    <p className="text-sm font-medium text-gray-700 dark:text-gray-200 mb-2">O que limpar</p>
                    <div className="flex flex-wrap gap-4">
                      <label className="inline-flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={redisCleanupProfilePic}
                          onChange={(e) => setRedisCleanupProfilePic(e.target.checked)}
                          className="rounded border-gray-300 dark:border-gray-600"
                        />
                        <span className="text-sm text-gray-700 dark:text-gray-300">Cache de fotos de perfil (7 dias)</span>
                      </label>
                      <label className="inline-flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={redisCleanupWebhook}
                          onChange={(e) => setRedisCleanupWebhook(e.target.checked)}
                          className="rounded border-gray-300 dark:border-gray-600"
                        />
                        <span className="text-sm text-gray-700 dark:text-gray-300">Cache de webhooks (24h)</span>
                      </label>
                    </div>
                    <div className="mt-3">
                      <Button
                        onClick={handleRedisCleanup}
                        disabled={isCleaningRedis || !redisOverview.config_ok || (!redisCleanupProfilePic && !redisCleanupWebhook)}
                      >
                        {isCleaningRedis ? (
                          <>
                            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                            Executando...
                          </>
                        ) : (
                          <>
                            <RefreshCw className="h-4 w-4 mr-2" />
                            Executar limpeza
                          </>
                        )}
                      </Button>
                    </div>
                  </div>
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                    <p className="text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">Persistência em disco</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">
                      Após limpar cache, o Redis pode manter arquivos antigos em disco. Compactar persistência (BGSAVE/BGREWRITEAOF) reescreve os arquivos e pode reduzir o uso de disco. Em Redis gerenciado esses comandos costumam estar desabilitados.
                    </p>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleRedisPersistRewrite}
                      disabled={isPersistRewriting || !redisOverview.config_ok}
                    >
                      {isPersistRewriting ? (
                        <>
                          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                          Executando...
                        </>
                      ) : (
                        <>
                          <Database className="h-4 w-4 mr-2" />
                          Compactar persistência (disco)
                        </>
                      )}
                    </Button>
                  </div>
                </div>

                {redisStats && (
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                    <p className="text-sm font-medium text-gray-700 dark:text-gray-200 mb-3">Estatísticas</p>
                    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                      <div>
                        <p className="text-xs text-gray-500 dark:text-gray-400">Últimos 7 dias</p>
                        <p className="text-lg font-semibold">{Number(redisStats.last_7_days?.total_cleanups) ?? 0} limpezas</p>
                        <p className="text-sm text-green-600 dark:text-green-400">
                          {(Number(redisStats.last_7_days?.success_rate) || 0).toFixed(1)}% sucesso
                        </p>
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                          {Number(redisStats.last_7_days?.total_keys_deleted) ?? 0} keys removidas
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-500 dark:text-gray-400">Últimos 30 dias</p>
                        <p className="text-lg font-semibold">{Number(redisStats.last_30_days?.total_cleanups) ?? 0} limpezas</p>
                        <p className="text-sm text-green-600 dark:text-green-400">
                          {(Number(redisStats.last_30_days?.success_rate) || 0).toFixed(1)}% sucesso
                        </p>
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                          {Number(redisStats.last_30_days?.total_keys_deleted) ?? 0} keys removidas
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-500 dark:text-gray-400">Média por execução</p>
                        <p className="text-lg font-semibold">{Number(redisStats.avg_keys_deleted_per_run) || 0} keys</p>
                        {(Number(redisStats.avg_bytes_freed_per_run) || 0) > 0 && (
                          <p className="text-xs text-gray-500 dark:text-gray-400">
                            ~{((Number(redisStats.avg_bytes_freed_per_run) || 0) / 1024 / 1024).toFixed(2)} MB
                          </p>
                        )}
                        {(Number(redisStats.avg_duration_seconds) || 0) > 0 && (
                          <p className="text-xs text-gray-500 dark:text-gray-400">
                            ~{Number(redisStats.avg_duration_seconds).toFixed(1)}s duração
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                )}

                <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                  <p className="text-sm text-gray-500 dark:text-gray-400">Projeção de crescimento</p>
                  <p className="mt-1 font-medium">
                    {redisOverview.growth_projection?.message ?? 'N/A'}
                  </p>
                </div>

                {(redisOverview.usage_history?.length ?? 0) > 0 && (
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                    <p className="text-sm font-medium text-gray-700 dark:text-gray-200 mb-2">Uso ao longo do tempo</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">
                      Memória Redis (e AOF em disco quando disponível). Amostras a cada 10 min; últimos 7 dias.
                    </p>
                    <div className="h-64">
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart
                          data={redisOverview.usage_history!.map((s) => ({
                            ...s,
                            time: new Date(s.sampled_at).toLocaleString('pt-BR', {
                              day: '2-digit',
                              month: '2-digit',
                              hour: '2-digit',
                              minute: '2-digit',
                            }),
                            memory_mb: Math.round((s.used_memory / 1024 / 1024) * 100) / 100,
                            aof_mb:
                              s.aof_current_size != null
                                ? Math.round((s.aof_current_size / 1024 / 1024) * 100) / 100
                                : null,
                          }))}
                          margin={{ top: 8, right: 16, left: 8, bottom: 8 }}
                        >
                          <defs>
                            <linearGradient id="redis-mem-grad" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="0%" stopColor="#8b5cf6" stopOpacity={0.3} />
                              <stop offset="100%" stopColor="#8b5cf6" stopOpacity={0} />
                            </linearGradient>
                            <linearGradient id="redis-aof-grad" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="0%" stopColor="#06b6d4" stopOpacity={0.3} />
                              <stop offset="100%" stopColor="#06b6d4" stopOpacity={0} />
                            </linearGradient>
                          </defs>
                          <CartesianGrid strokeDasharray="3 3" className="stroke-gray-200 dark:stroke-gray-700" />
                          <XAxis dataKey="time" tick={{ fontSize: 10 }} />
                          <YAxis
                            tick={{ fontSize: 10 }}
                            tickFormatter={(v) => `${v} MB`}
                            label={{ value: 'MB', angle: -90, position: 'insideLeft', style: { fontSize: 10 } }}
                          />
                          <Tooltip
                            formatter={(value: number) => [`${value} MB`, '']}
                            labelFormatter={(label) => label}
                            contentStyle={{ borderRadius: 8 }}
                          />
                          <Area
                            type="monotone"
                            dataKey="memory_mb"
                            name="Memória"
                            stroke="#8b5cf6"
                            fill="url(#redis-mem-grad)"
                            strokeWidth={2}
                          />
                          {redisOverview.usage_history!.some((s) => s.aof_current_size != null) && (
                            <Area
                              type="monotone"
                              dataKey="aof_mb"
                              name="Disco (AOF)"
                              stroke="#06b6d4"
                              fill="url(#redis-aof-grad)"
                              strokeWidth={2}
                            />
                          )}
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                    {(redisOverview.usage_history!.some((s) => s.keys_profile_pic != null || s.keys_webhook != null)) && (
                      <>
                        <p className="text-sm font-medium text-gray-700 dark:text-gray-200 mt-4 mb-2">Keys por categoria</p>
                        <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">
                          Contagem de keys (fotos de perfil e webhooks) ao longo do tempo. Ajuda a identificar qual categoria cresceu em picos de uso.
                        </p>
                        <div className="h-56">
                          <ResponsiveContainer width="100%" height="100%">
                            <LineChart
                              data={redisOverview.usage_history!.map((s) => ({
                                ...s,
                                time: new Date(s.sampled_at).toLocaleString('pt-BR', {
                                  day: '2-digit',
                                  month: '2-digit',
                                  hour: '2-digit',
                                  minute: '2-digit',
                                }),
                                fotos: s.keys_profile_pic ?? null,
                                webhook: s.keys_webhook ?? null,
                              }))}
                              margin={{ top: 8, right: 16, left: 8, bottom: 8 }}
                            >
                              <CartesianGrid strokeDasharray="3 3" className="stroke-gray-200 dark:stroke-gray-700" />
                              <XAxis dataKey="time" tick={{ fontSize: 10 }} />
                              <YAxis tick={{ fontSize: 10 }} label={{ value: 'Keys', angle: -90, position: 'insideLeft', style: { fontSize: 10 } }} />
                              <Tooltip
                                formatter={(value: number) => [value != null ? value.toLocaleString('pt-BR') : '—', '']}
                                labelFormatter={(label) => label}
                                contentStyle={{ borderRadius: 8 }}
                              />
                              {redisOverview.usage_history!.some((s) => s.keys_profile_pic != null) && (
                                <Line type="monotone" dataKey="fotos" name="Fotos de perfil" stroke="#8b5cf6" strokeWidth={2} dot={{ r: 2 }} connectNulls />
                              )}
                              {redisOverview.usage_history!.some((s) => s.keys_webhook != null) && (
                                <Line type="monotone" dataKey="webhook" name="Webhooks" stroke="#06b6d4" strokeWidth={2} dot={{ r: 2 }} connectNulls />
                              )}
                            </LineChart>
                          </ResponsiveContainer>
                        </div>
                      </>
                    )}
                  </div>
                )}

                {(redisOverview.warnings?.length ?? 0) > 0 && (
                  <div className="rounded-lg bg-amber-50 dark:bg-amber-900/20 p-4">
                    <p className="text-sm font-medium text-amber-800 dark:text-amber-200">Avisos</p>
                    <ul className="mt-1 list-disc list-inside text-sm text-amber-700 dark:text-amber-300">
                      {(redisOverview.warnings ?? []).map((w, i) => (
                        <li key={i}>{w}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ) : null}
          </Card>

          <Card className="p-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
              Histórico
            </h2>
            {isLoadingRedisHistory ? (
              <div className="flex justify-center py-8">
                <LoadingSpinner size="md" />
              </div>
            ) : redisHistory && redisHistory.results.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                  <thead>
                    <tr>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                        Data/Hora
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                        Status
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                        Keys (fotos)
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                        Keys (webhook)
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                        Bytes liberados
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                        Duração
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                        Acionado por
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase">
                        Erro
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {redisHistory.results.map((log) => (
                      <tr
                        key={log.id}
                        className="border-t border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800/50"
                      >
                        <td className="px-4 py-2 text-sm text-gray-900 dark:text-gray-100">
                          {formatDate(log.started_at)}
                        </td>
                        <td className="px-4 py-2">
                          <span
                            className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${getStatusBadge(
                              log.status
                            )}`}
                          >
                            {log.status}
                          </span>
                        </td>
                        <td className="px-4 py-2 text-sm">{log.keys_deleted_profile_pic}</td>
                        <td className="px-4 py-2 text-sm">{log.keys_deleted_webhook}</td>
                        <td className="px-4 py-2 text-sm">
                          {log.bytes_freed_estimate != null
                            ? `${(log.bytes_freed_estimate / 1024 / 1024).toFixed(2)} MB`
                            : '—'}
                        </td>
                        <td className="px-4 py-2 text-sm">
                          {log.duration_seconds != null && log.duration_seconds > 0
                            ? `${Number(log.duration_seconds).toFixed(1)}s`
                            : '—'}
                        </td>
                        <td className="px-4 py-2 text-sm">
                          {log.created_by_email || log.triggered_by}
                        </td>
                        <td className="px-4 py-2 text-sm max-w-[200px]">
                          {log.error_message ? (
                            <span
                              className="text-red-700 dark:text-red-300 truncate block"
                              title={log.error_message}
                            >
                              {log.error_message.length > 60
                                ? `${log.error_message.slice(0, 60)}…`
                                : log.error_message}
                            </span>
                          ) : (
                            '—'
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm text-gray-500 dark:text-gray-400 py-4">
                Nenhuma limpeza registrada.
              </p>
            )}
          </Card>
        </div>
      )}

      {activeTab === 'celery' && (
        <div className="space-y-6">
          <Card className="p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Overview – Celery</h2>
              <Button onClick={fetchCeleryOverview} disabled={isLoadingCeleryOverview} variant="outline" size="sm">
                <RefreshCw className={`h-4 w-4 mr-1 ${isLoadingCeleryOverview ? 'animate-spin' : ''}`} />
                Atualizar
              </Button>
            </div>
            {isLoadingCeleryOverview ? (
              <div className="flex justify-center py-8">
                <LoadingSpinner size="md" />
              </div>
            ) : celeryOverview ? (
              <div className="space-y-4">
                <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4 bg-gray-50/50 dark:bg-gray-800/30">
                  <p className="text-sm font-medium text-gray-700 dark:text-gray-200 mb-1">URL desta API (overview)</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">
                    GET autenticado (superadmin). Útil para documentação ou health manual.
                  </p>
                  <code className="block break-all text-sm rounded-md bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 px-3 py-2 font-mono text-gray-800 dark:text-gray-200">
                    {`${getApiBaseUrl().replace(/\/$/, '')}${celeryOverview.overview_api_path}`}
                  </code>
                </div>

                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                    <p className="text-sm text-gray-500 dark:text-gray-400">Broker configurado</p>
                    <div className="mt-1 flex items-center gap-2">
                      {celeryOverview.config_ok ? (
                        <CheckCircle2 className="h-5 w-5 text-green-500 shrink-0" />
                      ) : (
                        <AlertCircle className="h-5 w-5 text-amber-500 shrink-0" />
                      )}
                      <span className="font-medium">{celeryOverview.config_ok ? 'Sim' : 'Não'}</span>
                    </div>
                  </div>
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                    <p className="text-sm text-gray-500 dark:text-gray-400">Transporte</p>
                    <p className="mt-1 font-mono text-sm font-medium">{celeryOverview.broker_transport}</p>
                  </div>
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                    <p className="text-sm text-gray-500 dark:text-gray-400">Broker alcançável (API)</p>
                    <p className="mt-1 font-medium">
                      {celeryOverview.task_always_eager
                        ? 'N/A (eager)'
                        : celeryOverview.broker_reachable
                          ? 'Sim'
                          : 'Não'}
                    </p>
                    {celeryOverview.broker_error && !celeryOverview.task_always_eager && (
                      <p className="mt-1 text-xs text-red-600 dark:text-red-400 break-words">{celeryOverview.broker_error}</p>
                    )}
                  </div>
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                    <p className="text-sm text-gray-500 dark:text-gray-400">Workers online (ping)</p>
                    <p className="mt-1 font-medium">
                      {celeryOverview.task_always_eager
                        ? 'N/A (eager)'
                        : celeryOverview.workers_online === null
                          ? '—'
                          : String(celeryOverview.workers_online)}
                    </p>
                    {celeryOverview.workers_error && !celeryOverview.task_always_eager && (
                      <p className="mt-1 text-xs text-amber-700 dark:text-amber-300 break-words">{celeryOverview.workers_error}</p>
                    )}
                  </div>
                </div>

                <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                  <p className="text-sm font-medium text-gray-700 dark:text-gray-200 mb-2">Broker (senha mascarada)</p>
                  <code className="block break-all text-xs rounded bg-gray-100 dark:bg-gray-900 px-3 py-2 font-mono text-gray-800 dark:text-gray-200">
                    {celeryOverview.broker_url_masked || '—'}
                  </code>
                </div>

                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                    <p className="text-sm text-gray-500 dark:text-gray-400">Fila padrão</p>
                    <p className="mt-1 font-mono text-sm font-medium">{celeryOverview.default_queue}</p>
                    <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">Task debounce Dify</p>
                    <p className="mt-1 font-mono text-xs break-all">{celeryOverview.dify_debounce_task}</p>
                  </div>
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                    <p className="text-sm text-gray-500 dark:text-gray-400">CELERY_TASK_ALWAYS_EAGER</p>
                    <p className="mt-1 font-medium">{celeryOverview.task_always_eager ? 'true' : 'false'}</p>
                    <p className="mt-3 text-sm text-gray-500 dark:text-gray-400">Comando sugerido (Railway / VPS)</p>
                    <code className="mt-1 block break-all text-xs rounded bg-gray-100 dark:bg-gray-900 px-3 py-2 font-mono">
                      {celeryOverview.worker_start_command}
                    </code>
                  </div>
                </div>

                {celeryOverview.celery_queue && (
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                    <p className="text-sm font-medium text-gray-700 dark:text-gray-200 mb-2">Fila no RabbitMQ (passiva)</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">
                      Só quando o broker é AMQP. Com Redis como broker, use Redis/Outros para inspecionar keys.
                    </p>
                    {celeryOverview.celery_queue.error ? (
                      <p className="text-sm text-red-600 dark:text-red-400">{celeryOverview.celery_queue.error}</p>
                    ) : (
                      <ul className="text-sm space-y-1">
                        <li>
                          <span className="text-gray-500 dark:text-gray-400">Fila:</span>{' '}
                          <span className="font-mono">{celeryOverview.celery_queue.queue}</span>
                        </li>
                        {celeryOverview.celery_queue.messages_ready != null && (
                          <li>
                            <span className="text-gray-500 dark:text-gray-400">Mensagens:</span>{' '}
                            {celeryOverview.celery_queue.messages_ready}
                          </li>
                        )}
                        {celeryOverview.celery_queue.consumers != null && (
                          <li>
                            <span className="text-gray-500 dark:text-gray-400">Consumidores:</span>{' '}
                            {celeryOverview.celery_queue.consumers}
                          </li>
                        )}
                        {celeryOverview.celery_queue.note && (
                          <li className="text-amber-700 dark:text-amber-300">{celeryOverview.celery_queue.note}</li>
                        )}
                      </ul>
                    )}
                  </div>
                )}

                {(celeryOverview.warnings?.length ?? 0) > 0 && (
                  <div className="rounded-lg bg-amber-50 dark:bg-amber-900/20 p-4">
                    <p className="text-sm font-medium text-amber-800 dark:text-amber-200">Avisos</p>
                    <ul className="mt-1 list-disc list-inside text-sm text-amber-700 dark:text-amber-300">
                      {(celeryOverview.warnings ?? []).map((w, i) => (
                        <li key={i}>{w}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-sm text-gray-500 dark:text-gray-400">Carregue os dados com Atualizar.</p>
            )}
          </Card>
        </div>
      )}

      {activeTab === 'rabbitmq' && (
        <div className="space-y-6">
          <Card className="p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Overview – RabbitMQ</h2>
              <Button onClick={fetchRabbitmqOverview} disabled={isLoadingRabbitmqOverview} variant="outline" size="sm">
                <RefreshCw className={`h-4 w-4 mr-1 ${isLoadingRabbitmqOverview ? 'animate-spin' : ''}`} />
                Atualizar
              </Button>
            </div>
            {isLoadingRabbitmqOverview ? (
              <div className="flex justify-center py-8">
                <LoadingSpinner size="md" />
              </div>
            ) : rabbitmqOverview ? (
              <div className="space-y-4">
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                    <p className="text-sm text-gray-500 dark:text-gray-400">Configuração</p>
                    <div className="mt-1 flex items-center gap-2">
                      {rabbitmqOverview.config_ok ? (
                        <CheckCircle2 className="h-5 w-5 text-green-500" />
                      ) : (
                        <AlertCircle className="h-5 w-5 text-amber-500" />
                      )}
                      <span className="font-medium">{rabbitmqOverview.config_ok ? 'OK' : (rabbitmqOverview.error || 'Erro')}</span>
                    </div>
                  </div>
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                    <p className="text-sm text-gray-500 dark:text-gray-400">Conexão</p>
                    <p className="mt-1 font-medium">{rabbitmqOverview.connection_ok ? 'Conectado' : '—'}</p>
                  </div>
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                    <p className="text-sm text-gray-500 dark:text-gray-400">Consumer campanhas</p>
                    <p className="mt-1 font-medium">{rabbitmqOverview.consumer_running ? 'Rodando' : 'Parado'}</p>
                    <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">{rabbitmqOverview.active_campaign_threads} thread(s)</p>
                  </div>
                </div>
                {(rabbitmqOverview.queues?.length ?? 0) > 0 && (
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                    <p className="text-sm font-medium text-gray-700 dark:text-gray-200 mb-2">Filas</p>
                    <div className="overflow-x-auto">
                      <table className="min-w-full text-sm">
                        <thead>
                          <tr className="border-b border-gray-200 dark:border-gray-700">
                            <th className="py-2 text-left font-medium text-gray-500 dark:text-gray-400">Fila</th>
                            <th className="py-2 text-left font-medium text-gray-500 dark:text-gray-400">Mensagens</th>
                            <th className="py-2 text-left font-medium text-gray-500 dark:text-gray-400">Consumidores</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(rabbitmqOverview.queues ?? []).map((q) => (
                            <tr key={q.name} className="border-b border-gray-100 dark:border-gray-800">
                              <td className="py-2 font-mono text-xs">{q.name}</td>
                              <td className="py-2">{q.messages_ready}</td>
                              <td className="py-2">{q.consumers}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
                {(rabbitmqOverview.warnings_queues_not_found?.length ?? 0) > 0 && (
                  <div className="rounded-lg border border-amber-200 dark:border-amber-700 bg-amber-50 dark:bg-amber-900/20 p-4">
                    <p className="text-sm font-medium text-amber-800 dark:text-amber-200">Filas não encontradas</p>
                    <p className="mt-1 text-sm text-amber-700 dark:text-amber-300">
                      {rabbitmqOverview.warnings_queues_not_found!.length} fila(s):{' '}
                      {rabbitmqOverview.warnings_queues_not_found!.join(', ')}
                    </p>
                  </div>
                )}
                {(rabbitmqOverview.warnings?.length ?? 0) > 0 &&
                  (rabbitmqOverview.warnings_queues_not_found?.length ?? 0) === 0 && (
                    <div className="rounded-lg bg-amber-50 dark:bg-amber-900/20 p-4">
                      <p className="text-sm font-medium text-amber-800 dark:text-amber-200">Avisos</p>
                      <ul className="mt-1 list-disc list-inside text-sm text-amber-700 dark:text-amber-300">
                        {(rabbitmqOverview.warnings ?? []).map((w, i) => (
                          <li key={i}>{w}</li>
                        ))}
                      </ul>
                    </div>
                  )}
              </div>
            ) : (
              <p className="text-sm text-gray-500 dark:text-gray-400">Carregue os dados com Atualizar.</p>
            )}
          </Card>
        </div>
      )}

      {activeTab === 'postgres' && (
        <div className="space-y-6">
          <Card className="p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Overview – PostgreSQL</h2>
              <Button onClick={fetchPostgresOverview} disabled={isLoadingPostgresOverview} variant="outline" size="sm">
                <RefreshCw className={`h-4 w-4 mr-1 ${isLoadingPostgresOverview ? 'animate-spin' : ''}`} />
                Atualizar
              </Button>
            </div>
            {isLoadingPostgresOverview ? (
              <div className="flex justify-center py-8">
                <LoadingSpinner size="md" />
              </div>
            ) : postgresOverview ? (
              <div className="space-y-4">
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                    <p className="text-sm text-gray-500 dark:text-gray-400">Configuração</p>
                    <div className="mt-1 flex items-center gap-2">
                      {postgresOverview.config_ok ? (
                        <CheckCircle2 className="h-5 w-5 text-green-500" />
                      ) : (
                        <AlertCircle className="h-5 w-5 text-amber-500" />
                      )}
                      <span className="font-medium">{postgresOverview.config_ok ? 'OK' : (postgresOverview.error || 'Erro')}</span>
                    </div>
                  </div>
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                    <p className="text-sm text-gray-500 dark:text-gray-400">Conexões ativas (atual)</p>
                    <p className="mt-1 font-medium">{postgresOverview.connection_count != null ? postgresOverview.connection_count : '—'}</p>
                  </div>
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                    <p className="text-sm text-gray-500 dark:text-gray-400">Tamanho do banco (atual)</p>
                    <p className="mt-1 font-medium">{postgresOverview.database_size_human ?? '—'}</p>
                  </div>
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                    <p className="text-sm text-gray-500 dark:text-gray-400">Pico 24h – conexões</p>
                    <p className="mt-1 font-medium">
                      {postgresOverview.peak_24h_connections != null ? postgresOverview.peak_24h_connections : '—'}
                    </p>
                  </div>
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                    <p className="text-sm text-gray-500 dark:text-gray-400">Pico 24h – tamanho</p>
                    <p className="mt-1 font-medium">
                      {postgresOverview.peak_24h_size_bytes != null
                        ? postgresOverview.peak_24h_size_bytes >= 1024 ** 3
                          ? `${(postgresOverview.peak_24h_size_bytes / 1024 ** 3).toFixed(2)} GB`
                          : postgresOverview.peak_24h_size_bytes >= 1024 ** 2
                            ? `${(postgresOverview.peak_24h_size_bytes / 1024 ** 2).toFixed(2)} MB`
                            : `${(postgresOverview.peak_24h_size_bytes / 1024).toFixed(1)} KB`
                        : '—'}
                    </p>
                  </div>
                </div>
                {postgresOverview.config_ok && postgresOverview.database_size_bytes != null && (
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                    <p className="text-sm font-medium text-gray-700 dark:text-gray-200 mb-2">Uso total x espaço disponível (disco)</p>
                    <div className="h-64">
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie
                            data={(() => {
                              const used = postgresOverview.database_size_bytes ?? 0
                              const free = postgresOverview.disk_free_bytes ?? 0
                              if (free > 0) {
                                return [
                                  { name: 'Uso do banco', value: used, color: '#10b981' },
                                  { name: 'Espaço disponível', value: free, color: '#0ea5e9' },
                                ]
                              }
                              return [{ name: 'Uso do banco', value: used || 1, color: '#10b981' }]
                            })()}
                            cx="50%"
                            cy="50%"
                            innerRadius={48}
                            outerRadius={80}
                            paddingAngle={2}
                            dataKey="value"
                            label={({ name, value }) =>
                              `${name}: ${value >= 1024 ** 3 ? `${(value / 1024 ** 3).toFixed(2)} GB` : value >= 1024 ** 2 ? `${(value / 1024 ** 2).toFixed(2)} MB` : `${(value / 1024).toFixed(1)} KB`}`
                            }
                          >
                            {(() => {
                              const used = postgresOverview.database_size_bytes ?? 0
                              const free = postgresOverview.disk_free_bytes ?? 0
                              const d = free > 0
                                ? [
                                    { name: 'Uso do banco', value: used, color: '#10b981' },
                                    { name: 'Espaço disponível', value: free, color: '#0ea5e9' },
                                  ]
                                : [{ name: 'Uso do banco', value: used || 1, color: '#10b981' }]
                              return d.map((entry, i) => <Cell key={i} fill={entry.color} />)
                            })()}
                          </Pie>
                          <Tooltip
                            formatter={(value: number) =>
                              value >= 1024 ** 3
                                ? `${(value / 1024 ** 3).toFixed(2)} GB`
                                : value >= 1024 ** 2
                                  ? `${(value / 1024 ** 2).toFixed(2)} MB`
                                  : `${(value / 1024).toFixed(1)} KB`
                            }
                            contentStyle={{ borderRadius: 8 }}
                          />
                          <Legend />
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                    {(postgresOverview.disk_free_bytes == null || postgresOverview.disk_free_bytes === 0) && (
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                        Espaço disponível no disco não disponível (ex.: banco em servidor remoto).
                      </p>
                    )}
                  </div>
                )}
                {(postgresOverview.usage_history?.length ?? 0) > 0 && (
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4 space-y-6">
                    <p className="text-sm font-medium text-gray-700 dark:text-gray-200">Conexões ao longo do tempo</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 -mt-4">
                      Amostras a cada 10 min; qtde de conexões armazenada por 90 dias.
                    </p>
                    <div>
                      <p className="text-sm text-gray-600 dark:text-gray-300 mb-2">Conexões x data/hora (horários de pico)</p>
                      <div className="h-64">
                        <ResponsiveContainer width="100%" height="100%">
                          <AreaChart
                            data={postgresOverview.usage_history!.map((s) => ({
                              ...s,
                              time: new Date(s.sampled_at).toLocaleString('pt-BR', {
                                day: '2-digit',
                                month: '2-digit',
                                hour: '2-digit',
                                minute: '2-digit',
                              }),
                              connections: s.connection_count,
                            }))}
                            margin={{ top: 8, right: 16, left: 8, bottom: 8 }}
                          >
                            <defs>
                              <linearGradient id="pg-conn-grad" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor="#0ea5e9" stopOpacity={0.3} />
                                <stop offset="100%" stopColor="#0ea5e9" stopOpacity={0} />
                              </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" className="stroke-gray-200 dark:stroke-gray-700" />
                            <XAxis dataKey="time" tick={{ fontSize: 10 }} />
                            <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
                            <Tooltip
                              formatter={(value: number) => [value, 'Conexões']}
                              labelFormatter={(label) => label}
                              contentStyle={{ borderRadius: 8 }}
                            />
                            <Area
                              type="monotone"
                              dataKey="connections"
                              name="Conexões"
                              stroke="#0ea5e9"
                              fill="url(#pg-conn-grad)"
                              strokeWidth={2}
                            />
                          </AreaChart>
                        </ResponsiveContainer>
                      </div>
                    </div>
                  </div>
                )}
                {(postgresOverview.top_tables?.length ?? 0) > 0 && (
                  <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                    <p className="text-sm font-medium text-gray-700 dark:text-gray-200 mb-2">Maiores tabelas</p>
                    <div className="overflow-x-auto">
                      <table className="min-w-full text-sm">
                        <thead>
                          <tr className="border-b border-gray-200 dark:border-gray-700">
                            <th className="py-2 text-left font-medium text-gray-500 dark:text-gray-400">Tabela</th>
                            <th className="py-2 text-right font-medium text-gray-500 dark:text-gray-400">Tamanho</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(postgresOverview.top_tables ?? []).map((t) => (
                            <tr key={t.name} className="border-b border-gray-100 dark:border-gray-800">
                              <td className="py-2 font-mono text-xs">{t.name}</td>
                              <td className="py-2 text-right">
                                {t.size_bytes >= 1024 ** 3
                                  ? `${(t.size_bytes / 1024 ** 3).toFixed(2)} GB`
                                  : t.size_bytes >= 1024 ** 2
                                    ? `${(t.size_bytes / 1024 ** 2).toFixed(2)} MB`
                                    : `${(t.size_bytes / 1024).toFixed(1)} KB`}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
                {(postgresOverview.warnings?.length ?? 0) > 0 && (
                  <div className="rounded-lg bg-amber-50 dark:bg-amber-900/20 p-4">
                    <p className="text-sm font-medium text-amber-800 dark:text-amber-200">Avisos</p>
                    <ul className="mt-1 list-disc list-inside text-sm text-amber-700 dark:text-amber-300">
                      {(postgresOverview.warnings ?? []).map((w, i) => (
                        <li key={i}>{w}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-sm text-gray-500 dark:text-gray-400">Carregue os dados com Atualizar.</p>
            )}
          </Card>
        </div>
      )}
    </div>
  )
}
