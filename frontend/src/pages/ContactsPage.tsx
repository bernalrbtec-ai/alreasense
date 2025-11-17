import { useState, useEffect } from 'react'
import { Search, Plus, Upload, Download, Filter, X, Users as UsersIcon, Grid, Table as TableIcon, Edit, Trash2 } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import { api } from '../lib/api'
import { showSuccessToast, showErrorToast, showLoadingToast, updateToastSuccess, updateToastError } from '../lib/toastHelper'
import ContactCard from '../components/contacts/ContactCard'
import ImportContactsModal from '../components/contacts/ImportContactsModal'
import ContactsTable from '../components/contacts/ContactsTable'
import TagEditModal from '../components/contacts/TagEditModal'

interface Contact {
  id: string
  name: string
  phone: string
  email?: string
  city?: string
  state?: string
  birth_date?: string
  referred_by?: string
  lifecycle_stage: string
  rfm_segment: string
  engagement_score: number
  lifetime_value: number
  last_purchase_date?: string // ✅ Campo importado do CSV (data_compra)
  last_purchase_value?: number // ✅ Campo importado do CSV (Valor)
  days_until_birthday?: number
  tags: Tag[]
  is_active: boolean
  opted_out: boolean
  msgs_sent: number
  msgs_delivered: number
  created_at: string
  custom_fields?: Record<string, any> // Campos customizados importados
}

interface Tag {
  id: string
  name: string
  color: string
  description?: string
  contact_count?: number
}


