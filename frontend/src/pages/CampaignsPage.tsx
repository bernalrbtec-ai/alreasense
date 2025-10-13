import React, { useState, useEffect } from 'react'
import { Plus, Search, Send, Pause, Play, Edit, Trash2, Users, TrendingUp, Copy, FileText, Clock, X, AlertCircle } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Input } from '../components/ui/Input'
import { showSuccessToast, showErrorToast, showLoadingToast, updateToastSuccess, updateToastError } from '../lib/toastHelper'
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
    fetchData()
    
    // Atualização automática a cada 5 segundos (silenciosa, sem loading)
    const interval = setInterval(() => {
      if (!showModal) {  // Só atualizar se modal estiver fechado
        fetchData(true)  // silent mode
      }
    }, 5000)
    
    return () => clearInterval(interval)
  }, [showModal])

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
      fetchData()
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
      fetchData()
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
      fetchData()
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
      fetchData()
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
      fetchData()
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
      fetchData()
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
      setLogs(response.data)
    } catch (error: any) {
      console.error('Erro ao buscar logs:', error)
      showErrorToast('buscar', 'Logs', error)
    }
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

  const filteredCampaigns = campaigns.filter(campaign =>
    campaign.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    campaign.description.toLowerCase().includes(searchTerm.toLowerCase())
  )

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-accent-500"></div>
      </div>
    )
  }

  return (
    <div className="p-6">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">📤 Campanhas</h1>
          <p className="text-gray-600">Gerencie suas campanhas de disparo em massa</p>
        </div>
        <Button onClick={() => setShowModal(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Nova Campanha
        </Button>
      </div>

      {/* Filtros */}
      <div className="flex gap-4 mb-6">
        <div className="flex-1">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
            <Input
              placeholder="Buscar campanhas..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10"
            />
          </div>
        </div>
      </div>

      {/* Lista de Campanhas */}
      <div className="grid gap-4">
        {filteredCampaigns.map((campaign) => (
          <Card key={campaign.id} className="p-6">
            <div className="flex justify-between items-start mb-4">
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-2">
                  <h3 className="text-lg font-semibold text-gray-900">{campaign.name}</h3>
                  <span className={`px-2 py-1 text-xs font-medium rounded-full ${getStatusColor(campaign.status)}`}>
                    {campaign.status_display}
                  </span>
                </div>
                <p className="text-gray-600 mb-3">{campaign.description}</p>
                
                <div className="flex gap-4 text-sm text-gray-600">
                  <div className="flex items-center gap-1">
                    <Users className="h-4 w-4" />
                    <span>{campaign.instances_detail?.length || 0} instâncias</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <Send className="h-4 w-4" />
                    <span>{campaign.messages?.length || 0} mensagens</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <TrendingUp className="h-4 w-4" />
                    <span>{campaign.rotation_mode_display}</span>
                  </div>
                </div>
              </div>
              
              <div className="flex gap-2">
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
                <div className="grid grid-cols-5 gap-3 pt-2 border-t">
                  <div className="text-center">
                    <div className="text-lg font-bold text-blue-600">
                      {campaign.messages_sent || 0}
                    </div>
                    <div className="text-xs text-gray-500">Enviadas</div>
                  </div>
                  
                  <div className="text-center">
                    <div className="text-lg font-bold text-green-600">
                      {campaign.messages_delivered || 0}
                    </div>
                    <div className="text-xs text-gray-500">Entregues</div>
                  </div>
                  
                  <div className="text-center">
                    <div className="text-lg font-bold text-teal-600">
                      {campaign.messages_read || 0}
                    </div>
                    <div className="text-xs text-gray-500">Lidas</div>
                  </div>
                  
                  <div className="text-center">
                    <div className="text-lg font-bold text-red-600">
                      {campaign.messages_failed || 0}
                    </div>
                    <div className="text-xs text-gray-500">Falhas</div>
                  </div>
                  
                  <div className="text-center">
                    <div className={`text-lg font-bold ${
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
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center p-4 border-b sticky top-0 bg-white">
              <div>
                <h2 className="text-xl font-bold">Logs da Campanha</h2>
                <p className="text-sm text-gray-500">{selectedCampaignForLogs.name}</p>
              </div>
              <button onClick={() => setShowLogsModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="h-6 w-6" />
              </button>
            </div>

            <div className="p-4">
              {logs.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  Nenhum log encontrado
                </div>
              ) : (
                <div className="space-y-2">
                  {logs.map((log, idx) => {
                    const severityColors = {
                      'info': 'bg-blue-50 border-blue-200 text-blue-900',
                      'warning': 'bg-yellow-50 border-yellow-200 text-yellow-900',
                      'error': 'bg-red-50 border-red-200 text-red-900',
                      'critical': 'bg-red-100 border-red-300 text-red-950'
                    }
                    
                    const severityIcons = {
                      'info': '📘',
                      'warning': '⚠️',
                      'error': '❌',
                      'critical': '🔴'
                    }
                    
                    return (
                      <div key={idx} className={`border rounded p-3 text-sm ${severityColors[log.severity] || 'bg-gray-50'}`}>
                        <div className="flex items-start gap-2">
                          <span className="text-lg">{severityIcons[log.severity]}</span>
                          <div className="flex-1">
                            <div className="flex justify-between items-start mb-1">
                              <span className="font-semibold">{log.log_type_display}</span>
                              <span className="text-xs opacity-75">
                                {new Date(log.created_at).toLocaleString('pt-BR')}
                              </span>
                            </div>
                            <p className="mb-1">{log.message}</p>
                            
                            {log.contact_name && (
                              <p className="text-xs opacity-75">
                                👤 Contato: {log.contact_name}
                              </p>
                            )}
                            
                            {log.instance_name && (
                              <p className="text-xs opacity-75">
                                📱 Instância: {log.instance_name}
                              </p>
                            )}
                            
                            {log.details?.message_content && (
                              <div className="mt-2 p-3 bg-green-50 border border-green-200 rounded">
                                <p className="text-xs font-medium mb-1">💬 Mensagem enviada:</p>
                                <p className="text-xs whitespace-pre-wrap">{log.details.message_content}</p>
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>

            <div className="p-4 border-t bg-gray-50 flex justify-end">
              <Button onClick={() => setShowLogsModal(false)}>
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

