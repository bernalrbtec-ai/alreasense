import React, { useState, useEffect } from 'react'
import { Plus, Search, Send, Pause, Play, Edit, Trash2, Users, TrendingUp, Copy, FileText, Clock, X, AlertCircle, CheckCircle, Eye, MessageSquare, Phone, ChevronDown, ChevronUp, RefreshCw } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Input } from '../components/ui/Input'
import { showErrorToast, showLoadingToast, updateToastSuccess, updateToastError } from '../lib/toastHelper'
import { api } from '../lib/api'
import CampaignWizardModal from '../components/campaigns/CampaignWizardModal'

interface Campaign {
  id: string
  name: string
  description: string
  rotation_mode: 'round_robin' | 'balanced' | 'intelligent'
  rotation_mode_display: string
  status: 'draft' | 'scheduled' | 'running' | 'paused' | 'completed' | 'cancelled'
  status_display: string
  instances: string[]
  instances_detail: WhatsAppInstance[]
  messages: CampaignMessage[]
  interval_min: number
  interval_max: number
  daily_limit_per_instance: number
  pause_on_health_below: number
  total_contacts: number
  messages_sent: number
  messages_delivered: number
  messages_read: number
  messages_failed: number
  success_rate: number
  read_rate: number
  progress_percentage: number
  scheduled_at?: string
  last_message_sent_at?: string
  next_message_scheduled_at?: string
  countdown_seconds?: number
  next_contact_name?: string
  next_contact_phone?: string
  next_instance_name?: string
  last_contact_name?: string
  last_contact_phone?: string
  last_instance_name?: string
  created_at: string
  // Informações de retry (serão buscadas via API separada)
  retryInfo?: {
    is_retrying: boolean
    retry_contact_name?: string
    retry_contact_phone?: string
    retry_attempt: number
    retry_error_reason?: string
    retry_countdown: number
  }
}

interface WhatsAppInstance {
  id: string
  friendly_name: string
  instance_name: string
  api_url: string
  api_key: string
  status: string
}

interface CampaignMessage {
  id: string
  content: string
  order: number
}

// Componente para contador regressivo
const NextMessageCountdown: React.FC<{ campaign: Campaign }> = ({ campaign }) => {
  const [seconds, setSeconds] = useState<number>(campaign.countdown_seconds || 0)

  useEffect(() => {
    if (seconds <= 0) return

    const timer = setInterval(() => {
      setSeconds(prev => {
        if (prev <= 1) {
          // Quando chegar a 0, buscar dados atualizados
          fetchCampaignData()
          return 0
        }
        return prev - 1
      })
    }, 1000)

    return () => clearInterval(timer)
  }, [seconds])

  const fetchCampaignData = async () => {
    try {
      const response = await api.get(`/campaigns/campaigns/${campaign.id}/`)
      const updatedCampaign = response.data
      setSeconds(updatedCampaign.countdown_seconds || 0)
    } catch (error) {
      console.error('Erro ao buscar dados atualizados da campanha:', error)
    }
  }

  const formatTime = (totalSeconds: number) => {
    const hours = Math.floor(totalSeconds / 3600)
    const minutes = Math.floor((totalSeconds % 3600) / 60)
    const secs = totalSeconds % 60

    if (hours > 0) {
      return `${hours}h ${minutes}m ${secs}s`
    } else if (minutes > 0) {
      return `${minutes}m ${secs}s`
    } else {
      return `${secs}s`
    }
  }

  if (!campaign.next_message_scheduled_at || seconds <= 0) {
    return null
  }

  return (
    <div className="text-sm text-gray-600 bg-blue-50 border border-blue-200 rounded-lg p-2 mt-2">
      <span>Próximo disparo em aproximadamente: <span className="font-bold">{formatTime(seconds)}</span></span>
    </div>
  )
}

