import { useState, useEffect } from 'react'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Label } from '../components/ui/Label'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import { Bell, Mail, MessageSquare, Plus, Server, FileText, Eye, Trash2, Edit, Send, Check, X as XIcon } from 'lucide-react'
import { api } from '../lib/api'

interface NotificationTemplate {
  id: string
  name: string
  type: 'email' | 'whatsapp'
  category: string
  subject: string
  content: string
  is_active: boolean
  tenant_name: string
}

interface WhatsAppInstance {
  id: string
  name: string
  instance_name: string
  phone_number: string
  status: string
  is_active: boolean
  is_default: boolean
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

export default function NotificationsPage() {
  const [activeTab, setActiveTab] = useState<'templates' | 'instances' | 'smtp' | 'logs'>('templates')
  const [templates, setTemplates] = useState<NotificationTemplate[]>([])
  const [instances, setInstances] = useState<WhatsAppInstance[]>([])
  const [smtpConfigs, setSmtpConfigs] = useState<SMTPConfig[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [testEmailModal, setTestEmailModal] = useState<{ show: boolean, smtpId: string | null }>({ show: false, smtpId: null })
  const [testEmail, setTestEmail] = useState('')
  const [isTesting, setIsTesting] = useState(false)
  
  // Modals de cadastro
  const [showSMTPModal, setShowSMTPModal] = useState(false)
  const [showTemplateModal, setShowTemplateModal] = useState(false)
  const [showInstanceModal, setShowInstanceModal] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [editingSMTP, setEditingSMTP] = useState<SMTPConfig | null>(null)
  
  // Notificações toast
  const [toast, setToast] = useState<{ show: boolean, message: string, type: 'success' | 'error' }>({
    show: false,
    message: '',
    type: 'success'
  })
  
  // Form data para SMTP
  const [smtpForm, setSMTPForm] = useState({
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
  })

  useEffect(() => {
    fetchData()
  }, [activeTab])

  // Função para mostrar toast
  const showToast = (message: string, type: 'success' | 'error') => {
    setToast({ show: true, message, type })
    setTimeout(() => {
      setToast({ show: false, message: '', type: 'success' })
    }, 4000) // Auto-hide após 4 segundos
  }

  const fetchData = async () => {
    setIsLoading(true)
    try {
      if (activeTab === 'templates') {
        const response = await api.get('/notifications/templates/')
        setTemplates(Array.isArray(response.data) ? response.data : [])
      } else if (activeTab === 'instances') {
        const response = await api.get('/notifications/whatsapp-instances/')
        setInstances(Array.isArray(response.data) ? response.data : [])
      } else if (activeTab === 'smtp') {
        console.log('🔍 Fetching SMTP configs...')
        const response = await api.get('/notifications/smtp-configs/')
        console.log('📧 SMTP response:', response.data)
        const smtpData = Array.isArray(response.data) ? response.data : response.data?.results || []
        console.log('📧 SMTP data to set:', smtpData)
        setSmtpConfigs(smtpData)
        console.log('📧 SMTP configs state updated')
      }
    } catch (error) {
      console.error('Error fetching data:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleTestSMTP = async () => {
    if (!testEmailModal.smtpId || !testEmail) return
    
    setIsTesting(true)
    try {
      const response = await api.post(`/notifications/smtp-configs/${testEmailModal.smtpId}/test/`, {
        test_email: testEmail
      })
      
      if (response.data.success) {
        showToast('✅ Email de teste enviado com sucesso!', 'success')
      } else {
        showToast(`❌ Erro: ${response.data.message}`, 'error')
      }
      
      setTestEmailModal({ show: false, smtpId: null })
      setTestEmail('')
      fetchData()
    } catch (error: any) {
      showToast(`❌ Erro ao enviar email de teste: ${error.response?.data?.message || error.message}`, 'error')
    } finally {
      setIsTesting(false)
    }
  }

  const handleSaveSMTP = async () => {
    // Validação dos campos obrigatórios
    if (!smtpForm.name.trim()) {
      showToast('❌ Nome da configuração é obrigatório', 'error')
      return
    }
    if (!smtpForm.host.trim()) {
      showToast('❌ Servidor SMTP é obrigatório', 'error')
      return
    }
    if (!smtpForm.username.trim()) {
      showToast('❌ Usuário/Email é obrigatório', 'error')
      return
    }
    if (!smtpForm.password.trim()) {
      showToast('❌ Senha é obrigatória', 'error')
      return
    }
    if (!smtpForm.from_email.trim()) {
      showToast('❌ Email remetente é obrigatório', 'error')
      return
    }

    setIsSaving(true)
    try {
      let response
      if (editingSMTP) {
        // Editando servidor existente
        response = await api.patch(`/notifications/smtp-configs/${editingSMTP.id}/`, smtpForm)
        console.log('✅ SMTP config atualizado:', response.data)
        showToast('✅ Servidor SMTP atualizado com sucesso!', 'success')
      } else {
        // Criando novo servidor
        response = await api.post('/notifications/smtp-configs/', smtpForm)
        console.log('✅ SMTP config criado:', response.data)
        showToast('✅ Servidor SMTP cadastrado com sucesso!', 'success')
      }
      
      // Fechar modal e limpar formulário
      setShowSMTPModal(false)
      setEditingSMTP(null)
      setSMTPForm({
        name: '',
        host: '',
        port: 587,
        username: '',
        password: '',
        use_tls: true,
        use_ssl: false,
        from_email: '',
        from_name: '',
      })
      
      // Atualizar lista de configurações SMTP
      await fetchData()
      
    } catch (error: any) {
      console.error('❌ Erro ao salvar SMTP:', error)
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

  const handleCheckStatus = async (instanceId: string) => {
    try {
      await api.post(`/notifications/whatsapp-instances/${instanceId}/check_status/`)
      fetchData()
    } catch (error) {
      console.error('Error checking status:', error)
    }
  }

  // Função para excluir servidor SMTP
  const handleDeleteSMTP = async (smtpId: string) => {
    if (!confirm('Tem certeza que deseja excluir este servidor SMTP?')) {
      return
    }

    try {
      await api.delete(`/notifications/smtp-configs/${smtpId}/`)
      showToast('✅ Servidor SMTP excluído com sucesso!', 'success')
      fetchData()
    } catch (error: any) {
      showToast(`❌ Erro ao excluir servidor: ${error.response?.data?.detail || error.message}`, 'error')
    }
  }

  // Função para editar servidor SMTP
  const handleEditSMTP = (smtp: SMTPConfig) => {
    setSMTPForm({
      name: smtp.name,
      host: smtp.host,
      port: smtp.port,
      username: smtp.username,
      password: '', // Não preencher senha por segurança
      use_tls: smtp.use_tls,
      use_ssl: smtp.use_ssl,
      verify_ssl: smtp.verify_ssl ?? true,
      from_email: smtp.from_email,
      from_name: smtp.from_name,
    })
    setEditingSMTP(smtp)
    setShowSMTPModal(true)
  }


  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Sistema de Notificações</h1>
        <p className="text-sm text-gray-500 mt-1">
          Gerencie templates de email e WhatsApp, instâncias e histórico de envios
        </p>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab('templates')}
            className={`${
              activeTab === 'templates'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center gap-2`}
          >
            <FileText className="h-4 w-4" />
            Templates
          </button>
          <button
            onClick={() => setActiveTab('instances')}
            className={`${
              activeTab === 'instances'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center gap-2`}
          >
            <Server className="h-4 w-4" />
            Instâncias WhatsApp
          </button>
          <button
            onClick={() => setActiveTab('smtp')}
            className={`${
              activeTab === 'smtp'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center gap-2`}
          >
            <Mail className="h-4 w-4" />
            Servidor SMTP
          </button>
          <button
            onClick={() => setActiveTab('logs')}
            className={`${
              activeTab === 'logs'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center gap-2`}
          >
            <Eye className="h-4 w-4" />
            Histórico
          </button>
        </nav>
      </div>

      {/* Templates Tab */}
      {activeTab === 'templates' && (
        <>
          <div className="flex justify-end">
            <Button onClick={() => setShowTemplateModal(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Novo Template
            </Button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.isArray(templates) && templates.map((template) => (
            <Card key={template.id} className="p-4">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2">
                  {template.type === 'email' ? (
                    <Mail className="h-5 w-5 text-blue-500" />
                  ) : (
                    <MessageSquare className="h-5 w-5 text-green-500" />
                  )}
                  <div>
                    <h3 className="font-semibold text-gray-900">{template.name}</h3>
                    <p className="text-xs text-gray-500">{template.category}</p>
                  </div>
                </div>
                <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                  template.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                }`}>
                  {template.is_active ? 'Ativo' : 'Inativo'}
                </span>
              </div>
              <div className="mt-3">
                <p className="text-sm text-gray-600 line-clamp-2">{template.subject || template.content}</p>
              </div>
              <div className="mt-4 flex items-center justify-between">
                <span className="text-xs text-gray-500">{template.tenant_name}</span>
                <div className="flex gap-2">
                  <Button variant="ghost" size="sm">
                    <Edit className="h-4 w-4" />
                  </Button>
                  <Button variant="ghost" size="sm">
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </Card>
          ))}
          
          {(!Array.isArray(templates) || templates.length === 0) && (
            <div className="col-span-full text-center py-12">
              <Bell className="mx-auto h-12 w-12 text-gray-400" />
              <h3 className="mt-2 text-sm font-medium text-gray-900">Nenhum template cadastrado</h3>
              <p className="mt-1 text-sm text-gray-500">
                Comece criando um novo template de notificação
              </p>
            </div>
          )}
          </div>
        </>
      )}

      {/* Instances Tab */}
      {activeTab === 'instances' && (
        <>
          <div className="flex justify-end">
            <Button onClick={() => setShowInstanceModal(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Nova Instância WhatsApp
            </Button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Array.isArray(instances) && instances.map((instance) => (
            <Card key={instance.id} className="p-4">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-semibold text-gray-900">{instance.name}</h3>
                  <p className="text-sm text-gray-500">{instance.instance_name}</p>
                  {instance.phone_number && (
                    <p className="text-sm text-gray-600 mt-1">{instance.phone_number}</p>
                  )}
                </div>
                <div className="flex flex-col items-end gap-2">
                  <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                    instance.status === 'active' ? 'bg-green-100 text-green-800' :
                    instance.status === 'inactive' ? 'bg-yellow-100 text-yellow-800' :
                    'bg-red-100 text-red-800'
                  }`}>
                    {instance.status}
                  </span>
                  {instance.is_default && (
                    <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                      Padrão
                    </span>
                  )}
                </div>
              </div>
              <div className="mt-4 flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleCheckStatus(instance.id)}
                >
                  Verificar Status
                </Button>
                <Button variant="ghost" size="sm">
                  <Edit className="h-4 w-4" />
                </Button>
              </div>
            </Card>
          ))}
          
          {(!Array.isArray(instances) || instances.length === 0) && (
            <div className="col-span-full text-center py-12">
              <Server className="mx-auto h-12 w-12 text-gray-400" />
              <h3 className="mt-2 text-sm font-medium text-gray-900">Nenhuma instância cadastrada</h3>
              <p className="mt-1 text-sm text-gray-500">
                Configure uma instância do WhatsApp para enviar notificações
              </p>
            </div>
          )}
          </div>
        </>
      )}

               {/* SMTP Tab */}
               {activeTab === 'smtp' && (
                 <>
                   <div className="flex justify-end">
                     <Button onClick={() => setShowSMTPModal(true)}>
                       <Plus className="h-4 w-4 mr-2" />
                       Novo Servidor SMTP
                     </Button>
                   </div>
                   {console.log('🔍 Renderizando SMTP tab, smtpConfigs:', smtpConfigs, 'length:', smtpConfigs?.length)}
                   <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Array.isArray(smtpConfigs) && smtpConfigs.map((smtp) => (
            <Card key={smtp.id} className="p-4">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-semibold text-gray-900">{smtp.name}</h3>
                  <p className="text-sm text-gray-500">{smtp.host}:{smtp.port}</p>
                  <p className="text-sm text-gray-600 mt-1">{smtp.from_email}</p>
                  {smtp.from_name && (
                    <p className="text-xs text-gray-500">{smtp.from_name}</p>
                  )}
                </div>
                <div className="flex flex-col items-end gap-2">
                  <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                    smtp.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                  }`}>
                    {smtp.is_active ? 'Ativo' : 'Inativo'}
                  </span>
                  {smtp.is_default && (
                    <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                      Padrão
                    </span>
                  )}
                  {smtp.last_test_status && (
                    <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                      smtp.last_test_status === 'success' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                    }`}>
                      {smtp.last_test_status === 'success' ? (
                        <><Check className="h-3 w-3 mr-1" /> Teste OK</>
                      ) : (
                        <><XIcon className="h-3 w-3 mr-1" /> Falhou</>
                      )}
                    </span>
                  )}
                </div>
              </div>
              <div className="mt-4 flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setTestEmailModal({ show: true, smtpId: smtp.id })
                  }}
                >
                  <Send className="h-4 w-4 mr-2" />
                  Testar Email
                </Button>
                <Button 
                  variant="ghost" 
                  size="sm"
                  onClick={() => handleEditSMTP(smtp)}
                >
                  <Edit className="h-4 w-4" />
                </Button>
                <Button 
                  variant="ghost" 
                  size="sm"
                  onClick={() => handleDeleteSMTP(smtp.id)}
                  className="text-red-600 hover:text-red-700 hover:bg-red-50"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </Card>
          ))}
          
          {(!Array.isArray(smtpConfigs) || smtpConfigs.length === 0) && (
            <div className="col-span-full text-center py-12">
              <Mail className="mx-auto h-12 w-12 text-gray-400" />
              <h3 className="mt-2 text-sm font-medium text-gray-900">Nenhum servidor SMTP cadastrado</h3>
              <p className="mt-1 text-sm text-gray-500">
                Configure um servidor SMTP para enviar notificações por email
              </p>
            </div>
          )}
          </div>
        </>
      )}

      {/* Logs Tab */}
      {activeTab === 'logs' && (
        <div className="text-center py-12">
          <Eye className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-medium text-gray-900">Histórico de notificações</h3>
          <p className="mt-1 text-sm text-gray-500">
            Em desenvolvimento
          </p>
        </div>
      )}

      {/* SMTP Config Modal */}
      {showSMTPModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl p-6 max-h-[90vh] overflow-y-auto">
                   <div className="flex items-center justify-between mb-4">
                     <h3 className="text-lg font-semibold text-gray-900">
                       {editingSMTP ? 'Editar Servidor SMTP' : 'Novo Servidor SMTP'}
                     </h3>
                     <button
                       onClick={() => {
                         setShowSMTPModal(false)
                         setEditingSMTP(null)
                       }}
                       className="text-gray-400 hover:text-gray-600"
                     >
                       <XIcon className="h-5 w-5" />
                     </button>
                   </div>
            
            <div className="space-y-4">
                       <div className="grid grid-cols-2 gap-4">
                         <div className="col-span-2">
                           <Label htmlFor="smtp_name">Nome da Configuração *</Label>
                           <Input
                             id="smtp_name"
                             value={smtpForm.name}
                             onChange={(e) => setSMTPForm({ ...smtpForm, name: e.target.value })}
                             placeholder="Ex: Gmail Principal"
                             required
                           />
                         </div>
                         
                         <div>
                           <Label htmlFor="smtp_host">Servidor SMTP *</Label>
                           <Input
                             id="smtp_host"
                             value={smtpForm.host}
                             onChange={(e) => setSMTPForm({ ...smtpForm, host: e.target.value })}
                             placeholder="smtp.gmail.com"
                             required
                           />
                         </div>
                         
                         <div>
                           <Label htmlFor="smtp_port">Porta</Label>
                           <Input
                             id="smtp_port"
                             type="number"
                             value={smtpForm.port}
                             onChange={(e) => setSMTPForm({ ...smtpForm, port: parseInt(e.target.value) })}
                           />
                         </div>
                         
                         <div>
                           <Label htmlFor="smtp_username">Usuário/Email *</Label>
                           <Input
                             id="smtp_username"
                             value={smtpForm.username}
                             onChange={(e) => setSMTPForm({ ...smtpForm, username: e.target.value })}
                             placeholder="seu@email.com"
                             required
                           />
                         </div>
                         
                         <div>
                           <Label htmlFor="smtp_password">Senha *</Label>
                           <Input
                             id="smtp_password"
                             type="password"
                             value={smtpForm.password}
                             onChange={(e) => setSMTPForm({ ...smtpForm, password: e.target.value })}
                             required
                           />
                         </div>
                         
                         <div>
                           <Label htmlFor="smtp_from_email">Email Remetente *</Label>
                           <Input
                             id="smtp_from_email"
                             type="email"
                             value={smtpForm.from_email}
                             onChange={(e) => setSMTPForm({ ...smtpForm, from_email: e.target.value })}
                             placeholder="noreply@alreasense.com"
                             required
                           />
                         </div>
                         
                         <div>
                           <Label htmlFor="smtp_from_name">Nome Remetente</Label>
                           <Input
                             id="smtp_from_name"
                             value={smtpForm.from_name}
                             onChange={(e) => setSMTPForm({ ...smtpForm, from_name: e.target.value })}
                             placeholder="Alrea Sense"
                           />
                         </div>
                
                <div className="col-span-2 space-y-3">
                  <div className="flex gap-4">
                    <label className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={smtpForm.use_tls}
                        onChange={(e) => setSMTPForm({ ...smtpForm, use_tls: e.target.checked, use_ssl: false })}
                        className="h-4 w-4 text-blue-600 border-gray-300 rounded"
                      />
                      <span className="text-sm text-gray-700">Usar TLS (porta 587)</span>
                    </label>
                    
                    <label className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={smtpForm.use_ssl}
                        onChange={(e) => setSMTPForm({ ...smtpForm, use_ssl: e.target.checked, use_tls: false })}
                        className="h-4 w-4 text-blue-600 border-gray-300 rounded"
                      />
                      <span className="text-sm text-gray-700">Usar SSL (porta 465)</span>
                    </label>
                  </div>
                  
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={smtpForm.verify_ssl ?? true}
                      onChange={(e) => setSMTPForm({ ...smtpForm, verify_ssl: e.target.checked })}
                      className="h-4 w-4 text-blue-600 border-gray-300 rounded"
                    />
                    <span className="text-sm text-gray-700">Verificar certificado SSL</span>
                    <span className="text-xs text-gray-500">(desative se houver erro de certificado)</span>
                  </label>
                </div>
              </div>
              
              <div className="flex justify-between items-center pt-4 border-t">
                <p className="text-xs text-gray-500">
                  💡 Dica: Após salvar, use o botão "Testar Email" para verificar se está funcionando
                </p>
                <div className="flex gap-3">
                  <Button
                    variant="outline"
                    onClick={() => setShowSMTPModal(false)}
                  >
                    Cancelar
                  </Button>
                         <Button
                           onClick={handleSaveSMTP}
                           disabled={isSaving}
                         >
                           {isSaving ? (
                             <>
                               <LoadingSpinner size="sm" className="mr-2" />
                               {editingSMTP ? 'Atualizando...' : 'Salvando...'}
                             </>
                           ) : (
                             editingSMTP ? 'Atualizar Configuração' : 'Salvar Configuração'
                           )}
                         </Button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Test Email Modal */}
      {testEmailModal.show && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900">Testar Envio de Email</h3>
              <button
                onClick={() => {
                  setTestEmailModal({ show: false, smtpId: null })
                  setTestEmail('')
                }}
                className="text-gray-400 hover:text-gray-600"
              >
                <XIcon className="h-5 w-5" />
              </button>
            </div>
            
            <div className="space-y-4">
              <div>
                <Label htmlFor="test_email">Email para Teste</Label>
                <Input
                  id="test_email"
                  type="email"
                  value={testEmail}
                  onChange={(e) => setTestEmail(e.target.value)}
                  placeholder="seu@email.com"
                  className="mt-1"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Um email de teste será enviado para este endereço
                </p>
              </div>
              
              <div className="flex justify-end gap-3">
                <Button
                  variant="outline"
                  onClick={() => {
                    setTestEmailModal({ show: false, smtpId: null })
                    setTestEmail('')
                  }}
                >
                  Cancelar
                </Button>
                <Button
                  onClick={handleTestSMTP}
                  disabled={isTesting || !testEmail}
                >
                  {isTesting ? (
                    <>
                      <LoadingSpinner size="sm" className="mr-2" />
                      Enviando...
                    </>
                  ) : (
                    <>
                      <Send className="h-4 w-4 mr-2" />
                      Enviar Teste
                    </>
                  )}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Toast Notification */}
      {toast.show && (
        <div className={`fixed top-4 right-4 z-50 max-w-sm w-full bg-white rounded-lg shadow-lg border-l-4 ${
          toast.type === 'success' ? 'border-green-500' : 'border-red-500'
        }`}>
          <div className="p-4">
            <div className="flex items-start">
              <div className="flex-shrink-0">
                {toast.type === 'success' ? (
                  <Check className="h-5 w-5 text-green-500" />
                ) : (
                  <XIcon className="h-5 w-5 text-red-500" />
                )}
              </div>
              <div className="ml-3 w-0 flex-1">
                <p className={`text-sm font-medium ${
                  toast.type === 'success' ? 'text-green-800' : 'text-red-800'
                }`}>
                  {toast.message}
                </p>
              </div>
              <div className="ml-4 flex-shrink-0 flex">
                <button
                  className={`inline-flex rounded-md focus:outline-none focus:ring-2 focus:ring-offset-2 ${
                    toast.type === 'success' 
                      ? 'text-green-500 hover:text-green-600 focus:ring-green-500' 
                      : 'text-red-500 hover:text-red-600 focus:ring-red-500'
                  }`}
                  onClick={() => setToast({ show: false, message: '', type: 'success' })}
                >
                  <XIcon className="h-5 w-5" />
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

