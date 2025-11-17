import { useState, useEffect } from 'react'
import { X, ChevronRight, ChevronLeft, Check, AlertCircle, Info, Send, Users, MessageSquare, Settings, Eye, Zap } from 'lucide-react'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { api } from '../../lib/api'
import { showSuccessToast, showErrorToast, showLoadingToast, updateToastSuccess, updateToastError } from '../../lib/toastHelper'
import { MessageVariables } from './MessageVariables'
import { renderMessagePreview } from '../../hooks/useMessageVariables'

interface CampaignWizardModalProps {
  onClose: () => void
  onSuccess: () => void
  editingCampaign?: any | null
}

interface WhatsAppInstance {
  id: string
  friendly_name: string
  phone_number: string
  connection_state: string
  health_score: number
  msgs_sent_today: number
}

interface Tag {
  id: string
  name: string
  color: string
  contact_count: number  // ✅ Usar contador do backend
}

interface Contact {
  id: string
  name: string
  phone: string
  state?: string
  tags: Tag[]
}

export default function CampaignWizardModal({ onClose, onSuccess, editingCampaign }: CampaignWizardModalProps) {
  const [step, setStep] = useState(1) // 1-6
  const [instances, setInstances] = useState<WhatsAppInstance[]>([])
  const [tags, setTags] = useState<Tag[]>([])
  const [contacts, setContacts] = useState<Contact[]>([])
  const [tagContacts, setTagContacts] = useState<Contact[]>([])  // ✅ Contatos da tag selecionada
  const [isLoading, setIsLoading] = useState(false)

  const [formData, setFormData] = useState({
    // Step 1: Básico
    name: '',
    description: '',
    scheduled_at: '',
    
    // Step 2: Público
    audience_type: 'tag' as 'tag' | 'contacts',
    tag_id: '',
    contact_ids: [] as string[],
    
    // Step 3: Mensagens
    messages: [{ content: '', order: 1 }],
    
    // Step 4: Instâncias e Rotação
    instance_ids: [] as string[],
    rotation_mode: 'round_robin' as 'round_robin' | 'balanced' | 'intelligent',
    
    // Step 5: Configurações
    interval_min: 25,
    interval_max: 50,
    daily_limit_per_instance: 100,
    pause_on_health_below: 30
  })

  useEffect(() => {
    fetchData()
    
    // Listener para inserção de variáveis
    const handleInsertVariable = (event: any) => {
      const variable = event.detail
      // Usar callback para acessar o estado mais recente
      setFormData(prevFormData => {
        const targetIndex = prevFormData.messages.length - 1
        
        // Sempre inserir na última mensagem (não criar nova)
        const newMessages = [...prevFormData.messages]
        if (newMessages[targetIndex]) {
          newMessages[targetIndex].content += variable
        }
        return { ...prevFormData, messages: newMessages }
      })
    }
    
    window.addEventListener('insertVariable', handleInsertVariable)
    
    return () => {
      window.removeEventListener('insertVariable', handleInsertVariable)
    }
  }, []) // Remover dependência problemática

  // Popular formulário com dados da campanha sendo editada
  useEffect(() => {
    if (editingCampaign) {
      console.log('📝 Populando formulário com dados da campanha:', editingCampaign)
      
      setFormData({
        // Step 1: Básico
        name: editingCampaign.name || '',
        description: editingCampaign.description || '',
        scheduled_at: editingCampaign.scheduled_at || '',
        
        // Step 2: Público (será carregado via API)
        audience_type: 'tag' as 'tag' | 'contacts',
        tag_id: '',
        contact_ids: [],
        
        // Step 3: Mensagens
        messages: editingCampaign.messages?.length > 0 
          ? editingCampaign.messages.map((msg: any, index: number) => ({
              id: msg.id,
              content: msg.content || '',
              order: msg.order || index + 1,
              times_used: msg.times_used || 0
            }))
          : [{ content: '', order: 1 }],
        
        // Step 4: Instâncias e Rotação
        instance_ids: editingCampaign.instances || [],
        rotation_mode: editingCampaign.rotation_mode || 'round_robin',
        
        // Step 5: Configurações
        interval_min: editingCampaign.interval_min || 25,
        interval_max: editingCampaign.interval_max || 50,
        daily_limit_per_instance: editingCampaign.daily_limit_per_instance || 100,
        pause_on_health_below: editingCampaign.pause_on_health_below || 30
      })
    }
  }, [editingCampaign])

  const fetchData = async () => {
    try {
      const [instancesRes, tagsStatsRes] = await Promise.all([
        api.get('/notifications/whatsapp-instances/'),
        api.get('/contacts/tags/stats/') // Usar endpoint de stats para contagem real
      ])
      
      setInstances(instancesRes.data.results || instancesRes.data || [])
      setTags(tagsStatsRes.data.tags || []) // Usar dados do stats
      
      // Não precisamos mais buscar todos os contatos aqui
      // Eles serão carregados sob demanda quando necessário
      setContacts([])
    } catch (error) {
      console.error('Erro ao buscar dados:', error)
    }
  }

  // ✅ Função para carregar contatos de uma tag específica
  const fetchTagContacts = async (tagId: string) => {
    try {
      console.log(`🔍 Carregando contatos da tag: ${tagId}`)
      const response = await api.get(`/contacts/contacts/?tags=${tagId}&page_size=10000`)
      const contactsData = response.data.results || response.data || []
      console.log(`✅ Encontrados ${contactsData.length} contatos para a tag`)
      setTagContacts(contactsData)
      return contactsData
    } catch (error) {
      console.error('❌ Erro ao buscar contatos da tag:', error)
      setTagContacts([])
      return []
    }
  }

  const steps = [
    { num: 1, label: 'Informações', icon: Info },
    { num: 2, label: 'Público', icon: Users },
    { num: 3, label: 'Mensagens', icon: MessageSquare },
    { num: 4, label: 'Instâncias', icon: Zap },
    { num: 5, label: 'Configurações', icon: Settings },
    { num: 6, label: 'Revisão', icon: Eye }
  ]

  const getSelectedContactsCount = (): number => {
    // Sempre usar contact_ids, pois agora marcar/desmarcar atualiza essa lista
    const count = formData.contact_ids.length
    console.log(`📊 [COUNT] Contatos selecionados: ${count}`, {
      contact_ids: formData.contact_ids,
      audience_type: formData.audience_type,
      tag_id: formData.tag_id
    })
    return count
  }

  const canProceed = (): boolean => {
    switch (step) {
      case 1:
        return formData.name && typeof formData.name === 'string' && formData.name.trim().length > 0
      case 2:
        return getSelectedContactsCount() > 0
      case 3:
        return formData.messages.some(m => m.content && typeof m.content === 'string' && m.content.trim().length > 0)
      case 4:
        return formData.instance_ids.length > 0
      case 5:
        return true // Configs têm defaults
      case 6:
        return true
      default:
        return false
    }
  }

  const handleNext = () => {
    if (canProceed() && step < 6) {
      console.log(`🔄 [NAVIGATION] Indo do step ${step} para ${step + 1}`)
      console.log(`🔍 [NAVIGATION] Estado atual:`, {
        audience_type: formData.audience_type,
        tag_id: formData.tag_id,
        contact_ids: formData.contact_ids,
        contact_count: formData.contact_ids.length
      })
      setStep(step + 1)
    } else {
      console.log(`❌ [NAVIGATION] Não pode prosseguir do step ${step}:`, {
        canProceed: canProceed(),
        contact_count: getSelectedContactsCount()
      })
    }
  }

  const handleBack = () => {
    if (step > 1) {
      console.log(`🔄 [NAVIGATION] Voltando do step ${step} para ${step - 1}`)
      console.log(`🔍 [NAVIGATION] Estado atual:`, {
        audience_type: formData.audience_type,
        tag_id: formData.tag_id,
        contact_ids: formData.contact_ids,
        contact_count: formData.contact_ids.length
      })
      setStep(step - 1)
    }
  }

  const handleSubmit = async () => {
    setIsLoading(true)
    const toastId = showLoadingToast('criar', 'Campanha')

    try {
      const payload = {
        name: formData.name,
        description: formData.description,
        rotation_mode: formData.rotation_mode,
        instances: formData.instance_ids,
        messages: formData.messages.filter(m => m.content && typeof m.content === 'string' && m.content.trim()),
        interval_min: formData.interval_min,
        interval_max: formData.interval_max,
        daily_limit_per_instance: formData.daily_limit_per_instance,
        pause_on_health_below: formData.pause_on_health_below,
        scheduled_at: formData.scheduled_at || null,
        tag_id: (formData.audience_type === 'tag' && formData.contact_ids.length === 0) ? formData.tag_id : null,
        contact_ids: formData.contact_ids.length > 0 ? formData.contact_ids : []
      }

      console.log('🚀 [CAMPANHA] Payload sendo enviado:', {
        audience_type: formData.audience_type,
        tag_id: payload.tag_id,
        contact_ids: payload.contact_ids,
        total_contacts: payload.contact_ids.length,
        mode: payload.contact_ids.length > 0 ? 'CONTATOS_ESPECIFICOS' : 'TODOS_DA_TAG'
      })
      
      console.log('🔍 [DEBUG] Dados do formulário:', {
        name: formData.name,
        name_type: typeof formData.name,
        messages: formData.messages.map(m => ({
          content: m.content,
          content_type: typeof m.content,
          has_content: !!m.content
        }))
      })
      
      // Verificar se há campos vazios que podem causar erro
      console.log('🔍 [VALIDATION] Verificando nome:', {
        name: formData.name,
        name_type: typeof formData.name,
        name_length: formData.name ? formData.name.length : 0,
        name_trimmed: formData.name ? formData.name.trim() : ''
      })
      
      if (!formData.name || formData.name.trim() === '') {
        console.error('❌ [ERROR] Nome da campanha está vazio!')
        throw new Error('Nome da campanha é obrigatório')
      }
      
      // Verificar se há mensagens válidas
      const validMessages = formData.messages.filter(m => m.content && typeof m.content === 'string' && m.content.trim())
      if (validMessages.length === 0) {
        console.error('❌ [ERROR] Nenhuma mensagem válida encontrada!')
        throw new Error('Pelo menos uma mensagem é obrigatória')
      }

      await api.post('/campaigns/', payload)
      
      // ✅ Garantir que toast seja atualizado ANTES dos callbacks
      updateToastSuccess(toastId, 'criar', 'Campanha')
      
      // ✅ Executar callbacks em try/catch separado para não afetar o toast
      try {
      onSuccess()
      onClose()
      } catch (callbackError) {
        console.error('Erro nos callbacks:', callbackError)
        // Toast já foi atualizado, não afeta o resultado
      }
      
    } catch (error: any) {
      console.error('Erro ao salvar campanha:', error)
      updateToastError(toastId, 'criar', 'Campanha', error)
    } finally {
      setIsLoading(false)
    }
  }

  const addMessage = () => {
    setFormData(prevFormData => ({
      ...prevFormData,
      messages: [...prevFormData.messages, { content: '', order: prevFormData.messages.length + 1 }]
    }))
  }

  const removeMessage = (index: number) => {
    setFormData(prevFormData => {
      const newMessages = prevFormData.messages.filter((_, i) => i !== index)
      return { ...prevFormData, messages: newMessages }
    })
  }

  const updateMessage = (index: number, content: string) => {
    setFormData(prevFormData => {
      const newMessages = [...prevFormData.messages]
      newMessages[index].content = content
      return { ...prevFormData, messages: newMessages }
    })
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-7xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex justify-between items-center p-4 border-b sticky top-0 bg-white z-10">
          <div>
            <h2 className="text-xl font-bold">
              {editingCampaign ? 'Editar Campanha' : 'Nova Campanha'}
            </h2>
            <p className="text-sm text-gray-500">Passo {step} de 6</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="h-6 w-6" />
          </button>
        </div>

        {/* Progress Steps */}
        <div className="px-4 py-3 border-b bg-gray-50">
          <div className="flex items-center justify-between">
            {steps.map((s, idx) => {
              const Icon = s.icon
              const isActive = step === s.num
              const isCompleted = step > s.num
              
              return (
                <div key={s.num} className="flex items-center flex-1">
                  <div className="flex flex-col items-center flex-1">
                    <div
                      className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium transition-colors ${
                        isCompleted
                          ? 'bg-green-500 text-white'
                          : isActive
                          ? 'bg-blue-600 text-white'
                          : 'bg-gray-200 text-gray-500'
                      }`}
                    >
                      {isCompleted ? <Check className="h-4 w-4" /> : <Icon className="h-4 w-4" />}
                    </div>
                    <span className={`text-xs mt-1 ${isActive ? 'font-medium text-blue-600' : 'text-gray-500'}`}>
                      {s.label}
                    </span>
                  </div>
                  {idx < steps.length - 1 && (
                    <div className={`flex-1 h-0.5 ${isCompleted ? 'bg-green-500' : 'bg-gray-200'}`} />
                  )}
                </div>
              )
            })}
          </div>
        </div>

        {/* Body */}
        <div className="p-6">
          {/* STEP 1: Informações Básicas */}
          {step === 1 && (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold">Informações Básicas</h3>
              
              <div>
                <label className="block text-sm font-medium mb-2">
                  Nome da Campanha *
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="Ex: Lançamento Produto X"
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">
                  Descrição (Opcional)
                </label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder="Descreva o objetivo desta campanha..."
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                  rows={3}
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">
                  Agendar para (Opcional)
                </label>
                <input
                  type="datetime-local"
                  value={formData.scheduled_at}
                  onChange={(e) => setFormData({ ...formData, scheduled_at: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Deixe vazio para criar como rascunho
                </p>
              </div>
            </div>
          )}

          {/* STEP 2: Seleção de Público */}
          {step === 2 && (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold">Seleção de Público</h3>
              
              <div className="grid grid-cols-2 gap-4">
                <label className={`p-4 border-2 rounded-lg cursor-pointer transition-colors ${
                  formData.audience_type === 'tag' ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-gray-300'
                }`}>
                  <input
                    type="radio"
                    checked={formData.audience_type === 'tag'}
                    onChange={() => setFormData({ ...formData, audience_type: 'tag', contact_ids: [] })}
                    className="mr-2"
                  />
                  <span className="font-medium">Filtrar por Tag 🏷️</span>
                  <p className="text-xs text-gray-500 mt-1">Enviar para todos os contatos com uma tag específica</p>
                </label>

                <label className={`p-4 border-2 rounded-lg cursor-pointer transition-colors ${
                  formData.audience_type === 'contacts' ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-gray-300'
                }`}>
                  <input
                    type="radio"
                    checked={formData.audience_type === 'contacts'}
                    onChange={() => setFormData({ ...formData, audience_type: 'contacts', tag_id: '' })}
                    className="mr-2"
                  />
                  <span className="font-medium">Selecionar Avulsos</span>
                  <p className="text-xs text-gray-500 mt-1">Escolher contatos manualmente</p>
                </label>
              </div>

              {formData.audience_type === 'tag' && (
                <div className="space-y-4">
                  <label className="block text-sm font-medium mb-2">
                    Selecione a Tag *
                  </label>
                  <select
                    value={formData.tag_id}
                    onChange={async (e) => {
                      const tagId = e.target.value
                      
                      // ✅ Carregar contatos da tag via API quando seleciona uma tag
                      if (tagId) {
                        console.log(`🏷️ Tag selecionada: ${tagId}`)
                        const tagContacts = await fetchTagContacts(tagId)
                        setFormData({ 
                          ...formData, 
                          tag_id: tagId,
                          contact_ids: [] // Não selecionar automaticamente - deixar usuário escolher
                        })
                      } else {
                        setTagContacts([])  // Limpar contatos da tag
                        setFormData({ ...formData, tag_id: '', contact_ids: [] })
                      }
                    }}
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="">Escolha uma tag...</option>
                    {tags.map((tag) => (
                      <option key={tag.id} value={tag.id}>
                        🏷️ {tag.name} ({tag.contact_count} contatos)
                      </option>
                    ))}
                  </select>
                  
                  {formData.tag_id && (
                    <div className="space-y-2">
                      <div className="flex justify-between items-center">
                        <p className="text-sm font-medium text-gray-700">
                          Contatos com esta tag ({formData.contact_ids.length}/{tags.find(t => t.id === formData.tag_id)?.contact_count || 0} selecionados)
                        </p>
                        <div className="flex gap-2">
                          <button
                            type="button"
                            onClick={() => {
                              // ✅ Enviar para TODOS os contatos da tag (sem contact_ids específicos)
                              setFormData({ ...formData, contact_ids: [] })
                            }}
                            className="text-xs text-green-600 hover:text-green-800 font-medium"
                          >
                            Enviar para Todos
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              // ✅ Selecionar todos os contatos específicos
                              setFormData({ ...formData, contact_ids: tagContacts.map(c => c.id) })
                            }}
                            className="text-xs text-blue-600 hover:text-blue-800"
                          >
                            Selecionar Todos
                          </button>
                          <button
                            type="button"
                            onClick={() => setFormData({ ...formData, contact_ids: [] })}
                            className="text-xs text-gray-600 hover:text-gray-800"
                          >
                            Desmarcar Todos
                          </button>
                        </div>
                      </div>
                      
                      <div className="border rounded-lg max-h-80 overflow-y-auto">
                        <table className="w-full text-sm">
                          <thead className="bg-gray-50 sticky top-0">
                            <tr>
                              <th className="w-12 p-2 text-left">
                                <input
                                  type="checkbox"
                                  checked={
                                    tagContacts.length > 0 &&
                                    tagContacts.every(c => formData.contact_ids.includes(c.id))
                                  }
                                  onChange={(e) => {
                                    // ✅ Usar tagContacts carregados via API
                                    if (e.target.checked) {
                                      setFormData({ ...formData, contact_ids: tagContacts.map(c => c.id) })
                                    } else {
                                      setFormData({ ...formData, contact_ids: [] })
                                    }
                                  }}
                                  className="rounded"
                                />
                              </th>
                              <th className="p-2 text-left font-medium text-gray-700">Nome</th>
                              <th className="p-2 text-left font-medium text-gray-700">Telefone</th>
                            </tr>
                          </thead>
                          <tbody>
                            {tagContacts.map((contact, idx) => (
                                <tr key={contact.id} className={`border-t hover:bg-gray-50 ${idx % 2 === 0 ? 'bg-white' : 'bg-gray-25'}`}>
                                  <td className="p-2">
                                    <input
                                      type="checkbox"
                                      checked={formData.contact_ids.includes(contact.id)}
                                      onChange={(e) => {
                                        if (e.target.checked) {
                                          const newContactIds = [...formData.contact_ids, contact.id]
                                          console.log(`✅ [SELECT] Adicionando contato ${contact.id}:`, newContactIds)
                                          setFormData({ ...formData, contact_ids: newContactIds })
                                        } else {
                                          const newContactIds = formData.contact_ids.filter(id => id !== contact.id)
                                          console.log(`❌ [SELECT] Removendo contato ${contact.id}:`, newContactIds)
                                          setFormData({ ...formData, contact_ids: newContactIds })
                                        }
                                      }}
                                      className="rounded"
                                    />
                                  </td>
                                  <td className="p-2">{contact.name}</td>
                                  <td className="p-2 text-gray-600">{contact.phone}</td>
                                </tr>
                              ))}
                          </tbody>
                        </table>
                        {tagContacts.length === 0 && (
                          <div className="p-8 text-center text-gray-500">
                            Nenhum contato encontrado com esta tag
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}


              {formData.audience_type === 'contacts' && (
                <div>
                  <label className="block text-sm font-medium mb-2">
                    Selecione os Contatos *
                  </label>
                  <div className="border rounded-lg max-h-64 overflow-y-auto p-3 space-y-2">
                    {contacts.length === 0 ? (
                      <div className="text-center py-4">
                        <button
                          type="button"
                          onClick={() => {
                            // Carregar primeiros 100 contatos quando necessário
                            api.get('/contacts/contacts/?page_size=100')
                              .then(res => setContacts(res.data.results || []))
                              .catch(err => console.error('Erro ao carregar contatos:', err))
                          }}
                          className="text-blue-600 hover:text-blue-800 text-sm"
                        >
                          Carregar contatos para seleção
                        </button>
                      </div>
                    ) : (
                      contacts.map((contact) => (
                      <label key={contact.id} className="flex items-center gap-2 p-2 hover:bg-gray-50 rounded cursor-pointer">
                        <input
                          type="checkbox"
                          checked={formData.contact_ids.includes(contact.id)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              const newContactIds = [...formData.contact_ids, contact.id]
                              console.log(`✅ [SELECT-AVULSO] Adicionando contato ${contact.id}:`, newContactIds)
                              setFormData({ ...formData, contact_ids: newContactIds })
                            } else {
                              const newContactIds = formData.contact_ids.filter(id => id !== contact.id)
                              console.log(`❌ [SELECT-AVULSO] Removendo contato ${contact.id}:`, newContactIds)
                              setFormData({ ...formData, contact_ids: newContactIds })
                            }
                          }}
                        />
                        <span className="text-sm">{contact.name} - {contact.phone}</span>
                      </label>
                      ))
                    )}
                  </div>
                  {contacts.length > 0 && (
                  <p className="text-xs text-gray-500 mt-2">
                      Mostrando {contacts.length} contatos
                  </p>
                  )}
                </div>
              )}

              <Card className="p-4 bg-blue-50 border-blue-200">
                <div className="flex items-center gap-2">
                  <Users className="h-5 w-5 text-blue-600" />
                  <div>
                    <p className="font-medium text-blue-900">
                      {getSelectedContactsCount()} contatos selecionados
                    </p>
                    <p className="text-xs text-blue-700">
                      Estes contatos receberão as mensagens da campanha
                    </p>
                  </div>
                </div>
              </Card>
            </div>
          )}

          {/* STEP 3: Mensagens */}
          {step === 3 && (
            <div className="grid grid-cols-3 gap-6">
              {/* Coluna 1: Editor de Mensagens */}
              <div className="space-y-4">
                <div className="flex justify-between items-center">
                  <h3 className="text-lg font-semibold">✏️ Edição das Mensagens</h3>
                  <Button onClick={addMessage} size="sm">
                    + Adicionar
                  </Button>
                </div>

                {/* Mensagens */}
                <div className="space-y-3 max-h-96 overflow-y-auto">
                  {formData.messages.map((message, index) => (
                    <Card key={index} className="p-3">
                      <div className="flex items-start gap-2">
                        <div className="flex-shrink-0 w-6 h-6 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-xs font-medium">
                          {index + 1}
                        </div>
                        <div className="flex-1">
                          <textarea
                            value={message.content}
                            onChange={(e) => updateMessage(index, e.target.value)}
                            onDrop={(e) => {
                              e.preventDefault()
                              const variable = e.dataTransfer.getData('text/plain')
                              const textarea = e.target as HTMLTextAreaElement
                              
                              // Se não há seleção ou cursor, inserir no final
                              let start = textarea.selectionStart
                              let end = textarea.selectionEnd
                              
                              // Se start/end são null ou iguais, inserir no final
                              if (start === null || start === end) {
                                start = message.content.length
                                end = message.content.length
                              }
                              
                              const newContent = message.content.substring(0, start) + variable + message.content.substring(end)
                              updateMessage(index, newContent)
                              
                              // Limpar classes visuais
                              textarea.classList.remove('border-blue-400', 'bg-blue-50')
                              
                              // Reposicionar cursor após a variável inserida
                              setTimeout(() => {
                                textarea.focus()
                                textarea.setSelectionRange(start + variable.length, start + variable.length)
                              }, 0)
                            }}
                            onDragOver={(e) => {
                              e.preventDefault()
                              e.dataTransfer.dropEffect = 'copy'
                              // Adicionar classe visual para indicar que pode receber drop
                              textarea.classList.add('border-blue-400', 'bg-blue-50')
                            }}
                            onDragLeave={(e) => {
                              // Remover classes visuais quando sair da área
                              const textarea = e.target as HTMLTextAreaElement
                              textarea.classList.remove('border-blue-400', 'bg-blue-50')
                            }}
                            onDragEnter={(e) => {
                              e.preventDefault()
                              const textarea = e.target as HTMLTextAreaElement
                              textarea.classList.add('border-blue-400', 'bg-blue-50')
                            }}
                            placeholder="Digite a mensagem... Use {{nome}}, {{primeiro_nome}}, {{saudacao}}, etc."
                            className="w-full px-2 py-2 text-sm border rounded focus:ring-2 focus:ring-blue-500 transition-colors"
                            rows={4}
                          />
                          <p className="text-xs text-gray-500 mt-1">
                            {message.content.length} caracteres • Arraste variáveis aqui
                          </p>
                        </div>
                        {formData.messages.length > 1 && (
                          <button
                            onClick={() => removeMessage(index)}
                            className="text-red-500 hover:text-red-700"
                          >
                            <X className="h-4 w-4" />
                          </button>
                        )}
                      </div>
                    </Card>
                  ))}
                </div>
              </div>

              {/* Coluna 2: Preview WhatsApp */}
              <div className="space-y-4">
                <h3 className="text-lg font-semibold">📱 Preview do WhatsApp</h3>
                
                {/* Smartphone Mockup */}
                <div className="mx-auto max-w-sm">
                  <div className="bg-gray-900 rounded-3xl p-3 shadow-2xl">
                    {/* Tela do celular */}
                    <div className="bg-gradient-to-b from-teal-600 to-teal-700 rounded-2xl overflow-hidden">
                      {/* Status Bar */}
                      <div className="bg-teal-800 h-4 flex items-center justify-between px-4 text-white text-xs">
                        <span>9:41</span>
                        <div className="flex items-center gap-1">
                          <div className="w-4 h-2 bg-white rounded-sm">
                            <div className="w-3 h-full bg-green-400 rounded-sm"></div>
                          </div>
                          <span>100%</span>
                        </div>
                      </div>
                      
                      {/* Header WhatsApp */}
                      <div className="bg-teal-700 px-4 py-3 flex items-center gap-3">
                        <div className="w-8 h-8 bg-green-400 rounded-full flex items-center justify-center">
                          <svg className="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M18 10c0 3.866-3.582 7-8 7a8.841 8.841 0 01-4.083-.98L2 17l1.338-3.123C2.493 12.767 2 11.434 2 10c0-3.866 3.582-7 8-7s8 3.134 8 7zM7 9H5v2h2V9zm8 0h-2v2h2V9zM9 9h2v2H9V9z" clipRule="evenodd" />
                          </svg>
                        </div>
                        <div className="flex-1">
                          <p className="text-white font-medium text-sm">Maria Silva</p>
                          <p className="text-teal-100 text-xs">online</p>
                        </div>
                        <div className="flex gap-2">
                          <svg className="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 20 20">
                            <path d="M2 3a1 1 0 011-1h2.153a1 1 0 01.986.836l.74 4.435a1 1 0 01-.54 1.06l-1.548.773a11.037 11.037 0 006.105 6.105l.774-1.548a1 1 0 011.059-.54l4.435.74a1 1 0 01.836.986V17a1 1 0 01-1 1h-2C7.82 18 2 12.18 2 5V3z" />
                          </svg>
                          <svg className="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-3a1 1 0 00-.867.5 1 1 0 11-1.731-1A3 3 0 0113 8a3.001 3.001 0 01-2 2.83V11a1 1 0 11-2 0v-1a1 1 0 011-1 1 1 0 100-2zm0 8a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
                          </svg>
                        </div>
                      </div>

                      {/* Chat Area */}
                      <div className="bg-[#e5ddd5] h-96 p-3 overflow-y-auto">
                        {formData.messages.filter(m => m.content && typeof m.content === 'string' && m.content.trim()).map((msg, idx) => {
                          // Substituir variáveis para preview usando função helper
                          const previewText = renderMessagePreview(msg.content, {
                            nome: 'Maria Silva',
                            primeiro_nome: 'Maria',
                            email: 'maria@email.com',
                            cidade: 'São Paulo',
                            estado: 'SP',
                            clinica: 'Hospital Veterinário Santa Inês',
                            valor_compra: 'R$ 1.500,00',
                            data_compra: '25/03/2024',
                            quem_indicou: 'João Santos',
                            primeiro_nome_indicador: 'João'
                          })
                          
                          return (
                            <div key={idx} className="mb-3 flex justify-end">
                              <div className="max-w-[85%]">
                                <div className="bg-[#dcf8c6] rounded-lg rounded-tr-none px-3 py-2 shadow-sm relative">
                                  <p className="text-sm text-gray-800 whitespace-pre-wrap break-words leading-relaxed">
                                    {previewText}
                                  </p>
                                  <div className="flex items-center justify-end mt-1 gap-1">
                                    <span className="text-xs text-gray-500">
                                      {new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}
                                    </span>
                                    <svg className="w-3 h-3 text-blue-500" fill="currentColor" viewBox="0 0 20 20">
                                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                                    </svg>
                                  </div>
                                </div>
                              </div>
                            </div>
                          )
                        })}
                        
                        {formData.messages.filter(m => m.content && typeof m.content === 'string' && m.content.trim()).length === 0 && (
                          <div className="text-center text-gray-500 text-sm mt-20">
                            Digite uma mensagem para ver o preview
                          </div>
                        )}
                      </div>

                      {/* Input Area (só visual) */}
                      <div className="bg-white px-3 py-2 flex items-center gap-2 border-t border-gray-200">
                        <div className="flex-1 bg-gray-100 rounded-full px-4 py-2 flex items-center gap-2">
                          <svg className="w-4 h-4 text-gray-500" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clipRule="evenodd" />
                          </svg>
                          <span className="text-sm text-gray-500">Digite uma mensagem</span>
                        </div>
                        <div className="w-8 h-8 bg-teal-600 rounded-full flex items-center justify-center">
                          <svg className="h-4 w-4 text-white" fill="currentColor" viewBox="0 0 20 20">
                            <path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z" />
                          </svg>
                        </div>
                      </div>
                    </div>
                  </div>
                  
                  {/* Legenda */}
                  <p className="text-xs text-gray-500 text-center mt-3">
                    Preview atualiza em tempo real
                  </p>
                </div>
              </div>

              {/* Coluna 3: Variáveis Disponíveis */}
              <div className="space-y-4">
                <h3 className="text-lg font-semibold">📝 Variáveis Disponíveis</h3>
                <MessageVariables />
              </div>
            </div>
          )}

          {/* STEP 4: Instâncias e Rotação */}
          {step === 4 && (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold">Instâncias WhatsApp e Rotação</h3>

              <div>
                <label className="block text-sm font-medium mb-2">
                  Selecione as Instâncias *
                </label>
                <div className="space-y-2">
                  {instances.map((instance) => (
                    <label
                      key={instance.id}
                      className={`flex items-center gap-3 p-3 border-2 rounded-lg cursor-pointer transition-colors ${
                        formData.instance_ids.includes(instance.id)
                          ? 'border-blue-500 bg-blue-50'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={formData.instance_ids.includes(instance.id)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setFormData({ ...formData, instance_ids: [...formData.instance_ids, instance.id] })
                          } else {
                            setFormData({ ...formData, instance_ids: formData.instance_ids.filter(id => id !== instance.id) })
                          }
                        }}
                      />
                      <div className="flex-1">
                        <p className="font-medium">{instance.friendly_name}</p>
                        <p className="text-xs text-gray-500">{instance.phone_number}</p>
                      </div>
                      <div className="flex items-center gap-4 text-sm">
                        <div className={`px-2 py-1 rounded text-xs font-medium ${
                          instance.connection_state === 'connected'
                            ? 'bg-green-100 text-green-700'
                            : 'bg-gray-100 text-gray-700'
                        }`}>
                          {instance.connection_state}
                        </div>
                        <div className="text-right">
                          <p className="text-xs text-gray-500">Health Score</p>
                          <p className={`font-bold ${
                            instance.health_score >= 80 ? 'text-green-600' :
                            instance.health_score >= 50 ? 'text-yellow-600' :
                            'text-red-600'
                          }`}>
                            {instance.health_score}
                          </p>
                        </div>
                      </div>
                    </label>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">
                  Modo de Rotação
                </label>
                <div className="grid grid-cols-1 gap-3">
                  <label className={`p-4 border-2 rounded-lg cursor-pointer transition-colors ${
                    formData.rotation_mode === 'round_robin' ? 'border-blue-500 bg-blue-50' : 'border-gray-200'
                  }`}>
                    <input
                      type="radio"
                      checked={formData.rotation_mode === 'round_robin'}
                      onChange={() => setFormData({ ...formData, rotation_mode: 'round_robin' })}
                      className="mr-2"
                    />
                    <span className="font-medium">Round Robin (Rodízio Simples)</span>
                    <p className="text-xs text-gray-600 mt-1 ml-6">
                      Alterna entre instâncias de forma sequencial e igualitária
                    </p>
                  </label>

                  <label className={`p-4 border-2 rounded-lg cursor-not-allowed transition-colors opacity-50 ${
                    formData.rotation_mode === 'balanced' ? 'border-blue-500 bg-blue-50' : 'border-gray-200'
                  }`}>
                    <input
                      type="radio"
                      checked={formData.rotation_mode === 'balanced'}
                      onChange={() => setFormData({ ...formData, rotation_mode: 'balanced' })}
                      className="mr-2"
                      disabled
                    />
                    <span className="font-medium">Balanceado <span className="text-xs text-orange-600">(Em breve)</span></span>
                    <p className="text-xs text-gray-600 mt-1 ml-6">
                      Distribui com base na quantidade de mensagens enviadas por cada instância
                    </p>
                  </label>

                  <label className={`p-4 border-2 rounded-lg cursor-not-allowed transition-colors opacity-50 ${
                    formData.rotation_mode === 'intelligent' ? 'border-blue-500 bg-blue-50' : 'border-gray-200'
                  }`}>
                    <input
                      type="radio"
                      checked={formData.rotation_mode === 'intelligent'}
                      onChange={() => setFormData({ ...formData, rotation_mode: 'intelligent' })}
                      className="mr-2"
                      disabled
                    />
                    <span className="font-medium">Inteligente <span className="text-xs text-orange-600">(Em breve)</span></span>
                    <p className="text-xs text-gray-600 mt-1 ml-6">
                      Prioriza instâncias com melhor health score e taxa de entrega
                    </p>
                  </label>
                </div>
              </div>
            </div>
          )}

          {/* STEP 5: Configurações Avançadas */}
          {step === 5 && (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold">Configurações Avançadas</h3>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-2">
                    Intervalo Mínimo (segundos)
                  </label>
                  <input
                    type="number"
                    value={formData.interval_min}
                    onChange={(e) => setFormData({ ...formData, interval_min: parseInt(e.target.value) || 3 })}
                    min="1"
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2">
                    Intervalo Máximo (segundos)
                  </label>
                  <input
                    type="number"
                    value={formData.interval_max}
                    onChange={(e) => setFormData({ ...formData, interval_max: parseInt(e.target.value) || 8 })}
                    min="1"
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">
                  Limite Diário por Instância
                </label>
                <input
                  type="number"
                  value={formData.daily_limit_per_instance}
                  onChange={(e) => setFormData({ ...formData, daily_limit_per_instance: parseInt(e.target.value) || 100 })}
                  min="1"
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Quantidade máxima de mensagens que cada instância pode enviar por dia
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">
                  Pausar se Health Score abaixo de
                </label>
                <input
                  type="number"
                  value={formData.pause_on_health_below}
                  onChange={(e) => setFormData({ ...formData, pause_on_health_below: parseInt(e.target.value) || 50 })}
                  min="0"
                  max="100"
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                />
                <p className="text-xs text-gray-500 mt-1">
                  A campanha será pausada automaticamente se o health de uma instância cair abaixo deste valor
                </p>
              </div>

              <Card className="p-4 bg-gray-50">
                <h4 className="font-medium mb-2">⚙️ Resumo das Configurações</h4>
                <ul className="text-sm text-gray-700 space-y-1">
                  <li>• Intervalo entre mensagens: {formData.interval_min}-{formData.interval_max} segundos</li>
                  <li>• Limite diário: {formData.daily_limit_per_instance} mensagens/instância</li>
                  <li>• Pausar com health abaixo de: {formData.pause_on_health_below}%</li>
                </ul>
              </Card>
            </div>
          )}

          {/* STEP 6: Revisão */}
          {step === 6 && (
            <div className="space-y-4">
              <h3 className="text-lg font-semibold">Revisão Final</h3>

              <Card className="p-4">
                <h4 className="font-medium mb-3">📋 Informações da Campanha</h4>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-600">Nome:</span>
                    <span className="font-medium">{formData.name}</span>
                  </div>
                  {formData.description && (
                    <div className="flex justify-between">
                      <span className="text-gray-600">Descrição:</span>
                      <span className="font-medium">{formData.description}</span>
                    </div>
                  )}
                  {formData.scheduled_at && (
                    <div className="flex justify-between">
                      <span className="text-gray-600">Agendada para:</span>
                      <span className="font-medium">{new Date(formData.scheduled_at).toLocaleString('pt-BR')}</span>
                    </div>
                  )}
                </div>
              </Card>

              <Card className="p-4">
                <h4 className="font-medium mb-3">👥 Público</h4>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-600">Total de contatos:</span>
                    <span className="font-bold text-blue-600">{getSelectedContactsCount()}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Tipo:</span>
                    <span className="font-medium">
                      {formData.audience_type === 'tag' ? 'Filtrado por Tag' : 'Contatos Avulsos'}
                    </span>
                  </div>
                  {formData.audience_type === 'tag' && formData.tag_id && (
                    <div className="flex justify-between">
                      <span className="text-gray-600">Tag selecionada:</span>
                      <span className="font-medium">
                        🏷️ {tags.find(t => t.id === formData.tag_id)?.name}
                      </span>
                    </div>
                  )}
                </div>
              </Card>

              <Card className="p-4">
                <h4 className="font-medium mb-3">💬 Mensagens</h4>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-600">Templates criados:</span>
                    <span className="font-medium">{formData.messages.filter(m => m.content && typeof m.content === 'string' && m.content.trim()).length}</span>
                  </div>
                </div>
              </Card>

              <Card className="p-4">
                <h4 className="font-medium mb-3">⚡ Instâncias e Rotação</h4>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-600">Instâncias selecionadas:</span>
                    <span className="font-medium">{formData.instance_ids.length}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Modo de rotação:</span>
                    <span className="font-medium">
                      {formData.rotation_mode === 'round_robin' ? 'Round Robin' :
                       formData.rotation_mode === 'balanced' ? 'Balanceado' : 'Inteligente'}
                    </span>
                  </div>
                </div>
              </Card>

              <Card className="p-4 bg-green-50 border-green-200">
                <div className="flex items-start gap-2">
                  <Check className="h-5 w-5 text-green-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="font-medium text-green-900">Tudo pronto!</p>
                    <p className="text-sm text-green-700 mt-1">
                      Sua campanha será criada e {formData.scheduled_at ? 'executada automaticamente no horário agendado' : 'salva como rascunho'}
                    </p>
                  </div>
                </div>
              </Card>
            </div>
          )}
        </div>

        {/* Footer - Navigation */}
        <div className="flex justify-between items-center p-4 border-t bg-gray-50 sticky bottom-0">
          <Button
            variant="outline"
            onClick={handleBack}
            disabled={step === 1 || isLoading}
          >
            <ChevronLeft className="h-4 w-4 mr-1" />
            Voltar
          </Button>

          <div className="text-sm text-gray-600">
            Passo {step} de 6
          </div>

          {step < 6 ? (
            <Button
              onClick={handleNext}
              disabled={!canProceed() || isLoading}
            >
              Próximo
              <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          ) : (
            <Button
              onClick={handleSubmit}
              disabled={isLoading}
            >
              <Send className="h-4 w-4 mr-2" />
              {isLoading ? 'Criando...' : 'Criar Campanha'}
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}

