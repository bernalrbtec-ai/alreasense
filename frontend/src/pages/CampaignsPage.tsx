import React, { useState, useEffect, useCallback } from 'react'
import { Plus, Search, X, FileText, CheckCircle, AlertCircle, MessageSquare, Play, Pause, Clock, Users, Download, Send, Eye, RefreshCw } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Input } from '../components/ui/Input'
import { showErrorToast, showLoadingToast, updateToastSuccess, updateToastError } from '../lib/toastHelper'
import { api } from '../lib/api'
import CampaignWizardModal from '../components/campaigns/CampaignWizardModal'
import CampaignCardOptimized from '../components/campaigns/CampaignCardOptimized'
import { AddContactsModal } from '../components/campaigns/AddContactsModal'

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


const CampaignsPage: React.FC = () => {
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [editingCampaign, setEditingCampaign] = useState<Campaign | null>(null)
  const [showLogsModal, setShowLogsModal] = useState(false)
  const [selectedCampaignForLogs, setSelectedCampaignForLogs] = useState<Campaign | null>(null)
  const [logs, setLogs] = useState<any[]>([])
  const [showStoppedCampaigns, setShowStoppedCampaigns] = useState(false)
  const [logsLoading, setLogsLoading] = useState(false)
  const [showAddContactsModal, setShowAddContactsModal] = useState(false)
  const [selectedCampaignForAddContacts, setSelectedCampaignForAddContacts] = useState<Campaign | null>(null)

  useEffect(() => {
    fetchData(true) // Primeira carga com loading
    
    // Polling a cada 5 segundos para campanhas em execução (atualização em tempo real)
    const interval = setInterval(() => fetchData(false), 5000)
    return () => clearInterval(interval)
  }, [showStoppedCampaigns])

  // ✅ NOVO: Escutar atualizações de campanha via WebSocket (tempo real)
  useEffect(() => {
    // Criar um listener customizado para campaign_update
    const handleCampaignUpdate = (event: CustomEvent) => {
      const update = event.detail
      if (update && update.campaign_id) {
        console.log('📡 [CAMPAIGNS] Recebido update via WebSocket:', update.campaign_id, update.type)
        
        // Atualizar campanha específica no estado
        setCampaigns((prevCampaigns) => {
          return prevCampaigns.map((campaign) => {
            if (campaign.id === update.campaign_id) {
              // ✅ CORREÇÃO: Usar countdown_seconds diretamente do RabbitMQ (já calculado no backend)
              return {
                ...campaign,
                next_contact_name: update.next_contact_name !== undefined ? update.next_contact_name : campaign.next_contact_name,
                next_contact_phone: update.next_contact_phone !== undefined ? update.next_contact_phone : campaign.next_contact_phone,
                next_instance_name: update.next_instance_name !== undefined ? update.next_instance_name : campaign.next_instance_name,
                next_message_scheduled_at: update.next_message_scheduled_at !== undefined ? update.next_message_scheduled_at : campaign.next_message_scheduled_at,
                countdown_seconds: update.countdown_seconds !== undefined ? update.countdown_seconds : campaign.countdown_seconds,
              }
            }
            return campaign
          })
        })
      }
    }
    
    // Registrar listener customizado
    window.addEventListener('campaign_update', handleCampaignUpdate as EventListener)
    
    return () => {
      window.removeEventListener('campaign_update', handleCampaignUpdate as EventListener)
    }
  }, [])

  // ✅ MELHORIA: Função para buscar logs (reutilizável e estável com useCallback)
  const fetchLogsForModal = useCallback(async (showLoading = false) => {
    if (!selectedCampaignForLogs) return

    try {
      if (showLoading) setLogsLoading(true)
      
      const campaignId = selectedCampaignForLogs.id
      // ✅ CORREÇÃO: Buscar TODOS os logs sem paginação (page_size=10000)
      const logsResponse = await api.get(`/campaigns/logs/?campaign_id=${campaignId}&page_size=10000`)
      const logsData = logsResponse.data
      
      // ✅ CORREÇÃO: Também atualizar dados da campanha para ter estatísticas corretas nos cards
      const campaignResponse = await api.get(`/campaigns/${campaignId}/`)
      const campaignData = campaignResponse.data
      
      if (logsData.success && logsData.logs) {
        // ✅ CORREÇÃO: Atualizar logs mesmo se já existirem
        setLogs(logsData.logs)
        
        // ✅ CORREÇÃO: Atualizar dados da campanha para ter estatísticas corretas nos cards
        setSelectedCampaignForLogs({
          ...selectedCampaignForLogs,
          messages_sent: campaignData.messages_sent || 0,
          messages_delivered: campaignData.messages_delivered || 0,
          messages_read: campaignData.messages_read || 0,
          messages_failed: campaignData.messages_failed || 0,
        })
        
        console.log(`✅ [LOGS] Atualizados ${logsData.logs.length} logs para campanha ${campaignId}`)
        console.log(`   📊 Estatísticas da campanha (usadas nos cards):`, {
          sent: campaignData.messages_sent || 0,
          delivered: campaignData.messages_delivered || 0,
          read: campaignData.messages_read || 0,
          failed: campaignData.messages_failed || 0,
        })
        console.log(`   📋 Logs separados encontrados:`, {
          sent: logsData.logs.filter((l: any) => l.log_type === 'message_sent').length,
          delivered: logsData.logs.filter((l: any) => l.log_type === 'message_delivered').length,
          read: logsData.logs.filter((l: any) => l.log_type === 'message_read').length,
          failed: logsData.logs.filter((l: any) => l.log_type === 'message_failed').length,
        })
        // ✅ DEBUG: Mostrar IDs dos logs de delivered e read
        const deliveredLogs = logsData.logs.filter((l: any) => l.log_type === 'message_delivered')
        const readLogs = logsData.logs.filter((l: any) => l.log_type === 'message_read')
        if (deliveredLogs.length > 0) {
          console.log(`   ✅ Logs de delivered:`, deliveredLogs.map((l: any) => ({ id: l.id, contact: l.contact_name, created: l.created_at })))
        }
        if (readLogs.length > 0) {
          console.log(`   👁️ Logs de read:`, readLogs.map((l: any) => ({ id: l.id, contact: l.contact_name, created: l.created_at })))
        }
      }
    } catch (error: any) {
      console.error('Erro ao atualizar logs:', error)
    } finally {
      if (showLoading) setLogsLoading(false)
    }
  }, [selectedCampaignForLogs])

  // ✅ MELHORIA: Polling automático para atualizar logs quando o modal está aberto
  useEffect(() => {
    if (!showLogsModal || !selectedCampaignForLogs) return

    // Buscar imediatamente
    fetchLogsForModal(true)

    // ✅ CORREÇÃO: Polling a cada 2 segundos (mais frequente) quando o modal está aberto
    const interval = setInterval(() => fetchLogsForModal(false), 2000)
    return () => clearInterval(interval)
  }, [showLogsModal, selectedCampaignForLogs?.id, fetchLogsForModal]) // ✅ CORREÇÃO: Incluir fetchLogsForModal nas dependências

  const fetchData = async (showLoading = false) => {
    try {
      if (showLoading) {
        setLoading(true)
      }
      // Incluir campanhas paradas se solicitado
      // ✅ CORREÇÃO: Adicionar timestamp para evitar cache do navegador
      const timestamp = new Date().getTime()
      const url = showStoppedCampaigns 
        ? `/campaigns/?status=stopped&_t=${timestamp}` 
        : `/campaigns/?_t=${timestamp}`
      const response = await api.get(url)
      const campaigns = Array.isArray(response.data.results) ? response.data.results : 
                       Array.isArray(response.data) ? response.data : []
      
      // Buscar informações de retry para campanhas em execução
      const campaignsWithRetry = await Promise.all(
        campaigns.map(async (campaign: Campaign) => {
          if (campaign.status === 'running') {
            try {
              const retryResponse = await api.get(`/campaigns/${campaign.id}/retry-info/`)
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
      await api.post(`/campaigns/${campaign.id}/start/`)
      updateToastSuccess(toastId, 'iniciada', 'Campanha')
      fetchData(false)
    } catch (error: any) {
      updateToastError(toastId, 'iniciar', 'Campanha', error)
    }
  }

  const handlePause = async (campaign: Campaign) => {
    const toastId = showLoadingToast('pausando', 'Campanha')
    
    try {
      await api.post(`/campaigns/${campaign.id}/pause/`)
      updateToastSuccess(toastId, 'pausada', 'Campanha')
      fetchData(false)
    } catch (error: any) {
      updateToastError(toastId, 'pausar', 'Campanha', error)
    }
  }

  const handleResume = async (campaign: Campaign) => {
    const toastId = showLoadingToast('retomando', 'Campanha')
    
    try {
      await api.post(`/campaigns/${campaign.id}/resume/`)
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

  const handleViewLogs = async (campaign: Campaign) => {
    setSelectedCampaignForLogs(campaign)
    setShowLogsModal(true)
    // ✅ CORREÇÃO: Os logs serão buscados automaticamente pelo useEffect quando o modal abrir
    // Não precisa buscar aqui, o useEffect já faz isso
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
        return <Send className="h-4 w-4 text-blue-500" />
      case 'message_delivered':
        return <CheckCircle className="h-4 w-4 text-green-500" />
      case 'message_read':
        return <Eye className="h-4 w-4 text-purple-500" />
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
        return 'border-l-blue-500 bg-blue-50'
      case 'message_delivered':
        return 'border-l-green-500 bg-green-50'
      case 'message_read':
        return 'border-l-purple-500 bg-purple-50'
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


  const filteredCampaigns = Array.isArray(campaigns) ? campaigns
    .filter(campaign =>
    campaign.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    campaign.description.toLowerCase().includes(searchTerm.toLowerCase())
  )
    .sort((a, b) => {
      // Ordem: RASCUNHOS -> ATIVAS -> CONCLUÍDAS -> PARADAS
      const statusOrder = {
        'draft': 1,        // RASCUNHOS primeiro
        'scheduled': 2,    // AGENDADAS
        'running': 3,      // ATIVAS
        'paused': 4,       // PAUSADAS
        'completed': 5,    // CONCLUÍDAS
        'stopped': 6,      // PARADAS
        'cancelled': 7     // CANCELADAS
      }

      const aOrder = statusOrder[a.status as keyof typeof statusOrder] || 999
      const bOrder = statusOrder[b.status as keyof typeof statusOrder] || 999

      if (aOrder !== bOrder) {
        return aOrder - bOrder
      }

      // Se mesmo status, ordenar por data de criação (mais recentes primeiro)
      return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    }) : []

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
        <div className="flex gap-4 items-center">
        <div className="flex-1">
            <Input
              placeholder="Buscar campanhas..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full"
            />
          </div>
          <Button
            variant={showStoppedCampaigns ? "default" : "outline"}
            onClick={() => setShowStoppedCampaigns(!showStoppedCampaigns)}
            className="whitespace-nowrap"
          >
            {showStoppedCampaigns ? "🔒 Ocultar Paradas" : "📋 Ver Paradas"}
          </Button>
        </div>
        {showStoppedCampaigns && (
          <div className="mt-2 text-sm text-gray-600">
            ℹ️ Mostrando campanhas que foram paradas intencionalmente
          </div>
        )}
      </Card>

      {/* Lista de Campanhas */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
        {filteredCampaigns.map((campaign) => (
          <CampaignCardOptimized
            key={campaign.id}
            campaign={campaign}
            onStart={handleStart}
            onPause={handlePause}
            onResume={handleResume}
            onEdit={handleEdit}
            onViewLogs={handleViewLogs}
            onAddContacts={handleAddContacts}
          />
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
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={async () => {
                    try {
                      const toastId = showLoadingToast('exportar', 'Relatório PDF')
                      const response = await api.get(`/campaigns/${selectedCampaignForLogs.id}/export-pdf/`, {
                        responseType: 'blob'
                      })
                      
                      // Criar link para download
                      const url = window.URL.createObjectURL(new Blob([response.data]))
                      const link = document.createElement('a')
                      link.href = url
                      link.setAttribute('download', `campanha_${selectedCampaignForLogs.name.replace(/\s+/g, '_')}_${new Date().toISOString().split('T')[0]}.pdf`)
                      document.body.appendChild(link)
                      link.click()
                      link.remove()
                      window.URL.revokeObjectURL(url)
                      
                      updateToastSuccess(toastId, 'exportar', 'Relatório PDF')
                    } catch (error: any) {
                      console.error('Erro ao exportar PDF:', error)
                      showErrorToast('exportar', 'Relatório PDF', error)
                    }
                  }}
                  className="flex items-center gap-2"
                >
                  <Download className="h-4 w-4" />
                  <span className="hidden sm:inline">Exportar Log</span>
                </Button>
                <button onClick={() => setShowLogsModal(false)} className="text-gray-400 hover:text-gray-600 ml-2 flex-shrink-0">
                  <X className="h-5 w-5 sm:h-6 sm:w-6" />
                </button>
              </div>
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
                  {/* ✅ CORREÇÃO: Usar dados da campanha (igual ao card principal) */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 sm:gap-4 mb-4">
                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-2 sm:p-3 text-center">
                      <div className="text-lg sm:text-xl font-bold text-blue-600">
                        {selectedCampaignForLogs.messages_sent || 0}
                      </div>
                      <div className="text-xs sm:text-sm text-blue-800">Enviadas</div>
                    </div>
                    <div className="bg-green-50 border border-green-200 rounded-lg p-2 sm:p-3 text-center">
                      <div className="text-lg sm:text-xl font-bold text-green-600">
                        {selectedCampaignForLogs.messages_delivered || 0}
                      </div>
                      <div className="text-xs sm:text-sm text-green-800">Entregues</div>
                    </div>
                    <div className="bg-purple-50 border border-purple-200 rounded-lg p-2 sm:p-3 text-center">
                      <div className="text-lg sm:text-xl font-bold text-purple-600">
                        {selectedCampaignForLogs.messages_read || 0}
                      </div>
                      <div className="text-xs sm:text-sm text-purple-800">Lidas</div>
                    </div>
                    <div className="bg-red-50 border border-red-200 rounded-lg p-2 sm:p-3 text-center">
                      <div className="text-lg sm:text-xl font-bold text-red-600">
                        {selectedCampaignForLogs.messages_failed || 0}
                      </div>
                      <div className="text-xs sm:text-sm text-red-800">Falhas</div>
                    </div>
                  </div>
                  
                  {/* Lista de Logs */}
                  <div className="space-y-3">
                    {(() => {
                      // ✅ AGRUPAR LOGS POR CONTATO
                      const contactLogsMap = new Map<string, any>()
                      const otherLogs: any[] = []
                      
                      logs.forEach((log: any) => {
                        // Logs de mensagens (sent, delivered, read, failed) são agrupados por contato
                        if ((log.log_type === 'message_sent' || log.log_type === 'message_delivered' || log.log_type === 'message_read' || log.log_type === 'message_failed') && log.contact_name) {
                          const contactKey = `${log.contact_phone || log.contact_name}`
                          
                          if (!contactLogsMap.has(contactKey)) {
                            contactLogsMap.set(contactKey, {
                              contact_name: log.contact_name,
                              contact_phone: log.contact_phone,
                              instance_name: log.instance_name,
                              message_text: log.extra_data?.message_text || null,
                              sent_at: null,
                              delivered_at: null,
                              read_at: null,
                              failed: false,
                              error: null,
                              first_log_id: log.id
                            })
                          }
                          
                          const contactLog = contactLogsMap.get(contactKey)!
                          
                          // Consolidar informações de cada tipo de log
                          if (log.log_type === 'message_sent') {
                            contactLog.sent_at = log.extra_data?.sent_at || log.created_at
                            contactLog.message_text = log.extra_data?.message_text || contactLog.message_text
                          } else if (log.log_type === 'message_delivered') {
                            contactLog.delivered_at = log.extra_data?.delivered_at || log.created_at
                            // Se não tinha sent_at, usar o delivered_at como referência
                            if (!contactLog.sent_at) {
                              contactLog.sent_at = log.extra_data?.sent_at || log.created_at
                            }
                          } else if (log.log_type === 'message_read') {
                            contactLog.read_at = log.extra_data?.read_at || log.created_at
                            // Se não tinha delivered_at, usar o read_at como referência
                            if (!contactLog.delivered_at) {
                              contactLog.delivered_at = log.extra_data?.delivered_at || log.created_at
                            }
                            // Se não tinha sent_at, usar o read_at como referência
                            if (!contactLog.sent_at) {
                              contactLog.sent_at = log.extra_data?.sent_at || log.created_at
                            }
                          } else if (log.log_type === 'message_failed') {
                            contactLog.failed = true
                            contactLog.error = log.extra_data?.error || log.message
                            contactLog.sent_at = log.extra_data?.sent_at || log.created_at
                          }
                        } else {
                          // Outros logs (campaign_created, campaign_started, etc) não são agrupados
                          otherLogs.push(log)
                        }
                      })
                      
                      // Converter Map para Array e ordenar por sent_at (mais recente primeiro)
                      const groupedContactLogs = Array.from(contactLogsMap.values()).sort((a, b) => {
                        const aTime = a.sent_at ? new Date(a.sent_at).getTime() : 0
                        const bTime = b.sent_at ? new Date(b.sent_at).getTime() : 0
                        return bTime - aTime
                      })
                      
                      // ✅ CORREÇÃO: Ordenar outros logs por created_at (mais recente primeiro)
                      const sortedOtherLogs = otherLogs.sort((a, b) => {
                        const aTime = a.created_at ? new Date(a.created_at).getTime() : 0
                        const bTime = b.created_at ? new Date(b.created_at).getTime() : 0
                        return bTime - aTime
                      })
                      
                      // Combinar: primeiro logs de contatos agrupados, depois outros logs (ambos ordenados por tempo)
                      const allLogs = [...groupedContactLogs, ...sortedOtherLogs]
                      
                      return allLogs.map((log: any, idx: number) => {
                        // Se é um log agrupado por contato (tem contact_name mas não tem log_type)
                        if (log.contact_name && !log.log_type) {
                          return (
                            <div
                              key={log.first_log_id || `contact-${idx}`}
                              className="border-l-4 p-4 rounded-r-lg border-l-blue-500 bg-blue-50"
                            >
                              <div className="space-y-3">
                                {/* Header com Contato e Instância */}
                                <div className="flex items-center justify-between">
                                  <div className="flex items-center gap-2">
                                    <Send className="h-4 w-4 text-blue-500" />
                                    <div>
                                      <div className="font-medium text-gray-900">{log.contact_name}</div>
                                      <div className="text-sm text-gray-500">{log.contact_phone}</div>
                                    </div>
                                  </div>
                                  {log.instance_name && (
                                    <span className="text-xs text-green-600 bg-green-100 px-2 py-1 rounded">
                                      {log.instance_name}
                                    </span>
                                  )}
                                </div>

                                {/* Mensagem Enviada */}
                                {log.message_text && (
                                  <div className="bg-blue-50 border border-blue-200 rounded p-3">
                                    <div className="text-xs text-blue-600 font-medium mb-1">💬 Mensagem:</div>
                                    <div className="text-sm text-gray-700 whitespace-pre-wrap">{log.message_text}</div>
                                  </div>
                                )}

                                {/* Timeline de Status */}
                                <div className="grid grid-cols-3 gap-2 bg-gray-50 p-3 rounded">
                                  <div className="text-center">
                                    <div className="text-xs text-gray-500 mb-1">📤 Enviada em</div>
                                    <div className="text-sm font-medium text-gray-900">
                                      {log.sent_at ? formatDate(log.sent_at) : '---'}
                                    </div>
                                  </div>
                                  <div className="text-center border-l border-gray-200">
                                    <div className="text-xs text-gray-500 mb-1">✅ Entregue em</div>
                                    <div className="text-sm font-medium text-gray-600">
                                      {log.delivered_at ? formatDate(log.delivered_at) : '---'}
                                    </div>
                                  </div>
                                  <div className="text-center border-l border-gray-200">
                                    <div className="text-xs text-gray-500 mb-1">👁️ Visto em</div>
                                    <div className="text-sm font-medium text-gray-600">
                                      {log.read_at ? formatDate(log.read_at) : '---'}
                                    </div>
                                  </div>
                                </div>

                                {/* Erro se houver */}
                                {log.failed && log.error && (
                                  <div className="bg-red-50 border border-red-200 rounded p-2">
                                    <div className="text-xs text-red-600 font-medium mb-1">❌ Motivo da Falha:</div>
                                    <div className="text-sm text-red-700">{log.error}</div>
                                  </div>
                                )}
                              </div>
                            </div>
                          )
                        }
                        
                        // Log padrão (campaign_created, campaign_started, etc)
                        return (
                          <div
                            key={log.id || idx}
                            className={`border-l-4 p-4 rounded-r-lg ${getLogColor(log.log_type)}`}
                          >
                            {/* Card de Log Padrão (Campanha criada, iniciada, etc) */}
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
                        )
                      })
                    })()}
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

      {/* Modal de Adicionar Contatos */}
      {showAddContactsModal && selectedCampaignForAddContacts && (
        <AddContactsModal
          campaign={{
            id: selectedCampaignForAddContacts.id,
            name: selectedCampaignForAddContacts.name,
            total_contacts: selectedCampaignForAddContacts.total_contacts,
            status: selectedCampaignForAddContacts.status
          }}
          onClose={() => {
            setShowAddContactsModal(false)
            setSelectedCampaignForAddContacts(null)
          }}
          onSuccess={() => {
            fetchData(false)
          }}
        />
      )}
    </div>
  )
}

export default CampaignsPage
