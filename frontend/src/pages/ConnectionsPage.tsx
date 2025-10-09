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
import { Plus, Wifi, WifiOff, Settings, TestTube, Edit, Trash2, QrCode, MessageSquare, X as XIcon } from 'lucide-react'

interface Connection {
  id: number
  name: string
  evo_ws_url: string
  is_active: boolean
  status: string
  created_at: string
  updated_at: string
}

interface WhatsAppInstance {
  id: string
  friendly_name: string
  instance_name: string
  phone_number: string
  status: string
  is_active: boolean
  is_default: boolean
  connection_state: string
  qr_code?: string
  qr_code_expires_at?: string
}

export default function ConnectionsPage() {
  const [connections, setConnections] = useState<Connection[]>([])
  const [instances, setInstances] = useState<WhatsAppInstance[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [showAddForm, setShowAddForm] = useState(false)
  const [showInstanceModal, setShowInstanceModal] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [editingInstance, setEditingInstance] = useState<WhatsAppInstance | null>(null)
  const [showQRModal, setShowQRModal] = useState(false)
  const [qrCodeData, setQrCodeData] = useState<{qr_code: string, expires_at: string} | null>(null)
  const [isGeneratingQR, setIsGeneratingQR] = useState(false)
  
  // Form data para WhatsApp Instance
  const [instanceForm, setInstanceForm] = useState({
    friendly_name: '',
    phone_number: '',
    is_default: false,
  })
  
  // Notificações toast
  const { toast, showToast, hideToast } = useToast()
  const { confirm, showConfirm, hideConfirm, handleConfirm } = useConfirm()

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      setIsLoading(true)
      // Buscar conexões
      const connectionsResponse = await api.get('/connections/')
      setConnections(connectionsResponse.data)
      
      // Buscar instâncias WhatsApp
      const instancesResponse = await api.get('/notifications/whatsapp-instances/')
      setInstances(instancesResponse.data.results || instancesResponse.data)
    } catch (error) {
      console.error('Failed to fetch data:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const toggleConnection = async (id: number) => {
    try {
      await api.post(`/connections/${id}/toggle/`)
      fetchData() // Refresh list
    } catch (error) {
      console.error('Failed to toggle connection:', error)
    }
  }

  const testConnection = async (id: number) => {
    try {
      await api.post(`/connections/${id}/test/`)
      // Show success message
    } catch (error) {
      console.error('Failed to test connection:', error)
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
        api_url: 'https://evo.rbtec.com.br', // Usar servidor padrão
        api_key: '', // Será preenchido quando conectar
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
      })
      setEditingInstance(null)
      setShowInstanceModal(false)
      
      // Atualizar lista
      fetchData()
      
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
      fetchData()
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
    })
    setEditingInstance(instance)
    setShowInstanceModal(true)
  }

  const handleGenerateQR = async (instance: WhatsAppInstance) => {
    setIsGeneratingQR(true)
    try {
      const response = await api.post(`/notifications/whatsapp-instances/${instance.id}/generate_qr/`)
      if (response.data.success) {
        setQrCodeData({
          qr_code: response.data.qr_code,
          expires_at: response.data.expires_at
        })
        setShowQRModal(true)
        showToast('✅ QR code gerado com sucesso!', 'success')
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
            fetchData()
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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Conexões</h1>
          <p className="text-gray-600">
            Gerencie suas conexões com a Evolution API e instâncias WhatsApp
          </p>
        </div>
        <div className="flex gap-2">
          <Button onClick={() => setShowInstanceModal(true)}>
            <MessageSquare className="h-4 w-4 mr-2" />
            Nova Instância WhatsApp
          </Button>
          <Button onClick={() => setShowAddForm(true)}>
            <Plus className="h-4 w-4 mr-2" />
            Nova Conexão
          </Button>
        </div>
      </div>

      {/* Connections List */}
      <div className="grid gap-6">
        {isLoading ? (
          <div className="flex items-center justify-center h-32">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          </div>
        ) : connections.length === 0 ? (
          <Card>
            <CardContent className="text-center py-12">
              <WifiOff className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-500 mb-4">Nenhuma conexão configurada</p>
              <Button onClick={() => setShowAddForm(true)}>
                <Plus className="h-4 w-4 mr-2" />
                Adicionar Primeira Conexão
              </Button>
            </CardContent>
          </Card>
        ) : (
          Array.isArray(connections) && connections.map((connection) => (
            <Card key={connection.id}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    {connection.is_active ? (
                      <Wifi className="h-5 w-5 text-green-600" />
                    ) : (
                      <WifiOff className="h-5 w-5 text-red-600" />
                    )}
                    <div>
                      <CardTitle>{connection.name}</CardTitle>
                      <CardDescription>
                        Criada em {formatDate(connection.created_at)}
                      </CardDescription>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => testConnection(connection.id)}
                    >
                      <TestTube className="h-4 w-4 mr-2" />
                      Testar
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => toggleConnection(connection.id)}
                    >
                      {connection.is_active ? 'Desativar' : 'Ativar'}
                    </Button>
                    <Button variant="outline" size="sm">
                      <Settings className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <div>
                    <span className="text-sm font-medium text-gray-500">URL:</span>
                    <p className="text-sm text-gray-900 font-mono">{connection.evo_ws_url}</p>
                  </div>
                  <div>
                    <span className="text-sm font-medium text-gray-500">Status:</span>
                    <span className={`ml-2 inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                      connection.is_active 
                        ? 'bg-green-100 text-green-800' 
                        : 'bg-red-100 text-red-800'
                    }`}>
                      {connection.is_active ? 'Ativa' : 'Inativa'}
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))
        )}
      </div>

      {/* WhatsApp Instances Section */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold text-gray-900">Instâncias WhatsApp</h2>
            <p className="text-gray-600">Gerencie suas instâncias WhatsApp conectadas</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Array.isArray(instances) && instances.map((instance) => (
            <Card key={instance.id} className="p-6 hover:shadow-md transition-shadow duration-200 border-0 shadow-sm">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-semibold text-gray-900">{instance.friendly_name}</h3>
                  {instance.phone_number && (
                    <p className="text-sm text-gray-600 mt-1">{instance.phone_number}</p>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
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
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                      Padrão
                    </span>
                  )}
                </div>
              </div>
              <div className="mt-4 flex gap-2">
                <Button 
                  variant="ghost" 
                  size="sm"
                  onClick={() => handleGenerateQR(instance)}
                  disabled={isGeneratingQR}
                  className="text-accent-600 hover:text-accent-700 hover:bg-accent-50"
                  title="Gerar QR Code"
                >
                  <QrCode className="h-4 w-4" />
                </Button>
                <Button 
                  variant="ghost" 
                  size="sm"
                  onClick={() => handleDisconnect(instance)}
                  className="text-orange-600 hover:text-orange-700 hover:bg-orange-50"
                  title="Desconectar"
                >
                  <WifiOff className="h-4 w-4" />
                </Button>
                <Button 
                  variant="ghost" 
                  size="sm"
                  onClick={() => handleEditInstance(instance)}
                >
                  <Edit className="h-4 w-4" />
                </Button>
                <Button 
                  variant="ghost" 
                  size="sm"
                  onClick={() => handleDeleteInstance(instance.id)}
                  className="text-red-600 hover:text-red-700 hover:bg-red-50"
                >
                  <Trash2 className="h-4 w-4" />
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
      </div>

      {/* Add Connection Form */}
      {showAddForm && (
        <Card>
          <CardHeader>
            <CardTitle>Nova Conexão</CardTitle>
            <CardDescription>
              Configure uma nova conexão com a Evolution API
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Nome da Conexão
                </label>
                <input
                  type="text"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Ex: WhatsApp Principal"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  URL WebSocket
                </label>
                <input
                  type="url"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="wss://sua-evolution-api.com/ws"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Token de Acesso
                </label>
                <input
                  type="password"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Seu token da Evolution API"
                />
              </div>
              
              <div className="flex gap-2">
                <Button type="submit">
                  <Plus className="h-4 w-4 mr-2" />
                  Criar Conexão
                </Button>
                <Button 
                  type="button" 
                  variant="outline"
                  onClick={() => setShowAddForm(false)}
                >
                  Cancelar
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

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
                  src={`data:image/png;base64,${qrCodeData.qr_code}`}
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
                  onClick={() => handleGenerateQR(editingInstance!)}
                  disabled={isGeneratingQR}
                >
                  {isGeneratingQR ? 'Gerando...' : 'Atualizar QR'}
                </Button>
                <Button
                  onClick={() => setShowQRModal(false)}
                >
                  Fechar
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
