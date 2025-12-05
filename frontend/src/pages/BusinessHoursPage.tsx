import { useState, useEffect } from 'react'
import { Clock, MessageSquare, Calendar, Save, Plus, X, AlertCircle, Info } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Input } from '../components/ui/Input'
import { Label } from '../components/ui/Label'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import { api } from '../lib/api'
import { showSuccessToast, showErrorToast, showLoadingToast, updateToastSuccess, updateToastError } from '../lib/toastHelper'
import { useAuthStore } from '../stores/authStore'

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
  reply_to_groups: boolean
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
  auto_assign_to_agent?: string | null
  auto_assign_to_agent_name?: string
  include_message_preview: boolean
  is_active: boolean
}

interface Department {
  id: string
  name: string
}

interface User {
  id: string
  email: string
  first_name?: string
  last_name?: string
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

export default function BusinessHoursPage() {
  const { user } = useAuthStore()
  const [activeTab, setActiveTab] = useState<'hours' | 'message' | 'tasks'>('hours')
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [departments, setDepartments] = useState<Department[]>([])
  const [users, setUsers] = useState<User[]>([])
  const [selectedDepartment, setSelectedDepartment] = useState<string | null>(null)

  // Horários
  const [businessHours, setBusinessHours] = useState<BusinessHours | null>(null)
  const [holidaysInput, setHolidaysInput] = useState('')

  // Mensagem
  const [afterHoursMessage, setAfterHoursMessage] = useState<AfterHoursMessage | null>(null)

  // Tarefas
  const [taskConfig, setTaskConfig] = useState<AfterHoursTaskConfig | null>(null)

  useEffect(() => {
    console.log('🔄 [BUSINESS HOURS PAGE] useEffect - Carregando dados, department:', selectedDepartment)
    fetchData()
  }, [selectedDepartment])

  const fetchData = async () => {
    try {
      setIsLoading(true)
      
      // Buscar departamentos
      const deptResponse = await api.get('/auth/departments/')
      setDepartments(deptResponse.data || [])

      // Buscar usuários (para atribuição de tarefas)
      const usersResponse = await api.get('/auth/users/')
      setUsers(usersResponse.data || [])

      // Buscar configurações
      await Promise.all([
        fetchBusinessHours(),
        fetchAfterHoursMessage(),
        fetchTaskConfig(),
      ])
    } catch (error: any) {
      console.error('❌ Error fetching data:', error)
      showErrorToast('Erro ao carregar configurações')
    } finally {
      setIsLoading(false)
    }
  }

  const fetchBusinessHours = async () => {
    try {
      const params = selectedDepartment ? { department: selectedDepartment } : {}
      const response = await api.get('/chat/business-hours/current/', { params })
      
      if (response.data.has_config) {
        setBusinessHours(response.data.business_hours)
        setHolidaysInput((response.data.business_hours.holidays || []).join('\n'))
      } else {
        // Criar estrutura padrão
        setBusinessHours({
          tenant: user?.tenant_id || '',
          department: selectedDepartment || null,
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
      console.log('🔍 [BUSINESS HOURS] Buscando mensagem automática...')
      const params = selectedDepartment ? { department: selectedDepartment } : {}
      const response = await api.get('/chat/after-hours-messages/current/', { params })
      console.log('📥 [BUSINESS HOURS] Resposta da API:', response.data)
      
      if (response.data.has_config) {
        // ✅ Garantir que reply_to_groups sempre tenha valor (default: false)
        const messageData = response.data.after_hours_message || {}
        console.log('📥 [BUSINESS HOURS] Dados recebidos da API:', messageData)
        console.log('🔍 [BUSINESS HOURS] reply_to_groups no messageData:', messageData.reply_to_groups)
        const finalData = {
          ...messageData,
          reply_to_groups: messageData.reply_to_groups ?? false,
          // ✅ GARANTIR que is_active seja um booleano explícito - usar valor real da API
          // Se vier como string "false", converter para boolean false
          is_active: messageData.is_active === false || messageData.is_active === 'false' 
            ? false 
            : (messageData.is_active === true || messageData.is_active === 'true' ? true : true),
        }
        console.log('✅ [BUSINESS HOURS] Dados finais:', finalData)
        console.log('✅ [BUSINESS HOURS] is_active final:', finalData.is_active, '(tipo:', typeof finalData.is_active, ')')
        console.log('✅ [BUSINESS HOURS] reply_to_groups final:', finalData.reply_to_groups)
        setAfterHoursMessage(finalData)
      } else {
        console.log('⚠️ [BUSINESS HOURS] Nenhuma configuração encontrada, criando padrão')
        setAfterHoursMessage({
          tenant: user?.tenant_id || '',
          department: selectedDepartment || null,
          message_template: 'Olá {contact_name}! Recebemos sua mensagem fora do horário de atendimento.\n\nNosso horário de funcionamento é:\n{next_open_time}\n\nRetornaremos em breve!',
          reply_to_groups: false,
          is_active: true,
        })
      }
    } catch (error: any) {
      console.error('❌ Error fetching message:', error)
    }
  }

  const fetchTaskConfig = async () => {
    try {
      const params = selectedDepartment ? { department: selectedDepartment } : {}
      const response = await api.get('/chat/after-hours-task-configs/current/', { params })
      
      if (response.data.has_config) {
        setTaskConfig(response.data.task_config)
      } else {
        setTaskConfig({
          tenant: user?.tenant_id || '',
          department: selectedDepartment || null,
          create_task_enabled: true,
          task_title_template: 'Retornar contato de {contact_name}',
          task_description_template: 'Cliente entrou em contato fora do horário de atendimento.\n\nHorário: {message_time}\nMensagem: {message_content}\n\nPróximo horário: {next_open_time}',
          task_priority: 'high',
          task_due_date_offset_hours: 2,
          task_type: 'task',
          auto_assign_to_department: true,
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
      setIsSaving(true)

      // Processar feriados
      const holidays = holidaysInput
        .split('\n')
        .map(line => line.trim())
        .filter(line => line && /^\d{4}-\d{2}-\d{2}$/.test(line))

      const data = {
        ...businessHours,
        department: selectedDepartment || null,
        holidays,
      }

      if (businessHours.id) {
        await api.patch(`/chat/business-hours/${businessHours.id}/`, data)
      } else {
        await api.post('/chat/business-hours/', data)
      }

      updateToastSuccess(toastId, 'salvar', 'Horários de Atendimento')
      await fetchBusinessHours()
    } catch (error: any) {
      console.error('❌ Error saving business hours:', error)
      updateToastError(toastId, 'salvar', 'Horários de Atendimento', error)
    } finally {
      setIsSaving(false)
    }
  }

  const handleSaveMessage = async () => {
    if (!afterHoursMessage) return

    const toastId = showLoadingToast('salvar', 'Mensagem Automática')

    try {
      setIsSaving(true)

      // ✅ GARANTIR que is_active seja boolean explícito antes de enviar
      const data = {
        ...afterHoursMessage,
        department: selectedDepartment || null,
        is_active: Boolean(afterHoursMessage.is_active),
        reply_to_groups: Boolean(afterHoursMessage.reply_to_groups ?? false),
      }

      console.log('💾 [SAVE MESSAGE] Dados que serão enviados:', data)
      console.log('💾 [SAVE MESSAGE] is_active (tipo):', typeof data.is_active, 'valor:', data.is_active)
      console.log('💾 [SAVE MESSAGE] reply_to_groups (tipo):', typeof data.reply_to_groups, 'valor:', data.reply_to_groups)

      if (afterHoursMessage.id) {
        console.log('💾 [SAVE MESSAGE] Fazendo PATCH para:', afterHoursMessage.id)
        const response = await api.patch(`/chat/after-hours-messages/${afterHoursMessage.id}/`, data)
        console.log('✅ [SAVE MESSAGE] Resposta do PATCH:', response.data)
      } else {
        console.log('💾 [SAVE MESSAGE] Fazendo POST (novo registro)')
        const response = await api.post('/chat/after-hours-messages/', data)
        console.log('✅ [SAVE MESSAGE] Resposta do POST:', response.data)
      }

      updateToastSuccess(toastId, 'salvar', 'Mensagem Automática')
      console.log('🔄 [SAVE MESSAGE] Buscando dados atualizados...')
      // ✅ Aguardar um pouco antes de buscar para garantir que o banco foi atualizado
      await new Promise(resolve => setTimeout(resolve, 500))
      await fetchAfterHoursMessage()
      console.log('✅ [SAVE MESSAGE] Dados atualizados buscados')
    } catch (error: any) {
      console.error('❌ Error saving message:', error)
      updateToastError(toastId, 'salvar', 'Mensagem Automática', error)
    } finally {
      setIsSaving(false)
    }
  }

  const handleSaveTaskConfig = async () => {
    if (!taskConfig) return

    const toastId = showLoadingToast('salvar', 'Configuração de Tarefas')

    try {
      setIsSaving(true)

      const data = {
        ...taskConfig,
        department: selectedDepartment || null,
      }

      if (taskConfig.id) {
        await api.patch(`/chat/after-hours-task-configs/${taskConfig.id}/`, data)
      } else {
        await api.post('/chat/after-hours-task-configs/', data)
      }

      updateToastSuccess(toastId, 'salvar', 'Configuração de Tarefas')
      await fetchTaskConfig()
    } catch (error: any) {
      console.error('❌ Error saving task config:', error)
      updateToastError(toastId, 'salvar', 'Configuração de Tarefas', error)
    } finally {
      setIsSaving(false)
    }
  }

  const updateDayHours = (day: string, field: 'enabled' | 'start' | 'end', value: boolean | string) => {
    if (!businessHours) return

    setBusinessHours({
      ...businessHours,
      [`${day}_${field}`]: value,
    })
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
          <h1 className="text-2xl font-bold text-gray-900">Horários de Atendimento</h1>
          <p className="text-gray-600">Configure horários, mensagens automáticas e tarefas para fora de horário</p>
        </div>
      </div>

      {/* Seletor de Departamento */}
      <Card className="p-4">
        <div className="flex items-center gap-4">
          <Label className="font-medium">Departamento:</Label>
          <select
            value={selectedDepartment || ''}
            onChange={(e) => setSelectedDepartment(e.target.value || null)}
            className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="">Geral (Tenant)</option>
            {departments.map((dept) => (
              <option key={dept.id} value={dept.id}>
                {dept.name}
              </option>
            ))}
          </select>
          <div className="flex-1" />
          <div className="text-sm text-gray-500">
            {selectedDepartment
              ? `Configurando para: ${departments.find(d => d.id === selectedDepartment)?.name || 'Departamento'}`
              : 'Configurando para: Geral (todos os departamentos)'}
          </div>
        </div>
      </Card>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab('hours')}
            className={`py-2 px-1 border-b-2 font-medium text-sm flex items-center gap-2 ${
              activeTab === 'hours'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            <Clock className="h-4 w-4" />
            Horários
          </button>
          <button
            onClick={() => setActiveTab('message')}
            className={`py-2 px-1 border-b-2 font-medium text-sm flex items-center gap-2 ${
              activeTab === 'message'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            <MessageSquare className="h-4 w-4" />
            Mensagem Automática
          </button>
          <button
            onClick={() => setActiveTab('tasks')}
            className={`py-2 px-1 border-b-2 font-medium text-sm flex items-center gap-2 ${
              activeTab === 'tasks'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            <Calendar className="h-4 w-4" />
            Tarefas Automáticas
          </button>
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'hours' && businessHours && (
        <Card className="p-6">
          <div className="space-y-6">
            {/* Timezone */}
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

            {/* Dias da Semana */}
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

            {/* Feriados */}
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

            {/* Status */}
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

            {/* Botão Salvar */}
            <div className="flex justify-end">
              <Button
                onClick={handleSaveBusinessHours}
                disabled={isSaving}
                className="flex items-center gap-2"
              >
                <Save className="h-4 w-4" />
                {isSaving ? 'Salvando...' : 'Salvar Horários'}
              </Button>
            </div>
          </div>
        </Card>
      )}

      {activeTab === 'message' && afterHoursMessage && (
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

            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="message_is_active"
                  checked={Boolean(afterHoursMessage?.is_active)}
                  onChange={(e) => {
                    console.log('🔄 [CHECKBOX] is_active alterado:', e.target.checked)
                    setAfterHoursMessage({ ...afterHoursMessage, is_active: e.target.checked })
                  }}
                  className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                />
                <Label htmlFor="message_is_active" className="cursor-pointer">
                  Ativo
                </Label>
              </div>

              {/* ✅ CHECKBOX: Responder em Grupos */}
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="reply_to_groups"
                  checked={Boolean(afterHoursMessage?.reply_to_groups ?? false)}
                  onChange={(e) => {
                    console.log('🔄 [CHECKBOX] reply_to_groups alterado:', e.target.checked)
                    setAfterHoursMessage({ 
                      ...afterHoursMessage, 
                      reply_to_groups: e.target.checked 
                    })
                  }}
                  className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                />
                <Label htmlFor="reply_to_groups" className="cursor-pointer">
                  Responder em Grupos
                </Label>
              </div>
              <p className="text-sm text-gray-500 ml-6">
                Se habilitado, envia mensagem automática também para grupos. Se desabilitado, apenas para conversas individuais.
              </p>
            </div>

            <div className="flex justify-end">
              <Button
                onClick={handleSaveMessage}
                disabled={isSaving}
                className="flex items-center gap-2"
              >
                <Save className="h-4 w-4" />
                {isSaving ? 'Salvando...' : 'Salvar Mensagem'}
              </Button>
            </div>
          </div>
        </Card>
      )}

      {activeTab === 'tasks' && taskConfig && (
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
                    {users.map((user) => (
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
              <Button
                onClick={handleSaveTaskConfig}
                disabled={isSaving}
                className="flex items-center gap-2"
              >
                <Save className="h-4 w-4" />
                {isSaving ? 'Salvando...' : 'Salvar Configuração'}
              </Button>
            </div>
          </div>
        </Card>
      )}
    </div>
  )
}

