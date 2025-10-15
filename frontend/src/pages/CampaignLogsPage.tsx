import React, { useState, useEffect } from 'react'
import { Search, Filter, Download, RefreshCw, Calendar, User, MessageSquare, AlertCircle, CheckCircle, Clock, X, ChevronDown, ChevronUp } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Input } from '../components/ui/Input'
import { api } from '../lib/api'

interface CampaignLog {
  id: string
  created_at: string
  log_type: string
  log_type_display: string
  message: string
  campaign_id: string
  campaign_name: string
  campaign_status: string
  contact_name?: string
  contact_phone?: string
  instance_name?: string
  user_name: string
  extra_data?: any
}

interface LogsResponse {
  success: boolean
  logs: CampaignLog[]
  pagination: {
    page: number
    page_size: number
    total_count: number
    total_pages: number
    has_next: boolean
    has_previous: boolean
  }
  stats: {
    by_type: Record<string, { count: number; display: string }>
    by_campaign: Record<string, any>
    by_instance: Record<string, any>
  }
  filters_applied: Record<string, any>
}

export default function CampaignLogsPage() {
  const [logs, setLogs] = useState<CampaignLog[]>([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  const [filters, setFilters] = useState({
    campaign_id: '',
    log_type: '',
    instance_name: '',
    contact_name: '',
    date_from: '',
    date_to: ''
  })
  const [showFilters, setShowFilters] = useState(false)
  const [pagination, setPagination] = useState({
    page: 1,
    page_size: 50,
    total_count: 0,
    total_pages: 0,
    has_next: false,
    has_previous: false
  })
  const [stats, setStats] = useState<any>({})

  useEffect(() => {
    fetchLogs()
  }, [filters, pagination.page])

  const fetchLogs = async () => {
    try {
      setLoading(true)
      const params = new URLSearchParams({
        page: pagination.page.toString(),
        page_size: pagination.page_size.toString(),
        ...Object.fromEntries(Object.entries(filters).filter(([_, v]) => v))
      })

      const response = await api.get(`/campaigns/logs/?${params}`)
      const data: LogsResponse = response.data

      if (data.success) {
        setLogs(data.logs)
        setPagination(data.pagination)
        setStats(data.stats)
      }
    } catch (error) {
      console.error('Erro ao buscar logs:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSearch = () => {
    setPagination(prev => ({ ...prev, page: 1 }))
    fetchLogs()
  }

  const handleFilterChange = (key: string, value: string) => {
    setFilters(prev => ({ ...prev, [key]: value }))
  }

  const clearFilters = () => {
    setFilters({
      campaign_id: '',
      log_type: '',
      instance_name: '',
      contact_name: '',
      date_from: '',
      date_to: ''
    })
    setSearchTerm('')
    setPagination(prev => ({ ...prev, page: 1 }))
  }

  const getLogIcon = (logType: string) => {
    switch (logType) {
      case 'campaign_created':
        return <MessageSquare className="h-4 w-4 text-blue-500" />
      case 'message_sent':
        return <CheckCircle className="h-4 w-4 text-green-500" />
      case 'message_failed':
        return <AlertCircle className="h-4 w-4 text-red-500" />
      case 'campaign_started':
        return <Clock className="h-4 w-4 text-blue-500" />
      case 'campaign_paused':
        return <X className="h-4 w-4 text-orange-500" />
      default:
        return <MessageSquare className="h-4 w-4 text-gray-500" />
    }
  }

  const getLogColor = (logType: string) => {
    switch (logType) {
      case 'campaign_created':
        return 'border-l-blue-500 bg-blue-50'
      case 'message_sent':
        return 'border-l-green-500 bg-green-50'
      case 'message_failed':
        return 'border-l-red-500 bg-red-50'
      case 'campaign_started':
        return 'border-l-blue-500 bg-blue-50'
      case 'campaign_paused':
        return 'border-l-orange-500 bg-orange-50'
      default:
        return 'border-l-gray-500 bg-gray-50'
    }
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('pt-BR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  }

  const exportLogs = () => {
    // TODO: Implementar exportação para CSV
    console.log('Exportar logs para CSV')
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">📊 Logs de Campanhas</h1>
          <p className="text-gray-600">Monitore todas as atividades das suas campanhas</p>
        </div>
        <div className="flex gap-2">
          <Button onClick={fetchLogs} variant="outline" size="sm">
            <RefreshCw className="h-4 w-4 mr-2" />
            Atualizar
          </Button>
          <Button onClick={exportLogs} variant="outline" size="sm">
            <Download className="h-4 w-4 mr-2" />
            Exportar
          </Button>
        </div>
      </div>

      {/* Estatísticas */}
      {Object.keys(stats.by_type || {}).length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Object.entries(stats.by_type).map(([type, data]: [string, any]) => (
            <Card key={type} className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600">{data.display}</p>
                  <p className="text-2xl font-bold">{data.count}</p>
                </div>
                {getLogIcon(type)}
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Filtros */}
      <Card className="p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">🔍 Filtros</h3>
          <Button 
            onClick={() => setShowFilters(!showFilters)} 
            variant="outline" 
            size="sm"
          >
            <Filter className="h-4 w-4 mr-2" />
            {showFilters ? 'Ocultar' : 'Mostrar'} Filtros
            {showFilters ? <ChevronUp className="h-4 w-4 ml-2" /> : <ChevronDown className="h-4 w-4 ml-2" />}
          </Button>
        </div>

        {showFilters && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
            <Input
              placeholder="Nome da campanha..."
              value={filters.campaign_id}
              onChange={(e) => handleFilterChange('campaign_id', e.target.value)}
            />
            <Input
              placeholder="Nome do contato..."
              value={filters.contact_name}
              onChange={(e) => handleFilterChange('contact_name', e.target.value)}
            />
            <Input
              placeholder="Nome da instância..."
              value={filters.instance_name}
              onChange={(e) => handleFilterChange('instance_name', e.target.value)}
            />
            <Input
              type="date"
              placeholder="Data inicial..."
              value={filters.date_from}
              onChange={(e) => handleFilterChange('date_from', e.target.value)}
            />
            <Input
              type="date"
              placeholder="Data final..."
              value={filters.date_to}
              onChange={(e) => handleFilterChange('date_to', e.target.value)}
            />
            <select
              className="px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
              value={filters.log_type}
              onChange={(e) => handleFilterChange('log_type', e.target.value)}
            >
              <option value="">Todos os tipos</option>
              <option value="campaign_created">Campanha Criada</option>
              <option value="message_sent">Mensagem Enviada</option>
              <option value="message_failed">Mensagem Falhou</option>
              <option value="campaign_started">Campanha Iniciada</option>
              <option value="campaign_paused">Campanha Pausada</option>
            </select>
          </div>
        )}

        <div className="flex gap-2">
          <Button onClick={handleSearch}>
            <Search className="h-4 w-4 mr-2" />
            Buscar
          </Button>
          <Button onClick={clearFilters} variant="outline">
            <X className="h-4 w-4 mr-2" />
            Limpar
          </Button>
        </div>
      </Card>

      {/* Lista de Logs */}
      <Card className="p-4">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-semibold">
            📝 Logs ({pagination.total_count} total)
          </h3>
          <div className="text-sm text-gray-600">
            Página {pagination.page} de {pagination.total_pages}
          </div>
        </div>

        {loading ? (
          <div className="text-center py-8">
            <RefreshCw className="h-8 w-8 animate-spin mx-auto text-gray-400 mb-2" />
            <p className="text-gray-600">Carregando logs...</p>
          </div>
        ) : logs.length === 0 ? (
          <div className="text-center py-8">
            <MessageSquare className="h-12 w-12 mx-auto text-gray-400 mb-4" />
            <p className="text-gray-600">Nenhum log encontrado</p>
            <p className="text-sm text-gray-500">Tente ajustar os filtros</p>
          </div>
        ) : (
          <div className="space-y-3">
            {logs.map((log) => (
              <div
                key={log.id}
                className={`border-l-4 p-4 rounded-r-lg ${getLogColor(log.log_type)}`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-3">
                    {getLogIcon(log.log_type)}
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-medium text-gray-900">
                          {log.log_type_display}
                        </span>
                        {log.campaign_name && (
                          <span className="text-sm text-blue-600 bg-blue-100 px-2 py-1 rounded">
                            {log.campaign_name}
                          </span>
                        )}
                        {log.instance_name && (
                          <span className="text-sm text-green-600 bg-green-100 px-2 py-1 rounded">
                            {log.instance_name}
                          </span>
                        )}
                      </div>
                      <p className="text-gray-700 mb-2">{log.message}</p>
                      <div className="flex items-center gap-4 text-sm text-gray-500">
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {formatDate(log.created_at)}
                        </span>
                        {log.contact_name && (
                          <span className="flex items-center gap-1">
                            <User className="h-3 w-3" />
                            {log.contact_name}
                            {log.contact_phone && ` (${log.contact_phone})`}
                          </span>
                        )}
                        <span>por {log.user_name}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Paginação */}
        {pagination.total_pages > 1 && (
          <div className="flex justify-between items-center mt-6">
            <Button
              onClick={() => setPagination(prev => ({ ...prev, page: prev.page - 1 }))}
              disabled={!pagination.has_previous}
              variant="outline"
              size="sm"
            >
              Anterior
            </Button>
            <span className="text-sm text-gray-600">
              Página {pagination.page} de {pagination.total_pages}
            </span>
            <Button
              onClick={() => setPagination(prev => ({ ...prev, page: prev.page + 1 }))}
              disabled={!pagination.has_next}
              variant="outline"
              size="sm"
            >
              Próxima
            </Button>
          </div>
        )}
      </Card>
    </div>
  )
}
