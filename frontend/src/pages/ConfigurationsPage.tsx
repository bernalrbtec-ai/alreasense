import { useState, useEffect } from 'react'
import { 
  Settings, 
  Server, 
  CreditCard, 
  Mail, 
  Plus, 
  Edit, 
  Trash2, 
  Eye, 
  EyeOff,
  Check,
  X,
  AlertCircle,
  Info,
  QrCode,
  WifiOff,
  Phone,
  Key,
  TestTube,
  Send,
  Save,
  Crown,
  Users,
  Building2,
  Bell,
  Clock,
  MessageSquare,
  Calendar
} from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Input } from '../components/ui/Input'
import { Label } from '../components/ui/Label'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import { api } from '../lib/api'
import { showSuccessToast, showErrorToast, showLoadingToast, updateToastSuccess, updateToastError } from '../lib/toastHelper'
import { useAuthStore } from '../stores/authStore'
import { useTenantLimits } from '../hooks/useTenantLimits'
import { DepartmentsManager } from '../components/team/DepartmentsManager'
import { UsersManager } from '../components/team/UsersManager'
import { NotificationSettings } from '../modules/notifications/components/NotificationSettings'

interface WhatsAppInstance {
  id: string
  friendly_name: string
  instance_name: string
  phone_number: string
  status: string
  is_active: boolean
  is_default: boolean
  default_department?: string | null
  connection_state: string
  qr_code?: string
  qr_code_expires_at?: string
}

interface Plan {
  id: string
  name: string
  slug: string
  price: number
  description?: string
}

interface Tenant {
  id: string
  name: string
  current_plan?: Plan
  status: string
  monthly_total?: number
}

interface SMTPConfig {
  id: string
  name: string
  host: string
  port: number
  from_email: string
  from_name: string
  is_active: boolean
  is_default: boolean
  last_test_status: string
  last_test: string
}

interface EvolutionConfig {
  base_url: string
  api_key: string
  webhook_url: string
  is_active: boolean
  last_check?: string
  status?: 'active' | 'inactive' | 'error'
  last_error?: string | null
  instance_count?: number
}

