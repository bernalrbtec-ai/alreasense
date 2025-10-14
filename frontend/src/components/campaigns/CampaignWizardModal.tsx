import { useState, useEffect } from 'react'
import { X, ChevronRight, ChevronLeft, Check, AlertCircle, Info, Send, Users, MessageSquare, Settings, Eye, Zap } from 'lucide-react'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { api } from '../../lib/api'
import { showSuccessToast, showErrorToast, showLoadingToast, updateToastSuccess, updateToastError } from '../../lib/toastHelper'

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
    rotation_mode: 'intelligent' as 'round_robin' | 'balanced' | 'intelligent',
    
    // Step 5: Configurações
    interval_min: 25,
    interval_max: 50,
    daily_limit_per_instance: 100,
    pause_on_health_below: 30
  })

  useEffect(() => {
    fetchData()
  }, [])

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
        rotation_mode: editingCampaign.rotation_mode || 'intelligent',
        
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
    return formData.contact_ids.length
  }

  const canProceed = (): boolean => {
    switch (step) {
      case 1:
        return formData.name.trim().length > 0
      case 2:
        return getSelectedContactsCount() > 0
      case 3:
        return formData.messages.some(m => m.content.trim().length > 0)
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
      setStep(step + 1)
    }
  }

  const handleBack = () => {
    if (step > 1) {
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
        messages: formData.messages.filter(m => m.content.trim()),
        interval_min: formData.interval_min,
        interval_max: formData.interval_max,
        daily_limit_per_instance: formData.daily_limit_per_instance,
        pause_on_health_below: formData.pause_on_health_below,
        scheduled_at: formData.scheduled_at || null,
        tag_id: formData.audience_type === 'tag' ? formData.tag_id : null,
        contact_ids: formData.audience_type === 'contacts' ? formData.contact_ids : []
      }

      await api.post('/campaigns/campaigns/', payload)
      
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
    setFormData({
      ...formData,
      messages: [...formData.messages, { content: '', order: formData.messages.length + 1 }]
    })
  }

  const removeMessage = (index: number) => {
    const newMessages = formData.messages.filter((_, i) => i !== index)
    setFormData({ ...formData, messages: newMessages })
  }

  const updateMessage = (index: number, content: string) => {
    const newMessages = [...formData.messages]
    newMessages[index].content = content
    setFormData({ ...formData, messages: newMessages })
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
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
                      setFormData({ ...formData, tag_id: tagId })
                      
                      // ✅ Carregar contatos da tag via API quando seleciona uma tag
                      if (tagId) {
                        console.log(`🏷️ Tag selecionada: ${tagId}`)
                        const tagContacts = await fetchTagContacts(tagId)
                        setFormData({ 
                          ...formData, 
                          tag_id: tagId,
                          contact_ids: tagContacts.map(c => c.id)
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
                              // ✅ Usar tagContacts carregados via API
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
                                          setFormData({ ...formData, contact_ids: [...formData.contact_ids, contact.id] })
                                        } else {
                                          setFormData({ ...formData, contact_ids: formData.contact_ids.filter(id => id !== contact.id) })
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
                                setFormData({ ...formData, contact_ids: [...formData.contact_ids, contact.id] })
                              } else {
                                setFormData({ ...formData, contact_ids: formData.contact_ids.filter(id => id !== contact.id) })
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
            <div className="grid grid-cols-2 gap-4">
              {/* Coluna 1: Editor de Mensagens */}
              <div className="space-y-4">
                <div className="flex justify-between items-center">
                  <h3 className="text-lg font-semibold">Templates de Mensagem</h3>
                  <Button onClick={addMessage} size="sm">
                    + Adicionar
                  </Button>
                </div>

                {/* Variáveis Disponíveis */}
                <Card className="p-3 bg-blue-50 border-blue-200">
                  <p className="text-xs font-semibold text-blue-900 mb-2">📝 Variáveis disponíveis:</p>
                  <div className="grid grid-cols-2 gap-1 text-xs">
                    <button
                      type="button"
                      onClick={() => {
                        const lastIdx = formData.messages.length - 1
                        const lastMsg = formData.messages[lastIdx]
                        updateMessage(lastIdx, lastMsg.content + '{{nome}}')
                      }}
                      className="text-left px-2 py-1 bg-white rounded hover:bg-blue-100 text-blue-700"
                    >
                      <code>{'{{nome}}'}</code> - Nome completo
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        const lastIdx = formData.messages.length - 1
                        const lastMsg = formData.messages[lastIdx]
                        updateMessage(lastIdx, lastMsg.content + '{{primeiro_nome}}')
                      }}
                      className="text-left px-2 py-1 bg-white rounded hover:bg-blue-100 text-blue-700"
                    >
                      <code>{'{{primeiro_nome}}'}</code> - 1º nome
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        const lastIdx = formData.messages.length - 1
                        const lastMsg = formData.messages[lastIdx]
                        updateMessage(lastIdx, lastMsg.content + '{{saudacao}}')
                      }}
                      className="text-left px-2 py-1 bg-white rounded hover:bg-blue-100 text-blue-700"
                    >
                      <code>{'{{saudacao}}'}</code> - Bom dia/tarde/noite
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        const lastIdx = formData.messages.length - 1
                        const lastMsg = formData.messages[lastIdx]
                        updateMessage(lastIdx, lastMsg.content + '{{dia_semana}}')
                      }}
                      className="text-left px-2 py-1 bg-white rounded hover:bg-blue-100 text-blue-700"
                    >
                      <code>{'{{dia_semana}}'}</code> - Dia da semana
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        const lastIdx = formData.messages.length - 1
                        const lastMsg = formData.messages[lastIdx]
                        updateMessage(lastIdx, lastMsg.content + '{{quem_indicou}}')
                      }}
                      className="text-left px-2 py-1 bg-white rounded hover:bg-blue-100 text-blue-700"
                    >
                      <code>{'{{quem_indicou}}'}</code> - Quem indicou
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        const lastIdx = formData.messages.length - 1
                        const lastMsg = formData.messages[lastIdx]
                        updateMessage(lastIdx, lastMsg.content + '{{primeiro_nome_indicador}}')
                      }}
                      className="text-left px-2 py-1 bg-white rounded hover:bg-blue-100 text-blue-700"
                    >
                      <code>{'{{primeiro_nome_indicador}}'}</code> - 1º nome indicador
                    </button>
                  </div>
                </Card>

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
                            placeholder="Digite a mensagem... Use {{nome}}, {{saudacao}}, {{dia_semana}}"
                            className="w-full px-2 py-2 text-sm border rounded focus:ring-2 focus:ring-blue-500"
                            rows={3}
                          />
                          <p className="text-xs text-gray-500 mt-1">
                            {message.content.length} caracteres
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
              <div>
                <h3 className="text-lg font-semibold mb-4">Preview da Mensagem</h3>
                
                {/* Smartphone Mockup */}
                <div className="mx-auto max-w-sm">
                  <div className="bg-gray-900 rounded-3xl p-3 shadow-2xl">
                    {/* Tela do celular */}
                    <div className="bg-gradient-to-b from-teal-600 to-teal-700 rounded-2xl overflow-hidden">
                      {/* Header WhatsApp */}
                      <div className="bg-teal-700 px-4 py-3 flex items-center gap-3">
                        <div className="w-8 h-8 bg-gray-300 rounded-full"></div>
                        <div className="flex-1">
                          <p className="text-white font-medium text-sm">Você</p>
                          <p className="text-teal-100 text-xs">online</p>
                        </div>
                      </div>

                      {/* Chat Area */}
                      <div className="bg-[#e5ddd5] h-96 p-3 overflow-y-auto">
                        {formData.messages.filter(m => m.content.trim()).map((msg, idx) => {
                          // Substituir variáveis para preview
                          const nomeCompleto = 'Maria Silva'
                          const primeiroNome = nomeCompleto.split(' ')[0]
                          const quemIndicou = 'João Santos'
                          const primeiroNomeIndicador = quemIndicou.split(' ')[0]
                          
                          const previewText = msg.content
                            .replace(/\{\{nome\}\}/g, nomeCompleto)
                            .replace(/\{\{primeiro_nome\}\}/g, primeiroNome)
                            .replace(/\{\{quem_indicou\}\}/g, quemIndicou)
                            .replace(/\{\{primeiro_nome_indicador\}\}/g, primeiroNomeIndicador)
                            .replace(/\{\{saudacao\}\}/g, 
                              new Date().getHours() < 12 ? 'Bom dia' :
                              new Date().getHours() < 18 ? 'Boa tarde' : 'Boa noite'
                            )
                            .replace(/\{\{dia_semana\}\}/g, 
                              ['Domingo', 'Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado'][new Date().getDay()]
                            )
                          
                          return (
                            <div key={idx} className="mb-2 flex justify-end">
                              <div className="bg-[#dcf8c6] rounded-lg rounded-tr-none px-3 py-2 max-w-[85%] shadow-sm">
                                <p className="text-sm text-gray-800 whitespace-pre-wrap break-words">
                                  {previewText}
                                </p>
                                <p className="text-xs text-gray-500 text-right mt-1">
                                  {new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}
                                </p>
                              </div>
                            </div>
                          )
                        })}
                        
                        {formData.messages.filter(m => m.content.trim()).length === 0 && (
                          <div className="text-center text-gray-500 text-sm mt-20">
                            Digite uma mensagem para ver o preview
                          </div>
                        )}
                      </div>

                      {/* Input Area (só visual) */}
                      <div className="bg-gray-100 px-3 py-2 flex items-center gap-2">
                        <div className="flex-1 bg-white rounded-full px-4 py-2">
                          <p className="text-xs text-gray-400">Mensagem</p>
                        </div>
                        <div className="w-8 h-8 bg-teal-600 rounded-full flex items-center justify-center">
                          <Send className="h-4 w-4 text-white" />
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

                  <label className={`p-4 border-2 rounded-lg cursor-pointer transition-colors ${
                    formData.rotation_mode === 'balanced' ? 'border-blue-500 bg-blue-50' : 'border-gray-200'
                  }`}>
                    <input
                      type="radio"
                      checked={formData.rotation_mode === 'balanced'}
                      onChange={() => setFormData({ ...formData, rotation_mode: 'balanced' })}
                      className="mr-2"
                    />
                    <span className="font-medium">Balanceado</span>
                    <p className="text-xs text-gray-600 mt-1 ml-6">
                      Distribui com base na quantidade de mensagens enviadas por cada instância
                    </p>
                  </label>

                  <label className={`p-4 border-2 rounded-lg cursor-pointer transition-colors ${
                    formData.rotation_mode === 'intelligent' ? 'border-blue-500 bg-blue-50' : 'border-gray-200'
                  }`}>
                    <input
                      type="radio"
                      checked={formData.rotation_mode === 'intelligent'}
                      onChange={() => setFormData({ ...formData, rotation_mode: 'intelligent' })}
                      className="mr-2"
                    />
                    <span className="font-medium">Inteligente (Recomendado) ⭐</span>
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
                    <span className="font-medium">{formData.messages.filter(m => m.content.trim()).length}</span>
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