export default function ContactsPage() {
  const [contacts, setContacts] = useState<Contact[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [showImportModal, setShowImportModal] = useState(false)
  const [editingContact, setEditingContact] = useState<Contact | null>(null)
  const [tags, setTags] = useState<Tag[]>([])
  const [newTagName, setNewTagName] = useState('')
  const [newTagColor, setNewTagColor] = useState('#3B82F6')
  const [editingTag, setEditingTag] = useState<Tag | null>(null)
  const [isTagEditModalOpen, setIsTagEditModalOpen] = useState(false)
  
  // Paginação
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [totalCount, setTotalCount] = useState(0)
  const pageSize = 50
  
  // Filtros
  const [selectedTag, setSelectedTag] = useState('')
  const [selectedState, setSelectedState] = useState('')
  const [selectedCustomField, setSelectedCustomField] = useState('')
  const [customFieldValue, setCustomFieldValue] = useState('')
  
  // Visualização
  const [viewMode, setViewMode] = useState<'cards' | 'table'>('cards')
  
  // Campos customizados disponíveis (extraídos dos contatos)
  const [availableCustomFields, setAvailableCustomFields] = useState<string[]>([])
  
  // Stats gerais
  const [stats, setStats] = useState({
    total: 0,
    active: 0,
    leads: 0,
    customers: 0,
    opted_out: 0,
    delivery_problems: 0
  })
  
  // Estados brasileiros
  const brazilianStates = [
    'AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA',
    'MT', 'MS', 'MG', 'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN',
    'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO'
  ]
  
  const [formData, setFormData] = useState({
    name: '',
    phone: '',
    email: '',
    birth_date: '',
    gender: '',
    city: '',
    state: '',
    zipcode: '',
    referred_by: '',
    notes: '',
    tag_ids: [] as string[]
  })

  useEffect(() => {
    fetchContacts()
    fetchTags()
    fetchStats()
  }, [])
  
  // Buscar quando filtros mudarem (sempre, mesmo se limpar)
  useEffect(() => {
    fetchContacts(1)
    fetchStats() // Atualizar stats quando filtros mudarem
  }, [selectedTag, selectedState])
  
  // Busca em tempo real (debounced) - aguarda 500ms após parar de digitar
  useEffect(() => {
    const debounceTimer = setTimeout(() => {
      fetchContacts(1)
      fetchStats() // Atualizar stats quando busca mudar
    }, 500)
    
    return () => clearTimeout(debounceTimer)
  }, [searchTerm])

  const fetchContacts = async (page = 1) => {
    try {
      setIsLoading(true)
      const params = new URLSearchParams()
      
      // Busca por texto
      if (searchTerm) params.append('search', searchTerm)
      
      // Filtros
      if (selectedTag) params.append('tags', selectedTag)
      if (selectedState) params.append('state', selectedState)
      
      // Paginação
      params.append('page', page.toString())
      params.append('page_size', pageSize.toString())
      
      // Ordenação alfabética
      params.append('ordering', 'name')
      
      const response = await api.get(`/contacts/contacts/?${params}`)
      const data = response.data
      
      const contactsData = data.results || data
      setContacts(contactsData)
      setTotalCount(data.count || contactsData.length)
      setTotalPages(Math.ceil((data.count || contactsData.length) / pageSize))
      setCurrentPage(page)
      
      // Extrair campos customizados únicos dos contatos
      // ✅ CORREÇÃO: Incluir TODOS os campos, mesmo que vazios/null (para garantir que todos apareçam)
      const customFieldsSet = new Set<string>()
      contactsData.forEach((contact: Contact) => {
        if (contact.custom_fields && typeof contact.custom_fields === 'object') {
          Object.keys(contact.custom_fields).forEach(key => {
            // Adicionar campo mesmo se vazio/null (para garantir que todos apareçam na tabela)
            customFieldsSet.add(key)
          })
        }
      })
      const sortedFields = Array.from(customFieldsSet).sort()
      setAvailableCustomFields(sortedFields)
      console.log(`📋 Campos customizados detectados (${sortedFields.length}):`, sortedFields)
      
      console.log(`📊 Página ${page}: ${contactsData.length} contatos de ${data.count || 0} total`)
    } catch (error: any) {
      console.error('Error fetching contacts:', error)
      showErrorToast('carregar', 'Contatos', error)
    } finally {
      setIsLoading(false)
    }
  }

  const fetchTags = async () => {
    try {
      const response = await api.get('/contacts/tags/')
      setTags(response.data.results || response.data)
    } catch (error) {
      console.error('Error fetching tags:', error)
    }
  }

  const createTag = async () => {
    if (!newTagName.trim()) return
    
    try {
      const response = await api.post('/contacts/tags/', {
        name: newTagName.trim(),
        color: newTagColor
      })
      
      // Adicionar a nova tag à lista
      setTags(prev => [...prev, response.data])
      
      // Selecionar automaticamente a nova tag
      setFormData(prev => ({
        ...prev,
        tag_ids: [...prev.tag_ids, response.data.id]
      }))
      
      // Limpar campos
      setNewTagName('')
      setNewTagColor('#3B82F6')
      
      showSuccessToast('criar', 'Tag')
    } catch (error: any) {
      console.error('Error creating tag:', error)
      showErrorToast('criar', 'Tag', error)
    }
  }

  const handleEditTag = (tag: Tag) => {
    setEditingTag(tag)
    setIsTagEditModalOpen(true)
  }

  const handleDeleteTag = async (tag: Tag, deleteContacts: boolean) => {
    const toastId = showLoadingToast('excluir', 'Tag')
    
    try {
      await api.delete(`/contacts/tags/${tag.id}/delete_with_options/?delete_contacts=${deleteContacts}`)
      
      // Remover tag da lista
      setTags(prev => prev.filter(t => t.id !== tag.id))
      
      // Se estava selecionada, limpar seleção
      if (selectedTag === tag.id) {
        setSelectedTag('')
      }
      
      // Recarregar contatos se necessário
      fetchContacts(currentPage)
      
      updateToastSuccess(toastId, 'excluir', 'Tag')
    } catch (error: any) {
      updateToastError(toastId, 'excluir', 'Tag', error)
    }
  }

  const handleTagEditSuccess = () => {
    fetchTags()
    fetchContacts(currentPage)
  }

  
  const fetchStats = async () => {
    try {
      // Construir parâmetros de filtro para stats
      const params = new URLSearchParams()
      
      if (searchTerm) params.append('search', searchTerm)
      if (selectedTag) params.append('tags', selectedTag)
      if (selectedState) params.append('state', selectedState)
      
      // Buscar stats com os mesmos filtros aplicados
      const response = await api.get(`/contacts/contacts/stats/?${params}`)
      const data = response.data
      
      console.log('📊 Stats carregadas:', data)
      
      setStats({
        total: data.total || 0,
        active: data.active || 0,
        leads: data.leads || 0,
        customers: data.customers || 0,
        opted_out: data.opted_out || 0,
        delivery_problems: data.delivery_problems || 0
      })
    } catch (error) {
      console.error('Error fetching stats:', error)
      // Fallback para stats básicas
      setStats({
        total: totalCount,
        active: 0,
        leads: 0,
        customers: 0,
        opted_out: 0,
        delivery_problems: 0
      })
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    const toastId = showLoadingToast(editingContact ? 'atualizar' : 'criar', 'Contato')
    
    try {
      // 🔧 CORREÇÃO: Normalizar telefone para formato E.164
      let normalizedPhone = formData.phone.replace(/\D/g, '') // Remove tudo que não é número
      
      // Se não começar com código do país, adicionar +55 (Brasil)
      if (normalizedPhone && !normalizedPhone.startsWith('55')) {
        normalizedPhone = '55' + normalizedPhone
      }
      
      // Adicionar o +
      if (normalizedPhone && !normalizedPhone.startsWith('+')) {
        normalizedPhone = '+' + normalizedPhone
      }
      
      // 🔧 CORREÇÃO: Garantir que tag_ids seja sempre array
      const dataToSend = {
        ...formData,
        tag_ids: Array.isArray(formData.tag_ids) ? formData.tag_ids : [],
        // Garantir que campos vazios sejam strings vazias, não null
        name: formData.name || '',
        phone: normalizedPhone || '',
        email: formData.email || '',
        birth_date: formData.birth_date || '',
        gender: formData.gender || '',
        city: formData.city || '',
        state: formData.state || '',
        zipcode: formData.zipcode || '',
        referred_by: formData.referred_by || '',
        notes: formData.notes || ''
      }
      
      if (editingContact) {
        await api.put(`/contacts/contacts/${editingContact.id}/`, dataToSend)
        updateToastSuccess(toastId, 'atualizar', 'Contato')
      } else {
        await api.post('/contacts/contacts/', dataToSend)
        updateToastSuccess(toastId, 'criar', 'Contato')
      }
      
      handleCloseModal()
      fetchContacts()
    } catch (error: any) {
      console.error('Error saving contact:', error)
      updateToastError(toastId, editingContact ? 'atualizar' : 'criar', 'Contato', error)
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Deseja realmente excluir este contato?')) return
    
    const toastId = showLoadingToast('excluir', 'Contato')
    
    try {
      await api.delete(`/contacts/contacts/${id}/`)
      updateToastSuccess(toastId, 'excluir', 'Contato')
      fetchContacts()
    } catch (error: any) {
      console.error('Error deleting contact:', error)
      updateToastError(toastId, 'excluir', 'Contato', error)
    }
  }

  const handleEdit = (contact: Contact) => {
    setEditingContact(contact)
    setFormData({
      name: contact.name,
      phone: contact.phone,
      email: contact.email || '',
      birth_date: contact.birth_date || '',
      gender: '',
      city: contact.city || '',
      state: contact.state || '',
      zipcode: '',
      referred_by: contact.referred_by || '',
      notes: '',
      tag_ids: contact.tags.map(t => t.id)
    })
    setIsModalOpen(true)
  }

  const handleCloseModal = () => {
    setIsModalOpen(false)
    setEditingContact(null)
    setFormData({
      name: '',
      phone: '',
      email: '',
      birth_date: '',
      gender: '',
      city: '',
      state: '',
      zipcode: '',
      referred_by: '',
      notes: '',
      tag_ids: []
    })
  }

  const handleExport = async () => {
    try {
      const response = await api.get('/contacts/contacts/export_csv/', {
        responseType: 'blob'
      })
      
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `contacts_${new Date().toISOString().split('T')[0]}.csv`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      
      showSuccessToast('exportar', 'Contatos')
    } catch (error: any) {
      console.error('Error exporting contacts:', error)
      showErrorToast('exportar', 'Contatos', error)
    }
  }

  // Importação agora usa ImportContactsModal completo

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-900 flex items-center gap-2">
            <UsersIcon className="h-5 w-5 sm:h-6 sm:w-6" /> Contatos
          </h1>
          <p className="mt-1 text-sm text-gray-500">
            Gerencie sua base de contatos enriquecidos
          </p>
        </div>
        
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={handleExport}>
            <Download className="h-4 w-4 mr-2" />
            Exportar
          </Button>
          
          <Button variant="outline" onClick={() => setShowImportModal(true)}>
            <Upload className="h-4 w-4 mr-2" />
            Importar CSV
          </Button>
          
          <Button onClick={() => setIsModalOpen(true)}>
            <Plus className="h-4 w-4 mr-2" />
            Novo Contato
          </Button>
        </div>
      </div>

      {/* Toggle de Visualização */}
      <div className="flex justify-between items-center mb-4">
        <div className="flex gap-2">
          <Button
            variant={viewMode === 'cards' ? 'default' : 'outline'}
            onClick={() => setViewMode('cards')}
            className="flex items-center gap-2"
          >
            <Grid className="h-4 w-4" />
            Cards
          </Button>
          <Button
            variant={viewMode === 'table' ? 'default' : 'outline'}
            onClick={() => setViewMode('table')}
            className="flex items-center gap-2"
          >
            <TableIcon className="h-4 w-4" />
            Tabela
          </Button>
        </div>
      </div>

      {/* Filtros e Busca */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Busca por texto */}
        <div className="md:col-span-2 relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
          <input
            type="text"
            placeholder="Buscar por nome, telefone ou email..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-10 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
          {searchTerm && !isLoading && (
            <button
              onClick={() => setSearchTerm('')}
              className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600"
              title="Limpar busca"
            >
              <X className="h-4 w-4" />
            </button>
          )}
          {isLoading && searchTerm && (
            <div className="absolute right-3 top-1/2 transform -translate-y-1/2">
              <div className="animate-spin h-4 w-4 border-2 border-blue-600 border-t-transparent rounded-full"></div>
            </div>
          )}
        </div>
        
        {/* Filtro por Tag */}
        <div>
          <select
            value={selectedTag}
            onChange={(e) => {
              setSelectedTag(e.target.value)
              setCurrentPage(1)
            }}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            <option value="">Todas as tags</option>
            {tags.map((tag) => (
              <option key={tag.id} value={tag.id}>
                {tag.name}
              </option>
            ))}
          </select>
        </div>
        
        {/* Filtro por Estado */}
        <div>
          <select
            value={selectedState}
            onChange={(e) => {
              setSelectedState(e.target.value)
              setCurrentPage(1)
            }}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            <option value="">Todos os estados</option>
            {brazilianStates.map((state) => (
              <option key={state} value={state}>
                {state}
              </option>
            ))}
          </select>
        </div>
      </div>
      
      {/* Filtro por Campo Customizado */}
      {availableCustomFields.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Filtrar por Campo Customizado
            </label>
            <select
              value={selectedCustomField}
              onChange={(e) => {
                setSelectedCustomField(e.target.value)
                setCustomFieldValue('')
                setCurrentPage(1)
              }}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
            >
              <option value="">Selecione um campo</option>
              {availableCustomFields.map((field) => (
                <option key={field} value={field}>
                  {field.charAt(0).toUpperCase() + field.slice(1)}
                </option>
              ))}
            </select>
          </div>
          {selectedCustomField && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Valor do campo
              </label>
              <input
                type="text"
                placeholder={`Buscar por ${selectedCustomField}...`}
                value={customFieldValue}
                onChange={(e) => {
                  setCustomFieldValue(e.target.value)
                  setCurrentPage(1)
                }}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
              />
            </div>
          )}
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="p-4">
          <div className="text-sm text-gray-500">Total de Contatos</div>
          <div className="text-2xl font-bold">{stats.total}</div>
          <div className="text-xs text-gray-400 mt-1">
            {selectedTag || selectedState || searchTerm ? 'Filtrados' : 'Base completa'}
          </div>
        </Card>
        
        <Card className="p-4">
          <div className="text-sm text-gray-500">Ativos</div>
          <div className="text-2xl font-bold text-green-600">{stats.active}</div>
          <div className="text-xs text-gray-400 mt-1">
            Contatos ativos
          </div>
        </Card>
        
        <Card className="p-4">
          <div className="text-sm text-gray-500">Opt-out</div>
          <div className="text-2xl font-bold text-red-600">{stats.opted_out}</div>
          <div className="text-xs text-gray-400 mt-1">
            Contatos que saíram
          </div>
        </Card>
        
        <Card className="p-4">
          <div className="text-sm text-gray-500">Problemas de Entrega</div>
          <div className="text-2xl font-bold text-orange-600">{stats.delivery_problems}</div>
          <div className="text-xs text-gray-400 mt-1">
            Mensagens não entregues
          </div>
        </Card>
      </div>
      
      {/* Stats Detalhadas */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="p-4">
          <div className="text-sm text-gray-500">Leads</div>
          <div className="text-xl font-bold text-blue-600">{stats.leads}</div>
          <div className="text-xs text-gray-400 mt-1">
            Contatos sem compras
          </div>
        </Card>
        
        <Card className="p-4">
          <div className="text-sm text-gray-500">Clientes</div>
          <div className="text-xl font-bold text-green-600">{stats.customers}</div>
          <div className="text-xs text-gray-400 mt-1">
            Contatos com compras
          </div>
        </Card>
      </div>

      {/* Contact Grid ou Tabela */}
      {viewMode === 'cards' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {contacts
            .filter(contact => {
              // Filtrar por campo customizado se selecionado
              if (selectedCustomField && customFieldValue) {
                const fieldValue = contact.custom_fields?.[selectedCustomField]
                if (!fieldValue || !String(fieldValue).toLowerCase().includes(customFieldValue.toLowerCase())) {
                  return false
                }
              }
              return true
            })
            .map(contact => (
              <ContactCard
                key={contact.id}
                contact={contact}
                onEdit={handleEdit}
                onDelete={handleDelete}
              />
            ))}
        </div>
      ) : (
        <ContactsTable
          contacts={contacts.filter(contact => {
            // Filtrar por campo customizado se selecionado
            if (selectedCustomField && customFieldValue) {
              const fieldValue = contact.custom_fields?.[selectedCustomField]
              if (!fieldValue || !String(fieldValue).toLowerCase().includes(customFieldValue.toLowerCase())) {
                return false
              }
            }
            return true
          })}
          availableCustomFields={availableCustomFields}
          onEdit={handleEdit}
          onDelete={handleDelete}
        />
      )}
      
      {/* Paginação */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between border-t border-gray-200 bg-white px-4 py-3 sm:px-6 rounded-lg">
          <div className="flex flex-1 justify-between sm:hidden">
            <Button
              variant="outline"
              onClick={() => fetchContacts(currentPage - 1)}
              disabled={currentPage === 1}
            >
              Anterior
            </Button>
            <Button
              variant="outline"
              onClick={() => fetchContacts(currentPage + 1)}
              disabled={currentPage === totalPages}
            >
              Próxima
            </Button>
          </div>
          <div className="hidden sm:flex sm:flex-1 sm:items-center sm:justify-between">
            <div>
              <p className="text-sm text-gray-700">
                Mostrando <span className="font-medium">{(currentPage - 1) * pageSize + 1}</span> até{' '}
                <span className="font-medium">{Math.min(currentPage * pageSize, totalCount)}</span> de{' '}
                <span className="font-medium">{totalCount}</span> contatos
              </p>
            </div>
            <div>
              <nav className="isolate inline-flex -space-x-px rounded-md shadow-sm" aria-label="Pagination">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => fetchContacts(currentPage - 1)}
                  disabled={currentPage === 1}
                  className="rounded-l-md"
                >
                  Anterior
                </Button>
                
                {/* Páginas */}
                {[...Array(Math.min(5, totalPages))].map((_, idx) => {
                  let pageNum
                  if (totalPages <= 5) {
                    pageNum = idx + 1
                  } else if (currentPage <= 3) {
                    pageNum = idx + 1
                  } else if (currentPage >= totalPages - 2) {
                    pageNum = totalPages - 4 + idx
                  } else {
                    pageNum = currentPage - 2 + idx
                  }
                  
                  return (
                    <Button
                      key={pageNum}
                      variant={currentPage === pageNum ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => fetchContacts(pageNum)}
                      className="border-l-0"
                    >
                      {pageNum}
                    </Button>
                  )
                })}
                
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => fetchContacts(currentPage + 1)}
                  disabled={currentPage === totalPages}
                  className="rounded-r-md border-l-0"
                >
                  Próxima
                </Button>
              </nav>
            </div>
          </div>
        </div>
      )}

      {contacts.length === 0 && (
        <div className="text-center py-12">
          <UsersIcon className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-2 text-sm font-medium text-gray-900">Nenhum contato</h3>
          <p className="mt-1 text-sm text-gray-500">Comece adicionando um novo contato</p>
          <div className="mt-6">
            <Button onClick={() => setIsModalOpen(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Novo Contato
            </Button>
          </div>
        </div>
      )}

      {/* Create/Edit Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-xl font-bold">
                  {editingContact ? 'Editar Contato' : 'Novo Contato'}
                </h2>
                <button onClick={handleCloseModal} className="text-gray-500 hover:text-gray-700">
                  <X className="h-5 w-5" />
                </button>
              </div>

              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Nome *
                    </label>
                    <input
                      type="text"
                      required
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Telefone *
                    </label>
                    <input
                      type="tel"
                      required
                      value={formData.phone}
                      onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                      placeholder="+5511999999999"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Email
                    </label>
                    <input
                      type="email"
                      value={formData.email}
                      onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Data de Nascimento
                    </label>
                    <input
                      type="date"
                      value={formData.birth_date}
                      onChange={(e) => setFormData({ ...formData, birth_date: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Cidade
                    </label>
                    <input
                      type="text"
                      value={formData.city}
                      onChange={(e) => setFormData({ ...formData, city: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Estado
                    </label>
                    <input
                      type="text"
                      maxLength={2}
                      value={formData.state}
                      onChange={(e) => setFormData({ ...formData, state: e.target.value.toUpperCase() })}
                      placeholder="SP"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Quem Indicou
                    </label>
                    <input
                      type="text"
                      value={formData.referred_by}
                      onChange={(e) => setFormData({ ...formData, referred_by: e.target.value })}
                      placeholder="Nome de quem indicou o contato"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Observações
                  </label>
                  <textarea
                    rows={3}
                    value={formData.notes}
                    onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                {/* Tags */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Tags
                  </label>
                  
                  {/* Tags Existentes */}
                  <div className="flex flex-wrap gap-2 p-3 border border-gray-300 rounded-lg bg-gray-50 min-h-[60px] mb-3">
                    {tags.map((tag) => {
                      const isSelected = formData.tag_ids.includes(tag.id)
                      return (
                        <div
                          key={tag.id}
                          className={`group relative inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                            isSelected
                              ? 'bg-blue-600 text-white border-2 border-blue-600'
                              : 'bg-white text-gray-700 border-2 border-gray-300 hover:border-blue-400'
                          }`}
                          style={{ backgroundColor: isSelected ? tag.color : 'white', borderColor: tag.color }}
                        >
                          <button
                            type="button"
                            onClick={() => {
                              if (isSelected) {
                                setFormData({
                                  ...formData,
                                  tag_ids: formData.tag_ids.filter(id => id !== tag.id)
                                })
                              } else {
                                setFormData({
                                  ...formData,
                                  tag_ids: [...formData.tag_ids, tag.id]
                                })
                              }
                            }}
                            className="flex-1"
                          >
                            {tag.name}
                          </button>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation()
                              handleEditTag(tag)
                            }}
                            className="opacity-0 group-hover:opacity-100 p-0.5 hover:bg-black/10 rounded transition-opacity"
                            title="Editar tag"
                          >
                            <Edit className="h-3 w-3" />
                          </button>
                        </div>
                      )
                    })}
                    {tags.length === 0 && (
                      <p className="text-sm text-gray-500">Nenhuma tag cadastrada</p>
                    )}
                  </div>
                  
                  {/* Criar Nova Tag */}
                  <div className="border border-gray-300 rounded-lg p-3 bg-blue-50">
                    <h4 className="text-sm font-medium text-gray-700 mb-2">Criar Nova Tag</h4>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        placeholder="Nome da tag"
                        value={newTagName}
                        onChange={(e) => setNewTagName(e.target.value)}
                        className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-sm"
                      />
                      <input
                        type="color"
                        value={newTagColor}
                        onChange={(e) => setNewTagColor(e.target.value)}
                        className="w-12 h-10 border border-gray-300 rounded-lg cursor-pointer"
                        title="Cor da tag"
                      />
                      <Button
                        type="button"
                        size="sm"
                        onClick={createTag}
                        disabled={!newTagName.trim()}
                      >
                        Criar
                      </Button>
                    </div>
                  </div>
                  
                  <p className="text-xs text-gray-500 mt-1">
                    Clique nas tags para selecionar/remover • Crie novas tags conforme necessário
                  </p>
                </div>

                <div className="flex justify-end gap-2 pt-4 border-t">
                  <Button type="button" variant="outline" onClick={handleCloseModal}>
                    Cancelar
                  </Button>
                  <Button type="submit">
                    {editingContact ? 'Salvar' : 'Criar'}
                  </Button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* Tag Edit Modal */}
      <TagEditModal
        tag={editingTag}
        isOpen={isTagEditModalOpen}
        onClose={() => {
          setIsTagEditModalOpen(false)
          setEditingTag(null)
        }}
        onSuccess={handleTagEditSuccess}
        onDelete={handleDeleteTag}
      />

      {/* Import Modal */}
      {showImportModal && (
        <ImportContactsModal
          onClose={() => setShowImportModal(false)}
          onSuccess={() => {
            fetchContacts()
            fetchStats() // ✅ CORREÇÃO: Atualizar contadores após importação
            setShowImportModal(false)
          }}
        />
      )}
    </div>
  )
}

