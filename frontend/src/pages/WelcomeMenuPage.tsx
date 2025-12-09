import { useState, useEffect } from 'react'
import { 
  MessageSquare, 
  Save, 
  Plus, 
  X, 
  AlertCircle,
  Info,
  Check,
  Eye,
  EyeOff,
  Lock
} from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Input } from '../components/ui/Input'
import { Label } from '../components/ui/Label'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import { api } from '../lib/api'
import { showSuccessToast, showErrorToast } from '../lib/toastHelper'

interface Department {
  id: string
  name: string
  color: string
}

interface WelcomeMenuConfig {
  id: string
  tenant: string
  tenant_name: string
  enabled: boolean
  welcome_message: string
  departments: Department[]
  department_ids: string[]
  show_close_option: boolean
  close_option_text: string
  send_to_new_conversations: boolean
  send_to_closed_conversations: boolean
  ai_enabled: boolean
  created_at: string
  updated_at: string
}

export default function WelcomeMenuPage() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [config, setConfig] = useState<WelcomeMenuConfig | null>(null)
  const [availableDepartments, setAvailableDepartments] = useState<Department[]>([])
  const [preview, setPreview] = useState<string>('')
  const [showPreview, setShowPreview] = useState(false)

  useEffect(() => {
    loadConfig()
    loadDepartments()
  }, [])

  useEffect(() => {
    if (config) {
      generatePreview()
    }
  }, [config])

  const loadConfig = async () => {
    try {
      setLoading(true)
      const response = await api.get('/chat/welcome-menu-config/')
      setConfig(response.data)
    } catch (error: any) {
      console.error('Erro ao carregar configuração:', error)
      showErrorToast('Erro ao carregar configuração do menu')
    } finally {
      setLoading(false)
    }
  }

  const loadDepartments = async () => {
    try {
      const response = await api.get('/chat/welcome-menu-config/available_departments/')
      setAvailableDepartments(response.data)
    } catch (error: any) {
      console.error('Erro ao carregar departamentos:', error)
    }
  }

  const generatePreview = () => {
    if (!config) return
    
    const welcome = config.welcome_message || `Bem-vindo a ${config.tenant_name}!`
    const departments = config.departments || []
    const lines = [welcome, '', 'Escolha uma opção para atendimento:', '']
    
    departments.forEach((dept, idx) => {
      lines.push(`${idx + 1} - ${dept.name}`)
    })
    
    if (config.show_close_option) {
      lines.push(`${departments.length + 1} - ${config.close_option_text}`)
    }
    
    setPreview(lines.join('\n'))
  }

  const handleSave = async () => {
    if (!config) return
    
    // Validação
    if (config.enabled && (!config.department_ids || config.department_ids.length === 0)) {
      showErrorToast('Selecione pelo menos um departamento quando o menu estiver habilitado')
      return
    }
    
    try {
      setSaving(true)
      await api.post('/chat/welcome-menu-config/', {
        enabled: config.enabled,
        welcome_message: config.welcome_message,
        department_ids: config.department_ids || [],
        show_close_option: config.show_close_option,
        close_option_text: config.close_option_text,
        send_to_new_conversations: config.send_to_new_conversations,
        send_to_closed_conversations: config.send_to_closed_conversations
      })
      
      showSuccessToast('Configuração salva com sucesso!')
      await loadConfig()
    } catch (error: any) {
      console.error('Erro ao salvar configuração:', error)
      const errorMsg = error.response?.data?.error || error.response?.data?.detail || 'Erro ao salvar configuração'
      showErrorToast(errorMsg)
    } finally {
      setSaving(false)
    }
  }

  const toggleDepartment = (deptId: string) => {
    if (!config) return
    
    const currentIds = config.department_ids || []
    const newIds = currentIds.includes(deptId)
      ? currentIds.filter(id => id !== deptId)
      : [...currentIds, deptId]
    
    // Atualizar lista de departamentos selecionados
    const selectedDepts = availableDepartments.filter(d => newIds.includes(d.id))
    
    setConfig({
      ...config,
      department_ids: newIds,
      departments: selectedDepts
    })
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (!config) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <p className="text-gray-600">Erro ao carregar configuração</p>
        </div>
      </div>
    )
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-4xl">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white flex items-center gap-3">
          <MessageSquare className="w-8 h-8" />
          Menu de Boas-Vindas Automático
        </h1>
        <p className="text-gray-600 dark:text-gray-400 mt-2">
          Configure o menu automático que será enviado para conversas novas ou fechadas
        </p>
      </div>

      <Card className="p-6 mb-6">
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
                checked={config.enabled}
                onChange={(e) => setConfig({ ...config, enabled: e.target.checked })}
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
              value={config.welcome_message}
              onChange={(e) => setConfig({ ...config, welcome_message: e.target.value })}
              placeholder={`Bem-vindo a ${config.tenant_name}!`}
              maxLength={500}
              className="mt-1"
            />
            <p className="text-xs text-gray-500 mt-1">
              Mensagem exibida antes do menu. Use {'{tenant_name}'} para incluir o nome do tenant.
            </p>
          </div>

          {/* Departamentos */}
          <div>
            <Label>Departamentos no Menu</Label>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
              Selecione os departamentos que aparecerão no menu (em ordem)
            </p>
            {availableDepartments.length === 0 ? (
              <div className="p-4 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg border border-yellow-200 dark:border-yellow-800">
                <div className="flex items-center gap-2 text-yellow-800 dark:text-yellow-200">
                  <AlertCircle className="w-5 h-5" />
                  <p className="text-sm">Nenhum departamento disponível. Crie departamentos primeiro.</p>
                </div>
              </div>
            ) : (
              <div className="space-y-2">
                {availableDepartments.map((dept) => {
                  const isSelected = config.department_ids?.includes(dept.id) || false
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
                        onChange={() => toggleDepartment(dept.id)}
                        className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                      />
                      <div
                        className="w-4 h-4 rounded-full"
                        style={{ backgroundColor: dept.color }}
                      />
                      <span className="flex-1 font-medium">{dept.name}</span>
                      {isSelected && (
                        <span className="text-xs text-blue-600 dark:text-blue-400">
                          #{config.department_ids?.indexOf(dept.id)! + 1}
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
                checked={config.show_close_option}
                onChange={(e) => setConfig({ ...config, show_close_option: e.target.checked })}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
            </label>
          </div>

          {config.show_close_option && (
            <div>
              <Label htmlFor="close_option_text">Texto da Opção Encerrar</Label>
              <Input
                id="close_option_text"
                value={config.close_option_text}
                onChange={(e) => setConfig({ ...config, close_option_text: e.target.value })}
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
                checked={config.send_to_new_conversations}
                onChange={(e) => setConfig({ ...config, send_to_new_conversations: e.target.checked })}
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
                checked={config.send_to_closed_conversations}
                onChange={(e) => setConfig({ ...config, send_to_closed_conversations: e.target.checked })}
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
                onClick={() => setShowPreview(!showPreview)}
              >
                {showPreview ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                {showPreview ? 'Ocultar' : 'Mostrar'}
              </Button>
            </div>
            {showPreview && (
              <div className="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
                <pre className="whitespace-pre-wrap text-sm font-mono text-gray-700 dark:text-gray-300">
                  {preview}
                </pre>
              </div>
            )}
          </div>
        </div>
      </Card>

      {/* Botão Salvar */}
      <div className="flex justify-end gap-3">
        <Button
          onClick={handleSave}
          disabled={saving || (config.enabled && (!config.department_ids || config.department_ids.length === 0))}
          className="flex items-center gap-2"
        >
          {saving ? (
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
  )
}