const CampaignsPage: React.FC = () => {
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [editingCampaign, setEditingCampaign] = useState<Campaign | null>(null)
  const [showLogsModal, setShowLogsModal] = useState(false)
  const [selectedCampaignForLogs, setSelectedCampaignForLogs] = useState<Campaign | null>(null)
  const [logs, setLogs] = useState<any[]>([])

  useEffect(() => {
    fetchData(true) // Primeira carga com loading
    
    // Polling a cada 30 segundos SEM loading
    const interval = setInterval(() => fetchData(false), 30000)
    return () => clearInterval(interval)
  }, [])

  const fetchData = async (showLoading = false) => {
    try {
      if (showLoading) {
        setLoading(true)
      }
      const response = await api.get('/campaigns/campaigns/')
      const campaigns = response.data.results || response.data
      
      // Buscar informações de retry para campanhas em execução
      const campaignsWithRetry = await Promise.all(
        campaigns.map(async (campaign: Campaign) => {
          if (campaign.status === 'running') {
            try {
              const retryResponse = await api.get(`/campaigns/campaigns/${campaign.id}/retry-info/`)
              if (retryResponse.data.success) {
                campaign.retryInfo = retryResponse.data.retry_info
              }
            } catch (error) {
              console.error(`Erro ao buscar retry info para campanha ${campaign.id}:`, error)
            }
          }
          return campaign
        })
      )
      
      setCampaigns(campaignsWithRetry)
    } catch (error: any) {
      console.error('Erro ao buscar campanhas:', error)
      showErrorToast('buscar', 'Campanhas', error)
    } finally {
      if (showLoading) {
        setLoading(false)
      }
    }
  }

  const handleStart = async (campaign: Campaign) => {
    const toastId = showLoadingToast('iniciando', 'Campanha')
    
    try {
      await api.post(`/campaigns/campaigns/${campaign.id}/start/`)
      updateToastSuccess(toastId, 'iniciada', 'Campanha')
      fetchData(false)
    } catch (error: any) {
      updateToastError(toastId, 'iniciar', 'Campanha', error)
    }
  }

  const handlePause = async (campaign: Campaign) => {
    const toastId = showLoadingToast('pausando', 'Campanha')
    
    try {
      await api.post(`/campaigns/campaigns/${campaign.id}/pause/`)
      updateToastSuccess(toastId, 'pausada', 'Campanha')
      fetchData(false)
    } catch (error: any) {
      updateToastError(toastId, 'pausar', 'Campanha', error)
    }
  }

  const handleResume = async (campaign: Campaign) => {
    const toastId = showLoadingToast('retomando', 'Campanha')
    
    try {
      await api.post(`/campaigns/campaigns/${campaign.id}/resume/`)
      updateToastSuccess(toastId, 'retomada', 'Campanha')
      fetchData(false)
    } catch (error: any) {
      updateToastError(toastId, 'retomar', 'Campanha', error)
    }
  }

  const handleEdit = (campaign: Campaign) => {
    setEditingCampaign(campaign)
    setShowModal(true)
  }

  const handleDuplicate = async (campaign: Campaign) => {
    const toastId = showLoadingToast('duplicando', 'Campanha')
    
    try {
      const duplicateData = {
        name: `${campaign.name} (Cópia)`,
        description: campaign.description,
        rotation_mode: campaign.rotation_mode,
        instances: campaign.instances,
        messages: campaign.messages.map(msg => ({ content: msg.content, order: msg.order })),
        interval_min: campaign.interval_min,
        interval_max: campaign.interval_max,
        daily_limit_per_instance: campaign.daily_limit_per_instance,
        pause_on_health_below: campaign.pause_on_health_below
      }
      
      await api.post('/campaigns/campaigns/', duplicateData)
      updateToastSuccess(toastId, 'duplicada', 'Campanha')
      fetchData(false)
    } catch (error: any) {
      console.error('Erro ao duplicar campanha:', error)
      updateToastError(toastId, 'duplicar', 'Campanha', error)
    }
  }

  const handleViewLogs = async (campaign: Campaign) => {
    setSelectedCampaignForLogs(campaign)
    setShowLogsModal(true)
    
    try {
      // Usar a nova API de logs com filtro por campanha
      const response = await api.get(`/campaigns/logs/?campaign_id=${campaign.id}`)
      const data = response.data
      
      if (data.success) {
        setLogs(data.logs)
      } else {
        console.error('Erro na API de logs:', data.error)
        setLogs([])
      }
    } catch (error: any) {
      console.error('Erro ao buscar logs:', error)
      showErrorToast('buscar', 'Logs', error)
    }
  }

  // Função para obter ícone do tipo de log
  const getLogIcon = (logType: string) => {
    switch (logType) {
      case 'campaign_created':
      case 'created':
        return <MessageSquare className="h-4 w-4 text-blue-500" />
      case 'campaign_started':
      case 'started':
        return <Play className="h-4 w-4 text-green-500" />
      case 'message_sent':
        return <CheckCircle className="h-4 w-4 text-green-500" />
      case 'message_failed':
        return <AlertCircle className="h-4 w-4 text-red-500" />
      case 'campaign_paused':
      case 'paused':
        return <Pause className="h-4 w-4 text-orange-500" />
      case 'campaign_resumed':
      case 'resumed':
        return <Play className="h-4 w-4 text-blue-500" />
      case 'campaign_completed':
      case 'completed':
        return <CheckCircle className="h-4 w-4 text-purple-500" />
      default:
        return <FileText className="h-4 w-4 text-gray-500" />
    }
  }

  // Função para obter cor do tipo de log
  const getLogColor = (logType: string) => {
    switch (logType) {
      case 'campaign_created':
      case 'created':
        return 'border-l-blue-500 bg-blue-50'
      case 'campaign_started':
      case 'started':
        return 'border-l-green-500 bg-green-50'
      case 'message_sent':
        return 'border-l-green-500 bg-green-50'
      case 'message_failed':
        return 'border-l-red-500 bg-red-50'
      case 'campaign_paused':
      case 'paused':
        return 'border-l-orange-500 bg-orange-50'
      case 'campaign_resumed':
      case 'resumed':
        return 'border-l-blue-500 bg-blue-50'
      case 'campaign_completed':
      case 'completed':
        return 'border-l-purple-500 bg-purple-50'
      default:
        return 'border-l-gray-500 bg-gray-50'
    }
  }

  // Função para formatar data
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

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'draft': return 'bg-gray-100 text-gray-800'
      case 'scheduled': return 'bg-blue-100 text-blue-800'
      case 'running': return 'bg-green-100 text-green-800'
      case 'paused': return 'bg-yellow-100 text-yellow-800'
      case 'completed': return 'bg-purple-100 text-purple-800'
      case 'cancelled': return 'bg-red-100 text-red-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  const filteredCampaigns = campaigns
    .filter(campaign =>
    campaign.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    campaign.description.toLowerCase().includes(searchTerm.toLowerCase())
  )
    .sort((a, b) => {
      // Ordem: RASCUNHOS -> ATIVAS -> CONCLUÍDAS
      const statusOrder = {
        'draft': 1,        // RASCUNHOS primeiro
        'scheduled': 2,    // AGENDADAS
        'running': 3,      // ATIVAS
        'paused': 4,       // PAUSADAS
        'completed': 5,    // CONCLUÍDAS
        'cancelled': 6     // CANCELADAS
      }

      const aOrder = statusOrder[a.status as keyof typeof statusOrder] || 999
      const bOrder = statusOrder[b.status as keyof typeof statusOrder] || 999

      if (aOrder !== bOrder) {
        return aOrder - bOrder
      }

      // Se mesmo status, ordenar por data de criação (mais recentes primeiro)
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    })

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Carregando campanhas...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">📱 Campanhas</h1>
          <p className="text-gray-600">Gerencie suas campanhas de WhatsApp</p>
        </div>
        <Button onClick={() => setShowModal(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Nova Campanha
        </Button>
      </div>

      {/* Filtros */}
      <Card className="p-4">
        <div className="flex gap-4">
        <div className="flex-1">
            <Input
              placeholder="Buscar campanhas..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full"
            />
          </div>
        </div>
      </Card>

      {/* Lista de Campanhas */}
      <div className="grid gap-6">
        {filteredCampaigns.map((campaign) => (
          <Card key={campaign.id} className="p-6">
            <div className="flex justify-between items-start mb-4">
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-2">
                  <h3 className="text-xl font-semibold text-gray-900">{campaign.name}</h3>
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(campaign.status)}`}>
                    {campaign.status_display}
                  </span>
                </div>
                <p className="text-gray-600 mb-3">{campaign.description}</p>
                
                <div className="flex flex-wrap gap-4 text-sm text-gray-500 mb-4">
                  <span className="flex items-center gap-1">
                    <Users className="h-4 w-4" />
                    {campaign.total_contacts} contatos
                  </span>
                  <span className="flex items-center gap-1">
                    <MessageSquare className="h-4 w-4" />
                    {campaign.messages.length} mensagens
                  </span>
                  <span className="flex items-center gap-1">
                    <TrendingUp className="h-4 w-4" />
                    {campaign.success_rate}% sucesso
                  </span>
                  </div>

                {/* Contador regressivo */}
                <NextMessageCountdown campaign={campaign} />

                {/* Informações de retry ou próximo disparo */}
                {campaign.status === 'running' && (
                  <div className="mt-4 space-y-2 text-sm">
                    {/* Mostrar retry se estiver ativo */}
                    {campaign.retryInfo?.is_retrying ? (
                      <div className="space-y-2">
                        <div className="p-3 bg-orange-50 border border-orange-200 rounded-md">
                          <div className="flex items-center gap-2 text-orange-700 mb-2">
                            <RefreshCw className="h-4 w-4 animate-spin" />
                            <span className="font-medium">Tentativa {campaign.retryInfo.retry_attempt}/3</span>
                          </div>
                          <div className="text-sm text-gray-600">
                            <strong>Contato:</strong> {campaign.retryInfo.retry_contact_name} ({campaign.retryInfo.retry_contact_phone})
                          </div>
                          {campaign.retryInfo.retry_error_reason && (
                            <div className="text-sm text-red-600">
                              <strong>Erro:</strong> {campaign.retryInfo.retry_error_reason}
                            </div>
                          )}
                          <div className="text-sm text-blue-600">
                            <strong>Próximo retry em:</strong> {campaign.retryInfo.retry_countdown}s
                          </div>
                        </div>
                      </div>
                    ) : (
                      /* Layout com progress bars e informações lado a lado */
                      <div className="space-y-2">
                        {/* Linha superior: Próximo contato + Progress bars */}
                        <div className="flex items-start justify-between gap-4">
                          <div className="flex-1">
                            {campaign.next_contact_name && (
                              <div className="flex items-center gap-2 text-blue-600">
                                <Users className="h-4 w-4" />
                                <span><strong>Próximo:</strong> {campaign.next_contact_name} ({campaign.next_contact_phone})</span>
                              </div>
                            )}
                          </div>
                          
                          {/* Progress bars */}
                          <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 min-w-[280px]">
                            <div className="space-y-2">
                              <div className="flex items-center justify-between text-sm">
                                <span className="flex items-center gap-2 text-blue-600">
                                  <Send className="h-4 w-4" />
                                  Enviadas
                                </span>
                                <span className="font-medium">{((campaign.messages_sent / campaign.total_contacts) * 100).toFixed(0)}%</span>
                              </div>
                              <div className="w-full bg-gray-200 rounded-full h-2">
                                <div className="bg-blue-400 h-2 rounded-full" style={{width: `${(campaign.messages_sent / campaign.total_contacts) * 100}%`}}></div>
                              </div>
                              
                              <div className="flex items-center justify-between text-sm">
                                <span className="flex items-center gap-2 text-green-600">
                                  <CheckCircle className="h-4 w-4" />
                                  Entregues
                                </span>
                                <span className="font-medium">
                                  {campaign.messages_sent > 0 ? ((campaign.messages_delivered / campaign.messages_sent) * 100).toFixed(0) : 0}%
                                </span>
                              </div>
                              <div className="w-full bg-gray-200 rounded-full h-2">
                                <div className="bg-green-400 h-2 rounded-full" style={{width: `${campaign.messages_sent > 0 ? (campaign.messages_delivered / campaign.messages_sent) * 100 : 0}%`}}></div>
                              </div>
                              
                              <div className="flex items-center justify-between text-sm">
                                <span className="flex items-center gap-2 text-yellow-600">
                                  <Eye className="h-4 w-4" />
                                  Lidas
                                </span>
                                <span className="font-medium">
                                  {campaign.messages_delivered > 0 ? ((campaign.messages_read / campaign.messages_delivered) * 100).toFixed(0) : 0}%
                                </span>
                              </div>
                              <div className="w-full bg-gray-200 rounded-full h-2">
                                <div className="bg-yellow-400 h-2 rounded-full" style={{width: `${campaign.messages_delivered > 0 ? (campaign.messages_read / campaign.messages_delivered) * 100 : 0}%`}}></div>
                              </div>
                              
                              <div className="flex items-center justify-between text-sm">
                                <span className="flex items-center gap-2 text-red-600">
                                  <X className="h-4 w-4" />
                                  Falhas
                                </span>
                                <span className="font-medium">{((campaign.messages_failed / campaign.total_contacts) * 100).toFixed(0)}%</span>
                              </div>
                              <div className="w-full bg-gray-200 rounded-full h-2">
                                <div className="bg-red-400 h-2 rounded-full" style={{width: `${(campaign.messages_failed / campaign.total_contacts) * 100}%`}}></div>
                              </div>
                            </div>
                          </div>
                        </div>
                        
                        {/* Linha inferior: Último contato + Instância + Horário */}
                        <div className="flex items-center justify-between gap-4">
                          <div className="flex-1">
                            {campaign.last_contact_name && (
                              <div className="flex items-center gap-2 text-gray-600">
                                <Clock className="h-4 w-4" />
                                <span><strong>Último:</strong> {campaign.last_contact_name} ({campaign.last_contact_phone})</span>
                              </div>
                            )}
                          </div>
                          
                          <div className="flex items-center gap-4 text-sm text-gray-500">
                            {campaign.next_instance_name && (
                              <div className="flex items-center gap-2 text-green-600">
                                <Phone className="h-4 w-4" />
                                <span><strong>Via:</strong> {campaign.next_instance_name}</span>
                              </div>
                            )}
                            {campaign.last_message_sent_at && (
                              <div className="flex items-center gap-2 text-gray-500">
                                <Clock className="h-4 w-4" />
                                <span><strong>Enviado em:</strong> {new Date(campaign.last_message_sent_at).toLocaleString('pt-BR')}</span>
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Status de falhas totais (apenas se não há retry ativo) */}
                {campaign.status === 'running' && !campaign.retryInfo?.is_retrying && campaign.messages_failed > 0 && (
                  <div className="mt-3 p-2 bg-red-50 border border-red-200 rounded-md">
                    <div className="flex items-center gap-2 text-red-700">
                      <AlertCircle className="h-4 w-4" />
                      <span className="text-sm font-medium">
                        {campaign.messages_failed} mensagem(s) falharam
                      </span>
                    </div>
                  </div>
                )}
              </div>
              
              <div className="flex gap-2">
                {/* Ações básicas */}
                {campaign.status === 'draft' && (
                  <Button onClick={() => handleStart(campaign)} size="sm">
                    <Play className="h-4 w-4 mr-2" />
                    Iniciar
                  </Button>
                )}
                
                {campaign.status === 'running' && (
                  <Button onClick={() => handlePause(campaign)} variant="outline" size="sm">
                    <Pause className="h-4 w-4 mr-2" />
                    Pausar
                  </Button>
                )}
                
                {campaign.status === 'paused' && (
                  <Button onClick={() => handleResume(campaign)} size="sm">
                    <Play className="h-4 w-4 mr-2" />
                    Retomar
                  </Button>
                )}
                
                {/* Ações secundárias */}
                {campaign.status !== 'running' && (
                  <Button onClick={() => handleEdit(campaign)} variant="outline" size="sm">
                    <Edit className="h-4 w-4" />
                  </Button>
                )}
                
                <Button onClick={() => handleDuplicate(campaign)} variant="outline" size="sm">
                  <Copy className="h-4 w-4" />
                  </Button>
                
                {/* Ver Logs - para todas exceto draft */}
                {campaign.status !== 'draft' && (
                  <Button 
                    variant="outline" 
                    size="sm"
                    onClick={() => handleViewLogs(campaign)}
                    title="Ver logs da campanha"
                  >
                    <FileText className="h-4 w-4" />
                  </Button>
                )}
              </div>
            </div>

            {/* Progresso e Métricas */}
            {campaign.total_contacts > 0 && (
              <div className="space-y-4">
                <div className="bg-gray-200 rounded-full h-2">
                  <div 
                    className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${campaign.progress_percentage}%` }}
                  ></div>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="text-center">
                    <div className="text-2xl font-bold text-green-600">{campaign.messages_sent}</div>
                    <div className="text-sm text-gray-600">Enviadas</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-blue-600">{campaign.messages_delivered}</div>
                    <div className="text-sm text-gray-600">Entregues</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-purple-600">{campaign.messages_read}</div>
                    <div className="text-sm text-gray-600">Lidas</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-red-600">{campaign.messages_failed}</div>
                    <div className="text-sm text-gray-600">Falhas</div>
                      </div>
                    </div>
              </div>
            )}
          </Card>
        ))}
      </div>

      {/* Modal de Criação/Edição */}
      {showModal && (
        <CampaignWizardModal
          isOpen={showModal}
          onClose={() => {
            setShowModal(false)
            setEditingCampaign(null)
          }}
          onSuccess={fetchData}
          editingCampaign={editingCampaign}
        />
      )}

      {/* Modal de Logs */}
      {showLogsModal && selectedCampaignForLogs && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-modal p-2 sm:p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-5xl w-full max-h-[95vh] sm:max-h-[90vh] overflow-hidden flex flex-col">
            <div className="flex justify-between items-center p-3 sm:p-4 border-b sticky top-0 bg-white z-10">
              <div className="flex-1 min-w-0">
                <h2 className="text-lg sm:text-xl font-bold truncate">📊 Logs da Campanha</h2>
                <p className="text-xs sm:text-sm text-gray-500 truncate">{selectedCampaignForLogs.name}</p>
              </div>
              <button onClick={() => setShowLogsModal(false)} className="text-gray-400 hover:text-gray-600 ml-2 flex-shrink-0">
                <X className="h-5 w-5 sm:h-6 sm:w-6" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-3 sm:p-4">
              {logs.length === 0 ? (
                <div className="text-center py-6 sm:py-8 text-gray-500">
                  <FileText className="h-12 w-12 mx-auto text-gray-400 mb-4" />
                  <p className="text-gray-600">Nenhum log encontrado</p>
                  <p className="text-sm text-gray-500">Esta campanha ainda não possui logs</p>
                </div>
              ) : (
                <div className="space-y-3 sm:space-y-4">
                  {/* Estatísticas Rápidas */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 sm:gap-4 mb-4">
                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-2 sm:p-3 text-center">
                      <div className="text-lg sm:text-xl font-bold text-blue-600">
                        {logs.filter((log: any) => log.log_type === 'message_sent').length}
                      </div>
                      <div className="text-xs sm:text-sm text-blue-800">Enviadas</div>
                    </div>
                    <div className="bg-green-50 border border-green-200 rounded-lg p-2 sm:p-3 text-center">
                      <div className="text-lg sm:text-xl font-bold text-green-600">
                        {logs.filter((log: any) => log.log_type === 'message_delivered').length}
                      </div>
                      <div className="text-xs sm:text-sm text-green-800">Entregues</div>
                    </div>
                    <div className="bg-purple-50 border border-purple-200 rounded-lg p-2 sm:p-3 text-center">
                      <div className="text-lg sm:text-xl font-bold text-purple-600">
                        {logs.filter((log: any) => log.log_type === 'message_read').length}
                      </div>
                      <div className="text-xs sm:text-sm text-purple-800">Lidas</div>
                    </div>
                    <div className="bg-red-50 border border-red-200 rounded-lg p-2 sm:p-3 text-center">
                      <div className="text-lg sm:text-xl font-bold text-red-600">
                        {logs.filter((log: any) => log.log_type === 'message_failed').length}
                      </div>
                      <div className="text-xs sm:text-sm text-red-800">Falhas</div>
                    </div>
                  </div>
                  
                  {/* Lista de Logs */}
                  <div className="space-y-3">
                    {logs.map((log: any, idx: number) => (
                      <div
                        key={log.id || idx}
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
                                    <Users className="h-3 w-3" />
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
                </div>
              )}
            </div>

            <div className="p-3 sm:p-4 border-t bg-gray-50 flex justify-end">
              <Button onClick={() => setShowLogsModal(false)} size="sm" className="w-full sm:w-auto">
                Fechar
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default CampaignsPage