export default function ConfigurationsPage() {
  const { user } = useAuthStore()
  const [activeTab, setActiveTab] = useState<'instances' | 'smtp' | 'plan' | 'team' | 'notifications' | 'business-hours'>('instances')
  const [isLoading, setIsLoading] = useState(true)
  
  // Estados para instâncias WhatsApp
  const [instances, setInstances] = useState<WhatsAppInstance[]>([])
  const [isInstanceModalOpen, setIsInstanceModalOpen] = useState(false)
  const [editingInstance, setEditingInstance] = useState<WhatsAppInstance | null>(null)
  const [instanceFormData, setInstanceFormData] = useState({
    friendly_name: '',
    default_department: null as string | null
  })
  const [departments, setDepartments] = useState<Array<{id: string, name: string}>>([])
  const [qrCodeInstance, setQrCodeInstance] = useState<WhatsAppInstance | null>(null)
  const [showApiKeys, setShowApiKeys] = useState(false)
  const [testInstance, setTestInstance] = useState<WhatsAppInstance | null>(null)
  const [testPhoneNumber, setTestPhoneNumber] = useState('')
  
  // Estados para SMTP
  const [smtpConfigs, setSmtpConfigs] = useState<SMTPConfig[]>([])
  const [isSmtpModalOpen, setIsSmtpModalOpen] = useState(false)
  const [editingSmtp, setEditingSmtp] = useState<SMTPConfig | null>(null)
  const [smtpFormData, setSmtpFormData] = useState({
    name: '',
    host: '',
    port: 587,
    from_email: '',
    from_name: '',
    is_active: true,
    is_default: false
  })
  const [showSmtpPassword, setShowSmtpPassword] = useState(false)
  
  // Estados para plano
  const [tenant, setTenant] = useState<Tenant | null>(null)
  const { limits, loading: limitsLoading } = useTenantLimits()

  // Estados para Horários de Atendimento
  const [businessHoursDepts, setBusinessHoursDepts] = useState<Department[]>([])
  const [businessHoursUsers, setBusinessHoursUsers] = useState<User[]>([])
  const [selectedBusinessHoursDept, setSelectedBusinessHoursDept] = useState<string | null>(null)
  const [businessHoursSubTab, setBusinessHoursSubTab] = useState<'hours' | 'message' | 'tasks'>('hours')
  const [businessHours, setBusinessHours] = useState<BusinessHours | null>(null)
  const [holidaysInput, setHolidaysInput] = useState('')
  const [afterHoursMessage, setAfterHoursMessage] = useState<AfterHoursMessage | null>(null)
  const [taskConfig, setTaskConfig] = useState<AfterHoursTaskConfig | null>(null)

  useEffect(() => {
    fetchData()
    fetchDepartments()
    if (activeTab === 'business-hours') {
      fetchBusinessHoursData()
    }
  }, [activeTab, selectedBusinessHoursDept])
  
  const fetchDepartments = async () => {
    try {
      const response = await api.get('/auth/departments/')
      const depts = Array.isArray(response.data) ? response.data : (response.data?.results || [])
      setDepartments(depts.map((d: any) => ({ id: d.id, name: d.name })))
    } catch (error) {
      console.error('Erro ao buscar departamentos:', error)
    }
  }

  const fetchData = async () => {
    try {
      setIsLoading(true)
      await Promise.all([
        fetchInstances(),
        fetchSmtpConfigs(),
        fetchTenantInfo()
      ])
    } catch (error) {
      console.error('Error fetching configuration data:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const fetchInstances = async () => {
    try {
      const response = await api.get('/notifications/whatsapp-instances/')
      // O backend já filtra por tenant automaticamente
      setInstances(response.data.results || response.data)
    } catch (error) {
      console.error('Error fetching instances:', error)
    }
  }

  const fetchSmtpConfigs = async () => {
    try {
      const response = await api.get('/notifications/smtp-configs/')
      // O backend já filtra por tenant automaticamente
      setSmtpConfigs(response.data.results || response.data)
    } catch (error) {
      console.error('Error fetching SMTP configs:', error)
    }
  }

  const fetchTenantInfo = async () => {
    try {
      const response = await api.get('/tenants/tenants/current/')
      setTenant(response.data)
    } catch (error) {
      console.error('Error fetching tenant info:', error)
    }
  }

  // Funções para instâncias WhatsApp (replicadas do NotificationsPage)
  const handleCreateInstance = async () => {
    const toastId = showLoadingToast('criar', 'Instância')
    
    try {
      await api.post('/notifications/whatsapp-instances/', instanceFormData)
      updateToastSuccess(toastId, 'criar', 'Instância')
      
      // Atualizar lista de instâncias E limites
      await Promise.all([
        fetchInstances(),
        limits?.refetch?.()
      ])
      
      handleCloseInstanceModal()
    } catch (error: any) {
      console.error('Error creating instance:', error)
      updateToastError(toastId, 'criar', 'Instância', error)
    }
  }

  const handleUpdateInstance = async () => {
    if (!editingInstance) return
    
    const toastId = showLoadingToast('atualizar', 'Instância')
    
    try {
      await api.patch(`/notifications/whatsapp-instances/${editingInstance.id}/`, instanceFormData)
      updateToastSuccess(toastId, 'atualizar', 'Instância')
      
      await fetchInstances()
      handleCloseInstanceModal()
    } catch (error: any) {
      console.error('Error updating instance:', error)
      updateToastError(toastId, 'atualizar', 'Instância', error)
    }
  }

  const handleEditInstance = (instance: WhatsAppInstance) => {
    setEditingInstance(instance)
    setInstanceFormData({
      friendly_name: instance.friendly_name,
      default_department: instance.default_department || null
    })
    setIsInstanceModalOpen(true)
  }

  const handleDeleteInstance = async (id: string) => {
    if (!confirm('Tem certeza que deseja excluir esta instância?')) return
    
    const toastId = showLoadingToast('excluir', 'Instância')
    
    try {
      await api.delete(`/notifications/whatsapp-instances/${id}/`)
      updateToastSuccess(toastId, 'excluir', 'Instância')
      fetchInstances()
    } catch (error: any) {
      console.error('Error deleting instance:', error)
      updateToastError(toastId, 'excluir', 'Instância', error)
    }
  }

  const handleGenerateQR = async (instance: WhatsAppInstance) => {
    const toastId = showLoadingToast('criar', 'QR Code')
    
    try {
      const response = await api.post(`/notifications/whatsapp-instances/${instance.id}/generate_qr/`)
      
      if (response.data.qr_code) {
        // Atualizar instância com o QR Code retornado
        const updatedInstance = {
          ...instance,
          qr_code: response.data.qr_code,
          qr_code_expires_at: response.data.qr_code_expires_at
        }
        setQrCodeInstance(updatedInstance)
        updateToastSuccess(toastId, 'criar', 'QR Code')
        
        // Iniciar polling para verificar conexão
        startConnectionPolling(instance.id)
      } else {
        updateToastError(toastId, 'criar', 'QR Code', { message: 'QR Code não foi retornado' })
      }
    } catch (error: any) {
      console.error('Error generating QR code:', error)
      updateToastError(toastId, 'criar', 'QR Code', error)
    }
  }

  // Polling para verificar status de conexão
  const startConnectionPolling = (instanceId: string) => {
    console.log('🔄 Iniciando polling de conexão para instância:', instanceId)
    
    const intervalId = setInterval(async () => {
      try {
        console.log('⏱️ Verificando status da instância...')
        const response = await api.post(`/notifications/whatsapp-instances/${instanceId}/check_status/`)
        const status = response.data
        
        console.log('📊 Status atual:', status.connection_state)
        
        // Atualizar lista de instâncias para mostrar mudanças de status em tempo real
        fetchInstances()
        
        // Se conectou, parar polling e fechar modal
        if (status.connection_state === 'open') {
          console.log('✅ WhatsApp conectado! Parando polling...')
          stopConnectionPolling()
          setQrCodeInstance(null)
          showSuccessToast('conectar', 'WhatsApp')
          
          // Atualizar limites após conexão
          if (limits?.refetch) {
            limits.refetch()
          }
        }
      } catch (error) {
        console.error('❌ Error polling connection status:', error)
      }
    }, 3000) // Verifica a cada 3 segundos
    
    // Salvar ID do intervalo
    ;(window as any).connectionPollingInterval = intervalId
  }

  const stopConnectionPolling = () => {
    const intervalId = (window as any).connectionPollingInterval
    if (intervalId) {
      clearInterval(intervalId)
      ;(window as any).connectionPollingInterval = null
    }
  }

  // Limpar polling quando componente desmonta ou modal fecha
  useEffect(() => {
    return () => {
      stopConnectionPolling()
    }
  }, [])

  useEffect(() => {
    if (!qrCodeInstance) {
      stopConnectionPolling()
    }
  }, [qrCodeInstance])

  const handleCheckStatus = async (instance: WhatsAppInstance) => {
    const toastId = showLoadingToast('atualizar', 'Status')
    
    try {
      await api.post(`/notifications/whatsapp-instances/${instance.id}/check_status/`)
      updateToastSuccess(toastId, 'atualizar', 'Status')
      fetchInstances()
    } catch (error: any) {
      console.error('Error checking status:', error)
      updateToastError(toastId, 'atualizar', 'Status', error)
    }
  }

  const handleDisconnect = async (instance: WhatsAppInstance) => {
    if (!confirm('Tem certeza que deseja desconectar esta instância?')) return
    
    const toastId = showLoadingToast('desconectar', 'Instância')
    
    try {
      await api.post(`/notifications/whatsapp-instances/${instance.id}/disconnect/`)
      updateToastSuccess(toastId, 'desconectar', 'Instância')
      fetchInstances()
    } catch (error: any) {
      console.error('Error disconnecting instance:', error)
      updateToastError(toastId, 'desconectar', 'Instância', error)
    }
  }

  const handleSendTestMessage = async () => {
    if (!testInstance || !testPhoneNumber) return
    
    const toastId = showLoadingToast('enviar', 'Mensagem de Teste')
    
    try {
      // Normalizar o número de telefone (remover caracteres não numéricos)
      const normalizedPhone = testPhoneNumber.replace(/\D/g, '')
      
      // Enviar mensagem de teste
      await api.post(`/notifications/whatsapp-instances/${testInstance.id}/send_test/`, {
        phone: normalizedPhone,
        message: `🧪 Mensagem de teste enviada de ${testInstance.friendly_name}\n\nSe você recebeu esta mensagem, sua instância WhatsApp está funcionando corretamente! ✅`
      })
      
      updateToastSuccess(toastId, 'enviar', 'Mensagem de Teste')
      setTestInstance(null)
      setTestPhoneNumber('')
    } catch (error: any) {
      console.error('Error sending test message:', error)
      updateToastError(toastId, 'enviar', 'Mensagem de Teste', error)
    }
  }

  // Funções para SMTP
  const handleSaveSmtpConfig = async () => {
    const toastId = showLoadingToast(editingSmtp ? 'atualizar' : 'criar', 'Configuração SMTP')
    
    try {
      if (editingSmtp) {
        await api.patch(`/notifications/smtp-configs/${editingSmtp.id}/`, smtpFormData)
        updateToastSuccess(toastId, 'atualizar', 'Configuração SMTP')
      } else {
        await api.post('/notifications/smtp-configs/', smtpFormData)
        updateToastSuccess(toastId, 'criar', 'Configuração SMTP')
      }
      fetchSmtpConfigs()
      handleCloseSmtpModal()
    } catch (error: any) {
      console.error('Error saving SMTP config:', error)
      updateToastError(toastId, editingSmtp ? 'atualizar' : 'criar', 'Configuração SMTP', error)
    }
  }

  const handleDeleteSmtpConfig = async (id: string) => {
    if (!confirm('Tem certeza que deseja excluir esta configuração SMTP?')) return
    
    const toastId = showLoadingToast('excluir', 'Configuração SMTP')
    
    try {
      await api.delete(`/notifications/smtp-configs/${id}/`)
      updateToastSuccess(toastId, 'excluir', 'Configuração SMTP')
      fetchSmtpConfigs()
    } catch (error: any) {
      console.error('Error deleting SMTP config:', error)
      updateToastError(toastId, 'excluir', 'Configuração SMTP', error)
    }
  }

  const handleTestSmtp = async (config: SMTPConfig) => {
    const toastId = showLoadingToast('testar', 'SMTP')
    
    try {
      await api.post(`/notifications/smtp-configs/${config.id}/test/`)
      updateToastSuccess(toastId, 'testar', 'SMTP')
      fetchSmtpConfigs()
    } catch (error: any) {
      console.error('Error testing SMTP:', error)
      updateToastError(toastId, 'testar', 'SMTP', error)
    }
  }

  const handleCloseInstanceModal = () => {
    setIsInstanceModalOpen(false)
    setEditingInstance(null)
    setInstanceFormData({ friendly_name: '', default_department: null })
  }

  const handleCloseSmtpModal = () => {
    setIsSmtpModalOpen(false)
    setEditingSmtp(null)
    setSmtpFormData({
      name: '',
      host: '',
      port: 587,
      from_email: '',
      from_name: '',
      is_active: true,
      is_default: false
    })
  }

  const getConnectionStatusColor = (state: string) => {
    switch (state) {
      case 'open': return 'text-green-600 bg-green-100'
      case 'connecting': return 'text-yellow-600 bg-yellow-100'
      case 'close': return 'text-red-600 bg-red-100'
      default: return 'text-gray-600 bg-gray-100'
    }
  }

  const getConnectionStatusText = (state: string) => {
    switch (state) {
      case 'open': return 'Conectado'
      case 'connecting': return 'Conectando'
      case 'close': return 'Desconectado'
      default: return 'Desconhecido'
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Configurações</h1>
          <p className="text-gray-600">Gerencie suas instâncias, servidores e configurações</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab('instances')}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'instances'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            <Server className="h-4 w-4 inline mr-2" />
            Instâncias WhatsApp
          </button>
          <button
            onClick={() => setActiveTab('smtp')}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'smtp'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            <Mail className="h-4 w-4 inline mr-2" />
            Configurações SMTP
          </button>
          <button
            onClick={() => setActiveTab('plan')}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'plan'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            <CreditCard className="h-4 w-4 inline mr-2" />
            Meu Plano
          </button>
          <button
            onClick={() => setActiveTab('team')}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'team'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            <Users className="h-4 w-4 inline mr-2" />
            Equipe
          </button>
          <button
            onClick={() => setActiveTab('notifications')}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'notifications'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            <Bell className="h-4 w-4 inline mr-2" />
            Notificações
          </button>
          <button
            onClick={() => setActiveTab('business-hours')}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'business-hours'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            <Clock className="h-4 w-4 inline mr-2" />
            Horários de Atendimento
          </button>
        </nav>
      </div>

      {/* Tab Content - Instâncias WhatsApp */}
      {activeTab === 'instances' && (
        <div className="space-y-6">
          {/* Limites do Plano */}
          {limits && (
            <Card className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-medium text-gray-900">Limites do Plano</h3>
                <div className="flex items-center text-sm text-gray-500">
                  <Crown className="h-4 w-4 mr-1" />
                  {limits.plan?.name || 'Sem plano'}
                </div>
              </div>
              
              {limits.products?.flow && (
                <div className="bg-blue-50 p-4 rounded-lg">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="font-medium text-blue-900">ALREA Flow (WhatsApp)</h4>
                      <p className="text-sm text-blue-700">
                        {limits.products.flow.current_usage || 0} de {limits.products.flow.limit || 0} instâncias
                      </p>
                    </div>
                    <div className="text-right">
                      <div className="text-2xl font-bold text-blue-900">
                        {limits.products.flow.current_usage || 0}/{limits.products.flow.limit || 0}
                      </div>
                      <div className="text-sm text-blue-700">instâncias</div>
                    </div>
                  </div>
                </div>
              )}
            </Card>
          )}

          {/* Lista de Instâncias */}
          <Card className="p-6">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-medium text-gray-900">Suas Instâncias WhatsApp</h3>
              <div className="flex items-center space-x-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowApiKeys(!showApiKeys)}
                >
                  <Key className="h-4 w-4 mr-2" />
                  {showApiKeys ? 'Ocultar' : 'Mostrar'} API Keys
                </Button>
                <Button
                  onClick={() => setIsInstanceModalOpen(true)}
                  disabled={limits?.products?.flow && 
                    (limits.products.flow.current_usage || 0) >= (limits.products.flow.limit || 0)}
                >
                  <Plus className="h-4 w-4 mr-2" />
                  Nova Instância
                </Button>
              </div>
            </div>

            {instances.length === 0 ? (
              <div className="text-center py-12">
                <Server className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-gray-900 mb-2">Nenhuma instância cadastrada</h3>
                <p className="text-gray-500 mb-4">Crie sua primeira instância WhatsApp para começar</p>
                <Button onClick={() => setIsInstanceModalOpen(true)}>
                  <Plus className="h-4 w-4 mr-2" />
                  Criar Primeira Instância
                </Button>
              </div>
            ) : (
              <div className="grid gap-4">
                {instances.map((instance) => (
                  <div key={instance.id} className="border border-gray-200 rounded-lg p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <div className="flex items-center mb-2">
                          <h4 className="font-medium text-gray-900">{instance.friendly_name}</h4>
                          <span className={`ml-3 px-2 py-1 text-xs font-medium rounded-full ${getConnectionStatusColor(instance.connection_state)}`}>
                            {getConnectionStatusText(instance.connection_state)}
                          </span>
                        </div>
                        <div className="flex items-center space-x-4 text-sm text-gray-600">
                          {instance.phone_number && (
                            <div className="flex items-center">
                              <Phone className="h-4 w-4 mr-1" />
                              {instance.phone_number}
                            </div>
                          )}
                          {showApiKeys && (
                            <div className="flex items-center">
                              <Key className="h-4 w-4 mr-1" />
                              {instance.instance_name}
                            </div>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center space-x-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleCheckStatus(instance)}
                          disabled={instance.connection_state !== 'open'}
                          title="Verificar Status da Conexão"
                        >
                          <WifiOff className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleGenerateQR(instance)}
                          title="Gerar/Atualizar QR Code"
                        >
                          <QrCode className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setTestInstance(instance)
                            setTestPhoneNumber('')
                          }}
                          disabled={instance.connection_state !== 'open'}
                          title="Enviar Mensagem de Teste"
                          className="text-blue-600 hover:text-blue-700"
                        >
                          <Send className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleDisconnect(instance)}
                          disabled={instance.connection_state !== 'open'}
                          title="Desconectar Instância"
                        >
                          <X className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleEditInstance(instance)}
                          title="Editar Instância"
                          className="text-blue-600 hover:text-blue-700"
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleDeleteInstance(instance.id)}
                          className="text-red-600 hover:text-red-700"
                          title="Excluir Instância"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      )}

      {/* Tab Content - SMTP */}
      {activeTab === 'smtp' && (
        <div className="space-y-6">
          <Card className="p-6">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h3 className="text-lg font-medium text-gray-900">Configurações SMTP</h3>
                <p className="text-sm text-gray-600">Configure servidores SMTP para envio de emails</p>
              </div>
              <Button onClick={() => setIsSmtpModalOpen(true)}>
                <Plus className="h-4 w-4 mr-2" />
                Nova Configuração
              </Button>
            </div>

            {smtpConfigs.length === 0 ? (
              <div className="bg-gray-50 p-4 rounded-lg text-center">
                <Mail className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                <h4 className="font-medium text-gray-900 mb-2">Nenhuma configuração SMTP</h4>
                <p className="text-gray-600 mb-4">Configure um servidor SMTP para enviar emails</p>
                <Button onClick={() => setIsSmtpModalOpen(true)}>
                  <Plus className="h-4 w-4 mr-2" />
                  Criar Configuração
                </Button>
              </div>
            ) : (
              <div className="grid gap-4">
                {smtpConfigs.map((config) => (
                  <div key={config.id} className="border border-gray-200 rounded-lg p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <div className="flex items-center mb-2">
                          <h4 className="font-medium text-gray-900">{config.name}</h4>
                          {config.is_default && (
                            <span className="ml-2 px-2 py-1 text-xs font-medium bg-blue-100 text-blue-800 rounded-full">
                              Padrão
                            </span>
                          )}
                          <span className={`ml-2 px-2 py-1 text-xs font-medium rounded-full ${
                            config.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                          }`}>
                            {config.is_active ? 'Ativo' : 'Inativo'}
                          </span>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm text-gray-600">
                          <div>
                            <span className="font-medium">Servidor:</span> {config.host}:{config.port}
                          </div>
                          <div>
                            <span className="font-medium">Email de origem:</span> {config.from_email}
                          </div>
                          <div>
                            <span className="font-medium">Nome de origem:</span> {config.from_name}
                          </div>
                          <div>
                            <span className="font-medium">Último teste:</span> {config.last_test || 'Nunca'}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center space-x-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleTestSmtp(config)}
                        >
                          <TestTube className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setEditingSmtp(config)
                            setSmtpFormData({
                              name: config.name,
                              host: config.host,
                              port: config.port,
                              from_email: config.from_email,
                              from_name: config.from_name,
                              is_active: config.is_active,
                              is_default: config.is_default
                            })
                            setIsSmtpModalOpen(true)
                          }}
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleDeleteSmtpConfig(config.id)}
                          className="text-red-600 hover:text-red-700"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      )}

      {/* Tab Content - Equipe */}
      {activeTab === 'team' && (
        <div className="space-y-6">
          <Card className="p-6">
            <UsersManager />
          </Card>
          <Card className="p-6">
            <DepartmentsManager />
          </Card>
        </div>
      )}

      {activeTab === 'notifications' && (
        <NotificationSettings />
      )}

      {/* Tab Content - Plano */}
      {activeTab === 'plan' && (
        <div className="space-y-6">
          {tenant && (
            <Card className="p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Informações do Plano</h3>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <h4 className="font-medium text-gray-900 mb-2">Plano Atual</h4>
                  <div className="bg-blue-50 p-4 rounded-lg">
                    <div className="text-2xl font-bold text-blue-900">
                      {tenant.current_plan?.name || 'Sem plano'}
                    </div>
                    <div className="text-blue-700">
                      R$ {Number(tenant.current_plan?.price || 0).toFixed(2)}/mês
                    </div>
                  </div>
                </div>
                
                <div>
                  <h4 className="font-medium text-gray-900 mb-2">Status da Conta</h4>
                  <div className="bg-green-50 p-4 rounded-lg">
                    <div className="text-2xl font-bold text-green-900 capitalize">
                      {tenant.status}
                    </div>
                    <div className="text-green-700">
                      Conta ativa
                    </div>
                  </div>
                </div>
              </div>

              {tenant.current_plan?.description && (
                <div className="mt-6">
                  <h4 className="font-medium text-gray-900 mb-2">Descrição do Plano</h4>
                  <p className="text-gray-600">{tenant.current_plan.description}</p>
                </div>
              )}

              <div className="mt-6 p-4 bg-yellow-50 rounded-lg">
                <div className="flex items-center">
                  <AlertCircle className="h-5 w-5 text-yellow-600 mr-2" />
                  <div>
                    <h4 className="font-medium text-yellow-900">Precisa de mais recursos?</h4>
                    <p className="text-sm text-yellow-700">
                      Entre em contato conosco para upgrade do seu plano
                    </p>
                  </div>
                </div>
              </div>
            </Card>
          )}
        </div>
      )}

      {/* Modal de Nova Instância */}
      {isInstanceModalOpen && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-full items-end justify-center p-4 text-center sm:items-center sm:p-0">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" onClick={handleCloseInstanceModal} />
            
            <div className="relative transform overflow-hidden rounded-lg bg-white text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-lg">
              <form onSubmit={(e) => { e.preventDefault(); editingInstance ? handleUpdateInstance() : handleCreateInstance(); }}>
                <div className="bg-white px-4 pb-4 pt-5 sm:p-6 sm:pb-4">
                  <h3 className="text-lg font-medium leading-6 text-gray-900 mb-4">
                    {editingInstance ? 'Editar Instância WhatsApp' : 'Nova Instância WhatsApp'}
                  </h3>
                  
                  <div className="space-y-4">
                    <div>
                      <label htmlFor="friendly_name" className="block text-sm font-medium text-gray-700">
                        Nome da Instância *
                      </label>
                      <input
                        type="text"
                        id="friendly_name"
                        required
                        value={instanceFormData.friendly_name}
                        onChange={(e) => setInstanceFormData({ ...instanceFormData, friendly_name: e.target.value })}
                        className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                        placeholder="Ex: WhatsApp Principal"
                      />
                      <p className="mt-1 text-xs text-gray-500">
                        Nome de exibição para identificar esta instância
                      </p>
                    </div>

                    <div>
                      <label htmlFor="default_department" className="block text-sm font-medium text-gray-700">
                        Departamento Padrão
                      </label>
                      <select
                        id="default_department"
                        value={instanceFormData.default_department || ''}
                        onChange={(e) => setInstanceFormData({ ...instanceFormData, default_department: e.target.value || null })}
                        className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                      >
                        <option value="">Inbox (sem departamento)</option>
                        {departments.map((dept) => (
                          <option key={dept.id} value={dept.id}>
                            {dept.name}
                          </option>
                        ))}
                      </select>
                      <p className="mt-1 text-xs text-gray-500">
                        Novas conversas desta instância irão automaticamente para este departamento. Deixe em branco para ir para Inbox.
                      </p>
                    </div>

                    <div className="bg-blue-50 p-4 rounded-lg">
                      <p className="text-sm text-blue-700">
                        ℹ️ O identificador único e o telefone serão preenchidos automaticamente após conectar o WhatsApp via QR Code.
                      </p>
                    </div>
                  </div>
                </div>
                
                <div className="bg-gray-50 px-4 py-3 sm:flex sm:flex-row-reverse sm:px-6">
                  <Button type="submit" className="w-full sm:w-auto sm:ml-3">
                    <Save className="h-4 w-4 mr-2" />
                    {editingInstance ? 'Atualizar Instância' : 'Criar Instância'}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={handleCloseInstanceModal}
                    className="mt-3 w-full sm:mt-0 sm:w-auto"
                  >
                    Cancelar
                  </Button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* Modal de Configuração SMTP */}
      {isSmtpModalOpen && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-full items-end justify-center p-4 text-center sm:items-center sm:p-0">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" onClick={handleCloseSmtpModal} />
            
            <div className="relative transform overflow-hidden rounded-lg bg-white text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-2xl max-h-[90vh] overflow-y-auto">
              <form onSubmit={(e) => { e.preventDefault(); handleSaveSmtpConfig(); }}>
                <div className="bg-white px-4 pb-4 pt-5 sm:p-6 sm:pb-4">
                  <h3 className="text-lg font-medium leading-6 text-gray-900 mb-4">
                    {editingSmtp ? 'Editar Configuração SMTP' : 'Nova Configuração SMTP'}
                  </h3>
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label htmlFor="smtp_name" className="block text-sm font-medium text-gray-700">
                        Nome da Configuração *
                      </label>
                      <input
                        type="text"
                        id="smtp_name"
                        required
                        value={smtpFormData.name}
                        onChange={(e) => setSmtpFormData({ ...smtpFormData, name: e.target.value })}
                        className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                        placeholder="Ex: Gmail SMTP"
                      />
                    </div>

                    <div>
                      <label htmlFor="smtp_host" className="block text-sm font-medium text-gray-700">
                        Servidor SMTP *
                      </label>
                      <input
                        type="text"
                        id="smtp_host"
                        required
                        value={smtpFormData.host}
                        onChange={(e) => setSmtpFormData({ ...smtpFormData, host: e.target.value })}
                        className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                        placeholder="smtp.gmail.com"
                      />
                    </div>

                    <div>
                      <label htmlFor="smtp_port" className="block text-sm font-medium text-gray-700">
                        Porta *
                      </label>
                      <input
                        type="number"
                        id="smtp_port"
                        required
                        value={smtpFormData.port}
                        onChange={(e) => setSmtpFormData({ ...smtpFormData, port: parseInt(e.target.value) })}
                        className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                        placeholder="587"
                      />
                    </div>

                    <div>
                      <label htmlFor="from_email" className="block text-sm font-medium text-gray-700">
                        Email de Origem *
                      </label>
                      <input
                        type="email"
                        id="from_email"
                        required
                        value={smtpFormData.from_email}
                        onChange={(e) => setSmtpFormData({ ...smtpFormData, from_email: e.target.value })}
                        className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                        placeholder="noreply@suaempresa.com"
                      />
                    </div>

                    <div>
                      <label htmlFor="from_name" className="block text-sm font-medium text-gray-700">
                        Nome de Origem *
                      </label>
                      <input
                        type="text"
                        id="from_name"
                        required
                        value={smtpFormData.from_name}
                        onChange={(e) => setSmtpFormData({ ...smtpFormData, from_name: e.target.value })}
                        className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                        placeholder="Sua Empresa"
                      />
                    </div>
                  </div>

                  <div className="mt-4 space-y-2">
                    <label className="flex items-center">
                      <input
                        type="checkbox"
                        checked={smtpFormData.is_active}
                        onChange={(e) => setSmtpFormData({ ...smtpFormData, is_active: e.target.checked })}
                        className="rounded border-gray-300 text-blue-600 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                      />
                      <span className="ml-2 text-sm text-gray-700">Ativar configuração</span>
                    </label>
                    
                    <label className="flex items-center">
                      <input
                        type="checkbox"
                        checked={smtpFormData.is_default}
                        onChange={(e) => setSmtpFormData({ ...smtpFormData, is_default: e.target.checked })}
                        className="rounded border-gray-300 text-blue-600 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                      />
                      <span className="ml-2 text-sm text-gray-700">Usar como padrão</span>
                    </label>
                  </div>
                </div>
                
                <div className="bg-gray-50 px-4 py-3 sm:flex sm:flex-row-reverse sm:px-6">
                  <Button type="submit" className="w-full sm:w-auto sm:ml-3">
                    <Save className="h-4 w-4 mr-2" />
                    Salvar Configuração
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={handleCloseSmtpModal}
                    className="mt-3 w-full sm:mt-0 sm:w-auto"
                  >
                    Cancelar
                  </Button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* Modal de QR Code */}
      {qrCodeInstance && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-full items-end justify-center p-4 text-center sm:items-center sm:p-0">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" onClick={() => setQrCodeInstance(null)} />
            
            <div className="relative transform overflow-hidden rounded-lg bg-white text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-md">
              <div className="bg-white px-4 pb-4 pt-5 sm:p-6 sm:pb-4">
                <h3 className="text-lg font-medium leading-6 text-gray-900 mb-4">
                  QR Code - {qrCodeInstance.friendly_name}
                </h3>
                
                {qrCodeInstance.qr_code && (
                  <div className="text-center">
                    <img 
                      src={qrCodeInstance.qr_code} 
                      alt="QR Code WhatsApp" 
                      className="mx-auto max-w-full h-auto"
                    />
                    <p className="mt-4 text-sm text-gray-600">
                      Escaneie este QR Code com seu WhatsApp para conectar a instância
                    </p>
                  </div>
                )}
              </div>
              
              <div className="bg-gray-50 px-4 py-3 sm:flex sm:flex-row-reverse sm:px-6">
                <Button onClick={() => setQrCodeInstance(null)}>
                  Fechar
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modal de Teste de Mensagem */}
      {testInstance && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-full items-end justify-center p-4 text-center sm:items-center sm:p-0">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" onClick={() => {
              setTestInstance(null)
              setTestPhoneNumber('')
            }} />
            
            <div className="relative transform overflow-hidden rounded-lg bg-white text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-md">
              <div className="bg-white px-4 pb-4 pt-5 sm:p-6 sm:pb-4">
                <div className="flex items-center mb-4">
                  <div className="mx-auto flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full bg-blue-100 sm:mx-0 sm:h-10 sm:w-10">
                    <Send className="h-6 w-6 text-blue-600" />
                  </div>
                  <h3 className="ml-3 text-lg font-medium leading-6 text-gray-900">
                    Enviar Mensagem de Teste
                  </h3>
                </div>
                
                <div className="mt-4">
                  <p className="text-sm text-gray-600 mb-4">
                    Envie uma mensagem de teste de <strong>{testInstance.friendly_name}</strong> para validar a conexão.
                  </p>
                  
                  <div>
                    <label htmlFor="test_phone" className="block text-sm font-medium text-gray-700 mb-1">
                      Número do WhatsApp (com DDD)
                    </label>
                    <input
                      type="text"
                      id="test_phone"
                      value={testPhoneNumber}
                      onChange={(e) => setTestPhoneNumber(e.target.value)}
                      placeholder="5511999999999"
                      className="block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                    />
                    <p className="mt-1 text-xs text-gray-500">
                      Formato: Código do país + DDD + Número (ex: 5511999999999)
                    </p>
                  </div>
                </div>
              </div>
              
              <div className="bg-gray-50 px-4 py-3 sm:flex sm:flex-row-reverse sm:px-6 gap-2">
                <Button 
                  onClick={handleSendTestMessage}
                  disabled={!testPhoneNumber}
                  className="w-full sm:w-auto"
                >
                  <Send className="h-4 w-4 mr-2" />
                  Enviar Teste
                </Button>
                <Button 
                  variant="outline"
                  onClick={() => {
                    setTestInstance(null)
                    setTestPhoneNumber('')
                  }}
                  className="w-full sm:w-auto mt-2 sm:mt-0"
                >
                  Cancelar
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab: Horários de Atendimento */}
      {activeTab === 'business-hours' && (
        <div className="space-y-6">
          {/* Seletor de Departamento */}
          <Card className="p-4">
            <div className="flex items-center gap-4">
              <Label className="font-medium">Departamento:</Label>
              <select
                value={selectedBusinessHoursDept || ''}
                onChange={(e) => setSelectedBusinessHoursDept(e.target.value || null)}
                className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="">Geral (Tenant)</option>
                {businessHoursDepts.map((dept) => (
                  <option key={dept.id} value={dept.id}>
                    {dept.name}
                  </option>
                ))}
              </select>
              <div className="flex-1" />
              <div className="text-sm text-gray-500">
                {selectedBusinessHoursDept
                  ? `Configurando para: ${businessHoursDepts.find(d => d.id === selectedBusinessHoursDept)?.name || 'Departamento'}`
                  : 'Configurando para: Geral (todos os departamentos)'}
              </div>
            </div>
          </Card>

          {/* Sub-tabs */}
          <div className="border-b border-gray-200">
            <nav className="-mb-px flex space-x-8">
              <button
                onClick={() => setBusinessHoursSubTab('hours')}
                className={`py-2 px-1 border-b-2 font-medium text-sm flex items-center gap-2 ${
                  businessHoursSubTab === 'hours'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <Clock className="h-4 w-4" />
                Horários
              </button>
              <button
                onClick={() => setBusinessHoursSubTab('message')}
                className={`py-2 px-1 border-b-2 font-medium text-sm flex items-center gap-2 ${
                  businessHoursSubTab === 'message'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <MessageSquare className="h-4 w-4" />
                Mensagem Automática
              </button>
              <button
                onClick={() => setBusinessHoursSubTab('tasks')}
                className={`py-2 px-1 border-b-2 font-medium text-sm flex items-center gap-2 ${
                  businessHoursSubTab === 'tasks'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <Calendar className="h-4 w-4" />
                Tarefas Automáticas
              </button>
            </nav>
          </div>

          {/* Sub-tab Content: Horários */}
          {businessHoursSubTab === 'hours' && businessHours && (
            <Card className="p-6">
              <div className="space-y-6">
                <div>
                  <Label htmlFor="timezone">Fuso Horário</Label>
                  <select
                    id="timezone"
                    value={businessHours.timezone}
                    onChange={(e) => setBusinessHours({ ...businessHours, timezone: e.target.value })}
                    className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  >
                    {TIMEZONES.map((tz) => (
                      <option key={tz.value} value={tz.value}>
                        {tz.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="space-y-4">
                  <h3 className="text-lg font-semibold">Horários por Dia da Semana</h3>
                  {DAYS.map((day) => {
                    const enabled = businessHours[`${day.key}_enabled` as keyof BusinessHours] as boolean
                    const start = businessHours[`${day.key}_start` as keyof BusinessHours] as string
                    const end = businessHours[`${day.key}_end` as keyof BusinessHours] as string

                    return (
                      <div key={day.key} className="flex items-center gap-4 p-4 border border-gray-200 rounded-lg">
                        <div className="flex items-center gap-2 w-32">
                          <input
                            type="checkbox"
                            id={`${day.key}_enabled`}
                            checked={enabled}
                            onChange={(e) => updateDayHours(day.key, 'enabled', e.target.checked)}
                            className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                          />
                          <Label htmlFor={`${day.key}_enabled`} className="font-medium cursor-pointer">
                            {day.label}
                          </Label>
                        </div>
                        {enabled && (
                          <div className="flex items-center gap-2 flex-1">
                            <Input
                              type="time"
                              value={start}
                              onChange={(e) => updateDayHours(day.key, 'start', e.target.value)}
                              className="w-32"
                            />
                            <span className="text-gray-500">até</span>
                            <Input
                              type="time"
                              value={end}
                              onChange={(e) => updateDayHours(day.key, 'end', e.target.value)}
                              className="w-32"
                            />
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>

                <div>
                  <Label htmlFor="holidays">Feriados (um por linha, formato: YYYY-MM-DD)</Label>
                  <textarea
                    id="holidays"
                    value={holidaysInput}
                    onChange={(e) => setHolidaysInput(e.target.value)}
                    placeholder="2025-12-25&#10;2026-01-01"
                    rows={4}
                    className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono text-sm"
                  />
                  <p className="mt-1 text-sm text-gray-500">
                    Exemplo: 2025-12-25 (Natal), 2026-01-01 (Ano Novo)
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="is_active"
                    checked={businessHours.is_active}
                    onChange={(e) => setBusinessHours({ ...businessHours, is_active: e.target.checked })}
                    className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                  />
                  <Label htmlFor="is_active" className="cursor-pointer">
                    Ativo
                  </Label>
                </div>

                <div className="flex justify-end">
                  <Button onClick={handleSaveBusinessHours} disabled={isLoading} className="flex items-center gap-2">
                    <Save className="h-4 w-4" />
                    {isLoading ? 'Salvando...' : 'Salvar Horários'}
                  </Button>
                </div>
              </div>
            </Card>
          )}

          {/* Sub-tab Content: Mensagem */}
          {businessHoursSubTab === 'message' && afterHoursMessage && (
            <Card className="p-6">
              <div className="space-y-6">
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <div className="flex items-start gap-2">
                    <Info className="h-5 w-5 text-blue-600 mt-0.5" />
                    <div className="text-sm text-blue-800">
                      <p className="font-medium mb-1">Variáveis disponíveis:</p>
                      <ul className="list-disc list-inside space-y-1">
                        <li><code className="bg-blue-100 px-1 rounded">&#123;contact_name&#125;</code> - Nome do contato</li>
                        <li><code className="bg-blue-100 px-1 rounded">&#123;department_name&#125;</code> - Nome do departamento</li>
                        <li><code className="bg-blue-100 px-1 rounded">&#123;next_open_time&#125;</code> - Próximo horário de abertura</li>
                      </ul>
                    </div>
                  </div>
                </div>

                <div>
                  <Label htmlFor="message_template">Mensagem Automática</Label>
                  <textarea
                    id="message_template"
                    value={afterHoursMessage.message_template}
                    onChange={(e) => setAfterHoursMessage({ ...afterHoursMessage, message_template: e.target.value })}
                    rows={8}
                    className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    placeholder="Olá {contact_name}! Recebemos sua mensagem fora do horário..."
                  />
                </div>

                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="message_is_active"
                    checked={afterHoursMessage.is_active}
                    onChange={(e) => setAfterHoursMessage({ ...afterHoursMessage, is_active: e.target.checked })}
                    className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                  />
                  <Label htmlFor="message_is_active" className="cursor-pointer">
                    Ativo
                  </Label>
                </div>

                <div className="flex justify-end">
                  <Button onClick={handleSaveMessage} disabled={isLoading} className="flex items-center gap-2">
                    <Save className="h-4 w-4" />
                    {isLoading ? 'Salvando...' : 'Salvar Mensagem'}
                  </Button>
                </div>
              </div>
            </Card>
          )}

          {/* Sub-tab Content: Tarefas */}
          {businessHoursSubTab === 'tasks' && taskConfig && (
            <Card className="p-6">
              <div className="space-y-6">
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="create_task_enabled"
                    checked={taskConfig.create_task_enabled}
                    onChange={(e) => setTaskConfig({ ...taskConfig, create_task_enabled: e.target.checked })}
                    className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                  />
                  <Label htmlFor="create_task_enabled" className="cursor-pointer font-medium">
                    Criar Tarefa Automaticamente
                  </Label>
                </div>

                {taskConfig.create_task_enabled && (
                  <>
                    <div>
                      <Label htmlFor="task_title_template">Título da Tarefa</Label>
                      <Input
                        id="task_title_template"
                        value={taskConfig.task_title_template}
                        onChange={(e) => setTaskConfig({ ...taskConfig, task_title_template: e.target.value })}
                        placeholder="Retornar contato de {contact_name}"
                        className="mt-1"
                      />
                    </div>

                    <div>
                      <Label htmlFor="task_description_template">Descrição da Tarefa</Label>
                      <textarea
                        id="task_description_template"
                        value={taskConfig.task_description_template}
                        onChange={(e) => setTaskConfig({ ...taskConfig, task_description_template: e.target.value })}
                        rows={6}
                        className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        placeholder="Cliente entrou em contato fora do horário..."
                      />
                      <p className="mt-1 text-sm text-gray-500">
                        Variáveis: <code>&#123;contact_name&#125;</code>, <code>&#123;contact_phone&#125;</code>, <code>&#123;message_time&#125;</code>, <code>&#123;message_content&#125;</code>, <code>&#123;next_open_time&#125;</code>
                      </p>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <Label htmlFor="task_priority">Prioridade</Label>
                        <select
                          id="task_priority"
                          value={taskConfig.task_priority}
                          onChange={(e) => setTaskConfig({ ...taskConfig, task_priority: e.target.value as any })}
                          className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        >
                          <option value="low">Baixa</option>
                          <option value="medium">Média</option>
                          <option value="high">Alta</option>
                          <option value="urgent">Urgente</option>
                        </select>
                      </div>

                      <div>
                        <Label htmlFor="task_due_date_offset_hours">Vencimento (horas após mensagem)</Label>
                        <Input
                          id="task_due_date_offset_hours"
                          type="number"
                          min="1"
                          value={taskConfig.task_due_date_offset_hours}
                          onChange={(e) => setTaskConfig({ ...taskConfig, task_due_date_offset_hours: parseInt(e.target.value) || 2 })}
                          className="mt-1"
                        />
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        id="auto_assign_to_department"
                        checked={taskConfig.auto_assign_to_department}
                        onChange={(e) => setTaskConfig({ ...taskConfig, auto_assign_to_department: e.target.checked })}
                        className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                      />
                      <Label htmlFor="auto_assign_to_department" className="cursor-pointer">
                        Atribuir ao Departamento
                      </Label>
                    </div>

                    <div>
                      <Label htmlFor="auto_assign_to_agent">Atribuir a Agente Específico (opcional)</Label>
                      <select
                        id="auto_assign_to_agent"
                        value={taskConfig.auto_assign_to_agent || ''}
                        onChange={(e) => setTaskConfig({ ...taskConfig, auto_assign_to_agent: e.target.value || null })}
                        className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                      >
                        <option value="">Nenhum (usar departamento)</option>
                        {businessHoursUsers.map((user) => (
                          <option key={user.id} value={user.id}>
                            {user.first_name && user.last_name
                              ? `${user.first_name} ${user.last_name} (${user.email})`
                              : user.email}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        id="include_message_preview"
                        checked={taskConfig.include_message_preview}
                        onChange={(e) => setTaskConfig({ ...taskConfig, include_message_preview: e.target.checked })}
                        className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                      />
                      <Label htmlFor="include_message_preview" className="cursor-pointer">
                        Incluir Preview da Mensagem na Descrição
                      </Label>
                    </div>
                  </>
                )}

                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="task_is_active"
                    checked={taskConfig.is_active}
                    onChange={(e) => setTaskConfig({ ...taskConfig, is_active: e.target.checked })}
                    className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                  />
                  <Label htmlFor="task_is_active" className="cursor-pointer">
                    Ativo
                  </Label>
                </div>

                <div className="flex justify-end">
                  <Button onClick={handleSaveTaskConfig} disabled={isLoading} className="flex items-center gap-2">
                    <Save className="h-4 w-4" />
                    {isLoading ? 'Salvando...' : 'Salvar Configuração'}
                  </Button>
                </div>
              </div>
            </Card>
          )}
        </div>
      )}
    </div>
  )
}