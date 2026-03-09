import React, { useState, useEffect } from 'react'
import { RefreshCw, Settings, AlertCircle, CheckCircle2, Loader2, ChevronDown, ChevronRight, Database } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import { api } from '../lib/api'
import { toast } from 'sonner'

interface ProxyOverview {
  config_ok: boolean
  last_execution: {
    started_at: string
    finished_at: string | null
    status: string
    num_proxies: number
    num_instances: number
    num_updated: number
    num_errors: number
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

type TabId = 'proxy' | 'redis'

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

  useEffect(() => {
    fetchOverview()
  }, [])

  useEffect(() => {
    if (activeTab === 'proxy') {
      fetchHistory()
      fetchStats()
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

  const handleRedisCleanup = async () => {
    if (!redisCleanupProfilePic && !redisCleanupWebhook) {
      toast.error('Selecione ao menos um tipo de cache para limpar.')
      return
    }
    try {
      setIsCleaningRedis(true)
      await api.post('/servicos/redis/cleanup/', {
        profile_pic: redisCleanupProfilePic,
        webhook: redisCleanupWebhook,
      })
      toast.success('Limpeza Redis iniciada com sucesso')
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
              <Button
                onClick={fetchOverview}
                disabled={isLoadingOverview}
                variant="outline"
                size="sm"
              >
                <RefreshCw className={`h-4 w-4 mr-1 ${isLoadingOverview ? 'animate-spin' : ''}`} />
                Atualizar
              </Button>
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
                    {overview.is_running ? (
                      <div className="mt-1 flex items-center gap-2">
                        <Loader2 className="h-5 w-5 animate-spin text-blue-500" />
                        <span className="font-medium">Em execução</span>
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

                <div className="pt-4">
                  <Button
                    onClick={handleRotate}
                    disabled={isRotating || !overview.config_ok || overview.is_running}
                  >
                    {isRotating ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        Executando...
                      </>
                    ) : (
                      <>
                        <RefreshCw className="h-4 w-4 mr-2" />
                        Executar rotação
                      </>
                    )}
                  </Button>
                </div>
              </div>
            ) : null}
          </Card>

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

                <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
                  <p className="text-sm text-gray-500 dark:text-gray-400">Projeção de crescimento</p>
                  <p className="mt-1 font-medium">
                    {redisOverview.growth_projection?.message ?? 'N/A'}
                  </p>
                </div>

                {redisOverview.warnings && redisOverview.warnings.length > 0 && (
                  <div className="rounded-lg bg-amber-50 dark:bg-amber-900/20 p-4">
                    <p className="text-sm font-medium text-amber-800 dark:text-amber-200">Avisos</p>
                    <ul className="mt-1 list-disc list-inside text-sm text-amber-700 dark:text-amber-300">
                      {redisOverview.warnings.map((w, i) => (
                        <li key={i}>{w}</li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4 pt-4">
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
                </div>

                <div className="pt-2">
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
            ) : null}
          </Card>

          {redisStats && (
            <Card className="p-6">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-4">
                Estatísticas
              </h2>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Últimos 7 dias</p>
                  <p className="text-xl font-semibold">{Number(redisStats.last_7_days?.total_cleanups) ?? 0} limpezas</p>
                  <p className="text-sm text-green-600 dark:text-green-400">
                    {(Number(redisStats.last_7_days?.success_rate) || 0).toFixed(1)}% sucesso
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    {Number(redisStats.last_7_days?.total_keys_deleted) ?? 0} keys removidas
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Últimos 30 dias</p>
                  <p className="text-xl font-semibold">{Number(redisStats.last_30_days?.total_cleanups) ?? 0} limpezas</p>
                  <p className="text-sm text-green-600 dark:text-green-400">
                    {(Number(redisStats.last_30_days?.success_rate) || 0).toFixed(1)}% sucesso
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    {Number(redisStats.last_30_days?.total_keys_deleted) ?? 0} keys removidas
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Média por execução</p>
                  <p className="text-xl font-semibold">{Number(redisStats.avg_keys_deleted_per_run) || 0} keys</p>
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
            </Card>
          )}

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
    </div>
  )
}
