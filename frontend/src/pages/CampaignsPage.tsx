import React, { useState, useEffect } from 'react'
import { Plus, Search, Send, Pause, Play, Edit, Trash2, Users, TrendingUp, Copy, FileText, Clock, X, AlertCircle, CheckCircle, Eye, MessageSquare, Phone, ChevronDown, ChevronUp } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Input } from '../components/ui/Input'
import { showErrorToast, showLoadingToast, updateToastSuccess, updateToastError } from '../lib/toastHelper'
import { api } from '../lib/api'
import CampaignWizardModal from '../components/campaigns/CampaignWizardModal'
import { useWebSocket } from '../hooks/useWebSocket'

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
  next_contact_name?: string
  next_contact_phone?: string
  next_instance_name?: string
  last_contact_name?: string
  last_contact_phone?: string
  last_instance_name?: string
  created_at: string
}

interface WhatsAppInstance {
  id: string
  friendly_name: string
  phone_number: string
  connection_state: string
  health_score: number
  msgs_sent_today: number
}

interface CampaignMessage {
  id?: string
  content: string
  order: number
  times_used?: number
}

// Componente de Countdown
const NextMessageCountdown: React.FC<{ 
  nextScheduledAt?: string; 
  campaignStatus: string;
  nextContactName?: string;
  nextContactPhone?: string;
  nextInstanceName?: string;
  lastContactName?: string;
  lastContactPhone?: string;
  lastInstanceName?: string;
}> = ({ nextScheduledAt, campaignStatus, nextContactName, nextContactPhone, nextInstanceName, lastContactName, lastContactPhone, lastInstanceName }) => {
  const [seconds, setSeconds] = useState(0)

  useEffect(() => {
    // Só mostrar se campanha está realmente rodando
    if (!nextScheduledAt || campaignStatus !== 'running') {
      setSeconds(0)
      return
    }

    const updateCountdown = () => {
      const now = new Date().getTime()
      const target = new Date(nextScheduledAt).getTime()
      const diff = Math.max(0, Math.floor((target - now) / 1000))
      setSeconds(diff)
    }

    updateCountdown()
    const interval = setInterval(updateCountdown, 1000)
    return () => clearInterval(interval)
  }, [nextScheduledAt, campaignStatus])

  if (!nextScheduledAt || seconds === 0 || campaignStatus !== 'running') return null

  return (
    <div className="space-y-3">
      {/* Layout horizontal: Último disparo ------- Próximo disparo */}
      {(lastContactName && lastContactPhone) || (nextContactName && nextContactPhone) ? (
        <div className="bg-gray-50 rounded p-3 text-xs">
          <div className="flex items-center justify-between">
            {/* Último disparo */}
            <div className="flex-1">
              <div className="text-gray-500 mb-2 font-medium">Último disparo:</div>
              {lastContactName && lastContactPhone && (
                <div className="text-gray-700 space-y-1">
                  <div>📱 <span className="font-medium">{lastContactName}</span></div>
                  <div>☎️ <span className="font-medium">{lastContactPhone}</span></div>
                  {lastInstanceName && (
                    <div>🔄 <span className="font-medium">{lastInstanceName}</span></div>
                  )}
                </div>
              )}
            </div>

            {/* Seta visual */}
            <div className="flex items-center justify-center text-gray-400 mx-4">
              <div className="text-lg">→</div>
            </div>

            {/* Próximo disparo */}
            <div className="flex-1">
              <div className="text-blue-600 mb-2 font-medium flex items-center gap-1">
                <Clock className="h-3 w-3" />
                Próximo disparo em: <span className="font-bold">{seconds}s</span>
              </div>
              {nextContactName && nextContactPhone && (
                <div className="text-gray-700 space-y-1">
                  <div>📱 <span className="font-medium">{nextContactName}</span></div>
                  <div>☎️ <span className="font-medium">{nextContactPhone}</span></div>
                  {nextInstanceName && (
                    <div>🔄 <span className="font-medium">{nextInstanceName}</span></div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      ) : (
        /* Fallback para quando não há histórico */
      <div className="flex items-center gap-2 text-sm text-blue-600">
        <Clock className="h-4 w-4" />
        <span>Próximo disparo em: <span className="font-bold">{seconds}s</span></span>
      </div>
      )}
        </div>
  )
}

// Componente para exibir logs unificados por contato
  const ContactLogCard: React.FC<{ contactGroup: any }> = ({ contactGroup }) => {
    const [isExpanded, setIsExpanded] = useState(false)
    
    // Função para calcular tempo de entrega
    const getDeliveryTime = (messageEvent: any, events: any[]) => {
      const deliveredEvent = events.find((e: any) => e.log_type === 'message_delivered')
      if (deliveredEvent) {
        const sentTime = new Date(messageEvent.created_at).getTime()
        const deliveredTime = new Date(deliveredEvent.created_at).getTime()
        const diffMs = deliveredTime - sentTime
        const diffSeconds = Math.round(diffMs / 1000)
        
        if (diffSeconds < 60) {
          return `${diffSeconds}s`
        } else if (diffSeconds < 3600) {
          const minutes = Math.floor(diffSeconds / 60)
          const seconds = diffSeconds % 60
          return `${minutes}m ${seconds}s`
        } else {
          const hours = Math.floor(diffSeconds / 3600)
          const minutes = Math.floor((diffSeconds % 3600) / 60)
          return `${hours}h ${minutes}m`
        }
      }
      return 'N/A'
    }
    
    // Função para calcular tempo de visualização
    const getReadTime = (messageEvent: any, events: any[]) => {
      const readEvent = events.find((e: any) => e.log_type === 'message_read')
      if (readEvent) {
        const sentTime = new Date(messageEvent.created_at).getTime()
        const readTime = new Date(readEvent.created_at).getTime()
        const diffMs = readTime - sentTime
        const diffSeconds = Math.round(diffMs / 1000)
        
        if (diffSeconds < 60) {
          return `${diffSeconds}s`
        } else if (diffSeconds < 3600) {
          const minutes = Math.floor(diffSeconds / 60)
          const seconds = diffSeconds % 60
          return `${minutes}m ${seconds}s`
        } else {
          const hours = Math.floor(diffSeconds / 3600)
          const minutes = Math.floor((diffSeconds % 3600) / 60)
          return `${hours}h ${minutes}m`
        }
      }
      return 'N/A'
    }
    
    const getStatusInfo = (status: string) => {
    switch (status) {
      case 'read':
        return { 
          color: 'bg-green-100 text-green-800 border-green-200', 
          icon: <Eye className="h-4 w-4" />, 
          text: 'Lida' 
        }
      case 'delivered':
        return { 
          color: 'bg-blue-100 text-blue-800 border-blue-200', 
          icon: <CheckCircle className="h-4 w-4" />, 
          text: 'Entregue' 
        }
      case 'sent':
        return { 
          color: 'bg-yellow-100 text-yellow-800 border-yellow-200', 
          icon: <Send className="h-4 w-4" />, 
          text: 'Enviada' 
        }
      case 'failed':
        return { 
          color: 'bg-red-100 text-red-800 border-red-200', 
          icon: <X className="h-4 w-4" />, 
          text: 'Falhou' 
        }
      default:
        return { 
          color: 'bg-gray-100 text-gray-800 border-gray-200', 
          icon: <Clock className="h-4 w-4" />, 
          text: 'Pendente' 
        }
    }
  }
  
  const getEventIcon = (logType: string) => {
    switch (logType) {
      case 'message_sent':
        return <Send className="h-3 w-3 text-blue-600" />
      case 'message_delivered':
        return <CheckCircle className="h-3 w-3 text-green-600" />
      case 'message_read':
        return <Eye className="h-3 w-3 text-purple-600" />
      case 'message_failed':
        return <X className="h-3 w-3 text-red-600" />
      default:
        return <MessageSquare className="h-3 w-3 text-gray-600" />
    }
  }
  
  const getEventColor = (logType: string) => {
    switch (logType) {
      case 'message_sent':
        return 'bg-blue-50 border-blue-200'
      case 'message_delivered':
        return 'bg-green-50 border-green-200'
      case 'message_read':
        return 'bg-purple-50 border-purple-200'
      case 'message_failed':
        return 'bg-red-50 border-red-200'
      default:
        return 'bg-gray-50 border-gray-200'
    }
  }
  
  const statusInfo = getStatusInfo(contactGroup.status)
  const messageEvent = contactGroup.events.find((e: any) => e.details?.message_content)
  
  return (
    <Card className="overflow-hidden">
      {/* Header do Contato */}
      <div className="p-3 sm:p-4 border-b bg-gray-50">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <Phone className="h-4 w-4 text-gray-500 flex-shrink-0" />
              <div className="min-w-0">
                <h3 className="font-semibold text-gray-900 truncate">{contactGroup.contact_name}</h3>
                <p className="text-sm text-gray-600 truncate">{contactGroup.contact_phone}</p>
              </div>
            </div>
            <div className="hidden sm:flex items-center gap-2">
              <span className="text-xs text-gray-500">📱 {contactGroup.instance_name}</span>
            </div>
          </div>
          
          <div className="flex items-center justify-between sm:justify-end gap-3">
            {/* Status Badge */}
            <div className={`flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium border ${statusInfo.color}`}>
              {statusInfo.icon}
              <span className="hidden sm:inline">{statusInfo.text}</span>
            </div>
            
            {/* Botão Expandir */}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsExpanded(!isExpanded)}
              className="h-8 w-8 p-0 flex-shrink-0"
            >
              {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </Button>
          </div>
        </div>
        
        {/* Resumo da Timeline */}
        <div className="mt-3 flex flex-wrap items-center gap-2 sm:gap-4 text-xs text-gray-600">
          <span className="flex items-center gap-1">
            <span>🕐</span>
            <span className="hidden sm:inline">{new Date(contactGroup.first_event).toLocaleString('pt-BR')}</span>
            <span className="sm:hidden">{new Date(contactGroup.first_event).toLocaleDateString('pt-BR')}</span>
          </span>
          <span className="hidden sm:inline">•</span>
          <span className="flex items-center gap-1">
            <span>📊</span>
            <span>{contactGroup.events.length} evento{contactGroup.events.length !== 1 ? 's' : ''}</span>
          </span>
          {messageEvent && (
            <>
              <span className="hidden sm:inline">•</span>
              <span className="text-blue-600 flex items-center gap-1">
                <span>💬</span>
                <span className="hidden sm:inline">Mensagem incluída</span>
                <span className="sm:hidden">Msg</span>
              </span>
            </>
          )}
          <span className="sm:hidden text-gray-500">📱 {contactGroup.instance_name}</span>
    </div>
      </div>
      
      {/* Timeline Expandida */}
      {isExpanded && (
        <div className="p-3 sm:p-4 space-y-3">
                   {/* Mensagem (se houver) */}
                   {messageEvent && (
                     <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                       <div className="flex items-center gap-2 mb-2">
                         <MessageSquare className="h-4 w-4 text-blue-600 flex-shrink-0" />
                         <span className="font-medium text-blue-900">Mensagem Enviada</span>
                       </div>
                       <p className="text-sm text-blue-800 whitespace-pre-wrap break-words">
                         {messageEvent.details.message_content}
                       </p>
                       
                       {/* Status de Entrega e Visualização */}
                       <div className="mt-3 pt-3 border-t border-blue-200">
                         <div className="space-y-2 text-xs text-blue-700">
                           {/* Linha principal: Enviada e Status */}
                           <div className="flex flex-col sm:flex-row sm:items-center gap-2">
                             <span className="flex items-center gap-1">
                               <span>📤</span>
                               <span>Enviada em {new Date(messageEvent.created_at).toLocaleString('pt-BR')}</span>
                             </span>
                             
                             {/* Status de Entrega */}
                             {contactGroup.status === 'delivered' && (
                               <span className="flex items-center gap-1">
                                 <span>✅</span>
                                 <span>Entregue</span>
                               </span>
                             )}
                             
                             {/* Status de Visualização */}
                             {contactGroup.status === 'read' && (
                               <span className="flex items-center gap-1">
                                 <span>👁️</span>
                                 <span>Visualizada</span>
                               </span>
                             )}
                           </div>
                           
                           {/* Linha de tempos (se disponível) */}
                           <div className="flex flex-col sm:flex-row sm:items-center gap-2 text-blue-600">
                             {/* Tempo de Entrega (se disponível) */}
                             {contactGroup.events.find((e: any) => e.log_type === 'message_delivered') && (
                               <span className="flex items-center gap-1">
                                 <span>⏱️</span>
                                 <span>Tempo de entrega: {getDeliveryTime(messageEvent, contactGroup.events)}</span>
                               </span>
                             )}
                             
                             {/* Tempo de Visualização (se disponível) */}
                             {contactGroup.events.find((e: any) => e.log_type === 'message_read') && (
                               <span className="flex items-center gap-1">
                                 <span>⏱️</span>
                                 <span>Tempo de visualização: {getReadTime(messageEvent, contactGroup.events)}</span>
                               </span>
                             )}
                           </div>
                         </div>
                       </div>
                     </div>
                   )}
          
          {/* Timeline de Eventos */}
          <div className="space-y-2">
            <h4 className="text-sm font-medium text-gray-700 mb-2">Timeline de Eventos:</h4>
            {contactGroup.events.map((event: any, eventIdx: number) => (
              <div key={eventIdx} className={`border rounded-lg p-3 ${getEventColor(event.log_type)}`}>
                <div className="flex items-start gap-3">
                  <div className="flex-shrink-0 mt-0.5">
                    {getEventIcon(event.log_type)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1 mb-1">
                      <span className="text-sm font-medium text-gray-900">
                        {event.log_type_display || event.log_type}
                      </span>
                      <span className="text-xs text-gray-500">
                        {new Date(event.created_at).toLocaleString('pt-BR')}
                      </span>
                    </div>
                    <p className="text-sm text-gray-700 break-words">{event.message}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
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
  
  // WebSocket para atualizações em tempo real
  const { isConnected, lastMessage } = useWebSocket()

  useEffect(() => {
    fetchData()
    
    // Atualização automática a cada 30 segundos (backup para WebSocket)
    const interval = setInterval(() => {
      if (!showModal && !isConnected) {  // Só usar polling se WebSocket não estiver conectado
        fetchData(true)  // silent mode
      }
    }, 30000)
    
    return () => clearInterval(interval)
  }, [showModal, isConnected])
  
  // Processar mensagens do WebSocket
  useEffect(() => {
    if (lastMessage?.type === 'campaign_update') {
      const campaignData = lastMessage.data
      console.log('📡 [WEBSOCKET] Atualização de campanha recebida:', campaignData)
      
      // Atualizar campanha específica na lista
      setCampaigns(prevCampaigns => 
        prevCampaigns.map(campaign => 
          campaign.id === campaignData.campaign_id 
            ? {
                ...campaign,
                status: campaignData.status,
                messages_sent: campaignData.messages_sent,
                messages_delivered: campaignData.messages_delivered,
                messages_read: campaignData.messages_read,
                messages_failed: campaignData.messages_failed,
                total_contacts: campaignData.total_contacts,
                progress_percentage: campaignData.progress_percentage,
                last_contact_name: campaignData.last_message?.contact_name,
                last_contact_phone: campaignData.last_message?.contact_phone,
                last_message_sent_at: campaignData.last_message?.sent_at,
                next_contact_name: campaignData.next_message?.contact_name,
                next_contact_phone: campaignData.next_message?.contact_phone,
                next_message_scheduled_at: campaignData.next_message?.scheduled_at,
                updated_at: campaignData.updated_at
              }
            : campaign
        )
      )
    }
  }, [lastMessage])

  const fetchData = async (silent = false) => {
    try {
      if (!silent) {
        setLoading(true)
      }
      const response = await api.get('/campaigns/campaigns/')
      setCampaigns(response.data.results || response.data || [])
    } catch (error: any) {
      console.error('Erro ao buscar dados:', error)
      if (!silent) {
        showErrorToast('buscar', 'Dados', error)
      }
    } finally {
      if (!silent) {
        setLoading(false)
      }
    }
  }

  const handleEdit = (campaign: Campaign) => {
    setEditingCampaign(campaign)
    setShowModal(true)
  }

  const handleDelete = async (campaignId: string) => {
    if (!confirm('Tem certeza que deseja excluir esta campanha?')) return
    
    const toastId = showLoadingToast('excluir', 'Campanha')
    
    try {
      await api.delete(`/campaigns/campaigns/${campaignId}/`)
      updateToastSuccess(toastId, 'excluir', 'Campanha')
      
      // ✅ Executar callback em try/catch separado
      try {
        fetchData()
      } catch (callbackError) {
        console.error('Erro ao atualizar lista:', callbackError)
      }
    } catch (error: any) {
      console.error('Erro ao excluir campanha:', error)
      updateToastError(toastId, 'excluir', 'Campanha', error)
    }
  }

  const handleStart = async (campaignId: string) => {
    // Buscar campanha para verificar health das instâncias
    const campaign = campaigns.find(c => c.id === campaignId)
    
    if (campaign) {
      const lowHealthInstances = campaign.instances_detail?.filter(
        i => i.health_score < campaign.pause_on_health_below
      ) || []
      
      if (lowHealthInstances.length > 0) {
        const instanceNames = lowHealthInstances.map(i => `${i.friendly_name} (health: ${i.health_score})`).join(', ')
        
        const confirmed = confirm(
          `⚠️ ATENÇÃO: Health Score Baixo\n\n` +
          `As seguintes instâncias têm health abaixo de ${campaign.pause_on_health_below}:\n` +
          `${instanceNames}\n\n` +
          `A campanha pode ser pausada automaticamente.\n\n` +
          `Deseja iniciar mesmo assim?`
        )
        
        if (!confirmed) {
          return
        }
      }
    }
    
    const toastId = showLoadingToast('iniciar', 'Campanha')
    
    try {
      await api.post(`/campaigns/campaigns/${campaignId}/start/`)
      updateToastSuccess(toastId, 'iniciar', 'Campanha')
      
      // ✅ Executar callback em try/catch separado
      try {
        fetchData()
      } catch (callbackError) {
        console.error('Erro ao atualizar lista:', callbackError)
      }
    } catch (error: any) {
      console.error('Erro ao iniciar campanha:', error)
      updateToastError(toastId, 'iniciar', 'Campanha', error)
    }
  }

  const handlePause = async (campaignId: string) => {
    const toastId = showLoadingToast('pausar', 'Campanha')
    
    try {
      await api.post(`/campaigns/campaigns/${campaignId}/pause/`)
      updateToastSuccess(toastId, 'pausar', 'Campanha')
      
      // ✅ Executar callback em try/catch separado
      try {
        fetchData()
      } catch (callbackError) {
        console.error('Erro ao atualizar lista:', callbackError)
      }
    } catch (error: any) {
      console.error('Erro ao pausar campanha:', error)
      updateToastError(toastId, 'pausar', 'Campanha', error)
    }
  }

  const handleResume = async (campaignId: string) => {
    // Buscar campanha para verificar health das instâncias
    const campaign = campaigns.find(c => c.id === campaignId)
    
    if (campaign) {
      const lowHealthInstances = campaign.instances_detail?.filter(
        i => i.health_score < campaign.pause_on_health_below
      ) || []
      
      if (lowHealthInstances.length > 0) {
        const instanceNames = lowHealthInstances.map(
          i => `${i.friendly_name} (health: ${i.health_score})`
        ).join(', ')
        
        const confirmed = confirm(
          `⚠️ ATENÇÃO: Health Score Ainda Baixo\n\n` +
          `As seguintes instâncias ainda têm health abaixo de ${campaign.pause_on_health_below}:\n` +
          `${instanceNames}\n\n` +
          `A campanha pode ser pausada novamente.\n\n` +
          `Recomendação: Aguarde o health melhorar ou ajuste o limite.\n\n` +
          `Deseja retomar mesmo assim?`
        )
        
        if (!confirmed) {
          return
        }
      }
    }
    
    const toastId = showLoadingToast('retomar', 'Campanha')
    
    try {
      await api.post(`/campaigns/campaigns/${campaignId}/resume/`)
      updateToastSuccess(toastId, 'retomar', 'Campanha')
      
      // ✅ Executar callback em try/catch separado
      try {
        fetchData()
      } catch (callbackError) {
        console.error('Erro ao atualizar lista:', callbackError)
      }
    } catch (error: any) {
      console.error('Erro ao retomar campanha:', error)
      updateToastError(toastId, 'retomar', 'Campanha', error)
    }
  }

  const handleCancel = async (campaignId: string) => {
    // Confirmação (é definitivo!)
    const confirmed = confirm(
      '⚠️ TEM CERTEZA QUE DESEJA CANCELAR ESTA CAMPANHA?\n\n' +
      '⚠️ Esta ação é IRREVERSÍVEL!\n' +
      '⚠️ A campanha NÃO poderá ser retomada.\n\n' +
      'Histórico e logs serão mantidos para consulta.\n\n' +
      'Deseja realmente cancelar?'
    )
    
    if (!confirmed) {
      return
    }
    
    const toastId = showLoadingToast('cancelar', 'Campanha')
    
    try {
      await api.post(`/campaigns/campaigns/${campaignId}/cancel/`)
      updateToastSuccess(toastId, 'cancelar', 'Campanha')
      
      // ✅ Executar callback em try/catch separado
      try {
        fetchData()
      } catch (callbackError) {
        console.error('Erro ao atualizar lista:', callbackError)
      }
    } catch (error: any) {
      console.error('Erro ao cancelar campanha:', error)
      updateToastError(toastId, 'cancelar', 'Campanha', error)
    }
  }

  const handleCloseModal = () => {
    setShowModal(false)
    setEditingCampaign(null)
  }

  const handleDuplicate = async (campaign: Campaign) => {
    const toastId = showLoadingToast('duplicar', 'Campanha')
    
    try {
      const payload = {
        name: `${campaign.name} (Cópia)`,
        description: campaign.description,
        rotation_mode: campaign.rotation_mode,
        instances: campaign.instances,
        messages: campaign.messages.map((m, idx) => ({
          content: m.content,
          order: idx + 1
        })),
        interval_min: campaign.interval_min,
        interval_max: campaign.interval_max,
        daily_limit_per_instance: campaign.daily_limit_per_instance,
        pause_on_health_below: campaign.pause_on_health_below
      }
      
      await api.post('/campaigns/campaigns/', payload)
      updateToastSuccess(toastId, 'duplicar', 'Campanha')
      
      // ✅ Executar callback em try/catch separado
      try {
        fetchData()
      } catch (callbackError) {
        console.error('Erro ao atualizar lista:', callbackError)
      }
    } catch (error: any) {
      console.error('Erro ao duplicar campanha:', error)
      updateToastError(toastId, 'duplicar', 'Campanha', error)
    }
  }

  const handleViewLogs = async (campaign: Campaign) => {
    setSelectedCampaignForLogs(campaign)
    setShowLogsModal(true)
    
    try {
      const response = await api.get(`/campaigns/campaigns/${campaign.id}/logs/`)
      const rawLogs = response.data
      
      // Agrupar logs por contato
      const groupedLogs = groupLogsByContact(rawLogs)
      setLogs(groupedLogs)
    } catch (error: any) {
      console.error('Erro ao buscar logs:', error)
      showErrorToast('buscar', 'Logs', error)
    }
  }

  // Função para agrupar logs por contato
  const groupLogsByContact = (rawLogs: any[]) => {
    const contactGroups: { [key: string]: any } = {}
    
    rawLogs.forEach(log => {
      const contactKey = log.contact_id || log.contact_name || 'unknown'
      
      if (!contactGroups[contactKey]) {
        contactGroups[contactKey] = {
          contact_id: log.contact_id,
          contact_name: log.contact_name,
          contact_phone: log.contact_phone,
          instance_name: log.instance_name,
          events: [],
          status: 'pending',
          first_event: null,
          last_event: null,
          has_sent: false,
          has_delivered: false,
          has_read: false,
          has_failed: false
        }
      }
      
      // Adicionar evento à timeline
      contactGroups[contactKey].events.push({
        ...log,
        timestamp: new Date(log.created_at).getTime()
      })
      
      // Marcar tipos de eventos
      if (log.log_type === 'message_sent') {
        contactGroups[contactKey].has_sent = true
      } else if (log.log_type === 'message_delivered') {
        contactGroups[contactKey].has_delivered = true
      } else if (log.log_type === 'message_read') {
        contactGroups[contactKey].has_read = true
      } else if (log.log_type === 'message_failed') {
        contactGroups[contactKey].has_failed = true
      }
      
      // Atualizar primeiro e último evento
      if (!contactGroups[contactKey].first_event || log.created_at < contactGroups[contactKey].first_event) {
        contactGroups[contactKey].first_event = log.created_at
      }
      if (!contactGroups[contactKey].last_event || log.created_at > contactGroups[contactKey].last_event) {
        contactGroups[contactKey].last_event = log.created_at
      }
    })
    
    // Ordenar eventos por timestamp e determinar status final
    Object.values(contactGroups).forEach((group: any) => {
      group.events.sort((a: any, b: any) => a.timestamp - b.timestamp)
      
      // Determinar status baseado na prioridade (failed > read > delivered > sent)
      if (group.has_failed) {
        group.status = 'failed'
      } else if (group.has_read) {
        group.status = 'read'
      } else if (group.has_delivered) {
        group.status = 'delivered'
      } else if (group.has_sent) {
        group.status = 'sent'
      } else {
        group.status = 'pending'
      }
    })
    
    // Converter para array e ordenar por último evento
    return Object.values(contactGroups).sort((a: any, b: any) => 
      new Date(b.last_event).getTime() - new Date(a.last_event).getTime()
    )
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
      
      const aOrder = statusOrder[a.status] || 999
      const bOrder = statusOrder[b.status] || 999
      
      // Se status igual, ordenar por data de criação (mais recente primeiro)
      if (aOrder === bOrder) {
        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      }
      
      return aOrder - bOrder
    })

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-accent-500"></div>
      </div>
    )
  }

  return (
    <div className="space-y-4 sm:space-y-6">
      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl sm:text-2xl font-bold text-gray-900">📤 Campanhas</h1>
            {/* Indicador de conexão WebSocket */}
            <div className={`flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${
              isConnected 
                ? 'bg-green-100 text-green-800 border border-green-200' 
                : 'bg-red-100 text-red-800 border border-red-200'
            }`}>
              <div className={`w-2 h-2 rounded-full ${
                isConnected ? 'bg-green-500' : 'bg-red-500'
              }`}></div>
              <span>{isConnected ? 'Tempo Real' : 'Polling'}</span>
            </div>
          </div>
          <p className="text-sm sm:text-base text-gray-600">
            Gerencie suas campanhas de disparo em massa
            {isConnected && <span className="text-green-600 ml-2">• Atualizações em tempo real ativas</span>}
          </p>
        </div>
        <Button onClick={() => setShowModal(true)} className="w-full sm:w-auto">
          <Plus className="h-4 w-4 mr-2" />
          Nova Campanha
        </Button>
      </div>

      {/* Filtros */}
      <div className="space-y-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
            <Input
              placeholder="Buscar campanhas..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10 w-full"
            />
        </div>
      </div>

      {/* Lista de Campanhas */}
      <div className="grid gap-4">
        {filteredCampaigns.map((campaign) => (
          <Card key={campaign.id} className="p-4 sm:p-6">
            <div className="flex flex-col lg:flex-row lg:justify-between lg:items-start gap-4 mb-4">
              <div className="flex-1">
                <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-3 mb-2">
                  <h3 className="text-base sm:text-lg font-semibold text-gray-900">{campaign.name}</h3>
                  <span className={`px-2 py-1 text-xs font-medium rounded-full w-fit ${getStatusColor(campaign.status)}`}>
                    {campaign.status_display}
                  </span>
                </div>
                <p className="text-sm sm:text-base text-gray-600 mb-3">{campaign.description}</p>
                
                <div className="flex flex-wrap gap-3 sm:gap-4 text-xs sm:text-sm text-gray-600">
                  <div className="flex items-center gap-1">
                    <Users className="h-3 w-3 sm:h-4 sm:w-4" />
                    <span>{campaign.instances_detail?.length || 0} instâncias</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <Send className="h-3 w-3 sm:h-4 sm:w-4" />
                    <span>{campaign.messages?.length || 0} mensagens</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <TrendingUp className="h-3 w-3 sm:h-4 sm:w-4" />
                    <span className="hidden sm:inline">{campaign.rotation_mode_display}</span>
                    <span className="sm:hidden">Rotação</span>
                  </div>
                </div>
              </div>
              
              <div className="flex flex-wrap gap-2">
                {/* Iniciar - só para draft/scheduled */}
                {(campaign.status === 'draft' || campaign.status === 'scheduled') && (
                  <Button 
                    variant="default" 
                    size="sm"
                    onClick={() => handleStart(campaign.id)}
                    title="Iniciar campanha"
                  >
                    <Play className="h-4 w-4 mr-1" />
                    Iniciar
                  </Button>
                )}
                
                {/* Pausar - só para running */}
                {campaign.status === 'running' && (
                  <Button 
                    variant="outline" 
                    size="sm"
                    onClick={() => handlePause(campaign.id)}
                    title="Pausar campanha"
                  >
                    <Pause className="h-4 w-4" />
                  </Button>
                )}
                
                {/* Retomar - só para paused */}
                {campaign.status === 'paused' && (
                  <Button 
                    variant="outline" 
                    size="sm"
                    onClick={() => handleResume(campaign.id)}
                    title="Retomar campanha"
                  >
                    <Play className="h-4 w-4" />
                  </Button>
                )}
                
                {/* Cancelar - para running e paused */}
                {(campaign.status === 'running' || campaign.status === 'paused') && (
                  <Button 
                    variant="outline" 
                    size="sm"
                    onClick={() => handleCancel(campaign.id)}
                    className="text-red-600 hover:text-red-700 hover:bg-red-50 border-red-300"
                    title="Cancelar campanha (irreversível)"
                  >
                    <X className="h-4 w-4 mr-1" />
                    Cancelar
                  </Button>
                )}
                
                {/* Copiar - só para completed */}
                {campaign.status === 'completed' && (
                  <Button 
                    variant="outline" 
                    size="sm"
                    onClick={() => handleDuplicate(campaign)}
                    title="Copiar campanha"
                  >
                    <Copy className="h-4 w-4 mr-1" />
                    Copiar
                  </Button>
                )}
                
                {/* Editar - só para draft */}
                {campaign.status === 'draft' && (
                  <Button 
                    variant="outline" 
                    size="sm" 
                    onClick={() => handleEdit(campaign)}
                    title="Editar campanha"
                  >
                    <Edit className="h-4 w-4" />
                  </Button>
                )}
                
                {/* Excluir - só para draft */}
                {campaign.status === 'draft' && (
                  <Button 
                    variant="outline" 
                    size="sm" 
                    onClick={() => handleDelete(campaign.id)}
                    className="text-red-600 hover:text-red-700"
                    title="Excluir campanha"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                )}
                
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
              <div className="mt-4 space-y-3">
                {/* Barra de Progresso */}
                <div>
                  <div className="flex justify-between items-center text-sm mb-1">
                    <span className="text-gray-600">Progresso da Campanha</span>
                    <div className="flex items-center gap-3">
                      <span className="font-bold text-blue-600">
                        {campaign.messages_sent}/{campaign.total_contacts}
                      </span>
                      <span className="font-medium text-gray-900">
                        {campaign.progress_percentage?.toFixed(1) || 0}%
                      </span>
                    </div>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2.5">
                    <div 
                      className="bg-blue-600 h-2.5 rounded-full transition-all"
                      style={{ width: `${campaign.progress_percentage || 0}%` }}
                    />
                  </div>
                </div>

                {/* Estatísticas Detalhadas */}
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 pt-2 border-t">
                  <div className="text-center">
                    <div className="text-base sm:text-lg font-bold text-blue-600">
                      {campaign.messages_sent || 0}
                    </div>
                    <div className="text-xs text-gray-500">Enviadas</div>
                  </div>
                  
                  <div className="text-center">
                    <div className="text-base sm:text-lg font-bold text-green-600">
                      {campaign.messages_delivered || 0}
                    </div>
                    <div className="text-xs text-gray-500">Entregues</div>
                  </div>
                  
                  <div className="text-center">
                    <div className="text-base sm:text-lg font-bold text-teal-600">
                      {campaign.messages_read || 0}
                    </div>
                    <div className="text-xs text-gray-500">Lidas</div>
                  </div>
                  
                  <div className="text-center">
                    <div className="text-base sm:text-lg font-bold text-red-600">
                      {campaign.messages_failed || 0}
                    </div>
                    <div className="text-xs text-gray-500">Falhas</div>
                  </div>
                  
                  <div className="text-center col-span-2 sm:col-span-1">
                    <div className={`text-base sm:text-lg font-bold ${
                      campaign.messages_sent > 0 
                        ? `text-green-600` 
                        : 'text-gray-400'
                    }`}>
                      {campaign.messages_sent > 0 
                        ? ((campaign.messages_delivered / campaign.messages_sent) * 100).toFixed(1)
                        : '0.0'}%
                    </div>
                    <div className="text-xs text-gray-500">Taxa Entrega</div>
                  </div>
                </div>

                {/* Próximo Disparo */}
                {campaign.status === 'running' && campaign.next_message_scheduled_at && (
                  <div className="pt-2 border-t">
                    <NextMessageCountdown 
                      nextScheduledAt={campaign.next_message_scheduled_at} 
                      campaignStatus={campaign.status}
                      nextContactName={campaign.next_contact_name}
                      nextContactPhone={campaign.next_contact_phone}
                      nextInstanceName={campaign.next_instance_name}
                      lastContactName={campaign.last_contact_name}
                      lastContactPhone={campaign.last_contact_phone}
                      lastInstanceName={campaign.last_instance_name}
                    />
                  </div>
                )}
                
                {/* Alerta de Health Baixo */}
                {campaign.status === 'completed' && campaign.instances_detail?.some(i => i.health_score < campaign.pause_on_health_below) && (
                  <div className="pt-2 border-t">
                    <div className="bg-yellow-50 border border-yellow-200 rounded p-2 text-xs">
                      <div className="flex items-start gap-2">
                        <AlertCircle className="h-4 w-4 text-yellow-600 flex-shrink-0 mt-0.5" />
                        <div>
                          <p className="font-medium text-yellow-900">
                            Campanha pausada por health score baixo
                          </p>
                          <p className="text-yellow-700">
                            Instância(s) com health abaixo de {campaign.pause_on_health_below}. 
                            Verifique os logs para detalhes.
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </Card>
        ))}
      </div>

      {filteredCampaigns.length === 0 && (
        <div className="text-center py-12">
          <Send className="mx-auto h-12 w-12 text-gray-400 mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">Nenhuma campanha encontrada</h3>
          <p className="text-gray-600 mb-4">
            {searchTerm ? 'Tente ajustar os filtros de busca.' : 'Crie sua primeira campanha para começar.'}
          </p>
          {!searchTerm && (
            <Button onClick={() => setShowModal(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Nova Campanha
            </Button>
          )}
        </div>
      )}

      {/* Wizard Modal de Criação/Edição */}
      {showModal && (
        <CampaignWizardModal
          onClose={handleCloseModal}
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
                <h2 className="text-lg sm:text-xl font-bold truncate">Logs da Campanha</h2>
                <p className="text-xs sm:text-sm text-gray-500 truncate">{selectedCampaignForLogs.name}</p>
              </div>
              <button onClick={() => setShowLogsModal(false)} className="text-gray-400 hover:text-gray-600 ml-2 flex-shrink-0">
                <X className="h-5 w-5 sm:h-6 sm:w-6" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-3 sm:p-4">
              {logs.length === 0 ? (
                <div className="text-center py-6 sm:py-8 text-gray-500">
                  Nenhum log encontrado
                </div>
              ) : (
                <div className="space-y-3 sm:space-y-4">
                  {/* Estatísticas Rápidas */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 sm:gap-4 mb-4">
                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-2 sm:p-3 text-center">
                      <div className="text-lg sm:text-xl font-bold text-blue-600">
                        {logs.reduce((count, g: any) => count + (g.events.filter((e: any) => e.log_type === 'message_read').length), 0)}
                            </div>
                      <div className="text-xs sm:text-sm text-blue-800">Lidas</div>
                              </div>
                    <div className="bg-green-50 border border-green-200 rounded-lg p-2 sm:p-3 text-center">
                      <div className="text-lg sm:text-xl font-bold text-green-600">
                        {logs.reduce((count, g: any) => count + (g.events.filter((e: any) => e.log_type === 'message_delivered').length), 0)}
                          </div>
                      <div className="text-xs sm:text-sm text-green-800">Entregues</div>
                        </div>
                    <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-2 sm:p-3 text-center">
                      <div className="text-lg sm:text-xl font-bold text-yellow-600">
                        {logs.reduce((count, g: any) => count + (g.events.filter((e: any) => e.log_type === 'message_sent').length), 0)}
                      </div>
                      <div className="text-xs sm:text-sm text-yellow-800">Enviadas</div>
                    </div>
                    <div className="bg-red-50 border border-red-200 rounded-lg p-2 sm:p-3 text-center">
                      <div className="text-lg sm:text-xl font-bold text-red-600">
                        {logs.reduce((count, g: any) => count + (g.events.filter((e: any) => e.log_type === 'message_failed').length), 0)}
                      </div>
                      <div className="text-xs sm:text-sm text-red-800">Falhas</div>
                    </div>
                  </div>
                  
                  {/* Cards de Contatos */}
                  {logs.map((contactGroup: any, idx: number) => (
                    <ContactLogCard key={idx} contactGroup={contactGroup} />
                  ))}
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

