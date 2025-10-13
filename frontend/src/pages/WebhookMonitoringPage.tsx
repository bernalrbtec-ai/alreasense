import { useState, useEffect } from 'react'
import { RefreshCw, Database, Clock, TrendingUp, AlertCircle, CheckCircle, Filter, ChevronLeft, ChevronRight, Search } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import Toast from '../components/ui/Toast'
import { useToast } from '../hooks/useToast'
import { api } from '../lib/api'

interface CacheStats {
  total_events: number
  total_memory_bytes: number
  event_types: Record<string, number>
  cache_ttl_hours: number
}

interface WebhookEvent {
  _event_id: string
  _cached_at: string
  event: string
  instance: string
  server_url: string
  data: any
}

interface PaginationInfo {
  current_page: number
  page_size: number
  total_events: number
  total_pages: number
  has_next: boolean
  has_previous: boolean
}

interface EventsResponse {
  events: WebhookEvent[]
  pagination: PaginationInfo
  filters: {
    hours: number
    event_type: string
    start_date: string
    end_date: string
    instance: string
  }
}

export default function WebhookMonitoringPage() {
  const [stats, setStats] = useState<CacheStats | null>(null)
  const [recentEvents, setRecentEvents] = useState<WebhookEvent[]>([])
  const [pagination, setPagination] = useState<PaginationInfo | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [selectedEvent, setSelectedEvent] = useState<WebhookEvent | null>(null)
  const { toast, showToast, hideToast } = useToast()

  // Filter states
  const [filters, setFilters] = useState({
    event_type: '',
    start_date: '',
    end_date: '',
    instance: '',
    page: 1,
    page_size: 50
  })
  const [showFilters, setShowFilters] = useState(false)

  useEffect(() => {
    fetchData()
    // Auto refresh every 30 seconds
    const interval = setInterval(fetchData, 30000)
    return () => clearInterval(interval)
  }, [filters.page, filters.page_size])

  const fetchData = async () => {
    try {
      setIsRefreshing(true)
      
      // Fetch cache stats
      const statsResponse = await api.get('/connections/webhooks/cache/stats/')
      setStats(statsResponse.data.data)
      
      // Fetch recent events with filters
      const params = new URLSearchParams()
      if (filters.event_type) params.append('event_type', filters.event_type)
      if (filters.start_date) params.append('start_date', filters.start_date)
      if (filters.end_date) params.append('end_date', filters.end_date)
      if (filters.instance) params.append('instance', filters.instance)
      params.append('page', filters.page.toString())
      params.append('page_size', filters.page_size.toString())
      
      const eventsResponse = await api.get(`/connections/webhooks/cache/events/?${params}`)
      const eventsData: EventsResponse = eventsResponse.data.data
      
      setRecentEvents(eventsData.events)
      setPagination(eventsData.pagination)
      
    } catch (error) {
      console.error('Error fetching webhook monitoring data:', error)
      showToast('Erro ao carregar dados de monitoramento', 'error')
    } finally {
      setIsLoading(false)
      setIsRefreshing(false)
    }
  }

  const handleFilterChange = (key: string, value: string) => {
    setFilters(prev => ({
      ...prev,
      [key]: value,
      page: 1 // Reset to first page when filters change
    }))
  }

  const handlePageChange = (newPage: number) => {
    setFilters(prev => ({
      ...prev,
      page: newPage
    }))
  }

  const clearFilters = () => {
    setFilters({
      event_type: '',
      start_date: '',
      end_date: '',
      instance: '',
      page: 1,
      page_size: 50
    })
  }

  const handleReprocess = async () => {
    try {
      const response = await api.post('/connections/webhooks/cache/reprocess/')
      showToast(`Reprocessamento concluído: ${response.data.data.processed} eventos processados`, 'success')
      fetchData()
    } catch (error) {
      console.error('Error reprocessing events:', error)
      showToast('Erro ao reprocessar eventos', 'error')
    }
  }

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('pt-BR')
  }

  const getEventIcon = (eventType: string) => {
    switch (eventType) {
      case 'messages.upsert': return '📥'
      case 'messages.update': return '📤'
      case 'contacts.update': return '📞'
      case 'connection.update': return '🔗'
      case 'presence.update': return '👤'
      default: return '📋'
    }
  }

  const getEventColor = (eventType: string) => {
    switch (eventType) {
      case 'messages.upsert': return 'text-green-600 bg-green-50'
      case 'messages.update': return 'text-blue-600 bg-blue-50'
      case 'contacts.update': return 'text-purple-600 bg-purple-50'
      case 'connection.update': return 'text-orange-600 bg-orange-50'
      case 'presence.update': return 'text-gray-600 bg-gray-50'
      default: return 'text-gray-600 bg-gray-50'
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Monitoramento de Webhooks</h1>
          <p className="mt-1 text-sm text-gray-500">
            Cache Redis com TTL de 24h para reprocessamento de eventos
          </p>
        </div>
        <div className="flex gap-3">
          <Button 
            onClick={handleReprocess}
            variant="outline"
            className="text-orange-600 border-orange-300 hover:bg-orange-50"
          >
            <RefreshCw className="h-4 w-4 mr-2" />
            Reprocessar
          </Button>
          <Button 
            onClick={fetchData}
            disabled={isRefreshing}
            variant="outline"
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${isRefreshing ? 'animate-spin' : ''}`} />
            Atualizar
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-100 rounded-lg">
                <Database className="h-5 w-5 text-blue-600" />
              </div>
              <div>
                <p className="text-sm text-gray-500">Total de Eventos</p>
                <p className="text-2xl font-bold text-gray-900">{stats.total_events}</p>
              </div>
            </div>
          </Card>

          <Card className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-green-100 rounded-lg">
                <TrendingUp className="h-5 w-5 text-green-600" />
              </div>
              <div>
                <p className="text-sm text-gray-500">Memória Usada</p>
                <p className="text-2xl font-bold text-gray-900">{formatBytes(stats.total_memory_bytes)}</p>
              </div>
            </div>
          </Card>

          <Card className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-purple-100 rounded-lg">
                <Clock className="h-5 w-5 text-purple-600" />
              </div>
              <div>
                <p className="text-sm text-gray-500">TTL Cache</p>
                <p className="text-2xl font-bold text-gray-900">{stats.cache_ttl_hours}h</p>
              </div>
            </div>
          </Card>

          <Card className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-orange-100 rounded-lg">
                <AlertCircle className="h-5 w-5 text-orange-600" />
              </div>
              <div>
                <p className="text-sm text-gray-500">Tipos de Eventos</p>
                <p className="text-2xl font-bold text-gray-900">{Object.keys(stats.event_types).length}</p>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* Event Types Breakdown */}
      {stats && stats.event_types && (
        <Card className="p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Distribuição por Tipo de Evento</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {Object.entries(stats.event_types).map(([eventType, count]) => (
              <div key={eventType} className="text-center">
                <div className="text-2xl mb-1">{getEventIcon(eventType)}</div>
                <p className="text-sm font-medium text-gray-900">{count}</p>
                <p className="text-xs text-gray-500">{eventType}</p>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Recent Events */}
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">
            Eventos Recentes {pagination && `(${pagination.total_events} total)`}
          </h3>
          <div className="flex gap-2">
            <Button
              onClick={() => setShowFilters(!showFilters)}
              variant="outline"
              size="sm"
            >
              <Filter className="h-4 w-4 mr-2" />
              Filtros
            </Button>
          </div>
        </div>

        {/* Filters Panel */}
        {showFilters && (
          <div className="mb-6 p-4 bg-gray-50 rounded-lg">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Tipo de Evento
                </label>
                <input
                  type="text"
                  placeholder="Ex: messages.update"
                  value={filters.event_type}
                  onChange={(e) => handleFilterChange('event_type', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Instância
                </label>
                <input
                  type="text"
                  placeholder="Ex: Teste"
                  value={filters.instance}
                  onChange={(e) => handleFilterChange('instance', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Data Inicial
                </label>
                <input
                  type="datetime-local"
                  value={filters.start_date}
                  onChange={(e) => handleFilterChange('start_date', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Data Final
                </label>
                <input
                  type="datetime-local"
                  value={filters.end_date}
                  onChange={(e) => handleFilterChange('end_date', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-4">
              <Button
                onClick={clearFilters}
                variant="outline"
                size="sm"
              >
                Limpar Filtros
              </Button>
              <Button
                onClick={fetchData}
                size="sm"
              >
                <Search className="h-4 w-4 mr-2" />
                Buscar
              </Button>
            </div>
          </div>
        )}

        <div className="space-y-3">
          {recentEvents.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <AlertCircle className="h-12 w-12 mx-auto mb-4 text-gray-300" />
              <p>Nenhum evento encontrado com os filtros aplicados</p>
            </div>
          ) : (
            recentEvents.map((event) => (
              <div
                key={event._event_id}
                className="flex items-center justify-between p-4 border border-gray-200 rounded-lg hover:bg-gray-50 cursor-pointer"
                onClick={() => setSelectedEvent(event)}
              >
                <div className="flex items-center gap-4">
                  <div className="text-2xl">{getEventIcon(event.event)}</div>
                  <div>
                    <p className="font-medium text-gray-900">{event.event}</p>
                    <p className="text-sm text-gray-500">
                      {event.instance} • {formatDate(event._cached_at)}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${getEventColor(event.event)}`}>
                    {event.event}
                  </span>
                  <CheckCircle className="h-4 w-4 text-green-500" />
                </div>
              </div>
            ))
          )}
        </div>

        {/* Pagination */}
        {pagination && pagination.total_pages > 1 && (
          <div className="mt-6 flex items-center justify-between">
            <div className="text-sm text-gray-700">
              Mostrando {((pagination.current_page - 1) * pagination.page_size) + 1} a{' '}
              {Math.min(pagination.current_page * pagination.page_size, pagination.total_events)} de{' '}
              {pagination.total_events} eventos
            </div>
            <div className="flex items-center gap-2">
              <Button
                onClick={() => handlePageChange(pagination.current_page - 1)}
                disabled={!pagination.has_previous}
                variant="outline"
                size="sm"
              >
                <ChevronLeft className="h-4 w-4" />
                Anterior
              </Button>
              
              <div className="flex items-center gap-1">
                {Array.from({ length: Math.min(5, pagination.total_pages) }, (_, i) => {
                  const pageNum = Math.max(1, Math.min(
                    pagination.total_pages - 4,
                    pagination.current_page - 2
                  )) + i
                  
                  if (pageNum > pagination.total_pages) return null
                  
                  return (
                    <Button
                      key={pageNum}
                      onClick={() => handlePageChange(pageNum)}
                      variant={pageNum === pagination.current_page ? "default" : "outline"}
                      size="sm"
                      className="w-8 h-8 p-0"
                    >
                      {pageNum}
                    </Button>
                  )
                })}
              </div>
              
              <Button
                onClick={() => handlePageChange(pagination.current_page + 1)}
                disabled={!pagination.has_next}
                variant="outline"
                size="sm"
              >
                Próximo
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        )}
      </Card>

      {/* Event Details Modal */}
      {selectedEvent && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-4xl w-full mx-4 max-h-[80vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900">
                Detalhes do Evento: {selectedEvent._event_id}
              </h3>
              <Button
                onClick={() => setSelectedEvent(null)}
                variant="outline"
                size="sm"
              >
                Fechar
              </Button>
            </div>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-sm font-medium text-gray-500">Tipo de Evento</p>
                  <p className="text-sm text-gray-900">{selectedEvent.event}</p>
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-500">Instância</p>
                  <p className="text-sm text-gray-900">{selectedEvent.instance}</p>
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-500">Recebido em</p>
                  <p className="text-sm text-gray-900">{formatDate(selectedEvent._cached_at)}</p>
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-500">Server URL</p>
                  <p className="text-sm text-gray-900">{selectedEvent.server_url}</p>
                </div>
              </div>
              <div>
                <p className="text-sm font-medium text-gray-500 mb-2">Dados do Evento</p>
                <pre className="bg-gray-100 p-4 rounded-lg text-xs overflow-x-auto">
                  {JSON.stringify(selectedEvent.data, null, 2)}
                </pre>
              </div>
            </div>
          </div>
        </div>
      )}

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
