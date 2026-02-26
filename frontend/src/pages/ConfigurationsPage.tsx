import { useState, useEffect, useRef } from 'react'
import { useNavigate, Link } from 'react-router-dom'
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
  Calendar,
  Activity,
  Lock,
  Mic,
  ChevronRight,
  ChevronLeft,
  FileText,
  Sparkles,
  RefreshCw,
  ShieldCheck
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
import { RagMemoriesManager } from '../modules/ai/components/RagMemoriesManager'
import ConfirmDialog from '../components/ui/ConfirmDialog'

const INTEGRATION_EVOLUTION = 'evolution'
const INTEGRATION_META_CLOUD = 'meta_cloud'

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
  integration_type?: string
  phone_number_id?: string
  access_token_set?: boolean
  business_account_id?: string
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

interface Department {
  id: string
  name: string
  color?: string
}

interface User {
  id: string
  email: string
  first_name?: string
  last_name?: string
}

interface BusinessHours {
  id?: string
  tenant: string
  department?: string | null
  department_name?: string
  timezone: string
  monday_enabled: boolean
  monday_start: string
  monday_end: string
  tuesday_enabled: boolean
  tuesday_start: string
  tuesday_end: string
  wednesday_enabled: boolean
  wednesday_start: string
  wednesday_end: string
  thursday_enabled: boolean
  thursday_start: string
  thursday_end: string
  friday_enabled: boolean
  friday_start: string
  friday_end: string
  saturday_enabled: boolean
  saturday_start: string
  saturday_end: string
  sunday_enabled: boolean
  sunday_start: string
  sunday_end: string
  holidays: string[]
  is_active: boolean
}

interface AfterHoursMessage {
  id?: string
  tenant: string
  department?: string | null
  department_name?: string
  message_template: string
  is_active: boolean
}

interface AfterHoursTaskConfig {
  id?: string
  tenant: string
  department?: string | null
  department_name?: string
  create_task_enabled: boolean
  task_title_template: string
  task_description_template: string
  task_priority: 'low' | 'medium' | 'high' | 'urgent'
  task_due_date_offset_hours: number
  task_type: 'task' | 'agenda'
  auto_assign_to_department: boolean
  task_department?: string | null
  task_department_name?: string
  auto_assign_to_agent?: string | null
  auto_assign_to_agent_name?: string
  include_message_preview: boolean
  is_active: boolean
}

interface AiSettings {
  ai_enabled: boolean
  audio_transcription_enabled: boolean
  transcription_auto: boolean
  transcription_min_seconds: number
  transcription_max_mb: number
  triage_enabled: boolean
  secretary_enabled?: boolean
  secretary_model?: string
  agent_model: string
  n8n_audio_webhook_url: string
  n8n_triage_webhook_url: string
  n8n_ai_webhook_url: string
  n8n_models_webhook_url: string
}

interface SecretaryProfile {
  form_data: Record<string, unknown>
  prompt: string
  signature_name: string
  use_memory: boolean
  is_active: boolean
  inbox_idle_minutes: number
}

interface GatewayAuditItem {
  id: number
  conversation_id: string | null
  message_id: string | null
  contact_id: string | null
  department_id: string | null
  agent_id: string | null
  request_id: string
  trace_id: string
  status: string
  model_name: string
  latency_ms: number | null
  rag_hits: number | null
  prompt_version: string
  input_summary: string
  output_summary: string
  handoff: boolean
  handoff_reason: string
  error_code: string
  error_message: string
  request_payload_masked: Record<string, unknown>
  response_payload_masked: Record<string, unknown>
  created_at: string
}

interface MetaWhatsAppTemplate {
  id: string
  tenant: string
  name: string
  template_id: string
  language_code: string
  body_parameters_default: string[]
  is_active: boolean
  wa_instance: string | null
  wa_instance_name: string | null
  meta_status: string | null
  meta_status_updated_at: string | null
  created_at: string
  updated_at: string
}

const DAYS = [
  { key: 'monday', label: 'Segunda-feira', short: 'Seg' },
  { key: 'tuesday', label: 'Terça-feira', short: 'Ter' },
  { key: 'wednesday', label: 'Quarta-feira', short: 'Qua' },
  { key: 'thursday', label: 'Quinta-feira', short: 'Qui' },
  { key: 'friday', label: 'Sexta-feira', short: 'Sex' },
  { key: 'saturday', label: 'Sábado', short: 'Sáb' },
  { key: 'sunday', label: 'Domingo', short: 'Dom' },
]

const TIMEZONES = [
  { value: 'America/Sao_Paulo', label: 'Brasília (GMT-3)' },
  { value: 'America/Manaus', label: 'Manaus (GMT-4)' },
  { value: 'America/Rio_Branco', label: 'Rio Branco (GMT-5)' },
  { value: 'America/New_York', label: 'Nova York (GMT-5/-4)' },
  { value: 'America/Los_Angeles', label: 'Los Angeles (GMT-8/-7)' },
]

const DEFAULT_AI_MODELS: string[] = []

