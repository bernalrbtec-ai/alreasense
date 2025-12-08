import { useState, useEffect } from 'react'
import { X } from 'lucide-react'
import { Button } from '../ui/Button'
import { api } from '../../lib/api'
import { showSuccessToast, showErrorToast, showLoadingToast, updateToastSuccess, updateToastError } from '../../lib/toastHelper'

// Helper para gerar URL do media proxy
const getMediaProxyUrl = (externalUrl: string) => {
  const API_BASE_URL = (import.meta as any).env.VITE_API_BASE_URL || 'http://localhost:8000';
  if (!externalUrl) return null;
  return `${API_BASE_URL}/api/chat/media-proxy/?url=${encodeURIComponent(externalUrl)}`;
};

interface Tag {
  id: string
  name: string
  color: string
}

interface Contact {
  id?: string
  name: string
  phone: string
  email?: string
  profile_pic_url?: string | null  // ✅ NOVO: Foto de perfil
  birth_date?: string
  gender?: string
  city?: string
  state?: string
  zipcode?: string
  referred_by?: string
  notes?: string
  tags?: Tag[]
}

interface ContactModalProps {
  isOpen: boolean
  onClose: () => void
  contact?: Contact | null
  initialPhone?: string
  initialName?: string
  onSuccess?: () => void
}

export default function ContactModal({
  isOpen,
  onClose,
  contact,
  initialPhone = '',
  initialName = '',
  onSuccess
}: ContactModalProps) {
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
  
  const [tags, setTags] = useState<Tag[]>([])
  const [newTagName, setNewTagName] = useState('')
  const [newTagColor, setNewTagColor] = useState('#3b82f6')
  const [isLoading, setIsLoading] = useState(false)

  // Carregar tags ao abrir modal
  useEffect(() => {
    if (isOpen) {
      fetchTags()
    }
  }, [isOpen])

  // Preencher formulário quando contato ou dados iniciais mudarem
  useEffect(() => {
    if (isOpen) {
      if (contact) {
        // Editar contato existente
        setFormData({
          name: contact.name || '',
          phone: contact.phone || '',
          email: contact.email || '',
          birth_date: contact.birth_date || '',
          gender: contact.gender || '',
          city: contact.city || '',
          state: contact.state || '',
          zipcode: contact.zipcode || '',
          referred_by: contact.referred_by || '',
          notes: contact.notes || '',
          tag_ids: contact.tags ? contact.tags.map(t => typeof t === 'string' ? t : t.id) : []
        })
      } else {
        // Novo contato - usar dados iniciais se fornecidos
        setFormData({
          name: initialName || '',
          phone: initialPhone || '',
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
    }
  }, [isOpen, contact, initialPhone, initialName])

  const fetchTags = async () => {
    try {
      const response = await api.get('/contacts/tags/')
      setTags(response.data.results || response.data || [])
    } catch (error) {
      console.error('Erro ao carregar tags:', error)
    }
  }

  const createTag = async () => {
    if (!newTagName.trim()) return

    try {
      const response = await api.post('/contacts/tags/', {
        name: newTagName.trim(),
        color: newTagColor
      })
      setTags(prev => [...prev, response.data])
      setNewTagName('')
      setNewTagColor('#3b82f6')
      showSuccessToast('criar', 'Tag')
    } catch (error: any) {
      showErrorToast('criar', 'Tag', error)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!formData.name.trim() || !formData.phone.trim()) {
      showErrorToast('salvar', 'Contato', { message: 'Nome e telefone são obrigatórios' })
      return
    }

    const toastId = showLoadingToast(contact ? 'atualizar' : 'criar', 'Contato')
    setIsLoading(true)

    try {
      if (contact?.id) {
        // Atualizar contato existente
        await api.patch(`/contacts/contacts/${contact.id}/`, formData)
        // ✅ MELHORIA UX: Feedback visual melhorado ao atualizar nome
        updateToastSuccess(toastId, 'atualizar', 'Contato')
        // ✅ Toast adicional com detalhes (se nome mudou)
        if (formData.name !== contact.name) {
          const { toast: toastFn } = await import('sonner')
          toastFn.success('Nome atualizado! ✅', {
            description: `O nome "${formData.name}" foi atualizado com sucesso e já está visível na conversa`,
            duration: 4000,
          })
        }
      } else {
        // Criar novo contato
        await api.post('/contacts/contacts/', formData)
        updateToastSuccess(toastId, 'criar', 'Contato')
      }
      
      onSuccess?.()
      onClose()
    } catch (error: any) {
      updateToastError(toastId, contact ? 'atualizar' : 'criar', 'Contato', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleClose = () => {
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
    setNewTagName('')
    setNewTagColor('#3b82f6')
    onClose()
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-bold">
              {contact?.id ? 'Editar Contato' : 'Novo Contato'}
            </h2>
            <button onClick={handleClose} className="text-gray-500 hover:text-gray-700">
              <X className="h-5 w-5" />
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* ✅ NOVO: Foto de perfil (apenas ao editar) */}
            {contact?.id && contact?.profile_pic_url && (
              <div className="flex items-center gap-4 pb-4 border-b">
                <div className="flex-shrink-0 w-20 h-20 rounded-full bg-gray-200 overflow-hidden">
                  <img
                    src={getMediaProxyUrl(contact.profile_pic_url) || ''}
                    alt={contact.name}
                    className="w-full h-full object-cover"
                    onError={(e) => {
                      // Fallback se imagem não carregar
                      const target = e.currentTarget as HTMLImageElement;
                      target.style.display = 'none';
                      const parent = target.parentElement;
                      if (parent) {
                        parent.innerHTML = `
                          <div class="w-full h-full flex items-center justify-center bg-gray-300 text-gray-600 font-medium text-xl">
                            ${contact.name.charAt(0).toUpperCase()}
                          </div>
                        `;
                      }
                    }}
                  />
                </div>
                <div className="flex-1">
                  <p className="text-sm text-gray-600">Foto de perfil do WhatsApp</p>
                  <p className="text-xs text-gray-500">Atualizada automaticamente quando há mudança no WhatsApp</p>
                </div>
              </div>
            )}
            
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
                      className={`group relative inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-sm font-medium transition-colors cursor-pointer ${
                        isSelected
                          ? 'bg-blue-600 text-white border-2 border-blue-600'
                          : 'bg-white text-gray-700 border-2 border-gray-300 hover:border-blue-400'
                      }`}
                      style={{ backgroundColor: isSelected ? tag.color : 'white', borderColor: tag.color }}
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
                    >
                      {tag.name}
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
              <Button type="button" variant="outline" onClick={handleClose} disabled={isLoading}>
                Cancelar
              </Button>
              <Button type="submit" disabled={isLoading}>
                {isLoading ? 'Salvando...' : (contact?.id ? 'Salvar' : 'Criar')}
              </Button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}


