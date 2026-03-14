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
  List,
  Lock,
  Mic,
  ChevronRight,
  ChevronLeft,
  FileText,
  Sparkles,
  RefreshCw,
  ShieldCheck,
  AlertTriangle,
  Activity
} from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Input } from '../components/ui/Input'
import { Label } from '../components/ui/Label'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import { api } from '../lib/api'
import { showSuccessToast, showErrorToast, showLoadingToast, updateToastSuccess, updateToastError } from '../lib/toastHelper'
import { ApiErrorHandler } from '../lib/apiErrorHandler'
import { useAuthStore } from '../stores/authStore'
import { useTenantLimits } from '../hooks/useTenantLimits'
import { DepartmentsManager } from '../components/team/DepartmentsManager'
import { UsersManager } from '../components/team/UsersManager'
import { NotificationSettings } from '../modules/notifications/components/NotificationSettings'
import { RagMemoriesManager } from '../modules/ai/components/RagMemoriesManager'
import BiaAdminPage from './BiaAdminPage'
import ConfirmDialog from '../components/ui/ConfirmDialog'
import { InstanceHealthModal } from '../components/instances/InstanceHealthModal'

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
  health_score?: number | null
  msgs_sent_today?: number | null
  msgs_delivered_today?: number | null
  msgs_read_today?: number | null
  msgs_failed_today?: number | null
  consecutive_errors?: number | null
  last_success_at?: string | null
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
  username?: string
  from_email: string
  from_name: string
  use_tls?: boolean
  use_ssl?: boolean
  verify_ssl?: boolean
  is_active: boolean
  is_default: boolean
  last_test_status: string
  last_test: string | null
  last_test_error?: string
  last_test_status_display?: string
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
  response_delay_seconds?: number
  advanced_options?: Record<string, number> | null
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
  const isTenantAdmin = Boolean(user?.is_admin || user?.role === 'admin' || user?.is_superuser)
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<'instances' | 'smtp' | 'plan' | 'team' | 'notifications' | 'business-hours' | 'welcome-menu' | 'flow' | 'ai'>('instances')
  const [aiSubTab, setAiSubTab] = useState<'config' | 'ia-assistente' | 'rag-memories' | 'auditoria-ia'>('config')
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
  const [isSendingTest, setIsSendingTest] = useState(false)
  const [testPhoneError, setTestPhoneError] = useState('')
  const [checkingStatusId, setCheckingStatusId] = useState<string | null>(null)
  const [isValidatingMetaId, setIsValidatingMetaId] = useState<string | null>(null)
  const [instanceFormError, setInstanceFormError] = useState<string | null>(null)
  const [healthModalInstance, setHealthModalInstance] = useState<WhatsAppInstance | null>(null)
  
  // Estados para SMTP
  const [smtpConfigs, setSmtpConfigs] = useState<SMTPConfig[]>([])
  const [isSmtpModalOpen, setIsSmtpModalOpen] = useState(false)
  const [editingSmtp, setEditingSmtp] = useState<SMTPConfig | null>(null)
  const [smtpFormData, setSmtpFormData] = useState({
    name: '',
    host: '',
    port: 587,
    username: '',
    password: '',
    use_tls: true,
    use_ssl: false,
    verify_ssl: true,
    from_email: '',
    from_name: '',
    is_active: true,
    is_default: false
  })
  const [showSmtpPassword, setShowSmtpPassword] = useState(false)
  // Modal de teste SMTP
  const [smtpTestModalOpen, setSmtpTestModalOpen] = useState(false)
  const [smtpTestConfig, setSmtpTestConfig] = useState<SMTPConfig | null>(null)
  const [smtpTestEmail, setSmtpTestEmail] = useState('')
  const [smtpTestLoading, setSmtpTestLoading] = useState(false)
  const [smtpTestResult, setSmtpTestResult] = useState<{ success: boolean; message: string } | null>(null)
  
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
  const [showMetaTemplatesListModal, setShowMetaTemplatesListModal] = useState(false)
  const [metaTemplatesModalInstanceId, setMetaTemplatesModalInstanceId] = useState<string | null>(null)
  const [metaImportingInstanceId, setMetaImportingInstanceId] = useState<string | null>(null)
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

  const fetchMetaTemplates = async (options?: { silent?: boolean }) => {
    const silent = options?.silent === true
    try {
      if (!silent) setMetaTemplatesLoading(true)
      const response = await api.get('/notifications/whatsapp-templates/')
      setMetaTemplates(response.data.results || response.data || [])
    } catch (error) {
      if (!silent) {
        console.error('Erro ao carregar templates Meta:', error)
        showErrorToast('carregar', 'Templates', { message: 'Falha ao carregar templates' })
      }
    } finally {
      if (!silent) setMetaTemplatesLoading(false)
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
      syncMetaStatusInBackground()
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

  /** Sincroniza status dos templates com a Meta em background (sem toasts). Usado ao abrir aba/modal. */
  const syncMetaStatusInBackground = async () => {
    if (!hasMetaInstanceWithWaba) return
    try {
      await api.post('/notifications/whatsapp-templates/sync_meta_status/')
      await fetchMetaTemplates({ silent: true })
    } catch (e) {
      console.warn('Sync automático status Meta (templates):', e)
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

  const handleImportMetaTemplates = async (instanceId: string) => {
    setMetaImportingInstanceId(instanceId)
    try {
      const response = await api.post(`/notifications/whatsapp-instances/${instanceId}/import-templates/`)
      const data = response.data || {}
      if (data.success) {
        showSuccessToast('importar', 'Templates')
        fetchMetaTemplates()
      } else {
        showErrorToast('importar', 'Templates', { message: data.error || 'Falha ao importar templates' })
      }
    } catch (error: any) {
      const msg = error.response?.data?.error || error.message
      showErrorToast('importar', 'Templates', { message: msg })
    } finally {
      setMetaImportingInstanceId(null)
    }
  }

  useEffect(() => {
    fetchData()
    fetchDepartments()
    if (activeTab === 'business-hours') {
      fetchBusinessHoursData()
    }
    if (activeTab === 'welcome-menu' && isTenantAdmin) {
      // ✅ CORREÇÃO: Sempre recarregar quando entrar na aba (garantir dados atualizados)
      fetchWelcomeMenuConfig()
    }
    if (activeTab === 'ai' && isTenantAdmin) {
      fetchAiSettings()
      fetchSecretaryProfile()
      setGatewayAuditOffset(0)
      loadGatewayAudit({ offset: 0 })
    }
    if (activeTab === 'instances') {
      fetchMetaTemplates()
      syncMetaStatusInBackground()
    }
    if (activeTab === 'smtp') {
      fetchSmtpConfigs()
    }
  }, [activeTab, selectedBusinessHoursDept, isTenantAdmin])

  // Ao abrir o modal de templates WhatsApp (Meta), sincronizar status com a Meta e atualizar lista
  useEffect(() => {
    if (!showMetaTemplatesListModal || !hasMetaInstanceWithWaba) return
    syncMetaStatusInBackground()
  }, [showMetaTemplatesListModal, hasMetaInstanceWithWaba])

  // Fechar modal de templates Meta com Escape (só se o modal de criar/editar não estiver aberto)
  useEffect(() => {
    if (!showMetaTemplatesListModal) return
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !isMetaTemplateModalOpen) {
        setShowMetaTemplatesListModal(false)
        setMetaTemplatesModalInstanceId(null)
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [showMetaTemplatesListModal, isMetaTemplateModalOpen])

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
      const list = response.data?.results ?? response.data
      setSmtpConfigs(Array.isArray(list) ? list : [])
    } catch (error) {
      console.error('Error fetching SMTP configs:', error)
      setSmtpConfigs([])
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
      setInstanceFormError(null)
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
      const message = ApiErrorHandler.extractMessage(error)
      setInstanceFormError(message)
      updateToastError(toastId, 'criar', 'Instância', error)
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
      setInstanceFormError(null)
      await api.patch(`/notifications/whatsapp-instances/${editingInstance.id}/`, payload)
      updateToastSuccess(toastId, 'atualizar', 'Instância')
      
      await fetchInstances()
      handleCloseInstanceModal()
    } catch (error: any) {
      console.error('Error updating instance:', error)
      const backendError = error?.response?.status === 400 && error?.response?.data?.error
        ? (Array.isArray(error.response.data.error) ? error.response.data.error[0] : error.response.data.error)
        : null
      if (backendError) setInstanceFormError(backendError)
      updateToastError(toastId, 'atualizar', 'Instância', error)
    }
  }

  const handleEditInstance = (instance: WhatsAppInstance) => {
    setInstanceFormError(null)
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
    if (!testInstance || !testPhoneNumber.trim()) return
    const normalizedPhone = testPhoneNumber.replace(/\D/g, '')
    if (normalizedPhone.length < 10 || normalizedPhone.length > 15) {
      setTestPhoneError('Informe um número válido (ex: 5511999999999). Mínimo 10 dígitos.')
      return
    }
    setTestPhoneError('')
    const toastId = showLoadingToast('enviar', 'Mensagem de Teste')
    setIsSendingTest(true)
    try {
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
    } finally {
      setIsSendingTest(false)
    }
  }

  // Funções para SMTP
  const handleSaveSmtpConfig = async () => {
    if (!smtpFormData.username?.trim()) {
      showErrorToast('Informe o usuário/email de autenticação')
      return
    }
    if (!editingSmtp && !smtpFormData.password?.trim()) {
      showErrorToast('Informe a senha da conta para nova configuração')
      return
    }
    const payload: Record<string, unknown> = {
      name: smtpFormData.name.trim(),
      host: smtpFormData.host.trim(),
      port: Number(smtpFormData.port) || 587,
      username: smtpFormData.username.trim(),
      use_tls: smtpFormData.use_tls,
      use_ssl: smtpFormData.use_ssl,
      verify_ssl: smtpFormData.verify_ssl,
      from_email: smtpFormData.from_email.trim(),
      from_name: smtpFormData.from_name.trim(),
      is_active: smtpFormData.is_active,
      is_default: smtpFormData.is_default
    }
    if (smtpFormData.password.trim()) payload.password = smtpFormData.password

    const toastId = showLoadingToast(editingSmtp ? 'atualizar' : 'criar', 'Configuração SMTP')
    try {
      if (editingSmtp) {
        await api.patch(`/notifications/smtp-configs/${editingSmtp.id}/`, payload)
        updateToastSuccess(toastId, 'atualizar', 'Configuração SMTP')
      } else {
        await api.post('/notifications/smtp-configs/', payload)
        updateToastSuccess(toastId, 'criar', 'Configuração SMTP')
      }
      await fetchSmtpConfigs()
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
      await fetchSmtpConfigs()
    } catch (error: any) {
      console.error('Error deleting SMTP config:', error)
      updateToastError(toastId, 'excluir', 'Configuração SMTP', error)
    }
  }

  const handleOpenSmtpTestModal = (config: SMTPConfig) => {
    setSmtpTestConfig(config)
    setSmtpTestEmail('')
    setSmtpTestResult(null)
    setSmtpTestModalOpen(true)
  }

  const handleCloseSmtpTestModal = () => {
    setSmtpTestModalOpen(false)
    setSmtpTestConfig(null)
    setSmtpTestEmail('')
    setSmtpTestResult(null)
  }

  const handleSendSmtpTest = async () => {
    if (!smtpTestConfig) return
    const email = smtpTestEmail.trim()
    if (!email) {
      showErrorToast('Informe o email para receber o teste')
      return
    }
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (!re.test(email)) {
      showErrorToast('Email inválido')
      return
    }
    setSmtpTestLoading(true)
    setSmtpTestResult(null)
    try {
      const { data } = await api.post<{ success: boolean; message: string; smtp_config: SMTPConfig }>(
        `/notifications/smtp-configs/${smtpTestConfig.id}/test/`,
        { test_email: email }
      )
      setSmtpTestResult({ success: data.success, message: data.message })
      setSmtpConfigs((prev) => prev.map((c) => (c.id === data.smtp_config.id ? data.smtp_config : c)))
      if (data.success) {
        showSuccessToast(data.message)
      } else {
        showErrorToast(data.message)
      }
    } catch (error: any) {
      const res = error.response
      const message = res?.data?.message || error.message || 'Erro ao enviar teste'
      setSmtpTestResult({ success: false, message })
      showErrorToast(message)
      if (res?.status === 400 && res?.data?.smtp_config) {
        setSmtpConfigs((prev) =>
          prev.map((c) => (c.id === res.data.smtp_config.id ? res.data.smtp_config : c))
        )
      }
    } finally {
      setSmtpTestLoading(false)
    }
  }

  const handleCloseInstanceModal = () => {
    setIsInstanceModalOpen(false)
    setEditingInstance(null)
    setInstanceFormError(null)
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
      username: '',
      password: '',
      use_tls: true,
      use_ssl: false,
      verify_ssl: true,
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
      case 'open': return 'text-green-700 dark:text-green-200 bg-green-100 dark:bg-green-900/40'
      case 'connecting': return 'text-yellow-700 dark:text-yellow-200 bg-yellow-100 dark:bg-yellow-900/40'
      case 'close': return 'text-red-700 dark:text-red-200 bg-red-100 dark:bg-red-900/40'
      default: return 'text-gray-600 dark:text-gray-300 bg-gray-100 dark:bg-gray-600'
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
        response_delay_seconds: response.data?.response_delay_seconds ?? 0,
        advanced_options: (() => {
          const o = response.data?.advanced_options
          if (o != null && typeof o === 'object' && !Array.isArray(o)) return o as Record<string, number>
          return undefined
        })(),
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
      const payload = { ...profileToSave }
      if (payload.advanced_options != null && typeof payload.advanced_options === 'object') {
        const { num_ctx: _, ...rest } = payload.advanced_options as Record<string, unknown>
        payload.advanced_options = Object.keys(rest).length ? rest : null
      }
      const response = await api.put('/ai/secretary/profile/', payload)

      if (response.data) {
        const savedProfile: SecretaryProfile = {
          form_data: response.data?.form_data ?? {},
          prompt: response.data?.prompt ?? '',
          signature_name: response.data?.signature_name ?? '',
          use_memory: response.data?.use_memory ?? true,
          is_active: response.data?.is_active ?? false,
          inbox_idle_minutes: response.data?.inbox_idle_minutes ?? 0,
          response_delay_seconds: response.data?.response_delay_seconds ?? 0,
          advanced_options: (() => {
            const o = response.data?.advanced_options
            if (o != null && typeof o === 'object' && !Array.isArray(o)) return o as Record<string, number>
            return undefined
          })(),
        }
        setSecretaryProfile(savedProfile)
      }

      setSecretaryProfileErrors({})
      updateToastSuccess(toastId, 'salvar', 'Perfil da Secretária')
      // Persistir também o modelo do assistente: enviar o valor atual do select (não limpar se não estiver em aiModelOptions, para não sobrescrever com vazio).
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
          console.error('Erro ao salvar modelo do assistente:', settingsErr)
          showErrorToast('salvar', 'Modelo do assistente', settingsErr)
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
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Configurações</h1>
          <p className="text-gray-600 dark:text-gray-400">Gerencie suas instâncias, servidores e configurações</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 dark:border-gray-600 dark:bg-gray-800/50">
        <nav className="-mb-px flex flex-wrap gap-x-6 gap-y-1">
          <button
            onClick={() => setActiveTab('instances')}
            className={`py-3 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeTab === 'instances'
                ? 'border-blue-500 text-blue-600 dark:text-blue-400 dark:border-blue-400'
                : 'border-transparent text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 hover:border-gray-300 dark:hover:border-gray-500'
            }`}
          >
            <Server className="h-4 w-4 inline mr-2" />
            Instâncias WhatsApp
          </button>
          <button
            onClick={() => setActiveTab('smtp')}
            className={`py-3 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeTab === 'smtp'
                ? 'border-blue-500 text-blue-600 dark:text-blue-400 dark:border-blue-400'
                : 'border-transparent text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 hover:border-gray-300 dark:hover:border-gray-500'
            }`}
          >
            <Mail className="h-4 w-4 inline mr-2" />
            Configurações SMTP
          </button>
          <button
            onClick={() => setActiveTab('plan')}
            className={`py-3 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeTab === 'plan'
                ? 'border-blue-500 text-blue-600 dark:text-blue-400 dark:border-blue-400'
                : 'border-transparent text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 hover:border-gray-300 dark:hover:border-gray-500'
            }`}
          >
            <CreditCard className="h-4 w-4 inline mr-2" />
            Meu Plano
          </button>
          <button
            onClick={() => setActiveTab('team')}
            className={`py-3 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeTab === 'team'
                ? 'border-blue-500 text-blue-600 dark:text-blue-400 dark:border-blue-400'
                : 'border-transparent text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 hover:border-gray-300 dark:hover:border-gray-500'
            }`}
          >
            <Users className="h-4 w-4 inline mr-2" />
            Equipe
          </button>
          <button
            onClick={() => setActiveTab('notifications')}
            className={`py-3 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeTab === 'notifications'
                ? 'border-blue-500 text-blue-600 dark:text-blue-400 dark:border-blue-400'
                : 'border-transparent text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 hover:border-gray-300 dark:hover:border-gray-500'
            }`}
          >
            <Bell className="h-4 w-4 inline mr-2" />
            Notificações
          </button>
          <button
            onClick={() => setActiveTab('business-hours')}
            className={`py-3 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeTab === 'business-hours'
                ? 'border-blue-500 text-blue-600 dark:text-blue-400 dark:border-blue-400'
                : 'border-transparent text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 hover:border-gray-300 dark:hover:border-gray-500'
            }`}
          >
            <Clock className="h-4 w-4 inline mr-2" />
            Horários de Atendimento
          </button>
          {isTenantAdmin && (
            <button
              onClick={() => setActiveTab('ai')}
            className={`py-3 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeTab === 'ai'
                  ? 'border-blue-500 text-blue-600 dark:text-blue-400 dark:border-blue-400'
                  : 'border-transparent text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 hover:border-gray-300 dark:hover:border-gray-500'
              }`}
            >
              <Activity className="h-4 w-4 inline mr-2" />
              IA / Assistentes
            </button>
          )}
          {isTenantAdmin && (
            <button
              onClick={() => setActiveTab('welcome-menu')}
            className={`py-3 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeTab === 'welcome-menu'
                  ? 'border-blue-500 text-blue-600 dark:text-blue-400 dark:border-blue-400'
                  : 'border-transparent text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 hover:border-gray-300 dark:hover:border-gray-500'
              }`}
            >
              <MessageSquare className="h-4 w-4 inline mr-2" />
              Menu de Boas-Vindas
            </button>
          )}
          {isTenantAdmin && (
            <button
              onClick={() => navigate('/configurations/flows')}
              className="py-3 px-1 border-b-2 font-medium text-sm border-transparent text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 hover:border-gray-300 dark:hover:border-gray-500 transition-colors"
            >
              <List className="h-4 w-4 inline mr-2" />
              Fluxos (lista/botões)
            </button>
          )}
        </nav>
      </div>

      {/* Tab Content - Instâncias WhatsApp */}
      {activeTab === 'instances' && (
        <div className="space-y-6">
          {/* Aviso bem visível quando alguma instância Evolution está conectando ou desconectada */}
          {(() => {
            const list = Array.isArray(instances) ? instances : []
            const hasConnectingOrDisconnected = list.some(
              (i: WhatsAppInstance) =>
                i.integration_type !== INTEGRATION_META_CLOUD &&
                (i.connection_state === 'connecting' || i.connection_state === 'close' || i.connection_state === 'closed') &&
                (i.phone_number ?? '').trim() !== ''
            )
            const hasConnecting = list.some(
              (i: WhatsAppInstance) =>
                i.integration_type !== INTEGRATION_META_CLOUD &&
                i.connection_state === 'connecting' &&
                (i.phone_number ?? '').trim() !== ''
            )
            return hasConnectingOrDisconnected ? (
              <div
                className={`rounded-xl border-4 p-5 flex items-start gap-4 ${
                  hasConnecting
                    ? 'bg-amber-50 dark:bg-amber-950/40 border-amber-500 text-amber-900 dark:text-amber-100'
                    : 'bg-red-50 dark:bg-red-950/40 border-red-500 text-red-900 dark:text-red-100'
                }`}
              >
                <AlertTriangle className="h-12 w-12 flex-shrink-0 mt-0.5 opacity-90" />
                <div className="flex-1 min-w-0">
                  <h2 className="text-xl font-bold leading-tight">
                    {hasConnecting ? 'WhatsApp está conectando' : 'WhatsApp está desconectado'}
                  </h2>
                  <p className="mt-2 text-base">
                    {hasConnecting
                      ? 'Pode levar alguns segundos. Se demorar, use "Atualizar status" na instância abaixo.'
                      : 'Mensagens podem não ser enviadas. Reconecte a instância ou use "Atualizar status" na instância abaixo.'}
                  </p>
                  <Link to="/connections" className="mt-3 inline-flex items-center gap-2 text-base font-semibold underline hover:no-underline">
                    Ir para Conexões
                  </Link>
                </div>
              </div>
            ) : null
          })()}

          {/* Limites do Plano: exibir somente quando o plano tem produto Chat (único que define limite de instâncias) */}
          {limits?.plan && limits?.products?.chat?.has_access && (
            <Card className="p-6 border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 shadow-sm">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100">Limites do Plano</h3>
                <div className="flex items-center text-sm text-gray-500 dark:text-gray-400">
                  <Crown className="h-4 w-4 mr-1" />
                  {limits.plan.name}
                </div>
              </div>
              <div className="bg-blue-50 dark:bg-blue-900/25 p-4 rounded-lg border border-blue-100 dark:border-blue-800/50">
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="font-medium text-blue-900 dark:text-blue-100">Instâncias WhatsApp (ALREA Chat)</h4>
                    <p className="text-sm text-blue-700 dark:text-blue-200">
                      {limits.products.chat.unlimited
                        ? `${limits.products.chat.current ?? 0} instâncias (ilimitado)`
                        : `${limits.products.chat.current ?? 0} de ${limits.products.chat.limit ?? 0} instâncias`}
                    </p>
                  </div>
                  <div className="text-right">
                    <div className="text-2xl font-bold text-blue-900 dark:text-blue-100">
                      {limits.products.chat.unlimited
                        ? `${limits.products.chat.current ?? 0} / ∞`
                        : `${limits.products.chat.current ?? 0}/${limits.products.chat.limit ?? 0}`}
                    </div>
                    <div className="text-sm text-blue-700 dark:text-blue-200">instâncias</div>
                  </div>
                </div>
              </div>
            </Card>
          )}

          {/* Lista de Instâncias */}
          <Card className="p-6 border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 shadow-sm">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100">Suas Instâncias WhatsApp</h3>
              <div className="flex items-center flex-wrap gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowApiKeys(!showApiKeys)}
                  className="border-gray-300 dark:border-gray-500 text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700"
                >
                  <Key className="h-4 w-4 mr-2" />
                  {showApiKeys ? 'Ocultar' : 'Mostrar'} API Keys
                </Button>
                <Button
                  onClick={() => { setInstanceFormError(null); setIsInstanceModalOpen(true) }}
                  disabled={limits?.products?.chat?.has_access && limits.products.chat.can_create === false}
                >
                  <Plus className="h-4 w-4 mr-2" />
                  Nova Instância
                </Button>
              </div>
            </div>

            {instances.length === 0 ? (
              <div className="text-center py-12">
                <Server className="h-12 w-12 text-gray-400 dark:text-gray-500 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-2">Nenhuma instância cadastrada</h3>
                <p className="text-gray-500 dark:text-gray-400 mb-4">Crie sua primeira instância WhatsApp para começar</p>
                <Button onClick={() => { setInstanceFormError(null); setIsInstanceModalOpen(true) }}>
                  <Plus className="h-4 w-4 mr-2" />
                  Criar Primeira Instância
                </Button>
              </div>
            ) : (
              <div className="grid gap-4">
                {instances.map((instance) => (
                  <div key={instance.id} className="border border-gray-200 dark:border-gray-600 rounded-lg p-4 bg-gray-50/50 dark:bg-gray-700/30 hover:border-gray-300 dark:hover:border-gray-500 transition-colors">
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <div className="flex items-center mb-2 flex-wrap gap-x-2 gap-y-1">
                          <h4 className="font-medium text-gray-900 dark:text-gray-100">{instance.friendly_name}</h4>
                          {instance.integration_type === INTEGRATION_META_CLOUD && (
                            <span className="px-2 py-1 text-xs font-medium rounded-full bg-indigo-100 dark:bg-indigo-900/50 text-indigo-800 dark:text-indigo-200">API Meta</span>
                          )}
                          {instance.integration_type === INTEGRATION_META_CLOUD && (() => {
                            const score = Math.min(100, Math.max(0, Number(instance.health_score ?? 100) || 0))
                            const ledGreen = score >= 80
                            const ledYellow = score >= 50 && score < 80
                            return (
                              <span className="inline-flex items-center gap-1.5">
                                <span
                                  className={`inline-block w-2 h-2 rounded-full flex-shrink-0 ${
                                    ledGreen ? 'bg-emerald-500' : ledYellow ? 'bg-amber-500' : 'bg-red-500'
                                  }`}
                                  title={`Saúde: ${score}%`}
                                />
                                <span className="text-xs text-gray-600 dark:text-gray-400 whitespace-nowrap">
                                  Saúde em: {score}%
                                </span>
                              </span>
                            )
                          })()}
                          <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                            instance.integration_type === INTEGRATION_META_CLOUD ? 'text-green-700 dark:text-green-200 bg-green-100 dark:bg-green-900/40' : getConnectionStatusColor(instance.connection_state)
                          }`}>
                            {instance.integration_type === INTEGRATION_META_CLOUD ? 'Conectado' : getConnectionStatusText(instance.connection_state)}
                          </span>
                        </div>
                        <div className="flex items-center space-x-4 text-sm text-gray-600 dark:text-gray-300">
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
                              className="text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-300 border-indigo-200 dark:border-indigo-800 hover:bg-indigo-50 dark:hover:bg-indigo-900/30"
                            >
                              <ShieldCheck className={`h-4 w-4 ${isValidatingMetaId === instance.id ? 'animate-pulse' : ''}`} />
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => {
                                setMetaTemplatesModalInstanceId(instance.id)
                                fetchMetaTemplates()
                                setShowMetaTemplatesListModal(true)
                              }}
                              title="Templates WhatsApp (Meta)"
                              className="border-emerald-200 dark:border-emerald-800 text-emerald-600 dark:text-emerald-400 hover:bg-emerald-50 dark:hover:bg-emerald-900/30"
                            >
                              <FileText className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => { setTestInstance(instance); setTestPhoneNumber('') }}
                              title="Enviar Mensagem de Teste"
                              className="text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 border-blue-200 dark:border-blue-800 hover:bg-blue-50 dark:hover:bg-blue-900/30"
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
                              className="border-gray-300 dark:border-gray-500 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600"
                            >
                              <RefreshCw className={`h-4 w-4 ${checkingStatusId === instance.id ? 'animate-spin' : ''}`} />
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleGenerateQR(instance)}
                              title="Gerar/Atualizar QR Code"
                              className="border-gray-300 dark:border-gray-500 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600"
                            >
                              <QrCode className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => { setTestInstance(instance); setTestPhoneNumber('') }}
                              disabled={instance.connection_state !== 'open'}
                              title="Enviar Mensagem de Teste"
                              className="text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 border-blue-200 dark:border-blue-800 hover:bg-blue-50 dark:hover:bg-blue-900/30"
                            >
                              <Send className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleDisconnect(instance)}
                              disabled={instance.connection_state !== 'open'}
                              title="Desconectar Instância"
                              className="border-gray-300 dark:border-gray-500 text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600"
                            >
                              <X className="h-4 w-4" />
                            </Button>
                          </>
                        )}
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setHealthModalInstance(instance)}
                          title={instance.integration_type === INTEGRATION_META_CLOUD ? 'Ver indicadores de saúde (sincronizados com a Meta)' : 'Ver status da conexão (Evolution)'}
                          className="border-slate-300 dark:border-slate-500 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700"
                        >
                          <Activity className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleEditInstance(instance)}
                          title="Editar Instância"
                          className="text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 border-blue-200 dark:border-blue-800 hover:bg-blue-50 dark:hover:bg-blue-900/30"
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleDeleteInstance(instance.id)}
                          className="text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 border-red-200 dark:border-red-800 hover:bg-red-50 dark:hover:bg-red-900/20"
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

      {/* Modal Templates WhatsApp (Meta) - aberto ao clicar no ícone Meta da instância */}
      {showMetaTemplatesListModal && (
        <div
          className="fixed inset-0 bg-black/50 dark:bg-black/60 flex items-center justify-center z-50 p-4"
          onClick={() => { setShowMetaTemplatesListModal(false); setMetaTemplatesModalInstanceId(null) }}
          role="dialog"
          aria-modal="true"
          aria-labelledby="meta-templates-modal-title"
        >
          <div className="bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg shadow-xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
              <h3 id="meta-templates-modal-title" className="text-lg font-medium text-gray-900 dark:text-gray-100">Templates WhatsApp (Meta)</h3>
              <button
                type="button"
                onClick={() => { setShowMetaTemplatesListModal(false); setMetaTemplatesModalInstanceId(null) }}
                className="p-2 rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500 dark:text-gray-400"
                aria-label="Fechar"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <div className="p-4 overflow-y-auto flex-1">
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
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
                {metaTemplatesModalInstanceId && (
                  <Button
                    onClick={() => handleImportMetaTemplates(metaTemplatesModalInstanceId)}
                    disabled={metaImportingInstanceId === metaTemplatesModalInstanceId}
                    variant="outline"
                    title="Importar templates da Meta para esta instância"
                  >
                    {metaImportingInstanceId === metaTemplatesModalInstanceId ? (
                      <RefreshCw className="h-4 w-4 animate-spin mr-2" />
                    ) : null}
                    Importar templates
                  </Button>
                )}
                {!hasMetaInstanceWithWaba && (
                  <span className="text-sm text-amber-600 dark:text-amber-400">
                    Configure o ID da conta Business nas instâncias WhatsApp (tipo Meta) para sincronizar o status.
                  </span>
                )}
                <Button onClick={() => openMetaTemplateModal(null)}>
                  <Plus className="h-4 w-4 mr-2" />
                  Novo template
                </Button>
              </div>
              {metaTemplatesLoading ? (
                <div className="flex justify-center py-8">
                  <LoadingSpinner />
                </div>
              ) : metaTemplates.length === 0 ? (
                <p className="text-gray-500 dark:text-gray-400">Nenhum template cadastrado. Clique em Novo template para adicionar.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-600">
                    <thead className="bg-gray-50 dark:bg-gray-700">
                      <tr>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Nome</th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">ID (Meta)</th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Idioma</th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Status (Meta)</th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Última verificação</th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Instância</th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Ativo</th>
                        <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 dark:text-gray-300 uppercase">Ações</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-600">
                      {metaTemplates.map((t) => (
                        <tr key={t.id}>
                          <td className="px-4 py-2 text-sm text-gray-900 dark:text-gray-100">{t.name}</td>
                          <td className="px-4 py-2 text-sm text-gray-600 dark:text-gray-300">{t.template_id}</td>
                          <td className="px-4 py-2 text-sm text-gray-600 dark:text-gray-300">{t.language_code}</td>
                          <td className="px-4 py-2 text-sm">
                            {t.meta_status === 'approved' && 'Aprovado'}
                            {t.meta_status === 'pending' && 'Pendente'}
                            {t.meta_status === 'rejected' && 'Rejeitado'}
                            {t.meta_status === 'limited' && 'Limitado'}
                            {t.meta_status === 'disabled' && 'Desativado'}
                            {t.meta_status === 'sync_error' && 'Erro ao sincronizar'}
                            {(!t.meta_status || t.meta_status === 'unknown') && 'Não verificado'}
                          </td>
                          <td className="px-4 py-2 text-sm text-gray-500 dark:text-gray-400">
                            {t.meta_status_updated_at
                              ? new Date(t.meta_status_updated_at).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
                              : '-'}
                          </td>
                          <td className="px-4 py-2 text-sm text-gray-500 dark:text-gray-400">{t.wa_instance_name || 'Qualquer'}</td>
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
            </div>
          </div>
        </div>
      )}

      {/* Tab Content - SMTP */}
      {activeTab === 'smtp' && (
        <div className="space-y-6">
          <Card className="p-6">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100">Configurações SMTP</h3>
                <p className="text-sm text-gray-600 dark:text-gray-400">Configure servidores SMTP para envio de emails</p>
              </div>
              <Button onClick={() => {
                setEditingSmtp(null)
                setSmtpFormData({
                  name: '',
                  host: '',
                  port: 587,
                  username: '',
                  password: '',
                  use_tls: true,
                  use_ssl: false,
                  verify_ssl: true,
                  from_email: '',
                  from_name: '',
                  is_active: true,
                  is_default: false
                })
                setIsSmtpModalOpen(true)
              }}>
                <Plus className="h-4 w-4 mr-2" />
                Nova Configuração
              </Button>
            </div>

            {smtpConfigs.length === 0 ? (
              <div className="bg-gray-50 dark:bg-gray-800 p-4 rounded-lg text-center">
                <Mail className="h-12 w-12 text-gray-400 dark:text-gray-500 mx-auto mb-4" />
                <h4 className="font-medium text-gray-900 dark:text-gray-100 mb-2">Nenhuma configuração SMTP</h4>
                <p className="text-gray-600 dark:text-gray-400 mb-4">Configure um servidor SMTP para enviar emails</p>
                <Button onClick={() => {
                  setEditingSmtp(null)
                  setSmtpFormData({
                    name: '',
                    host: '',
                    port: 587,
                    username: '',
                    password: '',
                    use_tls: true,
                    use_ssl: false,
                    verify_ssl: true,
                    from_email: '',
                    from_name: '',
                    is_active: true,
                    is_default: false
                  })
                  setIsSmtpModalOpen(true)
                }}>
                  <Plus className="h-4 w-4 mr-2" />
                  Criar Configuração
                </Button>
              </div>
            ) : (
              <div className="grid gap-4">
                {smtpConfigs.map((config) => (
                  <div key={config.id} className="border border-gray-200 dark:border-gray-600 rounded-lg p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <div className="flex items-center mb-2">
                          <h4 className="font-medium text-gray-900 dark:text-gray-100">{config.name}</h4>
                          {config.is_default && (
                            <span className="ml-2 px-2 py-1 text-xs font-medium bg-blue-100 text-blue-800 rounded-full">
                              Padrão
                            </span>
                          )}
                          <span className={`ml-2 px-2 py-1 text-xs font-medium rounded-full ${
                            config.is_active ? 'bg-green-100 dark:bg-green-900/40 text-green-800 dark:text-green-200' : 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200'
                          }`}>
                            {config.is_active ? 'Ativo' : 'Inativo'}
                          </span>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm text-gray-600 dark:text-gray-300">
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
                            <span className="font-medium">Último teste:</span> {config.last_test ? new Date(config.last_test).toLocaleString('pt-BR') : 'Nunca'}
                            {config.last_test_status && (
                              <span className={`ml-2 px-2 py-0.5 text-xs font-medium rounded-full ${
                                config.last_test_status === 'success' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                              }`} title={config.last_test_error || undefined}>
                                {config.last_test_status === 'success' ? 'Sucesso' : 'Falhou'}
                              </span>
                            )}
                          </div>
                          {config.last_test_error && (
                            <div className="md:col-span-2 text-xs text-red-600" title={config.last_test_error}>
                              {config.last_test_error.length > 80 ? config.last_test_error.slice(0, 80) + '…' : config.last_test_error}
                            </div>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center space-x-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleOpenSmtpTestModal(config)}
                          title="Enviar email de teste"
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
                              username: config.username ?? '',
                              password: '',
                              use_tls: config.use_tls ?? true,
                              use_ssl: config.use_ssl ?? false,
                              verify_ssl: config.verify_ssl ?? true,
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
            <DepartmentsManager onDepartmentsChange={fetchDepartments} />
          </Card>
        </div>
      )}

      {activeTab === 'notifications' && (
        <NotificationSettings />
      )}

      {activeTab === 'ai' && isTenantAdmin && (
        <div className="space-y-6">
          <div className="flex gap-2 border-b border-gray-200 dark:border-gray-600 pb-2">
            <button
              type="button"
              onClick={() => setAiSubTab('config')}
              className={`px-4 py-2 rounded-t-lg text-sm font-medium ${aiSubTab === 'config' ? 'bg-white dark:bg-gray-800 border border-b-0 border-gray-200 dark:border-gray-600 text-gray-900 dark:text-gray-100' : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100'}`}
            >
              Configurações
            </button>
            <button
              type="button"
              onClick={() => setAiSubTab('ia-assistente')}
              className={`px-4 py-2 rounded-t-lg text-sm font-medium flex items-center gap-1 ${aiSubTab === 'ia-assistente' ? 'bg-white dark:bg-gray-800 border border-b-0 border-gray-200 dark:border-gray-600 text-gray-900 dark:text-gray-100' : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100'}`}
            >
              <MessageSquare className="h-4 w-4" />
              Secretaria
            </button>
            <button
              type="button"
              onClick={() => setAiSubTab('rag-memories')}
              className={`px-4 py-2 rounded-t-lg text-sm font-medium flex items-center gap-1 ${aiSubTab === 'rag-memories' ? 'bg-white dark:bg-gray-800 border border-b-0 border-gray-200 dark:border-gray-600 text-gray-900 dark:text-gray-100' : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100'}`}
            >
              <FileText className="h-4 w-4" />
              Contexto
            </button>
            <button
              type="button"
              onClick={() => setAiSubTab('auditoria-ia')}
              className={`px-4 py-2 rounded-t-lg text-sm font-medium ${aiSubTab === 'auditoria-ia' ? 'bg-white dark:bg-gray-800 border border-b-0 border-gray-200 dark:border-gray-600 text-gray-900 dark:text-gray-100' : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100'}`}
            >
              Auditoria IA
            </button>
          </div>

          {aiSubTab === 'rag-memories' ? (
            <RagMemoriesManager />
          ) : aiSubTab === 'ia-assistente' ? (
            <BiaAdminPage />
          ) : aiSubTab === 'auditoria-ia' ? (
            <Card className="p-6">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100">Auditoria IA</h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400">Histórico das chamadas (testes e produção).</p>
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
                    className="mt-1 block w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 px-3 py-2 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
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
                  className="border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-700"
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
                <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3 text-sm text-red-700 dark:text-red-200">
                  {gatewayAuditError}
                </div>
              )}

              {gatewayAuditLoading ? (
                <div className="flex items-center justify-center h-32">
                  <LoadingSpinner />
                </div>
              ) : gatewayAuditItems.length === 0 ? (
                <div className="text-sm text-gray-500 dark:text-gray-400">Nenhum registro encontrado.</div>
              ) : (
                <div className="space-y-3">
                  {gatewayAuditItems.map((item) => (
                    <div key={item.id} className="border border-gray-200 dark:border-gray-600 rounded-lg p-4">
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <div className="text-sm font-medium text-gray-900 dark:text-gray-100">
                            Request ID: {item.request_id}
                          </div>
                          <div className="text-xs text-gray-500 dark:text-gray-400">Trace ID: {item.trace_id}</div>
                        </div>
                        <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                          item.status === 'success' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                        }`}>
                          {item.status}
                        </span>
                      </div>

                      <div className="mt-2 grid grid-cols-1 md:grid-cols-3 gap-2 text-xs text-gray-600 dark:text-gray-300">
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
                        <div className="mt-2 text-xs text-gray-600 dark:text-gray-300 space-y-1">
                          <div><span className="font-medium">Input:</span> {item.input_summary || '-'}</div>
                          <div><span className="font-medium">Output:</span> {item.output_summary || '-'}</div>
                        </div>
                      )}

                      {item.error_message && (
                        <div className="mt-2 text-xs text-red-600">
                          {item.error_code ? `[${item.error_code}] ` : ''}{item.error_message}
                        </div>
                      )}

                      <details className="mt-2 text-xs text-gray-600 dark:text-gray-300">
                        <summary className="cursor-pointer text-blue-600">Ver payloads</summary>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-2">
                          <div>
                            <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Request (mascarado)</p>
                            <pre className="rounded-lg border border-border bg-background text-foreground p-3 text-xs overflow-auto max-h-56 whitespace-pre-wrap">
                              {item.request_payload_masked ? JSON.stringify(item.request_payload_masked, null, 2) : 'Sem request.'}
                            </pre>
                          </div>
                          <div>
                            <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Response (mascarado)</p>
                            <pre className="rounded-lg border border-border bg-background text-foreground p-3 text-xs overflow-auto max-h-56 whitespace-pre-wrap">
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
                <div className="flex flex-wrap items-center justify-between gap-2 mt-4 text-xs text-gray-600 dark:text-gray-300">
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
          ) : aiSettingsLoading || !aiSettings ? (
            <div className="flex items-center justify-center h-64">
              <LoadingSpinner />
            </div>
          ) : (
            <>
              <Card className="p-6 border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 shadow-sm">
                <div className="space-y-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <Label className="text-base font-semibold">Ativar IA</Label>
                      <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
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
                    <div className="bg-red-50 dark:bg-red-900/25 border border-red-200 dark:border-red-800 rounded-lg p-4 text-sm text-red-700 dark:text-red-200">
                      Nenhum modelo listado. A IA fica indisponível até o endpoint de modelos responder.
                    </div>
                  )}

                  {!aiSettings.ai_enabled && (
                    <div className="bg-gray-50 dark:bg-gray-700/50 border border-gray-200 dark:border-gray-600 rounded-lg p-4 text-sm text-gray-700 dark:text-gray-300">
                      Habilite a IA para editar as configurações abaixo.
                    </div>
                  )}

                  <div className="flex items-center justify-between">
                    <div>
                      <Label className="text-base font-semibold">Transcrição automática</Label>
                      <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
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
                      <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
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
                        className={`mt-1 bg-white dark:bg-gray-700 border-gray-300 dark:border-gray-600 text-gray-900 dark:text-gray-100 ${aiSettingsErrors.transcription_min_seconds ? 'border-red-500 dark:border-red-500' : ''}`}
                        disabled={!aiSettings.ai_enabled}
                      />
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
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
                        className={`mt-1 bg-white dark:bg-gray-700 border-gray-300 dark:border-gray-600 text-gray-900 dark:text-gray-100 ${aiSettingsErrors.transcription_max_mb ? 'border-red-500 dark:border-red-500' : ''}`}
                        disabled={!aiSettings.ai_enabled}
                      />
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
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
                        className="mt-1 block w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
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
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                        Use um modelo instalado no Ollama.
                      </p>
                    </div>
                  </div>

                  {(aiSettings.audio_transcription_enabled && !aiSettings.n8n_audio_webhook_url) ||
                  (aiSettings.ai_enabled && !aiSettings.n8n_ai_webhook_url) ? (
                    <div className="bg-red-50 dark:bg-red-900/25 border border-red-200 dark:border-red-800 rounded-lg p-4 text-sm text-red-700 dark:text-red-200">
                      Preencha os webhooks obrigatórios para ativar transcrição e IA.
                    </div>
                  ) : null}
                  {aiSettingsErrors.n8n_models_webhook_url ? (
                    <div className="bg-red-50 dark:bg-red-900/25 border border-red-200 dark:border-red-800 rounded-lg p-4 text-sm text-red-700 dark:text-red-200">
                      {aiSettingsErrors.n8n_models_webhook_url}
                    </div>
                  ) : null}

                  <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-4 text-sm text-yellow-800 dark:text-yellow-200">
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

            </>
          )}
        </div>
      )}

      {isModelsGatewayModalOpen && aiSettings && (
        <div className="fixed inset-0 z-50 overflow-y-auto" role="dialog" aria-modal="true" aria-labelledby="gateways-webhooks-modal-title">
          <div className="flex min-h-full items-end justify-center p-4 text-center sm:items-center sm:p-0">
            <div
              className="fixed inset-0 bg-black/50 dark:bg-black/60 transition-opacity"
              onClick={() => setIsModelsGatewayModalOpen(false)}
              aria-hidden
            />

            <div className="relative transform overflow-hidden rounded-xl bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-lg border border-gray-200 dark:border-gray-600">
              <div className="px-4 pb-4 pt-5 sm:p-6 sm:pb-4">
                <div className="flex items-center gap-3 mb-4">
                  <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-indigo-100 dark:bg-indigo-900/40 flex items-center justify-center">
                    <Server className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
                  </div>
                  <h3 id="gateways-webhooks-modal-title" className="text-lg font-semibold leading-6 text-gray-900 dark:text-gray-100">
                    Gateways e Webhooks
                  </h3>
                </div>
                <div className="space-y-5">
                  <div>
                    <Label htmlFor="n8n_models_webhook_url" className="text-gray-700 dark:text-gray-300">Webhook de modelos</Label>
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
                      className="mt-1"
                    />
                    <div className="flex items-center justify-between mt-3">
                      <Button
                        type="button"
                        variant="outline"
                        onClick={handleTestModelsGateway}
                        disabled={aiModelsLoading}
                      >
                        {aiModelsLoading ? (
                          <>
                            <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                            Testando…
                          </>
                        ) : (
                          'Testar'
                        )}
                      </Button>
                      {modelsGatewayTested && !modelsGatewayTestError ? (
                        <span className="text-xs text-green-600 dark:text-green-400">Consulta realizada.</span>
                      ) : null}
                    </div>
                    {modelsGatewayTestError ? (
                      <p className="text-xs text-red-600 dark:text-red-400 mt-2">{modelsGatewayTestError}</p>
                    ) : null}
                  </div>

                  <div>
                    <Label htmlFor="n8n_audio_webhook_url" className="text-gray-700 dark:text-gray-300">Webhook de transcrição</Label>
                    <div className="flex gap-2 mt-1">
                      <Input
                        id="n8n_audio_webhook_url"
                        type="text"
                        value={aiSettings.n8n_audio_webhook_url}
                        onChange={(e) => setAiSettings({ ...aiSettings, n8n_audio_webhook_url: e.target.value })}
                        className={aiSettingsErrors.n8n_audio_webhook_url ? 'border-red-500 dark:border-red-400' : ''}
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
                      <p className="text-xs text-red-600 dark:text-red-400 mt-1">{aiSettingsErrors.n8n_audio_webhook_url}</p>
                    )}
                  </div>

                  <div>
                    <Label htmlFor="n8n_ai_webhook_url" className="text-gray-700 dark:text-gray-300">Webhook do Gateway IA</Label>
                    <div className="flex gap-2 mt-1">
                      <Input
                        id="n8n_ai_webhook_url"
                        type="text"
                        value={aiSettings.n8n_ai_webhook_url}
                        onChange={(e) => setAiSettings({ ...aiSettings, n8n_ai_webhook_url: e.target.value })}
                        className={aiSettingsErrors.n8n_ai_webhook_url ? 'border-red-500 dark:border-red-400' : ''}
                        placeholder="https://integrador.alrea.ao/webhook/gateway-ia"
                      />
                      <Button
                        variant="outline"
                        onClick={() => handleTestWebhook('ai')}
                        disabled={webhookTesting.ai || !aiSettings.n8n_ai_webhook_url}
                      >
                        {webhookTesting.ai ? (
                          <>
                            <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                            Testando…
                          </>
                        ) : (
                          'Testar'
                        )}
                      </Button>
                    </div>
                    {aiSettingsErrors.n8n_ai_webhook_url && (
                      <p className="text-xs text-red-600 dark:text-red-400 mt-1">{aiSettingsErrors.n8n_ai_webhook_url}</p>
                    )}
                  </div>
                </div>
              </div>

              <div className="bg-gray-50 dark:bg-gray-700/50 px-4 py-3 sm:flex sm:flex-row-reverse sm:gap-2 sm:px-6 border-t border-gray-200 dark:border-gray-600">
                <Button
                  onClick={() => {
                    setIsModelsGatewayModalOpen(false)
                    handleSaveAiSettings()
                  }}
                  disabled={!modelsGatewayTested || aiSettingsSaving || aiModelsLoading}
                  className="w-full sm:w-auto"
                >
                  {aiSettingsSaving ? <RefreshCw className="h-4 w-4 mr-2 animate-spin" /> : null}
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
            <Card className="p-6 border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-800 shadow-sm">
              <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-4">Informações do Plano</h3>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <h4 className="font-medium text-gray-900 dark:text-gray-100 mb-2">Plano Atual</h4>
                  <div className="bg-blue-50 dark:bg-blue-900/25 p-4 rounded-lg border border-blue-100 dark:border-blue-800/50">
                    <div className="text-2xl font-bold text-blue-900 dark:text-blue-100">
                      {tenant.current_plan?.name || 'Sem plano'}
                    </div>
                    <div className="text-blue-700 dark:text-blue-200">
                      R$ {Number(tenant.current_plan?.price || 0).toFixed(2)}/mês
                    </div>
                  </div>
                </div>
                
                <div>
                  <h4 className="font-medium text-gray-900 dark:text-gray-100 mb-2">Status da Conta</h4>
                  <div className="bg-green-50 dark:bg-green-900/25 p-4 rounded-lg border border-green-100 dark:border-green-800/50">
                    <div className="text-2xl font-bold text-green-900 dark:text-green-100 capitalize">
                      {tenant.status}
                    </div>
                    <div className="text-green-700 dark:text-green-200">
                      Conta ativa
                    </div>
                  </div>
                </div>
              </div>

              {tenant.current_plan?.description && (
                <div className="mt-6">
                  <h4 className="font-medium text-gray-900 dark:text-gray-100 mb-2">Descrição do Plano</h4>
                  <p className="text-gray-600 dark:text-gray-300">{tenant.current_plan.description}</p>
                </div>
              )}

              <div className="mt-6 p-4 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg">
                <div className="flex items-center">
                  <AlertCircle className="h-5 w-5 text-yellow-600 dark:text-yellow-400 mr-2" />
                  <div>
                    <h4 className="font-medium text-yellow-900 dark:text-yellow-200">Precisa de mais recursos?</h4>
                    <p className="text-sm text-yellow-700 dark:text-yellow-300">
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
            <div className="fixed inset-0 bg-black/50 dark:bg-black/60 backdrop-blur-sm transition-opacity" onClick={handleCloseInstanceModal} />
            
            <div className="relative transform overflow-hidden rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-lg">
              <form onSubmit={(e) => { e.preventDefault(); editingInstance ? handleUpdateInstance() : handleCreateInstance(); }}>
                <div className="bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 px-4 pb-4 pt-5 sm:p-6 sm:pb-4">
                  <h3 className="text-lg font-semibold leading-6 text-gray-900 dark:text-gray-100 mb-4">
                    {editingInstance ? 'Editar Instância WhatsApp' : 'Nova Instância WhatsApp'}
                  </h3>

                  {instanceFormError && (
                    <div className="rounded-md bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 p-4 mb-4">
                      <p className="text-sm font-medium text-red-800 dark:text-red-200">{instanceFormError}</p>
                      <p className="text-xs text-red-600 dark:text-red-300 mt-1">
                        Verifique seu plano ou faça upgrade para criar mais instâncias WhatsApp.
                      </p>
                    </div>
                  )}
                  
                  <div className="space-y-4">
                    <div>
                      <label htmlFor="integration_type" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                        Tipo de conexão
                      </label>
                      <select
                        id="integration_type"
                        value={instanceFormData.integration_type}
                        onChange={(e) => setInstanceFormData({ ...instanceFormData, integration_type: e.target.value })}
                        className="mt-1 block w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                      >
                        <option value={INTEGRATION_EVOLUTION}>API não oficial (QR Code)</option>
                        <option value={INTEGRATION_META_CLOUD}>API oficial Meta</option>
                      </select>
                      <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                        {instanceFormData.integration_type === INTEGRATION_META_CLOUD
                          ? 'Conexão via WhatsApp Cloud API. Requer Phone Number ID e Access Token.'
                          : 'Conexão via API não oficial. Após salvar, use Gerar QR Code para conectar.'}
                      </p>
                    </div>

                    <div>
                      <label htmlFor="friendly_name" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                        Nome da Instância *
                      </label>
                      <input
                        type="text"
                        id="friendly_name"
                        required
                        value={instanceFormData.friendly_name}
                        onChange={(e) => setInstanceFormData({ ...instanceFormData, friendly_name: e.target.value })}
                        className="mt-1 block w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                        placeholder="Ex: WhatsApp Principal"
                      />
                      <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                        Nome de exibição para identificar esta instância
                      </p>
                    </div>

                    {instanceFormData.integration_type === INTEGRATION_META_CLOUD ? (
                      <>
                        <div>
                          <label htmlFor="phone_number_id" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                            Phone Number ID *
                          </label>
                          <input
                            type="text"
                            id="phone_number_id"
                            value={instanceFormData.phone_number_id}
                            onChange={(e) => setInstanceFormData({ ...instanceFormData, phone_number_id: e.target.value })}
                            disabled={!!editingInstance}
                            className="mt-1 block w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm disabled:opacity-60"
                            placeholder="ID do número no Meta Business"
                          />
                          <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">ID do número no Meta (não alterável após criar)</p>
                        </div>
                        <div>
                          <label htmlFor="access_token" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                            Access Token *
                          </label>
                          <input
                            type="password"
                            id="access_token"
                            value={instanceFormData.access_token}
                            onChange={(e) => setInstanceFormData({ ...instanceFormData, access_token: e.target.value })}
                            className="mt-1 block w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                            placeholder={editingInstance && (editingInstance as any).access_token_set ? '•••• (deixe em branco para manter)' : 'Token permanente do Meta'}
                          />
                        </div>
                        <div>
                          <label htmlFor="business_account_id" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                            Business Account ID (opcional)
                          </label>
                          <input
                            type="text"
                            id="business_account_id"
                            value={instanceFormData.business_account_id}
                            onChange={(e) => setInstanceFormData({ ...instanceFormData, business_account_id: e.target.value })}
                            className="mt-1 block w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                            placeholder="ID da conta Business"
                          />
                        </div>
                        <div className="bg-indigo-50 dark:bg-indigo-900/20 p-4 rounded-lg border border-indigo-100 dark:border-indigo-800/50">
                          <p className="text-sm text-indigo-700 dark:text-indigo-200">Configure o webhook no Meta Business Suite apontando para a URL do seu servidor.</p>
                        </div>
                      </>
                    ) : (
                      <div className="bg-blue-50 dark:bg-blue-900/20 p-4 rounded-lg border border-blue-100 dark:border-blue-800/50">
                        <p className="text-sm text-blue-700 dark:text-blue-200 flex items-start gap-2">
                          <Info className="h-4 w-4 shrink-0 mt-0.5" />
                          O identificador único e o telefone serão preenchidos automaticamente após conectar o WhatsApp via QR Code.
                        </p>
                      </div>
                    )}

                    <div>
                      <label htmlFor="default_department" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                        Departamento Padrão
                      </label>
                      <select
                        id="default_department"
                        value={instanceFormData.default_department || ''}
                        onChange={(e) => setInstanceFormData({ ...instanceFormData, default_department: e.target.value || null })}
                        className="mt-1 block w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 px-3 py-2 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                      >
                        <option value="">Inbox (sem departamento)</option>
                        {departments.map((dept) => (
                          <option key={dept.id} value={dept.id}>
                            {dept.name}
                          </option>
                        ))}
                      </select>
                      <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                        Novas conversas desta instância irão automaticamente para este departamento. Deixe em branco para ir para Inbox.
                      </p>
                    </div>
                  </div>
                </div>
                
                <div className="bg-gray-50 dark:bg-gray-700/50 border-t border-gray-200 dark:border-gray-600 px-4 py-3 sm:flex sm:flex-row-reverse sm:gap-2 sm:px-6">
                  <Button type="submit" className="w-full sm:w-auto">
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
            <div className="fixed inset-0 bg-black/50 dark:bg-black/60 backdrop-blur-sm transition-opacity" onClick={handleCloseSmtpModal} />
            <div className="relative transform overflow-hidden rounded-xl bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 text-left shadow-2xl ring-1 ring-black/5 transition-all sm:my-8 sm:w-full sm:max-w-2xl max-h-[90vh] overflow-y-auto">
              <form onSubmit={(e) => { e.preventDefault(); handleSaveSmtpConfig(); }}>
                {/* Header */}
                <div className="border-b border-gray-100 dark:border-gray-700 bg-gradient-to-b from-gray-50/80 to-white dark:from-gray-700/80 dark:to-gray-800 px-5 pt-5 pb-4 sm:px-6">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-blue-100 text-blue-600">
                      <Mail className="h-5 w-5" />
                    </div>
                    <div>
                      <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                        {editingSmtp ? 'Editar Configuração SMTP' : 'Nova Configuração SMTP'}
                      </h3>
                      <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
                        Configure servidor e autenticação para envio de emails
                      </p>
                    </div>
                  </div>
                </div>

                <div className="px-5 py-5 sm:px-6 space-y-6">
                  {/* Identificação */}
                  <div>
                    <label htmlFor="smtp_name" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                      Nome da configuração <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      id="smtp_name"
                      required
                      value={smtpFormData.name}
                      onChange={(e) => setSmtpFormData({ ...smtpFormData, name: e.target.value })}
                      className="block w-full rounded-lg border border-border bg-background text-foreground px-3.5 py-2.5 text-sm placeholder:text-muted-foreground focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none transition"
                      placeholder="Ex: Gmail SMTP"
                    />
                  </div>

                  {/* Servidor */}
                  <div className="rounded-lg border border-gray-100 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-700/50 p-4 space-y-4">
                    <p className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">Servidor</p>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 sm:gap-4">
                      <div className="sm:col-span-2">
                        <label htmlFor="smtp_host" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Servidor SMTP <span className="text-red-500">*</span></label>
                        <input
                          type="text"
                          id="smtp_host"
                          required
                          value={smtpFormData.host}
                          onChange={(e) => setSmtpFormData({ ...smtpFormData, host: e.target.value })}
                          className="block w-full rounded-lg border border-border bg-background text-foreground px-3.5 py-2.5 text-sm placeholder:text-muted-foreground focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none transition"
                          placeholder="smtp.gmail.com"
                        />
                      </div>
                      <div>
                        <label htmlFor="smtp_port" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Porta <span className="text-red-500">*</span></label>
                        <input
                          type="number"
                          id="smtp_port"
                          required
                          value={smtpFormData.port}
                          onChange={(e) => setSmtpFormData({ ...smtpFormData, port: parseInt(e.target.value, 10) || 587 })}
                          className="block w-full rounded-lg border border-border bg-background text-foreground px-3.5 py-2.5 text-sm placeholder:text-muted-foreground focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none transition"
                          placeholder="587"
                        />
                      </div>
                    </div>
                  </div>

                  {/* Autenticação */}
                  <div className="rounded-lg border border-gray-100 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-700/50 p-4 space-y-4">
                    <p className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">Autenticação</p>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <label htmlFor="smtp_username" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Usuário / e-mail <span className="text-red-500">*</span></label>
                        <input
                          type="text"
                          id="smtp_username"
                          required
                          value={smtpFormData.username}
                          onChange={(e) => setSmtpFormData({ ...smtpFormData, username: e.target.value })}
                          className="block w-full rounded-lg border border-border bg-background text-foreground px-3.5 py-2.5 text-sm placeholder:text-muted-foreground focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none transition"
                          placeholder="seu@email.com"
                        />
                      </div>
                      <div>
                        <label htmlFor="smtp_password" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                          Senha {editingSmtp && <span className="font-normal text-gray-500 dark:text-gray-400">(em branco = manter)</span>}
                          {!editingSmtp && <span className="text-red-500"> *</span>}
                        </label>
                        <div className="flex rounded-lg border border-border bg-background overflow-hidden focus-within:ring-2 focus-within:ring-blue-500/20 focus-within:border-blue-500">
                          <input
                            type={showSmtpPassword ? 'text' : 'password'}
                            id="smtp_password"
                            required={!editingSmtp}
                            value={smtpFormData.password}
                            onChange={(e) => setSmtpFormData({ ...smtpFormData, password: e.target.value })}
                            className="flex-1 min-w-0 px-3.5 py-2.5 text-sm text-foreground placeholder:text-muted-foreground outline-none border-0 bg-transparent"
                            placeholder={editingSmtp ? '••••••••' : 'Senha da conta'}
                          />
                          <button
                            type="button"
                            onClick={() => setShowSmtpPassword(!showSmtpPassword)}
                            className="px-3 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition"
                            title={showSmtpPassword ? 'Ocultar senha' : 'Mostrar senha'}
                          >
                            {showSmtpPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Remetente */}
                  <div className="rounded-lg border border-gray-100 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-700/50 p-4 space-y-4">
                    <p className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">Remetente</p>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <label htmlFor="from_email" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">E-mail de origem <span className="text-red-500">*</span></label>
                        <input
                          type="email"
                          id="from_email"
                          required
                          value={smtpFormData.from_email}
                          onChange={(e) => setSmtpFormData({ ...smtpFormData, from_email: e.target.value })}
                          className="block w-full rounded-lg border border-border bg-background text-foreground px-3.5 py-2.5 text-sm placeholder:text-muted-foreground focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none transition"
                          placeholder="noreply@suaempresa.com"
                        />
                      </div>
                      <div>
                        <label htmlFor="from_name" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Nome de origem <span className="text-red-500">*</span></label>
                        <input
                          type="text"
                          id="from_name"
                          required
                          value={smtpFormData.from_name}
                          onChange={(e) => setSmtpFormData({ ...smtpFormData, from_name: e.target.value })}
                          className="block w-full rounded-lg border border-border bg-background text-foreground px-3.5 py-2.5 text-sm placeholder:text-muted-foreground focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none transition"
                          placeholder="Sua Empresa"
                        />
                      </div>
                    </div>
                  </div>

                  {/* Conexão e opções */}
                  <div className="flex flex-wrap gap-x-6 gap-y-3">
                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        id="smtp_use_tls"
                        checked={smtpFormData.use_tls}
                        onChange={(e) => setSmtpFormData({ ...smtpFormData, use_tls: e.target.checked })}
                        className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500/20"
                      />
                      <label htmlFor="smtp_use_tls" className="text-sm text-gray-700 dark:text-gray-300">TLS (587)</label>
                    </div>
                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        id="smtp_use_ssl"
                        checked={smtpFormData.use_ssl}
                        onChange={(e) => setSmtpFormData({ ...smtpFormData, use_ssl: e.target.checked })}
                        className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500/20"
                      />
                      <label htmlFor="smtp_use_ssl" className="text-sm text-gray-700 dark:text-gray-300">SSL (465)</label>
                    </div>
                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        id="smtp_verify_ssl"
                        checked={smtpFormData.verify_ssl}
                        onChange={(e) => setSmtpFormData({ ...smtpFormData, verify_ssl: e.target.checked })}
                        className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500/20"
                      />
                      <label htmlFor="smtp_verify_ssl" className="text-sm text-gray-700 dark:text-gray-300">Verificar SSL</label>
                    </div>
                    <div className="flex items-center gap-2 ml-auto sm:ml-0">
                      <input
                        type="checkbox"
                        id="smtp_is_active"
                        checked={smtpFormData.is_active}
                        onChange={(e) => setSmtpFormData({ ...smtpFormData, is_active: e.target.checked })}
                        className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500/20"
                      />
                      <label htmlFor="smtp_is_active" className="text-sm text-gray-700 dark:text-gray-300">Ativar</label>
                    </div>
                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        id="smtp_is_default"
                        checked={smtpFormData.is_default}
                        onChange={(e) => setSmtpFormData({ ...smtpFormData, is_default: e.target.checked })}
                        className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500/20"
                      />
                      <label htmlFor="smtp_is_default" className="text-sm text-gray-700 dark:text-gray-300">Usar como padrão</label>
                    </div>
                  </div>
                </div>

                {/* Footer */}
                <div className="border-t border-gray-100 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-700/50 px-5 py-4 sm:px-6 flex flex-col-reverse sm:flex-row sm:justify-end gap-3">
                  <Button type="button" variant="outline" onClick={handleCloseSmtpModal} className="w-full sm:w-auto">
                    Cancelar
                  </Button>
                  <Button type="submit" className="w-full sm:w-auto">
                    <Save className="h-4 w-4 mr-2" />
                    Salvar configuração
                  </Button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* Modal de teste SMTP */}
      {smtpTestModalOpen && smtpTestConfig && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-full items-end justify-center p-4 text-center sm:items-center sm:p-0">
            <div className="fixed inset-0 bg-black/50 dark:bg-black/60 transition-opacity" onClick={handleCloseSmtpTestModal} />
            <div className="relative transform overflow-hidden rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-md">
              <div className="bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 px-4 pb-4 pt-5 sm:p-6 sm:pb-4">
                <div className="flex items-center mb-4">
                  <div className="mx-auto flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full bg-blue-100 sm:mx-0 sm:h-10 sm:w-10">
                    <TestTube className="h-6 w-6 text-blue-600" />
                  </div>
                  <h3 className="ml-3 text-lg font-medium leading-6 text-gray-900 dark:text-gray-100">
                    Enviar email de teste
                  </h3>
                </div>
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                  Configuração: <strong>{smtpTestConfig.name}</strong>
                </p>
                <label htmlFor="smtp_test_email" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Email para receber o teste *
                </label>
                <input
                  type="email"
                  id="smtp_test_email"
                  value={smtpTestEmail}
                  onChange={(e) => setSmtpTestEmail(e.target.value)}
                  placeholder="destino@exemplo.com"
                  className="mt-1 block w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 px-3 py-2 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                  disabled={smtpTestLoading}
                />
                {smtpTestResult && (
                  <div className={`mt-4 p-3 rounded-lg text-sm ${smtpTestResult.success ? 'bg-green-50 dark:bg-green-900/20 text-green-800 dark:text-green-200' : 'bg-red-50 dark:bg-red-900/20 text-red-800 dark:text-red-200'}`}>
                    {smtpTestResult.message}
                  </div>
                )}
              </div>
              <div className="bg-gray-50 dark:bg-gray-700/50 px-4 py-3 sm:flex sm:flex-row-reverse sm:px-6 gap-2">
                <Button
                  onClick={handleSendSmtpTest}
                  disabled={smtpTestLoading || !smtpTestEmail.trim()}
                >
                  {smtpTestLoading ? 'Enviando...' : 'Enviar teste'}
                </Button>
                <Button variant="outline" onClick={handleCloseSmtpTestModal}>
                  Fechar
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modal de Teste de Transcrição */}
      {isAudioTestModalOpen && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-full items-end justify-center p-4 text-center sm:items-center sm:p-0">
            <div className="fixed inset-0 bg-black/50 dark:bg-black/60 transition-opacity" onClick={handleCloseAudioTestModal} />

            <div className="relative transform overflow-hidden rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-lg">
              <div className="bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 px-4 pb-4 pt-5 sm:p-6 sm:pb-4">
                <div className="flex items-center mb-4">
                  <div className="mx-auto flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full bg-blue-100 sm:mx-0 sm:h-10 sm:w-10">
                    <TestTube className="h-6 w-6 text-blue-600" />
                  </div>
                  <h3 className="ml-3 text-lg font-medium leading-6 text-gray-900 dark:text-gray-100">
                    Teste de Transcrição
                  </h3>
                </div>

                <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
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
                    <div className="flex-1 px-3 text-sm text-gray-700 dark:text-gray-300">
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
            <div className="fixed inset-0 bg-black/50 dark:bg-black/60 transition-opacity" onClick={() => setQrCodeInstance(null)} />
            
            <div className="relative transform overflow-hidden rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-md">
              <div className="bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 px-4 pb-4 pt-5 sm:p-6 sm:pb-4">
                <h3 className="text-lg font-medium leading-6 text-gray-900 dark:text-gray-100 mb-4">
                  QR Code - {qrCodeInstance.friendly_name}
                </h3>
                
                {qrCodeInstance.qr_code && (
                  <div className="text-center">
                    <img 
                      src={qrCodeInstance.qr_code} 
                      alt="QR Code WhatsApp" 
                      className="mx-auto max-w-full h-auto"
                    />
                    <p className="mt-4 text-sm text-gray-600 dark:text-gray-400">
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

      {/* Modal Indicadores de Saúde da Instância */}
      <InstanceHealthModal
        open={!!healthModalInstance}
        onClose={() => setHealthModalInstance(null)}
        instance={healthModalInstance}
      />

      {/* Modal de Teste de Mensagem */}
      {testInstance && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-full items-end justify-center p-4 text-center sm:items-center sm:p-0">
            <div className="fixed inset-0 bg-black/50 dark:bg-black/60 transition-opacity" onClick={() => {
              setTestInstance(null)
              setTestPhoneNumber('')
              setTestPhoneError('')
            }} />
            
            <div className="relative transform overflow-hidden rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-md">
              <div className="bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 px-4 pb-4 pt-5 sm:p-6 sm:pb-4">
                <div className="flex items-center mb-4">
                  <div className="mx-auto flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full bg-blue-100 dark:bg-blue-900/30 sm:mx-0 sm:h-10 sm:w-10">
                    <Send className="h-6 w-6 text-blue-600 dark:text-blue-400" />
                  </div>
                  <h3 className="ml-3 text-lg font-medium leading-6 text-gray-900 dark:text-gray-100">
                    Enviar Mensagem de Teste
                  </h3>
                </div>
                
                <div className="mt-4">
                  <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                    Envie uma mensagem de teste de <strong>{testInstance.friendly_name}</strong> para validar a conexão.
                  </p>
                  
                  <div>
                    <Label htmlFor="test_phone" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Número do WhatsApp (com DDD)
                    </Label>
                    <Input
                      type="text"
                      id="test_phone"
                      value={testPhoneNumber}
                      onChange={(e) => {
                        setTestPhoneNumber(e.target.value)
                        setTestPhoneError('')
                      }}
                      placeholder="5511999999999"
                      className="mt-1"
                      disabled={isSendingTest}
                    />
                    {testPhoneError ? (
                      <p className="mt-1 text-sm text-red-600 dark:text-red-400">{testPhoneError}</p>
                    ) : (
                      <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                        Formato: Código do país + DDD + Número (ex: 5511999999999)
                      </p>
                    )}
                  </div>
                </div>
              </div>
              
              <div className="bg-gray-50 dark:bg-gray-700/50 px-4 py-3 sm:flex sm:flex-row-reverse sm:px-6 gap-2 border-t border-gray-200 dark:border-gray-600">
                <Button 
                  onClick={handleSendTestMessage}
                  disabled={!testPhoneNumber.trim() || isSendingTest}
                  className="w-full sm:w-auto"
                >
                  {isSendingTest ? (
                    <LoadingSpinner size="sm" className="mr-2" />
                  ) : (
                    <Send className="h-4 w-4 mr-2" />
                  )}
                  {isSendingTest ? 'Enviando...' : 'Enviar Teste'}
                </Button>
                <Button 
                  variant="outline"
                  onClick={() => {
                    setTestInstance(null)
                    setTestPhoneNumber('')
                    setTestPhoneError('')
                  }}
                  disabled={isSendingTest}
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
                className="px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="">Geral</option>
                {businessHoursDepts.map((dept) => (
                  <option key={dept.id} value={dept.id}>
                    {dept.name}
                  </option>
                ))}
              </select>
              <div className="flex-1" />
              <div className="text-sm text-gray-500 dark:text-gray-400">
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
                    : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300 dark:hover:border-gray-600'
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
                    : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300 dark:hover:border-gray-600'
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
                    : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300 dark:hover:border-gray-600'
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
                    className="mt-1 block w-full px-3 py-2 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
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
                      <div key={day.key} className="flex items-center gap-4 p-4 border border-gray-200 dark:border-gray-600 rounded-lg">
                        <div className="flex items-center gap-2 w-32">
                          <input
                            type="checkbox"
                            id={`${day.key}_enabled`}
                            checked={enabled}
                            onChange={(e) => updateDayHours(day.key, 'enabled', e.target.checked)}
                            className="w-4 h-4 rounded border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-blue-600 focus:ring-blue-500"
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
                            <span className="text-gray-500 dark:text-gray-400">até</span>
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
                  <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
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
                      <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
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
                        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
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
      {activeTab === 'welcome-menu' && isTenantAdmin && (
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
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
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
        <div className="fixed inset-0 bg-black/50 dark:bg-black/60 flex items-center justify-center z-50 p-4" role="dialog" aria-modal="true" aria-labelledby="meta-template-form-title">
          <div className="bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-xl shadow-xl w-full max-w-xl max-h-[90vh] overflow-y-auto border border-gray-200 dark:border-gray-700">
            <div className="p-6">
              <div className="flex items-start justify-between gap-4 mb-4">
                <div className="min-w-0">
                  <h3 id="meta-template-form-title" className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                    {editingMetaTemplate ? 'Editar Template WhatsApp (Meta)' : 'Novo Template WhatsApp (Meta)'}
                  </h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                    Cadastre só templates já aprovados no Meta Business. Usados para primeira mensagem ou fora da janela de 24h.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={closeMetaTemplateModal}
                  className="shrink-0 p-1.5 rounded-lg text-gray-500 hover:text-gray-700 hover:bg-gray-100 dark:hover:bg-gray-700 dark:hover:text-gray-200 transition-colors"
                  aria-label="Fechar"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
              <div className="space-y-5">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="sm:col-span-2">
                    <Label htmlFor="meta_template_name">Nome (exibição)</Label>
                    <Input
                      id="meta_template_name"
                      value={metaTemplateFormData.name}
                      onChange={(e) => setMetaTemplateFormData({ ...metaTemplateFormData, name: e.target.value })}
                      placeholder="Ex: Saudação inicial"
                      className="mt-1"
                    />
                  </div>
                  <div>
                    <Label htmlFor="meta_template_id">ID na Meta</Label>
                    <Input
                      id="meta_template_id"
                      value={metaTemplateFormData.template_id}
                      onChange={(e) => setMetaTemplateFormData({ ...metaTemplateFormData, template_id: e.target.value })}
                      placeholder="Ex: hello_world"
                      className="mt-1"
                    />
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Mesmo nome do template no Meta Business</p>
                  </div>
                  <div>
                    <Label htmlFor="meta_template_lang">Idioma</Label>
                    <Input
                      id="meta_template_lang"
                      value={metaTemplateFormData.language_code}
                      onChange={(e) => setMetaTemplateFormData({ ...metaTemplateFormData, language_code: e.target.value })}
                      placeholder="pt_BR"
                      className="mt-1"
                    />
                  </div>
                </div>
                <div>
                  <Label htmlFor="meta_template_params">Parâmetros padrão do body (opcional)</Label>
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
                    className="mt-1 font-mono text-sm"
                  />
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">JSON array. Ex: [] ou [&quot;valor1&quot;, &quot;valor2&quot;]</p>
                </div>
                <div className="flex flex-col sm:flex-row sm:items-center gap-4 sm:gap-6">
                  <div className="flex-1 min-w-0">
                    <Label htmlFor="meta_template_instance">Instância WhatsApp</Label>
                    <select
                      id="meta_template_instance"
                      className="mt-1 block w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-gray-100"
                      value={metaTemplateFormData.wa_instance || ''}
                      onChange={(e) => setMetaTemplateFormData({ ...metaTemplateFormData, wa_instance: e.target.value || null })}
                    >
                      <option value="">Qualquer instância</option>
                      {metaInstances.map((inst: WhatsAppInstance) => (
                        <option key={inst.id} value={inst.id}>{inst.friendly_name}</option>
                      ))}
                    </select>
                  </div>
                  <label className="flex items-center gap-2 cursor-pointer pt-2 sm:pt-8">
                    <input
                      type="checkbox"
                      checked={metaTemplateFormData.is_active}
                      onChange={(e) => setMetaTemplateFormData({ ...metaTemplateFormData, is_active: e.target.checked })}
                      className="w-4 h-4 rounded border-gray-300 dark:border-gray-600 text-accent-600 focus:ring-accent-500"
                    />
                    <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Ativo</span>
                  </label>
                </div>
              </div>
              <div className="flex justify-end gap-2 mt-6 pt-4 border-t border-gray-200 dark:border-gray-700">
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