export default function ConfigurationsPage() {
  const { user } = useAuthStore()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<'instances' | 'smtp' | 'plan' | 'team' | 'notifications' | 'meta' | 'business-hours' | 'welcome-menu' | 'ai'>('instances')
  const [aiSubTab, setAiSubTab] = useState<'config' | 'ia-assistente' | 'rag-memories'>('config')
  const [isLoading, setIsLoading] = useState(true)
  
  // Estados para instâncias WhatsApp
  const [instances, setInstances] = useState<WhatsAppInstance[]>([])
  const [isInstanceModalOpen, setIsInstanceModalOpen] = useState(false)
  const [editingInstance, setEditingInstance] = useState<WhatsAppInstance | null>(null)
  const [instanceFormData, setInstanceFormData] = useState({
    friendly_name: '',
    default_department: null as string | null,
    integration_type: INTEGRATION_EVOLUTION as string,
    phone_number_id: '',
    access_token: '',
    business_account_id: '',
  })
  const [departments, setDepartments] = useState<Array<{id: string, name: string, color?: string}>>([])
  const [qrCodeInstance, setQrCodeInstance] = useState<WhatsAppInstance | null>(null)
  const [showApiKeys, setShowApiKeys] = useState(false)
  const [testInstance, setTestInstance] = useState<WhatsAppInstance | null>(null)
  const [testPhoneNumber, setTestPhoneNumber] = useState('')
  const [checkingStatusId, setCheckingStatusId] = useState<string | null>(null)
  const [isValidatingMetaId, setIsValidatingMetaId] = useState<string | null>(null)
  
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

  // Estados para Menu de Boas-Vindas
  const [welcomeMenuConfig, setWelcomeMenuConfig] = useState<any>(null)
  const [welcomeMenuSaving, setWelcomeMenuSaving] = useState(false)
  const [welcomeMenuPreview, setWelcomeMenuPreview] = useState<string>('')
  const [showWelcomeMenuPreview, setShowWelcomeMenuPreview] = useState(false)
  
  // Estados para IA / Assistentes
  const [aiSettings, setAiSettings] = useState<AiSettings | null>(null)
  const [aiSettingsLoading, setAiSettingsLoading] = useState(false)
  const [aiSettingsSaving, setAiSettingsSaving] = useState(false)
  const [aiSettingsErrors, setAiSettingsErrors] = useState<Record<string, string>>({})
  const [webhookTesting, setWebhookTesting] = useState<{ audio: boolean; triage: boolean; ai: boolean }>({
    audio: false,
    triage: false,
    ai: false
  })
  const [aiModelOptions, setAiModelOptions] = useState<string[]>(DEFAULT_AI_MODELS)
  const [aiModelsLoading, setAiModelsLoading] = useState(false)
  const [isModelsGatewayModalOpen, setIsModelsGatewayModalOpen] = useState(false)
  const [modelsGatewayTested, setModelsGatewayTested] = useState(false)
  const [modelsGatewayTestError, setModelsGatewayTestError] = useState<string | null>(null)
  const [isAudioTestModalOpen, setIsAudioTestModalOpen] = useState(false)
  const [audioTestFile, setAudioTestFile] = useState<File | null>(null)
  const [audioTestResult, setAudioTestResult] = useState<string | null>(null)
  const [audioTestError, setAudioTestError] = useState<string | null>(null)
  const [secretaryProfile, setSecretaryProfile] = useState<SecretaryProfile | null>(null)
  const [secretaryProfileLoading, setSecretaryProfileLoading] = useState(false)
  const [secretaryProfileSaving, setSecretaryProfileSaving] = useState(false)
  const [secretaryProfileErrors, setSecretaryProfileErrors] = useState<Record<string, string>>({})
  const [audioTestLoading, setAudioTestLoading] = useState(false)
  const [isAudioRecording, setIsAudioRecording] = useState(false)
  const [audioRecordingTime, setAudioRecordingTime] = useState(0)
  const [audioPreviewUrl, setAudioPreviewUrl] = useState<string | null>(null)
  const audioRecorderRef = useRef<MediaRecorder | null>(null)
  const audioStreamRef = useRef<MediaStream | null>(null)
  const audioChunksRef = useRef<Blob[]>([])
  const audioTimerRef = useRef<NodeJS.Timeout | null>(null)
  const [gatewayAuditItems, setGatewayAuditItems] = useState<GatewayAuditItem[]>([])
  const [gatewayAuditLoading, setGatewayAuditLoading] = useState(false)
  const [gatewayAuditError, setGatewayAuditError] = useState<string | null>(null)
  const [gatewayAuditRequestId, setGatewayAuditRequestId] = useState('')
  const [gatewayAuditTraceId, setGatewayAuditTraceId] = useState('')
  const [gatewayAuditStatus, setGatewayAuditStatus] = useState('all')
  const [gatewayAuditModelName, setGatewayAuditModelName] = useState('')
  const [gatewayAuditFrom, setGatewayAuditFrom] = useState('')
  const [gatewayAuditTo, setGatewayAuditTo] = useState('')
  const [gatewayAuditOffset, setGatewayAuditOffset] = useState(0)
  const [gatewayAuditCount, setGatewayAuditCount] = useState(0)
  const gatewayAuditLimit = 20

  // Estados para aba META (templates WhatsApp)
  const [metaTemplates, setMetaTemplates] = useState<MetaWhatsAppTemplate[]>([])
  const [metaTemplatesLoading, setMetaTemplatesLoading] = useState(false)
  const [isMetaTemplateModalOpen, setIsMetaTemplateModalOpen] = useState(false)
  const [editingMetaTemplate, setEditingMetaTemplate] = useState<MetaWhatsAppTemplate | null>(null)
  const [metaTemplateToDelete, setMetaTemplateToDelete] = useState<MetaWhatsAppTemplate | null>(null)
  const [metaSyncLoading, setMetaSyncLoading] = useState(false)
  const [metaTemplateFormData, setMetaTemplateFormData] = useState({
    name: '',
    template_id: '',
    language_code: 'pt_BR',
    body_parameters_default: [] as string[],
    wa_instance: null as string | null,
    is_active: true,
  })

  const loadGatewayAudit = async (options?: { offset?: number }) => {
    try {
      setGatewayAuditLoading(true)
      setGatewayAuditError(null)
      const params = new URLSearchParams()
      const resolvedOffset = options?.offset ?? gatewayAuditOffset
      params.set('limit', String(gatewayAuditLimit))
      params.set('offset', String(resolvedOffset))
      if (gatewayAuditRequestId.trim()) {
        params.set('request_id', gatewayAuditRequestId.trim())
      }
      if (gatewayAuditTraceId.trim()) {
        params.set('trace_id', gatewayAuditTraceId.trim())
      }
      if (gatewayAuditStatus !== 'all') {
        params.set('status', gatewayAuditStatus)
      }
      if (gatewayAuditModelName.trim()) {
        params.set('model_name', gatewayAuditModelName.trim())
      }
      if (gatewayAuditFrom) {
        const parsed = new Date(gatewayAuditFrom)
        if (!Number.isNaN(parsed.getTime())) {
          params.set('created_from', parsed.toISOString())
        }
      }
      if (gatewayAuditTo) {
        const parsed = new Date(gatewayAuditTo)
        if (!Number.isNaN(parsed.getTime())) {
          params.set('created_to', parsed.toISOString())
        }
      }
      const response = await api.get(`/ai/gateway/audit/?${params.toString()}`)
      setGatewayAuditItems(response.data.results || [])
      setGatewayAuditCount(response.data.count || 0)
      setGatewayAuditOffset(resolvedOffset)
    } catch (error) {
      console.error('Erro ao carregar auditoria do Gateway IA:', error)
      setGatewayAuditError('Falha ao carregar auditoria.')
    } finally {
      setGatewayAuditLoading(false)
    }
  }

  const fetchMetaTemplates = async () => {
    try {
      setMetaTemplatesLoading(true)
      const response = await api.get('/notifications/whatsapp-templates/')
      setMetaTemplates(response.data.results || response.data || [])
    } catch (error) {
      console.error('Erro ao carregar templates Meta:', error)
      showErrorToast('carregar', 'Templates', { message: 'Falha ao carregar templates' })
    } finally {
      setMetaTemplatesLoading(false)
    }
  }

  const metaInstances = instances.filter((i: WhatsAppInstance) => i.integration_type === INTEGRATION_META_CLOUD)
  const hasMetaInstanceWithWaba = metaInstances.some((i: WhatsAppInstance) => !!(i.business_account_id || '').trim())

  const openMetaTemplateModal = (template?: MetaWhatsAppTemplate | null) => {
    if (template) {
      setEditingMetaTemplate(template)
      setMetaTemplateFormData({
        name: template.name,
        template_id: template.template_id,
        language_code: template.language_code || 'pt_BR',
        body_parameters_default: Array.isArray(template.body_parameters_default) ? template.body_parameters_default : [],
        wa_instance: template.wa_instance || null,
        is_active: template.is_active,
      })
    } else {
      setEditingMetaTemplate(null)
      setMetaTemplateFormData({
        name: '',
        template_id: '',
        language_code: 'pt_BR',
        body_parameters_default: [],
        wa_instance: null,
        is_active: true,
      })
    }
    setIsMetaTemplateModalOpen(true)
  }

  const closeMetaTemplateModal = () => {
    setIsMetaTemplateModalOpen(false)
    setEditingMetaTemplate(null)
  }

  const saveMetaTemplate = async () => {
    if (!metaTemplateFormData.name?.trim()) {
      showErrorToast('salvar', 'Template', { message: 'Nome é obrigatório' })
      return
    }
    if (!metaTemplateFormData.template_id?.trim()) {
      showErrorToast('salvar', 'Template', { message: 'ID do template na Meta é obrigatório' })
      return
    }
    const toastId = showLoadingToast(editingMetaTemplate ? 'atualizar' : 'criar', 'Template')
    try {
      const payload = {
        name: metaTemplateFormData.name.trim(),
        template_id: metaTemplateFormData.template_id.trim(),
        language_code: metaTemplateFormData.language_code || 'pt_BR',
        body_parameters_default: metaTemplateFormData.body_parameters_default || [],
        wa_instance: metaTemplateFormData.wa_instance || null,
        is_active: metaTemplateFormData.is_active,
      }
      if (editingMetaTemplate) {
        await api.patch(`/notifications/whatsapp-templates/${editingMetaTemplate.id}/`, payload)
        updateToastSuccess(toastId, 'atualizar', 'Template')
      } else {
        await api.post('/notifications/whatsapp-templates/', payload)
        updateToastSuccess(toastId, 'criar', 'Template')
      }
      closeMetaTemplateModal()
      fetchMetaTemplates()
    } catch (err: unknown) {
      const data = (err as { response?: { data?: Record<string, unknown>; status?: number } })?.response?.data
      let message: string
      if (data && typeof data === 'object') {
        if (typeof (data as { detail?: string }).detail === 'string') message = (data as { detail: string }).detail
        else if (Array.isArray((data as { template_id?: string[] }).template_id)) message = (data as { template_id: string[] }).template_id[0]
        else if (Array.isArray((data as { tenant?: string[] }).tenant)) message = (data as { tenant: string[] }).tenant[0]
        else if (typeof (data as { error?: string }).error === 'string') message = (data as { error: string }).error
        else {
          const firstKey = Object.keys(data)[0]
          const firstVal = firstKey ? (data as Record<string, unknown>)[firstKey] : undefined
          message = Array.isArray(firstVal) ? String(firstVal[0]) : String(firstVal ?? 'Erro ao salvar template.')
        }
      } else {
        message = 'Erro ao salvar template. Verifique se já não existe um template com o mesmo ID e idioma.'
      }
      updateToastError(toastId, editingMetaTemplate ? 'atualizar' : 'criar', 'Template', { message })
    }
  }

  const deleteMetaTemplate = async () => {
    if (!metaTemplateToDelete) return
    const toastId = showLoadingToast('excluir', 'Template')
    try {
      await api.delete(`/notifications/whatsapp-templates/${metaTemplateToDelete.id}/`)
      updateToastSuccess(toastId, 'excluir', 'Template')
      setMetaTemplateToDelete(null)
      fetchMetaTemplates()
    } catch (error) {
      updateToastError(toastId, 'excluir', 'Template')
      setMetaTemplateToDelete(null)
    }
  }

  const syncMetaStatus = async () => {
    setMetaSyncLoading(true)
    try {
      const response = await api.post('/notifications/whatsapp-templates/sync_meta_status/')
      const data = response.data || {}
      const synced = data.synced_instances ?? 0
      const errors = data.errors || []
      if (errors.length > 0) {
        showErrorToast('sincronizar', 'Status Meta', { message: errors.join('; ') })
      } else if (synced === 0 && !hasMetaInstanceWithWaba) {
        showErrorToast('sincronizar', 'Status Meta', { message: 'Configure o ID da conta Business nas instâncias WhatsApp (tipo Meta) para sincronizar.' })
      } else {
        showSuccessToast('sincronizar', 'Status Meta')
      }
      fetchMetaTemplates()
    } catch (error) {
      showErrorToast('sincronizar', 'Status Meta', { message: 'Falha ao sincronizar' })
    } finally {
      setMetaSyncLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    fetchDepartments()
    if (activeTab === 'business-hours') {
      fetchBusinessHoursData()
    }
    if (activeTab === 'welcome-menu' && user?.is_admin) {
      // ✅ CORREÇÃO: Sempre recarregar quando entrar na aba (garantir dados atualizados)
      fetchWelcomeMenuConfig()
    }
    if (activeTab === 'ai' && user?.is_admin) {
      fetchAiSettings()
      fetchSecretaryProfile()
      setGatewayAuditOffset(0)
      loadGatewayAudit({ offset: 0 })
    }
    if (activeTab === 'meta') {
      fetchMetaTemplates()
    }
  }, [activeTab, selectedBusinessHoursDept, user?.is_admin])
  
  const fetchDepartments = async () => {
    try {
      const response = await api.get('/auth/departments/')
      const depts = Array.isArray(response.data) ? response.data : (response.data?.results || [])
      // ✅ CORREÇÃO: Incluir color dos departamentos (necessário para o menu)
      setDepartments(depts.map((d: any) => ({ 
        id: d.id, 
        name: d.name,
        color: d.color || '#3b82f6'  // Cor padrão se não tiver
      })))
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

  const fetchInstances = async (forceRefresh = false) => {
    try {
      const url = forceRefresh
        ? '/notifications/whatsapp-instances/?_refresh=true'
        : '/notifications/whatsapp-instances/'
      const response = await api.get(url)
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
    if (!instanceFormData.friendly_name?.trim()) {
      showErrorToast('salvar', 'Instância', { message: 'Nome da instância é obrigatório' })
      return
    }
    const isMeta = instanceFormData.integration_type === INTEGRATION_META_CLOUD
    if (isMeta) {
      if (!(instanceFormData.phone_number_id || '').trim()) {
        showErrorToast('salvar', 'Instância', { message: 'Phone Number ID é obrigatório para API Meta' })
        return
      }
      if (!(instanceFormData.access_token || '').trim()) {
        showErrorToast('salvar', 'Instância', { message: 'Access Token é obrigatório para API Meta' })
        return
      }
    }
    const toastId = showLoadingToast('criar', 'Instância')
    const payload: Record<string, unknown> = {
      friendly_name: instanceFormData.friendly_name.trim(),
      default_department: instanceFormData.default_department || null,
      integration_type: instanceFormData.integration_type,
    }
    if (isMeta) {
      payload.phone_number_id = (instanceFormData.phone_number_id || '').trim()
      payload.access_token = (instanceFormData.access_token || '').trim()
      if ((instanceFormData.business_account_id || '').trim()) payload.business_account_id = instanceFormData.business_account_id.trim()
    } else {
      payload.instance_name = crypto.randomUUID()
    }
    try {
      await api.post('/notifications/whatsapp-instances/', payload)
      updateToastSuccess(toastId, 'criar', 'Instância')

      // Forçar refresh da lista para evitar cache e garantir que a nova instância apareça
      await Promise.all([
        fetchInstances(true),
        limits?.refetch?.()
      ])

      handleCloseInstanceModal()
    } catch (error: any) {
      console.error('Error creating instance:', error)
      // Se o servidor retornar 500 com HTML, mostrar mensagem amigável em vez do corpo da página
      const errPayload =
        error?.response?.status === 500 &&
        typeof error?.response?.data === 'string' &&
        (error.response.data.includes('<!') || error.response.data.includes('<html'))
          ? { message: 'Erro no servidor (500). Tente novamente ou contacte o suporte.' }
          : error
      updateToastError(toastId, 'criar', 'Instância', errPayload)
    }
  }

  const handleUpdateInstance = async () => {
    if (!editingInstance) return
    if (!instanceFormData.friendly_name?.trim()) {
      showErrorToast('atualizar', 'Instância', { message: 'Nome da instância é obrigatório' })
      return
    }
    const isMeta = instanceFormData.integration_type === INTEGRATION_META_CLOUD
    const payload: Record<string, unknown> = {
      friendly_name: instanceFormData.friendly_name.trim(),
      default_department: instanceFormData.default_department || null,
      integration_type: instanceFormData.integration_type,
    }
    if (isMeta) {
      if ((instanceFormData.access_token || '').trim()) payload.access_token = instanceFormData.access_token.trim()
      if ((instanceFormData.business_account_id || '').trim()) payload.business_account_id = instanceFormData.business_account_id.trim()
    }
    const toastId = showLoadingToast('atualizar', 'Instância')
    try {
      await api.patch(`/notifications/whatsapp-instances/${editingInstance.id}/`, payload)
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
      default_department: instance.default_department || null,
      integration_type: instance.integration_type || INTEGRATION_EVOLUTION,
      phone_number_id: instance.phone_number_id || '',
      access_token: '',
      business_account_id: instance.business_account_id || '',
    })
    setIsInstanceModalOpen(true)
  }

  const handleValidateMeta = async (instance: WhatsAppInstance) => {
    if (instance.integration_type !== INTEGRATION_META_CLOUD) return
    setIsValidatingMetaId(instance.id)
    try {
      const response = await api.post(`/notifications/whatsapp-instances/${instance.id}/validate_meta/`)
      if (response.data?.success) {
        showSuccessToast('validar', 'API Meta')
      } else {
        showErrorToast('validar', 'API Meta', { message: response.data?.error || 'Falha na validação' })
      }
    } catch (error: any) {
      showErrorToast('validar', 'API Meta', error)
    } finally {
      setIsValidatingMetaId(null)
    }
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
    setCheckingStatusId(instance.id)
    const toastId = showLoadingToast('atualizar', 'Status')
    
    try {
      await api.post(`/notifications/whatsapp-instances/${instance.id}/check_status/`)
      updateToastSuccess(toastId, 'atualizar', 'Status')
      await fetchInstances()
    } catch (error: any) {
      console.error('Error checking status:', error)
      updateToastError(toastId, 'atualizar', 'Status', error)
    } finally {
      setCheckingStatusId(null)
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
    setInstanceFormData({
      friendly_name: '',
      default_department: null,
      integration_type: INTEGRATION_EVOLUTION,
      phone_number_id: '',
      access_token: '',
      business_account_id: '',
    })
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

  const formatAudioTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }

  const resetAudioRecorder = () => {
    if (audioTimerRef.current) {
      clearInterval(audioTimerRef.current)
      audioTimerRef.current = null
    }
    if (audioStreamRef.current) {
      audioStreamRef.current.getTracks().forEach((track) => track.stop())
      audioStreamRef.current = null
    }
    audioRecorderRef.current = null
    audioChunksRef.current = []
    setIsAudioRecording(false)
    setAudioRecordingTime(0)
  }

  const handleCloseAudioTestModal = () => {
    setIsAudioTestModalOpen(false)
    setAudioTestFile(null)
    setAudioTestResult(null)
    setAudioTestError(null)
    setAudioTestLoading(false)
    if (audioPreviewUrl) {
      URL.revokeObjectURL(audioPreviewUrl)
      setAudioPreviewUrl(null)
    }
    resetAudioRecorder()
  }

  const handleStartAudioRecording = async () => {
    if (isAudioRecording || audioTestLoading) return

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      })
      audioStreamRef.current = stream

      let mimeType = 'audio/ogg;codecs=opus'
      if (!MediaRecorder.isTypeSupported(mimeType)) {
        mimeType = 'audio/webm;codecs=opus'
      }

      const recorder = new MediaRecorder(stream, { mimeType })
      audioRecorderRef.current = recorder
      audioChunksRef.current = []

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data)
        }
      }

      recorder.onstop = () => {
        const blob = new Blob(audioChunksRef.current, { type: recorder.mimeType || 'audio/ogg' })
        const extension = blob.type.includes('ogg') ? 'ogg' : 'webm'
        const file = new File([blob], `transcription-test.${extension}`, { type: blob.type })
        setAudioTestFile(file)
        setAudioTestResult(null)
        setAudioTestError(null)
        if (audioPreviewUrl) {
          URL.revokeObjectURL(audioPreviewUrl)
        }
        setAudioPreviewUrl(URL.createObjectURL(blob))
      }

      recorder.start()
      setIsAudioRecording(true)
      setAudioRecordingTime(0)
      audioTimerRef.current = setInterval(() => {
        setAudioRecordingTime((prev) => prev + 1)
      }, 1000)
    } catch (error) {
      setAudioTestError('Erro ao acessar o microfone.')
    }
  }

  const handleStopAudioRecording = () => {
    if (!audioRecorderRef.current || !isAudioRecording) return
    audioRecorderRef.current.stop()
    resetAudioRecorder()
  }

  const handleCancelAudioRecording = () => {
    resetAudioRecorder()
    setAudioTestFile(null)
    setAudioTestResult(null)
    setAudioTestError(null)
    if (audioPreviewUrl) {
      URL.revokeObjectURL(audioPreviewUrl)
      setAudioPreviewUrl(null)
    }
  }

  const handleAudioWebhookTest = async () => {
    if (!aiSettings?.n8n_audio_webhook_url) {
      setAudioTestError('Informe o webhook de transcrição.')
      return
    }
    if (!audioTestFile) {
      setAudioTestError('Selecione um arquivo de áudio.')
      return
    }

    setAudioTestError(null)
    setAudioTestResult(null)
    setAudioTestLoading(true)

    try {
      const formData = new FormData()
      formData.append('file', audioTestFile)
      formData.append('action', 'transcribe')
      formData.append('filename', audioTestFile.name)

      const response = await fetch(aiSettings.n8n_audio_webhook_url, {
        method: 'POST',
        body: formData,
      })

      const text = await response.text()
      if (!response.ok) {
        throw new Error(text || 'Falha ao chamar webhook.')
      }
      setAudioTestResult(text)
    } catch (error) {
      setAudioTestError(error instanceof Error ? error.message : 'Erro ao testar webhook.')
    } finally {
      setAudioTestLoading(false)
    }
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

  // Funções para Horários de Atendimento
  const fetchBusinessHoursData = async () => {
    try {
      // Buscar departamentos e usuários
      const [deptResponse, usersResponse] = await Promise.all([
        api.get('/auth/departments/'),
        api.get('/auth/users/')
      ])
      const depts = Array.isArray(deptResponse.data) ? deptResponse.data : (deptResponse.data?.results || [])
      const users = Array.isArray(usersResponse.data) ? usersResponse.data : (usersResponse.data?.results || [])
      setBusinessHoursDepts(depts.map((d: any) => ({ id: d.id, name: d.name })))
      setBusinessHoursUsers(users.map((u: any) => ({ id: u.id, email: u.email, first_name: u.first_name, last_name: u.last_name })))
      
      // Buscar configurações
      await Promise.all([
        fetchBusinessHours(),
        fetchAfterHoursMessage(),
        fetchTaskConfig(),
      ])
    } catch (error: any) {
      console.error('❌ Error fetching business hours data:', error)
    }
  }

  const fetchBusinessHours = async () => {
    try {
      const params = selectedBusinessHoursDept ? { department: selectedBusinessHoursDept } : {}
      const response = await api.get('/chat/business-hours/current/', { params })
      
      if (response.data.has_config) {
        setBusinessHours(response.data.business_hours)
        setHolidaysInput((response.data.business_hours.holidays || []).join('\n'))
      } else {
        setBusinessHours({
          tenant: user?.tenant_id || '',
          department: selectedBusinessHoursDept || null,
          timezone: 'America/Sao_Paulo',
          monday_enabled: true,
          monday_start: '09:00',
          monday_end: '18:00',
          tuesday_enabled: true,
          tuesday_start: '09:00',
          tuesday_end: '18:00',
          wednesday_enabled: true,
          wednesday_start: '09:00',
          wednesday_end: '18:00',
          thursday_enabled: true,
          thursday_start: '09:00',
          thursday_end: '18:00',
          friday_enabled: true,
          friday_start: '09:00',
          friday_end: '18:00',
          saturday_enabled: false,
          saturday_start: '09:00',
          saturday_end: '18:00',
          sunday_enabled: false,
          sunday_start: '09:00',
          sunday_end: '18:00',
          holidays: [],
          is_active: true,
        })
        setHolidaysInput('')
      }
    } catch (error: any) {
      console.error('❌ Error fetching business hours:', error)
    }
  }

  const fetchAfterHoursMessage = async () => {
    try {
      const params = selectedBusinessHoursDept ? { department: selectedBusinessHoursDept } : {}
      const response = await api.get('/chat/after-hours-messages/current/', { params })
      
      if (response.data.has_config) {
        setAfterHoursMessage(response.data.after_hours_message)
      } else {
        setAfterHoursMessage({
          tenant: user?.tenant_id || '',
          department: selectedBusinessHoursDept || null,
          message_template: 'Olá {contact_name}! Recebemos sua mensagem fora do horário de atendimento.\n\nNosso horário de funcionamento é:\n{next_open_time}\n\nRetornaremos em breve!',
          is_active: true,
        })
      }
    } catch (error: any) {
      console.error('❌ Error fetching message:', error)
    }
  }

  const fetchTaskConfig = async () => {
    try {
      const params = selectedBusinessHoursDept ? { department: selectedBusinessHoursDept } : {}
      const response = await api.get('/chat/after-hours-task-configs/current/', { params })
      
      if (response.data.has_config) {
        setTaskConfig(response.data.task_config)
      } else {
        setTaskConfig({
          tenant: user?.tenant_id || '',
          department: selectedBusinessHoursDept || null,
          create_task_enabled: true,
          task_title_template: 'Retornar contato de {contact_name}',
          task_description_template: 'Cliente entrou em contato fora do horário de atendimento.\n\nHorário: {message_time}\nMensagem: {message_content}\n\nPróximo horário: {next_open_time}',
          task_priority: 'high',
          task_due_date_offset_hours: 2,
          task_type: 'task',
          auto_assign_to_department: true,
          task_department: null,
          include_message_preview: true,
          is_active: true,
        })
      }
    } catch (error: any) {
      console.error('❌ Error fetching task config:', error)
    }
  }

  const handleSaveBusinessHours = async () => {
    if (!businessHours) return
    const toastId = showLoadingToast('salvar', 'Horários de Atendimento')
    try {
      const holidays = holidaysInput.split('\n').map(line => line.trim()).filter(line => line && /^\d{4}-\d{2}-\d{2}$/.test(line))
      const data = { ...businessHours, department: selectedBusinessHoursDept || null, holidays }
      if (businessHours.id) {
        await api.patch(`/chat/business-hours/${businessHours.id}/`, data)
      } else {
        await api.post('/chat/business-hours/', data)
      }
      updateToastSuccess(toastId, 'salvar', 'Horários de Atendimento')
      await fetchBusinessHours()
    } catch (error: any) {
      updateToastError(toastId, 'salvar', 'Horários de Atendimento', error)
    }
  }

  const handleSaveMessage = async () => {
    if (!afterHoursMessage) return
    const toastId = showLoadingToast('salvar', 'Mensagem Automática')
    try {
      const data = { ...afterHoursMessage, department: selectedBusinessHoursDept || null }
      if (afterHoursMessage.id) {
        await api.patch(`/chat/after-hours-messages/${afterHoursMessage.id}/`, data)
      } else {
        await api.post('/chat/after-hours-messages/', data)
      }
      updateToastSuccess(toastId, 'salvar', 'Mensagem Automática')
      await fetchAfterHoursMessage()
    } catch (error: any) {
      updateToastError(toastId, 'salvar', 'Mensagem Automática', error)
    }
  }

  const handleSaveTaskConfig = async () => {
    if (!taskConfig) return
    const toastId = showLoadingToast('salvar', 'Configuração de Tarefas')
    try {
      const data = { ...taskConfig, department: selectedBusinessHoursDept || null }
      if (taskConfig.id) {
        await api.patch(`/chat/after-hours-task-configs/${taskConfig.id}/`, data)
      } else {
        await api.post('/chat/after-hours-task-configs/', data)
      }
      updateToastSuccess(toastId, 'salvar', 'Configuração de Tarefas')
      await fetchTaskConfig()
    } catch (error: any) {
      updateToastError(toastId, 'salvar', 'Configuração de Tarefas', error)
    }
  }

  // Funções para Menu de Boas-Vindas
  const fetchWelcomeMenuConfig = async () => {
    try {
      const response = await api.get('/chat/welcome-menu-config/')
      const data = response.data
      
      // ✅ CORREÇÃO: Converter departments (objetos) para department_ids (IDs)
      // O backend retorna 'departments' como array de objetos, mas o frontend usa 'department_ids'
      const configData = {
        ...data,
        department_ids: data.departments?.map((d: any) => d.id) || data.department_ids || []
      }
      
      console.log('📋 [WELCOME MENU] Configuração carregada:', {
        enabled: configData.enabled,
        department_ids: configData.department_ids,
        departments_count: data.departments?.length || 0
      })
      
      setWelcomeMenuConfig(configData)
      generateWelcomeMenuPreview(configData)
    } catch (error: any) {
      console.error('Erro ao carregar configuração do menu:', error)
      if (error.response?.status === 403) {
        showErrorToast('Apenas administradores podem acessar esta configuração')
      }
    }
  }

  const fetchAiSettings = async () => {
    try {
      setAiSettingsLoading(true)
      const response = await api.get('/ai/settings/')
      setAiSettings(response.data)
      if (response.data?.n8n_models_webhook_url) {
        fetchAiModels(response.data)
      } else {
        setAiModelOptions([])
      }
    } catch (error: any) {
      console.error('Erro ao carregar configurações de IA:', error)
      if (error.response?.status === 403) {
        showErrorToast('Apenas administradores podem acessar esta configuração')
      } else {
        showErrorToast('Erro ao carregar configurações de IA')
      }
    } finally {
      setAiSettingsLoading(false)
    }
  }

  const fetchSecretaryProfile = async () => {
    try {
      setSecretaryProfileLoading(true)
      const response = await api.get('/ai/secretary/profile/')
      const loadedProfile = {
        form_data: response.data?.form_data ?? {},
        prompt: response.data?.prompt ?? '',
        signature_name: response.data?.signature_name ?? '',
        use_memory: response.data?.use_memory ?? true,
        is_active: response.data?.is_active ?? false,
        inbox_idle_minutes: response.data?.inbox_idle_minutes ?? 0,
      }
      console.log('[SECRETARY FETCH] Dados carregados do servidor:', {
        form_data_keys: Object.keys(loadedProfile.form_data),
        form_data: loadedProfile.form_data,
        is_active: loadedProfile.is_active
      })
      setSecretaryProfile(loadedProfile)
      setSecretaryProfileErrors({})
    } catch (error: any) {
      console.error('Erro ao carregar perfil da secretária:', error)
      setSecretaryProfile(null)
      if (error.response?.status === 403) {
        showErrorToast('Apenas administradores podem acessar esta configuração')
      }
    } finally {
      setSecretaryProfileLoading(false)
    }
  }

  const handleSaveSecretaryProfile = async (profileOverride?: Partial<SecretaryProfile> | null) => {
    if (!secretaryProfile) return
    const profileToSave: SecretaryProfile =
      profileOverride != null ? { ...secretaryProfile, ...profileOverride } : secretaryProfile
    const errors: Record<string, string> = {}
    if (profileToSave.inbox_idle_minutes < 0 || profileToSave.inbox_idle_minutes > 1440) {
      errors.inbox_idle_minutes = 'Valor entre 0 e 1440.'
    }
    setSecretaryProfileErrors(errors)
    if (Object.keys(errors).length > 0) return

    const hadOverride = profileOverride != null
    const toastId = showLoadingToast('salvar', 'Perfil da Secretária')
    try {
      setSecretaryProfileSaving(true)
      const response = await api.put('/ai/secretary/profile/', profileToSave)

      if (response.data) {
        const savedProfile: SecretaryProfile = {
          form_data: response.data?.form_data ?? {},
          prompt: response.data?.prompt ?? '',
          signature_name: response.data?.signature_name ?? '',
          use_memory: response.data?.use_memory ?? true,
          is_active: response.data?.is_active ?? false,
          inbox_idle_minutes: response.data?.inbox_idle_minutes ?? 0,
        }
        setSecretaryProfile(savedProfile)
      }

      setSecretaryProfileErrors({})
      updateToastSuccess(toastId, 'salvar', 'Perfil da Secretária')
      // Persistir também o modelo da BIA: enviar o valor atual do select (não limpar se não estiver em aiModelOptions, para não sobrescrever com vazio).
      if (aiSettings) {
        try {
          const secretaryModel = (aiSettings.secretary_model ?? '').trim()
          const settingsRes = await api.put('/ai/settings/', {
            ...aiSettings,
            secretary_model: secretaryModel,
            secretary_enabled: profileToSave.is_active,
          })
          if (settingsRes?.data) setAiSettings(settingsRes.data)
        } catch (settingsErr: any) {
          console.error('Erro ao salvar modelo da BIA:', settingsErr)
          showErrorToast('salvar', 'Modelo da BIA', settingsErr)
        }
      }
    } catch (error: any) {
      if (hadOverride) {
        setSecretaryProfile(secretaryProfile)
      }
      const apiErrors = error.response?.data?.errors || {}
      if (apiErrors && typeof apiErrors === 'object') {
        setSecretaryProfileErrors(apiErrors)
      }
      updateToastError(toastId, 'salvar', 'Perfil da Secretária', error)
    } finally {
      setSecretaryProfileSaving(false)
    }
  }

  const fetchAiModels = async (currentSettings?: AiSettings, overrideUrl?: string) => {
    try {
      setAiModelsLoading(true)
      const response = await api.get('/ai/models/', {
        params: overrideUrl ? { url: overrideUrl } : undefined
      })
      const models = Array.isArray(response.data?.models) ? response.data.models : []
      if (models.length > 0) {
        setAiModelOptions(models)
        const activeSettings = currentSettings || aiSettings
        if (activeSettings && !models.includes(activeSettings.agent_model)) {
          setAiSettings({ ...activeSettings, agent_model: models[0] })
        }
      } else {
        setAiModelOptions([])
        const activeSettings = currentSettings || aiSettings
        if (activeSettings?.ai_enabled) {
          setAiSettings({ ...activeSettings, ai_enabled: false })
        }
      }
      return true
    } catch (error) {
      setAiModelOptions([])
      if (aiSettings?.ai_enabled) {
        setAiSettings({ ...aiSettings, ai_enabled: false })
      }
      return false
    } finally {
      setAiModelsLoading(false)
    }
  }

  const handleTestModelsGateway = async () => {
    if (!aiSettings?.n8n_models_webhook_url) {
      setModelsGatewayTestError('Informe o webhook de modelos para testar.')
      setModelsGatewayTested(false)
      return
    }

    setModelsGatewayTestError(null)
    const ok = await fetchAiModels(aiSettings, aiSettings.n8n_models_webhook_url)
    setModelsGatewayTested(ok)
    if (!ok) {
      setModelsGatewayTestError('Falha ao consultar modelos.')
    }
  }

  const handleSaveAiSettings = async () => {
    if (!aiSettings) return

    const errors: Record<string, string> = {}
    if (aiSettings.ai_enabled) {
      if (!aiSettings.n8n_models_webhook_url) {
        errors.n8n_models_webhook_url = 'Webhook de modelos obrigatório.'
      }
      if (!aiSettings.n8n_ai_webhook_url) {
        errors.n8n_ai_webhook_url = 'Webhook da IA obrigatório.'
      }
      if (aiModelOptions.length === 0) {
        errors.agent_model = 'Nenhum modelo disponível.'
      }
      if (aiSettings.audio_transcription_enabled && !aiSettings.n8n_audio_webhook_url) {
        errors.n8n_audio_webhook_url = 'Webhook de transcrição obrigatório.'
      }
    }

    if (aiSettings.transcription_min_seconds < 0) {
      errors.transcription_min_seconds = 'Valor inválido.'
    }
    if (aiSettings.transcription_max_mb < 0) {
      errors.transcription_max_mb = 'Valor inválido.'
    }

    setAiSettingsErrors(errors)
    if (Object.keys(errors).length > 0) {
      showErrorToast('Preencha os campos obrigatórios antes de salvar.')
      return
    }

    const toastId = showLoadingToast('salvar', 'Configurações de IA')
    try {
      setAiSettingsSaving(true)
      const response = await api.put('/ai/settings/', aiSettings)
      setAiSettings(response.data)
      setAiSettingsErrors({})
      updateToastSuccess(toastId, 'salvar', 'Configurações de IA')
    } catch (error: any) {
      console.error('Erro ao salvar configurações de IA:', error)
      const apiErrors = error.response?.data?.errors || {}
      if (apiErrors && typeof apiErrors === 'object') {
        setAiSettingsErrors(apiErrors)
      }
      updateToastError(toastId, 'salvar', 'Configurações de IA', error)
    } finally {
      setAiSettingsSaving(false)
    }
  }

  const handleTestWebhook = async (type: 'audio' | 'triage' | 'ai') => {
    if (!aiSettings) return
    const toastLabel =
      type === 'audio' ? 'de transcrição' : type === 'triage' ? 'de triagem' : 'da IA'
    const toastId = showLoadingToast('testar', `Webhook ${toastLabel}`)
    try {
      setWebhookTesting((prev) => ({ ...prev, [type]: true }))
      await api.post('/ai/webhook/test/', { type })
      updateToastSuccess(toastId, 'testar', 'Webhook')
    } catch (error: any) {
      updateToastError(toastId, 'testar', 'Webhook', error)
    } finally {
      setWebhookTesting((prev) => ({ ...prev, [type]: false }))
    }
  }

  const generateWelcomeMenuPreview = (config: any) => {
    if (!config) return
    
    const welcome = config.welcome_message || `Bem-vindo a ${config.tenant_name || 'nossa empresa'}!`
    // ✅ CORREÇÃO: Usar department_ids para buscar departamentos selecionados
    const deptList = departments.filter((d: any) => (config.department_ids || []).includes(d.id))
    const lines = [welcome, '', 'Escolha uma opção para atendimento:', '']
    
    deptList.forEach((dept: any, idx: number) => {
      lines.push(`${idx + 1} - ${dept.name}`)
    })
    
    if (config.show_close_option) {
      lines.push(`${deptList.length + 1} - ${config.close_option_text || 'Encerrar'}`)
    }
    
    setWelcomeMenuPreview(lines.join('\n'))
  }

  const handleSaveWelcomeMenu = async () => {
    if (!welcomeMenuConfig) return
    
    // Validação
    if (welcomeMenuConfig.enabled && (!welcomeMenuConfig.department_ids || welcomeMenuConfig.department_ids.length === 0)) {
      showErrorToast('Selecione pelo menos um departamento quando o menu estiver habilitado')
      return
    }
    
    const toastId = showLoadingToast('salvar', 'Configuração do Menu')
    try {
      setWelcomeMenuSaving(true)
      
      const payload = {
        enabled: welcomeMenuConfig.enabled,
        welcome_message: welcomeMenuConfig.welcome_message,
        department_ids: welcomeMenuConfig.department_ids || [],
        show_close_option: welcomeMenuConfig.show_close_option,
        close_option_text: welcomeMenuConfig.close_option_text,
        send_to_new_conversations: welcomeMenuConfig.send_to_new_conversations,
        send_to_closed_conversations: welcomeMenuConfig.send_to_closed_conversations
      }
      
      console.log('💾 [WELCOME MENU] Salvando configuração:', payload)
      
      const response = await api.post('/chat/welcome-menu-config/', payload)
      
      console.log('✅ [WELCOME MENU] Configuração salva com sucesso:', response.data)
      
      updateToastSuccess(toastId, 'salvar', 'Configuração do Menu')
      // ✅ CORREÇÃO: Recarregar configuração após salvar para garantir sincronização
      await fetchWelcomeMenuConfig()
    } catch (error: any) {
      console.error('❌ [WELCOME MENU] Erro ao salvar configuração:', error)
      const errorMsg = error.response?.data?.error || error.response?.data?.detail || 'Erro ao salvar configuração'
      updateToastError(toastId, 'salvar', 'Configuração do Menu', error)
    } finally {
      setWelcomeMenuSaving(false)
    }
  }

  const toggleWelcomeMenuDepartment = (deptId: string) => {
    if (!welcomeMenuConfig) return
    
    const currentIds = welcomeMenuConfig.department_ids || []
    const newIds = currentIds.includes(deptId)
      ? currentIds.filter((id: string) => id !== deptId)
      : [...currentIds, deptId]
    
    const updatedConfig = {
      ...welcomeMenuConfig,
      department_ids: newIds
    }
    
    setWelcomeMenuConfig(updatedConfig)
    generateWelcomeMenuPreview(updatedConfig)
  }

  const updateDayHours = (day: string, field: 'enabled' | 'start' | 'end', value: boolean | string) => {
    if (!businessHours) return
    setBusinessHours({ ...businessHours, [`${day}_${field}`]: value })
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
            onClick={() => setActiveTab('meta')}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'meta'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            <FileText className="h-4 w-4 inline mr-2" />
            META
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
          {user?.is_admin && (
            <button
              onClick={() => setActiveTab('ai')}
              className={`py-2 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'ai'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <Activity className="h-4 w-4 inline mr-2" />
              IA / Assistentes
            </button>
          )}
          {user?.is_admin && (
            <button
              onClick={() => setActiveTab('welcome-menu')}
              className={`py-2 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'welcome-menu'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <MessageSquare className="h-4 w-4 inline mr-2" />
              Menu de Boas-Vindas
            </button>
          )}
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
                          {instance.integration_type === INTEGRATION_META_CLOUD && (
                            <span className="ml-2 px-2 py-1 text-xs font-medium rounded-full bg-indigo-100 text-indigo-800">API Meta</span>
                          )}
                          <span className={`ml-3 px-2 py-1 text-xs font-medium rounded-full ${
                            instance.integration_type === INTEGRATION_META_CLOUD ? 'text-green-600 bg-green-100' : getConnectionStatusColor(instance.connection_state)
                          }`}>
                            {instance.integration_type === INTEGRATION_META_CLOUD ? 'Conectado' : getConnectionStatusText(instance.connection_state)}
                          </span>
                        </div>
                        <div className="flex items-center space-x-4 text-sm text-gray-600">
                          {instance.integration_type === INTEGRATION_META_CLOUD && instance.phone_number_id && (
                            <div className="flex items-center font-mono text-xs">{instance.phone_number_id}</div>
                          )}
                          {instance.phone_number && (
                            <div className="flex items-center">
                              <Phone className="h-4 w-4 mr-1" />
                              {instance.phone_number}
                            </div>
                          )}
                          {showApiKeys && instance.integration_type !== INTEGRATION_META_CLOUD && (
                            <div className="flex items-center">
                              <Key className="h-4 w-4 mr-1" />
                              {instance.instance_name}
                            </div>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center space-x-2 flex-wrap">
                        {instance.integration_type === INTEGRATION_META_CLOUD ? (
                          <>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleValidateMeta(instance)}
                              disabled={isValidatingMetaId === instance.id}
                              title="Validar token e Phone Number ID"
                              className="text-indigo-600 hover:text-indigo-700"
                            >
                              <ShieldCheck className={`h-4 w-4 ${isValidatingMetaId === instance.id ? 'animate-pulse' : ''}`} />
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => { setTestInstance(instance); setTestPhoneNumber('') }}
                              title="Enviar Mensagem de Teste"
                              className="text-blue-600 hover:text-blue-700"
                            >
                              <Send className="h-4 w-4" />
                            </Button>
                          </>
                        ) : (
                          <>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleCheckStatus(instance)}
                              disabled={checkingStatusId === instance.id}
                              title="Atualizar status (sincronizar com API não oficial)"
                            >
                              <RefreshCw className={`h-4 w-4 ${checkingStatusId === instance.id ? 'animate-spin' : ''}`} />
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
                              onClick={() => { setTestInstance(instance); setTestPhoneNumber('') }}
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
                          </>
                        )}
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

      {activeTab === 'meta' && (
        <div className="space-y-6">
          <Card className="p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-1">Templates WhatsApp (Meta)</h3>
            <p className="text-sm text-gray-500 mb-4">
              Usados para primeira mensagem ou envio fora da janela de 24h. Crie e aprove o template no Meta Business Manager antes de cadastrar aqui.
            </p>
            <div className="flex flex-wrap gap-2 mb-4">
              <Button
                onClick={syncMetaStatus}
                disabled={metaSyncLoading || !hasMetaInstanceWithWaba}
                variant="outline"
              >
                {metaSyncLoading ? <RefreshCw className="h-4 w-4 animate-spin mr-2" /> : null}
                Atualizar status da Meta
              </Button>
              {!hasMetaInstanceWithWaba && (
                <span className="text-sm text-amber-600">
                  Configure o ID da conta Business nas instâncias WhatsApp (tipo Meta) para sincronizar o status.
                </span>
              )}
              <Button onClick={() => openMetaTemplateModal(null)}>
                <Plus className="h-4 w-4 mr-2" />
                Novo template
              </Button>
            </div>
            {metaTemplatesLoading ? (
              <LoadingSpinner />
            ) : metaTemplates.length === 0 ? (
              <p className="text-gray-500">Nenhum template cadastrado. Clique em Novo template para adicionar.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Nome</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">ID (Meta)</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Idioma</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Status (Meta)</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Última verificação</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Instância</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Ativo</th>
                      <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Ações</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {metaTemplates.map((t) => (
                      <tr key={t.id}>
                        <td className="px-4 py-2 text-sm text-gray-900">{t.name}</td>
                        <td className="px-4 py-2 text-sm text-gray-600">{t.template_id}</td>
                        <td className="px-4 py-2 text-sm text-gray-600">{t.language_code}</td>
                        <td className="px-4 py-2 text-sm">
                          {t.meta_status === 'approved' && 'Aprovado'}
                          {t.meta_status === 'pending' && 'Pendente'}
                          {t.meta_status === 'rejected' && 'Rejeitado'}
                          {t.meta_status === 'limited' && 'Limitado'}
                          {t.meta_status === 'disabled' && 'Desativado'}
                          {t.meta_status === 'sync_error' && 'Erro ao sincronizar'}
                          {(!t.meta_status || t.meta_status === 'unknown') && 'Não verificado'}
                        </td>
                        <td className="px-4 py-2 text-sm text-gray-500">
                          {t.meta_status_updated_at
                            ? new Date(t.meta_status_updated_at).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
                            : '-'}
                        </td>
                        <td className="px-4 py-2 text-sm text-gray-500">{t.wa_instance_name || 'Qualquer'}</td>
                        <td className="px-4 py-2 text-sm">{t.is_active ? 'Sim' : 'Não'}</td>
                        <td className="px-4 py-2 text-right">
                          <Button variant="outline" size="sm" onClick={() => openMetaTemplateModal(t)} className="mr-1">
                            <Edit className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setMetaTemplateToDelete(t)}
                            className="text-red-600 hover:text-red-700"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
      )}

      {activeTab === 'ai' && user?.is_admin && (
        <div className="space-y-6">
          <div className="flex gap-2 border-b border-gray-200 pb-2">
            <button
              type="button"
              onClick={() => setAiSubTab('config')}
              className={`px-4 py-2 rounded-t-lg text-sm font-medium ${aiSubTab === 'config' ? 'bg-white border border-b-0 border-gray-200 text-gray-900' : 'text-gray-600 hover:text-gray-900'}`}
            >
              Configurações
            </button>
            <button
              type="button"
              onClick={() => setAiSubTab('ia-assistente')}
              className={`px-4 py-2 rounded-t-lg text-sm font-medium flex items-center gap-1 ${aiSubTab === 'ia-assistente' ? 'bg-white border border-b-0 border-gray-200 text-gray-900' : 'text-gray-600 hover:text-gray-900'}`}
            >
              <MessageSquare className="h-4 w-4" />
              IA/Assistente
            </button>
            <button
              type="button"
              onClick={() => setAiSubTab('rag-memories')}
              className={`px-4 py-2 rounded-t-lg text-sm font-medium flex items-center gap-1 ${aiSubTab === 'rag-memories' ? 'bg-white border border-b-0 border-gray-200 text-gray-900' : 'text-gray-600 hover:text-gray-900'}`}
            >
              <FileText className="h-4 w-4" />
              RAG e Lembranças
            </button>
          </div>

          {aiSubTab === 'rag-memories' ? (
            <RagMemoriesManager />
          ) : aiSubTab === 'ia-assistente' ? (
            <Card className="p-6">
              <div className="space-y-4">
                <p className="text-gray-600 dark:text-gray-400">
                  Configuração e homologação da BIA (secretária virtual). Configure o prompt, o modelo e teste conversas.
                </p>
                <Button onClick={() => navigate('/admin/bia')}>Abrir BIA</Button>
              </div>
            </Card>
          ) : aiSettingsLoading || !aiSettings ? (
            <div className="flex items-center justify-center h-64">
              <LoadingSpinner />
            </div>
          ) : (
            <>
              <Card className="p-6">
                <div className="space-y-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <Label className="text-base font-semibold">Ativar IA</Label>
                      <p className="text-sm text-gray-600 mt-1">
                        Controla o uso de recursos de IA para este tenant.
                      </p>
                    </div>
                      <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                          disabled={aiModelOptions.length === 0}
                        checked={aiSettings.ai_enabled}
                        onChange={(e) => setAiSettings({ ...aiSettings, ai_enabled: e.target.checked })}
                        className="sr-only peer"
                      />
                      <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                    </label>
                  </div>

                  {aiModelOptions.length === 0 && (
                    <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
                      Nenhum modelo listado. A IA fica indisponível até o endpoint de modelos responder.
                    </div>
                  )}

                  {!aiSettings.ai_enabled && (
                    <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 text-sm text-gray-700">
                      Habilite a IA para editar as configurações abaixo.
                    </div>
                  )}

                  <div className="flex items-center justify-between">
                    <div>
                      <Label className="text-base font-semibold">Transcrição automática</Label>
                      <p className="text-sm text-gray-600 mt-1">
                        Executa transcrição automaticamente ao receber áudios.
                      </p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        disabled={!aiSettings.ai_enabled}
                        checked={aiSettings.transcription_auto}
                        onChange={(e) => setAiSettings({ ...aiSettings, transcription_auto: e.target.checked })}
                        className="sr-only peer"
                      />
                      <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                    </label>
                  </div>

                  <div className="flex items-center justify-between">
                    <div>
                      <Label className="text-base font-semibold">Transcrição de áudio</Label>
                      <p className="text-sm text-gray-600 mt-1">
                        Habilita o fluxo de transcrição de áudio.
                      </p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        disabled={!aiSettings.ai_enabled}
                        checked={aiSettings.audio_transcription_enabled}
                        onChange={(e) => setAiSettings({ ...aiSettings, audio_transcription_enabled: e.target.checked })}
                        className="sr-only peer"
                      />
                      <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                    </label>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                      <Label htmlFor="transcription_min_seconds">Min. segundos para transcrição</Label>
                      <Input
                        id="transcription_min_seconds"
                        type="number"
                        value={aiSettings.transcription_min_seconds}
                        onChange={(e) => setAiSettings({ ...aiSettings, transcription_min_seconds: Number(e.target.value) })}
                        className={`mt-1 ${aiSettingsErrors.transcription_min_seconds ? 'border-red-500' : ''}`}
                        disabled={!aiSettings.ai_enabled}
                      />
                      <p className="text-xs text-gray-500 mt-1">
                        Evita transcrever áudios curtos.
                      </p>
                    </div>
                    <div>
                      <Label htmlFor="transcription_max_mb">Máx. MB por áudio</Label>
                      <Input
                        id="transcription_max_mb"
                        type="number"
                        value={aiSettings.transcription_max_mb}
                        onChange={(e) => setAiSettings({ ...aiSettings, transcription_max_mb: Number(e.target.value) })}
                        className={`mt-1 ${aiSettingsErrors.transcription_max_mb ? 'border-red-500' : ''}`}
                        disabled={!aiSettings.ai_enabled}
                      />
                      <p className="text-xs text-gray-500 mt-1">
                        Limite de tamanho por arquivo de áudio.
                      </p>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <div className="flex items-center justify-between gap-3">
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setModelsGatewayTested(false)
                            setModelsGatewayTestError(null)
                            setIsModelsGatewayModalOpen(true)
                          }}
                        >
                          Gateways e Webhooks
                        </Button>
                        <Label htmlFor="agent_model">Modelo padrão</Label>
                      </div>
                      <select
                        id="agent_model"
                        value={aiModelOptions.includes(aiSettings.agent_model) ? aiSettings.agent_model : ''}
                        onChange={(e) => setAiSettings({ ...aiSettings, agent_model: e.target.value })}
                        className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                        disabled={!aiSettings.ai_enabled || aiModelOptions.length === 0}
                      >
                        {aiModelOptions.map((option) => (
                          <option key={option} value={option}>
                            {option}
                          </option>
                        ))}
                      </select>
                      {aiSettingsErrors.agent_model && (
                        <p className="text-xs text-red-600 mt-1">{aiSettingsErrors.agent_model}</p>
                      )}
                      <p className="text-xs text-gray-500 mt-1">
                        Use um modelo instalado no Ollama.
                      </p>
                    </div>
                  </div>

                  {(aiSettings.audio_transcription_enabled && !aiSettings.n8n_audio_webhook_url) ||
                  (aiSettings.ai_enabled && !aiSettings.n8n_ai_webhook_url) ? (
                    <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
                      Preencha os webhooks obrigatórios para ativar transcrição e IA.
                    </div>
                  ) : null}
                  {aiSettingsErrors.n8n_models_webhook_url ? (
                    <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
                      {aiSettingsErrors.n8n_models_webhook_url}
                    </div>
                  ) : null}

                  <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 text-sm text-yellow-800">
                    A transcrição automática só roda quando <strong>IA</strong> estiver habilitada.
                  </div>

                  <div className="flex justify-end">
                    <Button onClick={handleSaveAiSettings} disabled={aiSettingsSaving}>
                      <Save className="h-4 w-4 mr-2" />
                      {aiSettingsSaving ? 'Salvando...' : 'Salvar Configurações'}
                    </Button>
                  </div>
                </div>
              </Card>

              {/* Secretária IA (Bia) – simplificado (Fase 0: formulário de dados da empresa em Planos > Dados da Empresa) */}
              <Card className="p-6">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h3 className="text-lg font-medium text-gray-900 mb-1">Secretária IA (Bia)</h3>
                    <p className="text-sm text-gray-600">
                      Ativar ou desativar a secretária virtual. Configure os dados da empresa em Planos.
                    </p>
                  </div>
                  {secretaryProfileLoading || secretaryProfile === null ? (
                    <LoadingSpinner />
                  ) : (
                    <div className="flex items-center gap-3">
                      {secretaryProfile.is_active && (
                        <span className="px-3 py-1 bg-green-100 text-green-700 rounded-full text-sm font-medium">
                          Ativa
                        </span>
                      )}
                      <Link to="/billing/company">
                        <Button variant="outline">
                          <Edit className="h-4 w-4 mr-2" />
                          Editar dados da empresa
                        </Button>
                      </Link>
                    </div>
                  )}
                </div>
                {secretaryProfile && !secretaryProfileLoading && (
                  <div className="mt-4 space-y-4">
                    <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                      <div>
                        <Label className="text-base font-semibold">Ativar BIA</Label>
                        <p className="text-sm text-gray-600 mt-1">
                          A secretária responderá em conversas do Inbox quando habilitada.
                        </p>
                      </div>
                      <label className="relative inline-flex items-center cursor-pointer">
                        <input
                          type="checkbox"
                          checked={secretaryProfile.is_active}
                          disabled={secretaryProfileSaving}
                          onChange={(e) => {
                            const isActive = e.target.checked
                            setSecretaryProfile((prev) => (prev ? { ...prev, is_active: isActive } : prev))
                            handleSaveSecretaryProfile({ is_active: isActive })
                          }}
                          className="sr-only peer"
                        />
                        <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                      </label>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div>
                        <Label htmlFor="secretary_model">Modelo da BIA</Label>
                        <select
                          id="secretary_model"
                          value={aiSettings?.secretary_model ?? ''}
                          onChange={(e) => setAiSettings((prev) => (prev ? { ...prev, secretary_model: e.target.value } : prev))}
                          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                          disabled={!aiSettings || aiModelOptions.length === 0}
                        >
                          <option value="">Padrão (modelo do agente)</option>
                          {aiSettings?.secretary_model && !aiModelOptions.includes(aiSettings.secretary_model) && (
                            <option value={aiSettings.secretary_model}>{aiSettings.secretary_model}</option>
                          )}
                          {aiModelOptions.map((option) => (
                            <option key={option} value={option}>
                              {option}
                            </option>
                          ))}
                        </select>
                        <p className="text-xs text-gray-500 mt-1">
                          Se não escolher, a BIA usa o mesmo modelo do agente.
                        </p>
                      </div>
                      <div>
                        <Label htmlFor="secretary_inbox_idle_minutes">Fechar Inbox sem resposta (min)</Label>
                        <Input
                          id="secretary_inbox_idle_minutes"
                          type="number"
                          min={0}
                          max={1440}
                          value={secretaryProfile.inbox_idle_minutes ?? 0}
                          onChange={(e) => setSecretaryProfile({ ...secretaryProfile, inbox_idle_minutes: Number(e.target.value) || 0 })}
                          className={`mt-1 ${secretaryProfileErrors.inbox_idle_minutes ? 'border-red-500' : ''}`}
                        />
                        {secretaryProfileErrors.inbox_idle_minutes && (
                          <p className="text-xs text-red-600 mt-1">{secretaryProfileErrors.inbox_idle_minutes}</p>
                        )}
                      </div>
                      <div className="flex items-center pt-6">
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={secretaryProfile.use_memory}
                            onChange={(e) => setSecretaryProfile({ ...secretaryProfile, use_memory: e.target.checked })}
                            className="rounded border-gray-300"
                          />
                          <span className="text-sm">Usar memória por contato</span>
                        </label>
                      </div>
                    </div>
                    <div className="flex justify-end">
                      <Button onClick={() => handleSaveSecretaryProfile()} disabled={secretaryProfileSaving}>
                        <Save className="h-4 w-4 mr-2" />
                        {secretaryProfileSaving ? 'Salvando...' : 'Salvar'}
                      </Button>
                    </div>
                  </div>
                )}
              </Card>

              <Card className="p-6">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h3 className="text-lg font-medium text-gray-900">Auditoria Gateway IA</h3>
                    <p className="text-sm text-gray-600">Histórico das chamadas (testes e produção).</p>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => loadGatewayAudit()}
                    disabled={gatewayAuditLoading}
                  >
                    {gatewayAuditLoading ? 'Atualizando...' : 'Atualizar'}
                  </Button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                  <div>
                    <Label htmlFor="gateway_audit_request_id">Request ID</Label>
                    <Input
                      id="gateway_audit_request_id"
                      value={gatewayAuditRequestId}
                      onChange={(e) => setGatewayAuditRequestId(e.target.value)}
                      placeholder="uuid"
                    />
                  </div>
                  <div>
                    <Label htmlFor="gateway_audit_trace_id">Trace ID</Label>
                    <Input
                      id="gateway_audit_trace_id"
                      value={gatewayAuditTraceId}
                      onChange={(e) => setGatewayAuditTraceId(e.target.value)}
                      placeholder="uuid"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                  <div>
                    <Label htmlFor="gateway_audit_status">Status</Label>
                    <select
                      id="gateway_audit_status"
                      value={gatewayAuditStatus}
                      onChange={(e) => setGatewayAuditStatus(e.target.value)}
                      className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                    >
                      <option value="all">Todos</option>
                      <option value="success">Success</option>
                      <option value="failed">Failed</option>
                    </select>
                  </div>
                  <div>
                    <Label htmlFor="gateway_audit_model">Modelo</Label>
                    <Input
                      id="gateway_audit_model"
                      value={gatewayAuditModelName}
                      onChange={(e) => setGatewayAuditModelName(e.target.value)}
                      placeholder="Ex: gpt-4o, llama3"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                  <div>
                    <Label htmlFor="gateway_audit_from">De (data/hora)</Label>
                    <Input
                      id="gateway_audit_from"
                      type="datetime-local"
                      value={gatewayAuditFrom}
                      onChange={(e) => setGatewayAuditFrom(e.target.value)}
                    />
                  </div>
                  <div>
                    <Label htmlFor="gateway_audit_to">Até (data/hora)</Label>
                    <Input
                      id="gateway_audit_to"
                      type="datetime-local"
                      value={gatewayAuditTo}
                      onChange={(e) => setGatewayAuditTo(e.target.value)}
                    />
                  </div>
                </div>

                <div className="flex flex-wrap gap-2 mb-4">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => loadGatewayAudit({ offset: 0 })}
                    disabled={gatewayAuditLoading}
                  >
                    Filtrar
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => {
                      setGatewayAuditRequestId('')
                      setGatewayAuditTraceId('')
                      setGatewayAuditStatus('all')
                      setGatewayAuditModelName('')
                      setGatewayAuditFrom('')
                      setGatewayAuditTo('')
                      loadGatewayAudit({ offset: 0 })
                    }}
                    disabled={gatewayAuditLoading}
                  >
                    Limpar filtros
                  </Button>
                </div>

                {gatewayAuditError && (
                  <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">
                    {gatewayAuditError}
                  </div>
                )}

                {gatewayAuditLoading ? (
                  <div className="flex items-center justify-center h-32">
                    <LoadingSpinner />
                  </div>
                ) : gatewayAuditItems.length === 0 ? (
                  <div className="text-sm text-gray-500">Nenhum registro encontrado.</div>
                ) : (
                  <div className="space-y-3">
                    {gatewayAuditItems.map((item) => (
                      <div key={item.id} className="border border-gray-200 rounded-lg p-4">
                        <div className="flex items-center justify-between gap-3">
                          <div>
                            <div className="text-sm font-medium text-gray-900">
                              Request ID: {item.request_id}
                            </div>
                            <div className="text-xs text-gray-500">Trace ID: {item.trace_id}</div>
                          </div>
                          <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                            item.status === 'success' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                          }`}>
                            {item.status}
                          </span>
                        </div>

                        <div className="mt-2 grid grid-cols-1 md:grid-cols-3 gap-2 text-xs text-gray-600">
                          <span>Modelo: {item.model_name || '-'}</span>
                          <span>Latência: {item.latency_ms ?? '-'}</span>
                          <span>RAG hits: {item.rag_hits ?? '-'}</span>
                          <span>Handoff: {String(item.handoff)}</span>
                          <span>Motivo: {item.handoff_reason || '-'}</span>
                          <span>Data: {item.created_at ? new Date(item.created_at).toLocaleString() : '-'}</span>
                        </div>

                        {item.conversation_id && (
                          <div className="mt-2">
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              onClick={() => {
                                navigate(`/chat?conversation_id=${item.conversation_id}`)
                              }}
                            >
                              Abrir conversa
                            </Button>
                          </div>
                        )}

                        {(item.input_summary || item.output_summary) && (
                          <div className="mt-2 text-xs text-gray-600 space-y-1">
                            <div><span className="font-medium">Input:</span> {item.input_summary || '-'}</div>
                            <div><span className="font-medium">Output:</span> {item.output_summary || '-'}</div>
                          </div>
                        )}

                        {item.error_message && (
                          <div className="mt-2 text-xs text-red-600">
                            {item.error_code ? `[${item.error_code}] ` : ''}{item.error_message}
                          </div>
                        )}

                        <details className="mt-2 text-xs text-gray-600">
                          <summary className="cursor-pointer text-blue-600">Ver payloads</summary>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-2">
                            <div>
                              <p className="text-xs text-gray-500 mb-1">Request (mascarado)</p>
                              <pre className="rounded-lg border border-gray-200 bg-white p-3 text-xs overflow-auto max-h-56 whitespace-pre-wrap">
                                {item.request_payload_masked ? JSON.stringify(item.request_payload_masked, null, 2) : 'Sem request.'}
                              </pre>
                            </div>
                            <div>
                              <p className="text-xs text-gray-500 mb-1">Response (mascarado)</p>
                              <pre className="rounded-lg border border-gray-200 bg-white p-3 text-xs overflow-auto max-h-56 whitespace-pre-wrap">
                                {item.response_payload_masked ? JSON.stringify(item.response_payload_masked, null, 2) : 'Sem response.'}
                              </pre>
                            </div>
                          </div>
                        </details>
                      </div>
                    ))}
                  </div>
                )}

                {gatewayAuditCount > 0 && (
                  <div className="flex flex-wrap items-center justify-between gap-2 mt-4 text-xs text-gray-600">
                    <span>
                      Mostrando {gatewayAuditOffset + 1}-
                      {Math.min(gatewayAuditOffset + gatewayAuditItems.length, gatewayAuditCount)} de {gatewayAuditCount}
                    </span>
                    <div className="flex gap-2">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => loadGatewayAudit({ offset: Math.max(0, gatewayAuditOffset - gatewayAuditLimit) })}
                        disabled={gatewayAuditLoading || gatewayAuditOffset === 0}
                      >
                        Anterior
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => loadGatewayAudit({ offset: gatewayAuditOffset + gatewayAuditLimit })}
                        disabled={gatewayAuditLoading || gatewayAuditOffset + gatewayAuditLimit >= gatewayAuditCount}
                      >
                        Próxima
                      </Button>
                    </div>
                  </div>
                )}
              </Card>
            </>
          )}
        </div>
      )}

      {isModelsGatewayModalOpen && aiSettings && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-full items-end justify-center p-4 text-center sm:items-center sm:p-0">
            <div
              className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity"
              onClick={() => setIsModelsGatewayModalOpen(false)}
            />

            <div className="relative transform overflow-hidden rounded-lg bg-white text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-lg">
              <div className="bg-white px-4 pb-4 pt-5 sm:p-6 sm:pb-4">
                <h3 className="text-lg font-medium leading-6 text-gray-900 mb-4">
                  Gateways e Webhooks
                </h3>
                <div className="space-y-5">
                  <div>
                    <Label htmlFor="n8n_models_webhook_url">Webhook de modelos</Label>
                    <Input
                      id="n8n_models_webhook_url"
                      type="text"
                      value={aiSettings.n8n_models_webhook_url}
                      onChange={(e) => {
                        setAiSettings({ ...aiSettings, n8n_models_webhook_url: e.target.value })
                        setModelsGatewayTested(false)
                        setModelsGatewayTestError(null)
                      }}
                      placeholder="https://integrador.alrea.ao/webhook/models"
                    />
                    <div className="flex items-center justify-between mt-3">
                      <Button
                        type="button"
                        variant="outline"
                        onClick={handleTestModelsGateway}
                        disabled={aiModelsLoading}
                      >
                        {aiModelsLoading ? 'Testando...' : 'Testar'}
                      </Button>
                      {modelsGatewayTested && !modelsGatewayTestError ? (
                        <span className="text-xs text-green-600">Consulta realizada.</span>
                      ) : null}
                    </div>
                    {modelsGatewayTestError ? (
                      <p className="text-xs text-red-600 mt-2">{modelsGatewayTestError}</p>
                    ) : null}
                  </div>

                  <div>
                    <Label htmlFor="n8n_audio_webhook_url">Webhook de transcrição</Label>
                    <div className="flex gap-2 mt-1">
                      <Input
                        id="n8n_audio_webhook_url"
                        type="text"
                        value={aiSettings.n8n_audio_webhook_url}
                        onChange={(e) => setAiSettings({ ...aiSettings, n8n_audio_webhook_url: e.target.value })}
                        className={aiSettingsErrors.n8n_audio_webhook_url ? 'border-red-500' : ''}
                        placeholder="https://integrador.alrea.ao/webhook/transcribe"
                      />
                      <Button
                        variant="outline"
                        onClick={() => {
                          setAudioTestFile(null)
                          setAudioTestResult(null)
                          setAudioTestError(null)
                          setIsAudioTestModalOpen(true)
                        }}
                        disabled={!aiSettings.n8n_audio_webhook_url}
                      >
                        Testar
                      </Button>
                    </div>
                    {aiSettingsErrors.n8n_audio_webhook_url && (
                      <p className="text-xs text-red-600 mt-1">{aiSettingsErrors.n8n_audio_webhook_url}</p>
                    )}
                  </div>

                  <div>
                    <Label htmlFor="n8n_ai_webhook_url">Webhook do Gateway IA</Label>
                    <div className="flex gap-2 mt-1">
                      <Input
                        id="n8n_ai_webhook_url"
                        type="text"
                        value={aiSettings.n8n_ai_webhook_url}
                        onChange={(e) => setAiSettings({ ...aiSettings, n8n_ai_webhook_url: e.target.value })}
                        className={aiSettingsErrors.n8n_ai_webhook_url ? 'border-red-500' : ''}
                        placeholder="https://integrador.alrea.ao/webhook/gateway-ia"
                      />
                      <Button
                        variant="outline"
                        onClick={() => handleTestWebhook('ai')}
                        disabled={webhookTesting.ai || !aiSettings.n8n_ai_webhook_url}
                      >
                        {webhookTesting.ai ? 'Testando...' : 'Testar'}
                      </Button>
                    </div>
                    {aiSettingsErrors.n8n_ai_webhook_url && (
                      <p className="text-xs text-red-600 mt-1">{aiSettingsErrors.n8n_ai_webhook_url}</p>
                    )}
                  </div>
                </div>
              </div>

              <div className="bg-gray-50 px-4 py-3 sm:flex sm:flex-row-reverse sm:px-6">
                <Button
                  onClick={() => {
                    setIsModelsGatewayModalOpen(false)
                    handleSaveAiSettings()
                  }}
                  disabled={!modelsGatewayTested || aiSettingsSaving || aiModelsLoading}
                  className="w-full sm:w-auto sm:ml-3"
                >
                  Salvar
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setIsModelsGatewayModalOpen(false)}
                  className="mt-3 w-full sm:mt-0 sm:w-auto"
                >
                  Cancelar
                </Button>
              </div>
            </div>
          </div>
        </div>
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
                      <label htmlFor="integration_type" className="block text-sm font-medium text-gray-700">
                        Tipo de conexão
                      </label>
                      <select
                        id="integration_type"
                        value={instanceFormData.integration_type}
                        onChange={(e) => setInstanceFormData({ ...instanceFormData, integration_type: e.target.value })}
                        className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                      >
                        <option value={INTEGRATION_EVOLUTION}>API não oficial (QR Code)</option>
                        <option value={INTEGRATION_META_CLOUD}>API oficial Meta</option>
                      </select>
                      <p className="mt-1 text-xs text-gray-500">
                        {instanceFormData.integration_type === INTEGRATION_META_CLOUD
                          ? 'Conexão via WhatsApp Cloud API. Requer Phone Number ID e Access Token.'
                          : 'Conexão via API não oficial. Após salvar, use Gerar QR Code para conectar.'}
                      </p>
                    </div>

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

                    {instanceFormData.integration_type === INTEGRATION_META_CLOUD ? (
                      <>
                        <div>
                          <label htmlFor="phone_number_id" className="block text-sm font-medium text-gray-700">
                            Phone Number ID *
                          </label>
                          <input
                            type="text"
                            id="phone_number_id"
                            value={instanceFormData.phone_number_id}
                            onChange={(e) => setInstanceFormData({ ...instanceFormData, phone_number_id: e.target.value })}
                            disabled={!!editingInstance}
                            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                            placeholder="ID do número no Meta Business"
                          />
                          <p className="mt-1 text-xs text-gray-500">ID do número no Meta (não alterável após criar)</p>
                        </div>
                        <div>
                          <label htmlFor="access_token" className="block text-sm font-medium text-gray-700">
                            Access Token *
                          </label>
                          <input
                            type="password"
                            id="access_token"
                            value={instanceFormData.access_token}
                            onChange={(e) => setInstanceFormData({ ...instanceFormData, access_token: e.target.value })}
                            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                            placeholder={editingInstance && (editingInstance as any).access_token_set ? '•••• (deixe em branco para manter)' : 'Token permanente do Meta'}
                          />
                        </div>
                        <div>
                          <label htmlFor="business_account_id" className="block text-sm font-medium text-gray-700">
                            Business Account ID (opcional)
                          </label>
                          <input
                            type="text"
                            id="business_account_id"
                            value={instanceFormData.business_account_id}
                            onChange={(e) => setInstanceFormData({ ...instanceFormData, business_account_id: e.target.value })}
                            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                            placeholder="ID da conta Business"
                          />
                        </div>
                        <div className="bg-indigo-50 p-4 rounded-lg">
                          <p className="text-sm text-indigo-700">Configure o webhook no Meta Business Suite apontando para a URL do seu servidor.</p>
                        </div>
                      </>
                    ) : (
                      <div className="bg-blue-50 p-4 rounded-lg">
                        <p className="text-sm text-blue-700">
                          ℹ️ O identificador único e o telefone serão preenchidos automaticamente após conectar o WhatsApp via QR Code.
                        </p>
                      </div>
                    )}

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

      {/* Modal de Teste de Transcrição */}
      {isAudioTestModalOpen && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-full items-end justify-center p-4 text-center sm:items-center sm:p-0">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" onClick={handleCloseAudioTestModal} />

            <div className="relative transform overflow-hidden rounded-lg bg-white text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-lg">
              <div className="bg-white px-4 pb-4 pt-5 sm:p-6 sm:pb-4">
                <div className="flex items-center mb-4">
                  <div className="mx-auto flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full bg-blue-100 sm:mx-0 sm:h-10 sm:w-10">
                    <TestTube className="h-6 w-6 text-blue-600" />
                  </div>
                  <h3 className="ml-3 text-lg font-medium leading-6 text-gray-900">
                    Teste de Transcrição
                  </h3>
                </div>

                <p className="text-sm text-gray-600 mb-4">
                  Grave um áudio e veja o retorno da transcrição.
                </p>

                <div className="space-y-3">
                  <div className={`flex items-center justify-between rounded-lg border p-3 ${
                    isAudioRecording ? 'border-red-200 bg-red-50' : 'border-gray-200 bg-gray-50'
                  }`}>
                    <button
                      type="button"
                      onClick={isAudioRecording ? handleStopAudioRecording : handleStartAudioRecording}
                      className={`flex h-12 w-12 items-center justify-center rounded-full ${
                        isAudioRecording ? 'bg-red-500 text-white animate-pulse' : 'bg-white text-gray-700 border border-gray-300'
                      }`}
                      title={isAudioRecording ? 'Parar gravação' : 'Gravar áudio'}
                    >
                      <Mic className="h-5 w-5" />
                    </button>
                    <div className="flex-1 px-3 text-sm text-gray-700">
                      {isAudioRecording ? `Gravando... ${formatAudioTime(audioRecordingTime)}` : 'Clique no microfone para gravar'}
                    </div>
                    {isAudioRecording && (
                      <Button type="button" variant="outline" size="sm" onClick={handleCancelAudioRecording}>
                        <X className="h-4 w-4" />
                      </Button>
                    )}
                  </div>

                  {audioPreviewUrl && (
                    <div className="rounded-md border border-gray-200 p-3">
                      <audio controls src={audioPreviewUrl} className="w-full" />
                    </div>
                  )}
                </div>

                {audioTestError && (
                  <div className="mt-4 text-sm text-red-600">
                    {audioTestError}
                  </div>
                )}

                {audioTestResult && (
                  <div className="mt-4 rounded-md bg-gray-50 p-3 text-xs whitespace-pre-wrap">
                    {audioTestResult}
                  </div>
                )}
              </div>

              <div className="bg-gray-50 px-4 py-3 sm:flex sm:flex-row-reverse sm:px-6 gap-2">
                <Button
                  onClick={handleAudioWebhookTest}
                  disabled={!audioTestFile || audioTestLoading || isAudioRecording}
                  className="w-full sm:w-auto"
                >
                  {audioTestLoading ? 'Enviando...' : 'Enviar para webhook'}
                </Button>
                <Button
                  variant="outline"
                  onClick={handleCloseAudioTestModal}
                  className="w-full sm:w-auto mt-2 sm:mt-0"
                >
                  Cancelar
                </Button>
              </div>
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
                <option value="">Geral</option>
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

                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                      <div className="flex items-start gap-2">
                        <Info className="h-5 w-5 text-blue-600 mt-0.5" />
                        <div className="text-sm text-blue-800">
                          <p className="font-medium mb-1">Vencimento Automático:</p>
                          <p>A tarefa vencerá automaticamente <strong>1 hora após o início</strong> do expediente:</p>
                          <ul className="mt-1 text-xs list-disc list-inside space-y-1">
                            <li><strong>Antes do expediente:</strong> Vence no mesmo dia (ex: mensagem 7h, atendimento 9h → vence 10h do mesmo dia)</li>
                            <li><strong>Depois do expediente:</strong> Vence no próximo dia de atendimento (ex: mensagem sexta 22h → vence segunda 10h se atendimento começa 9h)</li>
                          </ul>
                        </div>
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

                    {taskConfig.auto_assign_to_department && (
                      <div>
                        <Label htmlFor="task_department">Departamento onde a Tarefa será Criada</Label>
                        <select
                          id="task_department"
                          value={taskConfig.task_department || ''}
                          onChange={(e) => setTaskConfig({ ...taskConfig, task_department: e.target.value || null })}
                          className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                        >
                          <option value="">Usar departamento da conversa</option>
                          {businessHoursDepts.map((dept) => (
                            <option key={dept.id} value={dept.id}>
                              {dept.name}
                            </option>
                          ))}
                        </select>
                        <p className="mt-1 text-sm text-gray-500">
                          Se não selecionar, a tarefa será criada no departamento da conversa
                        </p>
                      </div>
                    )}

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

      {/* Tab Content - Menu de Boas-Vindas (Apenas Admin) */}
      {activeTab === 'welcome-menu' && user?.is_admin && (
        <div className="space-y-6">
          {!welcomeMenuConfig ? (
            <div className="flex items-center justify-center h-64">
              <LoadingSpinner />
            </div>
          ) : (
            <Card className="p-6">
              <div className="space-y-6">
                {/* Habilitar/Desabilitar Menu */}
                <div className="flex items-center justify-between">
                  <div>
                    <Label className="text-base font-semibold">Habilitar Menu Estático</Label>
                    <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                      Quando habilitado, o menu será enviado automaticamente para conversas novas ou fechadas
                    </p>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={welcomeMenuConfig.enabled || false}
                      onChange={(e) => {
                        const updated = { ...welcomeMenuConfig, enabled: e.target.checked }
                        setWelcomeMenuConfig(updated)
                        generateWelcomeMenuPreview(updated)
                      }}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                  </label>
                </div>

                {/* Mensagem de Boas-Vindas */}
                <div>
                  <Label htmlFor="welcome_message">Mensagem de Boas-Vindas</Label>
                  <Input
                    id="welcome_message"
                    value={welcomeMenuConfig.welcome_message || ''}
                    onChange={(e) => {
                      const updated = { ...welcomeMenuConfig, welcome_message: e.target.value }
                      setWelcomeMenuConfig(updated)
                      generateWelcomeMenuPreview(updated)
                    }}
                    placeholder={`Bem-vindo a ${user?.tenant_name || 'nossa empresa'}!`}
                    maxLength={500}
                    className="mt-1"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Mensagem exibida antes do menu.
                  </p>
                </div>

                {/* Departamentos */}
                <div>
                  <Label>Departamentos no Menu</Label>
                  <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
                    Selecione os departamentos que aparecerão no menu (em ordem)
                  </p>
                  {departments.length === 0 ? (
                    <div className="p-4 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg border border-yellow-200 dark:border-yellow-800">
                      <div className="flex items-center gap-2 text-yellow-800 dark:text-yellow-200">
                        <AlertCircle className="w-5 h-5" />
                        <p className="text-sm">Nenhum departamento disponível. Crie departamentos primeiro.</p>
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {departments.map((dept: any) => {
                        const isSelected = welcomeMenuConfig.department_ids?.includes(dept.id) || false
                        return (
                          <label
                            key={dept.id}
                            className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                              isSelected
                                ? 'bg-blue-50 dark:bg-blue-900/20 border-blue-300 dark:border-blue-700'
                                : 'bg-gray-50 dark:bg-gray-800 border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-700'
                            }`}
                          >
                            <input
                              type="checkbox"
                              checked={isSelected}
                              onChange={() => toggleWelcomeMenuDepartment(dept.id)}
                              className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                            />
                            <span className="flex-1 font-medium">{dept.name}</span>
                            {isSelected && (
                              <span className="text-xs text-blue-600 dark:text-blue-400">
                                #{welcomeMenuConfig.department_ids?.indexOf(dept.id)! + 1}
                              </span>
                            )}
                          </label>
                        )
                      })}
                    </div>
                  )}
                </div>

                {/* Opção Encerrar */}
                <div className="flex items-center justify-between">
                  <div>
                    <Label>Mostrar Opção Encerrar</Label>
                    <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                      Adiciona uma opção no menu para o cliente encerrar a conversa
                    </p>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={welcomeMenuConfig.show_close_option || false}
                      onChange={(e) => {
                        const updated = { ...welcomeMenuConfig, show_close_option: e.target.checked }
                        setWelcomeMenuConfig(updated)
                        generateWelcomeMenuPreview(updated)
                      }}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                  </label>
                </div>

                {welcomeMenuConfig.show_close_option && (
                  <div>
                    <Label htmlFor="close_option_text">Texto da Opção Encerrar</Label>
                    <Input
                      id="close_option_text"
                      value={welcomeMenuConfig.close_option_text || 'Encerrar'}
                      onChange={(e) => {
                        const updated = { ...welcomeMenuConfig, close_option_text: e.target.value }
                        setWelcomeMenuConfig(updated)
                        generateWelcomeMenuPreview(updated)
                      }}
                      placeholder="Encerrar"
                      maxLength={50}
                      className="mt-1"
                    />
                  </div>
                )}

                {/* Quando Enviar */}
                <div className="space-y-4">
                  <Label>Quando Enviar o Menu</Label>
                  
                  <label className="flex items-center gap-3 p-3 rounded-lg border border-gray-200 dark:border-gray-700 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800">
                    <input
                      type="checkbox"
                      checked={welcomeMenuConfig.send_to_new_conversations !== false}
                      onChange={(e) => setWelcomeMenuConfig({ ...welcomeMenuConfig, send_to_new_conversations: e.target.checked })}
                      className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                    />
                    <div>
                      <p className="font-medium">Conversas Novas</p>
                      <p className="text-sm text-gray-600 dark:text-gray-400">
                        Enviar menu quando uma nova conversa é criada (status=pending)
                      </p>
                    </div>
                  </label>

                  <label className="flex items-center gap-3 p-3 rounded-lg border border-gray-200 dark:border-gray-700 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800">
                    <input
                      type="checkbox"
                      checked={welcomeMenuConfig.send_to_closed_conversations !== false}
                      onChange={(e) => setWelcomeMenuConfig({ ...welcomeMenuConfig, send_to_closed_conversations: e.target.checked })}
                      className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                    />
                    <div>
                      <p className="font-medium">Conversas Fechadas</p>
                      <p className="text-sm text-gray-600 dark:text-gray-400">
                        Enviar menu quando uma conversa fechada recebe uma nova mensagem
                      </p>
                    </div>
                  </label>
                </div>

                {/* IA (Bloqueado) */}
                <div className="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
                  <div className="flex items-start gap-3">
                    <Lock className="w-5 h-5 text-gray-400 mt-0.5" />
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <Label className="text-base font-semibold">IA para Atendimento</Label>
                        <span className="px-2 py-0.5 text-xs bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-200 rounded">
                          Addon Futuro
                        </span>
                      </div>
                      <p className="text-sm text-gray-600 dark:text-gray-400">
                        Esta funcionalidade será disponibilizada como addon cobrado separadamente.
                        Use o menu estático acima para roteamento básico.
                      </p>
                    </div>
                  </div>
                </div>

                {/* Preview */}
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <Label>Preview do Menu</Label>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setShowWelcomeMenuPreview(!showWelcomeMenuPreview)}
                    >
                      {showWelcomeMenuPreview ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      {showWelcomeMenuPreview ? 'Ocultar' : 'Mostrar'}
                    </Button>
                  </div>
                  {showWelcomeMenuPreview && (
                    <div className="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
                      <pre className="whitespace-pre-wrap text-sm font-mono text-gray-700 dark:text-gray-300">
                        {welcomeMenuPreview}
                      </pre>
                    </div>
                  )}
                </div>

                {/* Botão Salvar */}
                <div className="flex justify-end">
                  <Button
                    onClick={handleSaveWelcomeMenu}
                    disabled={welcomeMenuSaving || (welcomeMenuConfig.enabled && (!welcomeMenuConfig.department_ids || welcomeMenuConfig.department_ids.length === 0))}
                    className="flex items-center gap-2"
                  >
                    {welcomeMenuSaving ? (
                      <>
                        <LoadingSpinner size="sm" />
                        Salvando...
                      </>
                    ) : (
                      <>
                        <Save className="w-4 h-4" />
                        Salvar Configuração
                      </>
                    )}
                  </Button>
                </div>
              </div>
            </Card>
          )}
        </div>
      )}

      {/* Modal Template META (criar/editar) */}
      {isMetaTemplateModalOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-2">
                {editingMetaTemplate ? 'Editar Template WhatsApp (Meta)' : 'Novo Template WhatsApp (Meta)'}
              </h3>
              <p className="text-sm text-gray-500 mb-4">
                Crie e submeta o template no Meta Business Manager para aprovação antes de cadastrar aqui. Só templates aprovados podem ser usados para primeira mensagem ou fora da janela de 24h.
              </p>
              <div className="space-y-4">
                <div>
                  <Label htmlFor="meta_template_name">Nome (exibição)</Label>
                  <Input
                    id="meta_template_name"
                    value={metaTemplateFormData.name}
                    onChange={(e) => setMetaTemplateFormData({ ...metaTemplateFormData, name: e.target.value })}
                    placeholder="Ex: Saudação inicial"
                  />
                </div>
                <div>
                  <Label htmlFor="meta_template_id">ID do template na Meta</Label>
                  <Input
                    id="meta_template_id"
                    value={metaTemplateFormData.template_id}
                    onChange={(e) => setMetaTemplateFormData({ ...metaTemplateFormData, template_id: e.target.value })}
                    placeholder="Ex: hello_world"
                  />
                  <p className="text-xs text-gray-500 mt-1">Igual ao nome do template no Meta Business (ex.: hello_world)</p>
                </div>
                <div>
                  <Label htmlFor="meta_template_lang">Código do idioma</Label>
                  <Input
                    id="meta_template_lang"
                    value={metaTemplateFormData.language_code}
                    onChange={(e) => setMetaTemplateFormData({ ...metaTemplateFormData, language_code: e.target.value })}
                    placeholder="pt_BR"
                  />
                </div>
                <div>
                  <Label htmlFor="meta_template_params">Parâmetros padrão do body (JSON array, opcional)</Label>
                  <Input
                    id="meta_template_params"
                    value={JSON.stringify(metaTemplateFormData.body_parameters_default || [])}
                    onChange={(e) => {
                      const raw = e.target.value || '[]'
                      try {
                        const parsed = JSON.parse(raw)
                        setMetaTemplateFormData({ ...metaTemplateFormData, body_parameters_default: Array.isArray(parsed) ? parsed : [] })
                      } catch {
                        // mantém valor anterior se JSON inválido
                      }
                    }}
                    placeholder='["Olá", "João"]'
                  />
                </div>
                <div>
                  <Label htmlFor="meta_template_instance">Instância WhatsApp (opcional)</Label>
                  <select
                    id="meta_template_instance"
                    className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                    value={metaTemplateFormData.wa_instance || ''}
                    onChange={(e) => setMetaTemplateFormData({ ...metaTemplateFormData, wa_instance: e.target.value || null })}
                  >
                    <option value="">Qualquer instância Meta</option>
                    {metaInstances.map((inst: WhatsAppInstance) => (
                      <option key={inst.id} value={inst.id}>{inst.friendly_name}</option>
                    ))}
                  </select>
                </div>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={metaTemplateFormData.is_active}
                    onChange={(e) => setMetaTemplateFormData({ ...metaTemplateFormData, is_active: e.target.checked })}
                    className="w-4 h-4 rounded border-gray-300"
                  />
                  <span className="text-sm">Ativo</span>
                </label>
              </div>
              <div className="flex justify-end gap-2 mt-6">
                <Button variant="outline" onClick={closeMetaTemplateModal}>Cancelar</Button>
                <Button onClick={saveMetaTemplate}>
                  <Save className="h-4 w-4 mr-2" />
                  {editingMetaTemplate ? 'Salvar' : 'Criar'}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      <ConfirmDialog
        show={!!metaTemplateToDelete}
        title="Excluir template"
        message={metaTemplateToDelete ? `Excluir o template "${metaTemplateToDelete.name}"? Esta ação não pode ser desfeita.` : ''}
        confirmText="Excluir"
        variant="danger"
        onConfirm={deleteMetaTemplate}
        onCancel={() => setMetaTemplateToDelete(null)}
      />

      {/* Modal Secretária IA - Wizard removido (Fase 0 - dados da empresa em Planos > Dados da Empresa) */}
    </div>
  )
}
