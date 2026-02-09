import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Label } from '../components/ui/Label'
import Toast from '../components/ui/Toast'
import ConfirmDialog from '../components/ui/ConfirmDialog'
import { useToast } from '../hooks/useToast'
import { useConfirm } from '../hooks/useConfirm'
import { api } from '../lib/api'
import { formatDate } from '../lib/utils'
import { WifiOff, Edit, Trash2, QrCode, MessageSquare, X as XIcon, Check, Eye, EyeOff } from 'lucide-react'

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
  api_key?: string
}

export default function ConnectionsPage() {
  const [instances, setInstances] = useState<WhatsAppInstance[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [showInstanceModal, setShowInstanceModal] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [editingInstance, setEditingInstance] = useState<WhatsAppInstance | null>(null)
  const [showQRModal, setShowQRModal] = useState(false)
  const [qrCodeData, setQrCodeData] = useState<{qr_code: string, expires_at: string} | null>(null)
  const [qrInstance, setQrInstance] = useState<WhatsAppInstance | null>(null)
  const [isGeneratingQR, setIsGeneratingQR] = useState(false)
  const [visibleApiKeys, setVisibleApiKeys] = useState<Set<string>>(new Set())
  const [showTestModal, setShowTestModal] = useState(false)
  const [testInstance, setTestInstance] = useState<WhatsAppInstance | null>(null)
  const [testPhone, setTestPhone] = useState('')
  const [isSendingTest, setIsSendingTest] = useState(false)
  
  // Função para formatar telefone
  const formatPhone = (phone: string) => {
    if (!phone) return ''
    // Remove caracteres não numéricos
    const numbers = phone.replace(/\D/g, '')
    
    // Formato brasileiro: +55 17 99125-3112
    if (numbers.length === 13 && numbers.startsWith('55')) {
      const ddi = numbers.substring(0, 2)
      const ddd = numbers.substring(2, 4)
      const part1 = numbers.substring(4, 9)
      const part2 = numbers.substring(9, 13)
      return `+${ddi} ${ddd} ${part1}-${part2}`
    }
    
    // Outros formatos: apenas +XX XXXXXXXXX
    return `+${numbers}`
  }
  
  // Form data para WhatsApp Instance
  const [instanceForm, setInstanceForm] = useState({
    friendly_name: '',
    phone_number: '',
    is_default: false,
    default_department: null as string | null,
  })
  
  // Lista de departamentos para o select
  const [departments, setDepartments] = useState<Array<{id: string, name: string}>>([])
  
  // Notificações toast
  const { toast, showToast, hideToast } = useToast()
  const { confirm, showConfirm, hideConfirm, handleConfirm } = useConfirm()

  useEffect(() => {
    fetchData()
    fetchDepartments()
  }, [])
  
  const fetchDepartments = async () => {
    try {
      const response = await api.get('/auth/departments/')
      const depts = Array.isArray(response.data) ? response.data : (response.data?.results || [])
      setDepartments(depts.map((d: any) => ({ id: d.id, name: d.name })))
    } catch (error) {
      console.error('Erro ao buscar departamentos:', error)
    }
  }

  const fetchData = async (forceRefresh = false) => {
    try {
      setIsLoading(true)
      // ✅ MELHORIA: Adicionar parâmetro _refresh para forçar busca do banco
      const url = forceRefresh
        ? '/notifications/whatsapp-instances/?_refresh=true'
        : '/notifications/whatsapp-instances/'
      
      const instancesResponse = await api.get(url)
      const instances = instancesResponse.data.results || instancesResponse.data
      setInstances(instances)
      console.log(`✅ [INSTANCES] Carregadas ${instances.length} instâncias (refresh: ${forceRefresh})`)
    } catch (error) {
      console.error('Failed to fetch instances:', error)
    } finally {
      setIsLoading(false)
    }
  }


  // ==================== WhatsApp Instance Functions ====================
  
  const handleSaveInstance = async () => {
    // Validação dos campos obrigatórios
    if (!instanceForm.friendly_name.trim()) {
      showToast('❌ Nome amigável é obrigatório', 'error')
      return
    }

    setIsSaving(true)
    try {
      // Preparar dados para envio
      const instanceData = {
        ...instanceForm,
        instance_name: crypto.randomUUID(), // Gerar UUID automaticamente
        // api_url será obtido do servidor Evolution global configurado no backend
        // Não enviar api_url nem api_key - backend gerencia isso
      }

      if (editingInstance) {
        // Editar instância existente
        const response = await api.patch(`/notifications/whatsapp-instances/${editingInstance.id}/`, instanceData)
        showToast('✅ Instância WhatsApp atualizada com sucesso!', 'success')
      } else {
        // Criar nova instância
        const response = await api.post('/notifications/whatsapp-instances/', instanceData)
        showToast('✅ Instância WhatsApp criada com sucesso!', 'success')
      }
      
      // Limpar formulário e fechar modal
      setInstanceForm({
        friendly_name: '',
        phone_number: '',
        is_default: false,
        default_department: null,
      })
      setEditingInstance(null)
      setShowInstanceModal(false)
      
      // ✅ MELHORIA: Aguardar um pouco e forçar refresh para garantir dados atualizados
      await new Promise(resolve => setTimeout(resolve, 300)) // 300ms de delay
      await fetchData(true) // Forçar refresh
      
    } catch (error: any) {
      console.error('❌ Erro ao salvar instância:', error)
      if (error.response?.data) {
        // Mostrar erros específicos do backend
        const errors = error.response.data
        let errorMessage = '❌ Erro ao salvar: '
        Object.keys(errors).forEach(field => {
          if (Array.isArray(errors[field])) {
            errorMessage += `${field}: ${errors[field][0]} `
          }
        })
        showToast(errorMessage, 'error')
      } else {
        showToast(`❌ Erro ao salvar: ${error.message}`, 'error')
      }
    } finally {
      setIsSaving(false)
    }
  }

  const handleDeleteInstance = async (id: string) => {
    showConfirm(
      'Excluir Instância WhatsApp',
      'Tem certeza que deseja excluir esta instância WhatsApp? Esta ação não pode ser desfeita.',
      () => deleteInstance(id)
    )
  }

  const deleteInstance = async (id: string) => {
    try {
      await api.delete(`/notifications/whatsapp-instances/${id}/`)
      showToast('✅ Instância WhatsApp excluída com sucesso!', 'success')
      // ✅ MELHORIA: Aguardar um pouco e forçar refresh para garantir dados atualizados
      await new Promise(resolve => setTimeout(resolve, 300)) // 300ms de delay
      await fetchData(true) // Forçar refresh
    } catch (error: any) {
      console.error('❌ Erro ao excluir instância:', error)
      showToast(`❌ Erro ao excluir instância: ${error.response?.data?.detail || error.message}`, 'error')
    }
  }

  const handleEditInstance = (instance: WhatsAppInstance) => {
    setInstanceForm({
      friendly_name: instance.friendly_name,
      phone_number: instance.phone_number || '',
      is_default: instance.is_default,
      default_department: (instance as any).default_department || null,
    })
    setEditingInstance(instance)
    setShowInstanceModal(true)
  }

  const handleGenerateQR = async (instance: WhatsAppInstance) => {
    setIsGeneratingQR(true)
    setQrInstance(instance) // Salvar instância para usar no modal
    try {
      const response = await api.post(`/notifications/whatsapp-instances/${instance.id}/generate_qr/`)
      if (response.data.success) {
        setQrCodeData({
          qr_code: response.data.qr_code,
          expires_at: response.data.expires_at
        })
        setShowQRModal(true)
        showToast('✅ QR code gerado com sucesso! Aguardando conexão...', 'success')
        
        // Iniciar polling para verificar status (a cada 5 segundos por 3 minutos)
        let checks = 0
        const maxChecks = 36 // 36 checks * 5s = 3 minutos
        const checkInterval = setInterval(async () => {
          checks++
          console.log(`🔄 Verificando conexão... (tentativa ${checks}/${maxChecks})`)
          
          try {
            const statusResponse = await api.post(`/notifications/whatsapp-instances/${instance.id}/check_status/`)
            
            if (statusResponse.data.success) {
              const connectionState = statusResponse.data.connection_state
              console.log(`📱 Estado atual: ${connectionState}`)
              
            if (connectionState === 'open') {
              clearInterval(checkInterval)
              setShowQRModal(false)
              setQrInstance(null)
              // ✅ MELHORIA: Forçar refresh após conectar
              await new Promise(resolve => setTimeout(resolve, 300))
              await fetchData(true) // Recarregar lista para mostrar número e status atualizado
              showToast('🎉 WhatsApp conectado com sucesso!', 'success')
              console.log('✅ WhatsApp conectado! Polling encerrado.')
            }
            }
          } catch (err: any) {
            // Não mostrar erro para o usuário durante polling (pode ser temporário)
            console.log(`⚠️ Erro ao verificar (ignorando): ${err.message}`)
          }
          
          if (checks >= maxChecks) {
            clearInterval(checkInterval)
            console.log('⏱️ Tempo limite atingido. Polling encerrado.')
            showToast('⏱️ Tempo limite para conexão. Tente verificar status manualmente.', 'warning')
          }
        }, 5000) // 5 segundos entre cada verificação
        
        // Limpar interval quando fechar o modal
        const originalClose = () => setShowQRModal(false)
        // Guardar referência do interval para limpar depois
        ;(window as any).__qrCheckInterval = checkInterval
      } else {
        showToast(`❌ Erro ao gerar QR code: ${response.data.error}`, 'error')
      }
    } catch (error: any) {
      console.error('❌ Erro ao gerar QR code:', error)
      showToast(`❌ Erro ao gerar QR code: ${error.response?.data?.error || error.message}`, 'error')
    } finally {
      setIsGeneratingQR(false)
    }
  }

  const handleDisconnect = async (instance: WhatsAppInstance) => {
    showConfirm(
      'Desconectar Instância',
      `Tem certeza que deseja desconectar a instância "${instance.friendly_name}"?`,
      async () => {
        try {
          const response = await api.post(`/notifications/whatsapp-instances/${instance.id}/disconnect/`)
          if (response.data.success) {
            showToast('✅ Instância desconectada com sucesso!', 'success')
            // ✅ MELHORIA: Forçar refresh após desconectar
            await new Promise(resolve => setTimeout(resolve, 300))
            await fetchData(true)
          } else {
            showToast(`❌ Erro ao desconectar: ${response.data.error}`, 'error')
          }
        } catch (error: any) {
          console.error('❌ Erro ao desconectar:', error)
          showToast(`❌ Erro ao desconectar: ${error.response?.data?.error || error.message}`, 'error')
        }
      }
    )
  }

  const handleCheckStatus = async (instance: WhatsAppInstance) => {
    try {
      const response = await api.post(`/notifications/whatsapp-instances/${instance.id}/check_status/`)
      if (response.data.success) {
        showToast('✅ Status verificado com sucesso!', 'success')
        // ✅ MELHORIA: Forçar refresh após verificar status
        await new Promise(resolve => setTimeout(resolve, 300))
        await fetchData(true)
      } else {
        showToast(`❌ Erro ao verificar status: ${response.data.error}`, 'error')
      }
    } catch (error: any) {
      console.error('❌ Erro ao verificar status:', error)
      showToast(`❌ Erro ao verificar status: ${error.response?.data?.error || error.message}`, 'error')
    }
  }

  const handleOpenTestModal = (instance: WhatsAppInstance) => {
    setTestInstance(instance)
    setTestPhone(instance.phone_number || '') // Pré-preencher com número da instância se disponível
    setShowTestModal(true)
  }

  const handleSendTest = async () => {
    if (!testInstance) return
    
    // Validar telefone
    if (!testPhone.trim()) {
      showToast('❌ Digite um número de telefone', 'error')
      return
    }

    setIsSendingTest(true)
    try {
      const response = await api.post(`/notifications/whatsapp-instances/${testInstance.id}/send_test/`, {
        phone: testPhone
      })
      if (response.data.success) {
        showToast('✅ Mensagem de teste enviada com sucesso!', 'success')
        setShowTestModal(false)
        setTestPhone('')
      } else {
        showToast(`❌ Erro ao enviar: ${response.data.error}`, 'error')
      }
    } catch (error: any) {
      console.error('❌ Erro ao enviar mensagem de teste:', error)
      showToast(`❌ Erro ao enviar: ${error.response?.data?.error || error.message}`, 'error')
    } finally {
      setIsSendingTest(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Instâncias WhatsApp</h1>
          <p className="text-gray-600">
            Gerencie suas instâncias WhatsApp conectadas
          </p>
        </div>
        <Button onClick={() => setShowInstanceModal(true)}>
          <MessageSquare className="h-4 w-4 mr-2" />
          Nova Instância WhatsApp
        </Button>
      </div>

      {/* WhatsApp Instances Section */}
      <div className="space-y-4">
        {isLoading ? (
          <div className="flex items-center justify-center h-32">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          </div>
        ) : (
          <>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {Array.isArray(instances) && instances.map((instance) => (
            <Card key={instance.id} className="p-3 hover:shadow-md transition-shadow duration-200 border-0 shadow-sm">
              {/* Header com nome e badges - mais compacto */}
              <div className="flex items-center justify-between mb-1.5">
                <h3 className="font-semibold text-gray-900 text-sm">{instance.friendly_name}</h3>
                <div className="flex items-center gap-1 flex-shrink-0">
                  <span className={`inline-flex items-center px-1.5 py-0.5 rounded-full text-xs font-medium ${
                    instance.connection_state === 'open' 
                      ? 'bg-green-100 text-green-800' 
                      : instance.connection_state === 'connecting'
                      ? 'bg-yellow-100 text-yellow-800'
                      : 'bg-red-100 text-red-800'
                  }`}>
                    {instance.connection_state === 'open' ? 'Conectado' : 
                     instance.connection_state === 'connecting' ? 'Conectando' : 'Desconectado'}
                  </span>
                  {instance.is_default && (
                    <span className="inline-flex items-center px-1.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                      Padrão
                    </span>
                  )}
                </div>
              </div>
              
              {/* Conteúdo principal - telefone e API key */}
              <div className="space-y-1">
                {instance.phone_number && (
                  <p className="text-xs text-gray-600">📱 {formatPhone(instance.phone_number)}</p>
                )}
                {instance.api_key && (
                  <div className="flex items-center gap-1">
                    <span className="text-xs">🔑</span>
                    <p className="text-xs text-gray-600 font-mono break-all">
                      {visibleApiKeys.has(instance.id) ? instance.api_key : '••••••••••••••••••••••••••••••'}
                    </p>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        setVisibleApiKeys(prev => {
                          const next = new Set(prev)
                          if (next.has(instance.id)) {
                            next.delete(instance.id)
                          } else {
                            next.add(instance.id)
                          }
                          return next
                        })
                      }}
                      className="text-gray-400 hover:text-gray-600 flex-shrink-0 ml-1"
                      title={visibleApiKeys.has(instance.id) ? 'Ocultar API Key' : 'Mostrar API Key'}
                    >
                      {visibleApiKeys.has(instance.id) ? '👁️' : '👁️‍🗨️'}
                    </button>
                  </div>
                )}
                {!instance.api_key && instance.instance_name && (
                  <p className="text-xs text-gray-400 italic">API Key será gerada ao conectar</p>
                )}
              </div>
              <div className="mt-2 flex gap-1">
                <Button 
                  variant="ghost" 
                  size="sm"
                  onClick={() => handleGenerateQR(instance)}
                  disabled={isGeneratingQR}
                  className="text-accent-600 hover:text-accent-700 hover:bg-accent-50"
                  title="Gerar QR Code"
                >
                  <QrCode className="h-3 w-3" />
                </Button>
                <Button 
                  variant="ghost" 
                  size="sm"
                  onClick={() => handleCheckStatus(instance)}
                  className="text-green-600 hover:text-green-700 hover:bg-green-50"
                  title="Verificar Status"
                >
                  <Check className="h-3 w-3" />
                </Button>
                <Button 
                  variant="ghost" 
                  size="sm"
                  onClick={() => handleOpenTestModal(instance)}
                  disabled={instance.connection_state !== 'open'}
                  className={`${
                    instance.connection_state === 'open' 
                      ? 'text-blue-600 hover:text-blue-700 hover:bg-blue-50' 
                      : 'text-gray-300 cursor-not-allowed'
                  }`}
                  title={instance.connection_state === 'open' ? 'Enviar Mensagem de Teste' : 'Conecte a instância primeiro'}
                >
                  <MessageSquare className="h-3 w-3" />
                </Button>
                <Button 
                  variant="ghost" 
                  size="sm"
                  onClick={() => handleDisconnect(instance)}
                  disabled={instance.connection_state !== 'open'}
                  className={`${
                    instance.connection_state === 'open' 
                      ? 'text-orange-600 hover:text-orange-700 hover:bg-orange-50' 
                      : 'text-gray-300 cursor-not-allowed'
                  }`}
                  title={instance.connection_state === 'open' ? 'Desconectar' : 'Instância não conectada'}
                >
                  <WifiOff className="h-3 w-3" />
                </Button>
                <Button 
                  variant="ghost" 
                  size="sm"
                  onClick={() => handleEditInstance(instance)}
                >
                  <Edit className="h-3 w-3" />
                </Button>
                <Button 
                  variant="ghost" 
                  size="sm"
                  onClick={() => handleDeleteInstance(instance.id)}
                  className="text-red-600 hover:text-red-700 hover:bg-red-50"
                >
                  <Trash2 className="h-3 w-3" />
                </Button>
              </div>
            </Card>
          ))}
          
          {(!Array.isArray(instances) || instances.length === 0) && (
            <Card className="col-span-full">
              <CardContent className="text-center py-12">
                <MessageSquare className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-500 mb-4">Nenhuma instância WhatsApp configurada</p>
                <Button onClick={() => setShowInstanceModal(true)}>
                  <MessageSquare className="h-4 w-4 mr-2" />
                  Adicionar Primeira Instância
                </Button>
              </CardContent>
            </Card>
          )}
        </div>
          </>
        )}
      </div>

      {/* WhatsApp Instance Modal */}
      {showInstanceModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900">
                {editingInstance ? 'Editar Instância WhatsApp' : 'Nova Instância WhatsApp'}
              </h3>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setShowInstanceModal(false)
                  setEditingInstance(null)
                  setInstanceForm({
                    friendly_name: '',
                    phone_number: '',
                    is_default: false,
                    default_department: null,
                  })
                }}
              >
                <XIcon className="h-4 w-4" />
              </Button>
            </div>
            
            <div className="space-y-4">
              <div>
                <Label htmlFor="friendly_name">Nome Amigável *</Label>
                <Input
                  id="friendly_name"
                  value={instanceForm.friendly_name}
                  onChange={(e) => setInstanceForm({ ...instanceForm, friendly_name: e.target.value })}
                  placeholder="Ex: WhatsApp Suporte"
                  required
                />
                <p className="text-xs text-gray-500 mt-1">Nome amigável para identificar esta instância</p>
              </div>
              
              <div>
                <Label htmlFor="phone_number">Número de Telefone</Label>
                <Input
                  id="phone_number"
                  value={instanceForm.phone_number}
                  onChange={(e) => setInstanceForm({ ...instanceForm, phone_number: e.target.value })}
                  placeholder="Ex: 5517991234567"
                />
                <p className="text-xs text-gray-500 mt-1">Número do WhatsApp (opcional, será preenchido automaticamente ao conectar)</p>
              </div>
              
              <div>
                <Label htmlFor="default_department">Departamento Padrão</Label>
                <select
                  id="default_department"
                  value={instanceForm.default_department || ''}
                  onChange={(e) => setInstanceForm({ ...instanceForm, default_department: e.target.value || null })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  <option value="">Inbox (sem departamento)</option>
                  {departments.map((dept) => (
                    <option key={dept.id} value={dept.id}>
                      {dept.name}
                    </option>
                  ))}
                </select>
                <p className="text-xs text-gray-500 mt-1">
                  Novas conversas desta instância irão automaticamente para este departamento. Deixe em branco para ir para Inbox.
                </p>
              </div>
              
              <div className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  id="is_default"
                  checked={instanceForm.is_default}
                  onChange={(e) => setInstanceForm({ ...instanceForm, is_default: e.target.checked })}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <Label htmlFor="is_default" className="text-sm">
                  Definir como instância padrão
                </Label>
              </div>
              
              <div className="bg-blue-50 p-3 rounded-lg">
                <p className="text-sm text-blue-800">
                  <strong>Dica:</strong> Após salvar, use "Gerar QR Code" para conectar a instância ao WhatsApp.
                </p>
              </div>
            </div>
            
            <div className="flex gap-2 justify-end mt-6">
              <Button
                variant="outline"
                onClick={() => {
                  setShowInstanceModal(false)
                  setEditingInstance(null)
                  setInstanceForm({
                    friendly_name: '',
                    phone_number: '',
                    is_default: false,
                    default_department: null,
                  })
                }}
              >
                Cancelar
              </Button>
              <Button
                onClick={handleSaveInstance}
                disabled={isSaving}
              >
                {isSaving ? 'Salvando...' : 'Salvar Instância'}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* QR Code Modal */}
      {showQRModal && qrCodeData && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900">Conectar WhatsApp</h3>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowQRModal(false)}
              >
                <XIcon className="h-4 w-4" />
              </Button>
            </div>
            
            <div className="text-center">
              <div className="mb-4">
                <img 
                  src={
                    qrCodeData.qr_code.startsWith('data:') 
                      ? qrCodeData.qr_code 
                      : `data:image/png;base64,${qrCodeData.qr_code}`
                  }
                  alt="QR Code para conectar WhatsApp"
                  className="mx-auto border border-gray-200 rounded-lg"
                />
              </div>
              
              <p className="text-sm text-gray-600 mb-4">
                Escaneie o QR Code com seu WhatsApp para conectar a instância
              </p>
              
              {qrCodeData.expires_at && (
                <p className="text-xs text-gray-500 mb-4">
                  Expira em: {new Date(qrCodeData.expires_at).toLocaleString()}
                </p>
              )}
              
              <div className="flex gap-2 justify-center">
                <Button
                  variant="outline"
                  onClick={() => qrInstance && handleGenerateQR(qrInstance)}
                  disabled={isGeneratingQR || !qrInstance}
                >
                  {isGeneratingQR ? 'Gerando...' : 'Atualizar QR'}
                </Button>
                <Button
                  onClick={() => {
                    // Limpar interval de verificação
                    if ((window as any).__qrCheckInterval) {
                      clearInterval((window as any).__qrCheckInterval)
                    }
                    setShowQRModal(false)
                    setQrInstance(null)
                  }}
                >
                  Fechar
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modal Teste de Mensagem */}
      {showTestModal && testInstance && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg max-w-md w-full">
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-900">
                  📱 Enviar Mensagem de Teste
                </h3>
                <button
                  onClick={() => {
                    setShowTestModal(false)
                    setTestPhone('')
                    setTestInstance(null)
                  }}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <XIcon className="h-5 w-5" />
                </button>
              </div>

              <div className="space-y-4">
                <div>
                  <p className="text-sm text-gray-600 mb-4">
                    Instância: <strong>{testInstance.friendly_name}</strong>
                  </p>
                  <Label htmlFor="test-phone">
                    Número de Telefone (com DDI)
                  </Label>
                  <Input
                    id="test-phone"
                    type="text"
                    placeholder="5511999999999"
                    value={testPhone}
                    onChange={(e) => setTestPhone(e.target.value)}
                    className="mt-1"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Formato: DDI + DDD + Número (ex: 5511999999999)
                  </p>
                </div>

                <div className="bg-blue-50 p-3 rounded-lg">
                  <p className="text-sm text-blue-800">
                    <strong>💬 Mensagem:</strong> "Olá! Esta é uma mensagem de teste da Alrea Sense."
                  </p>
                </div>
              </div>

              <div className="flex gap-2 justify-end mt-6">
                <Button
                  variant="outline"
                  onClick={() => {
                    setShowTestModal(false)
                    setTestPhone('')
                    setTestInstance(null)
                  }}
                >
                  Cancelar
                </Button>
                <Button
                  onClick={handleSendTest}
                  disabled={isSendingTest || !testPhone.trim()}
                >
                  {isSendingTest ? 'Enviando...' : 'Enviar Teste'}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Toast */}
      <Toast
        show={toast.show}
        message={toast.message}
        type={toast.type}
        onClose={hideToast}
      />

      {/* Confirm Dialog */}
      <ConfirmDialog
        show={confirm.show}
        title={confirm.title}
        message={confirm.message}
        confirmText={confirm.confirmText}
        cancelText={confirm.cancelText}
        variant={confirm.variant}
        onConfirm={handleConfirm}
        onCancel={hideConfirm}
      />
    </div>
  )
}
