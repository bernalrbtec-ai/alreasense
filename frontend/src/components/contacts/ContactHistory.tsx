import { useState, useEffect } from 'react'
import { Clock, MessageSquare, Send, CheckCircle, XCircle, User, ArrowRight, FileText, Plus, Edit, Trash2, X } from 'lucide-react'
import { api } from '../../lib/api'
import { showSuccessToast, showErrorToast } from '../../lib/toastHelper'
import { Button } from '../ui/Button'
import LoadingSpinner from '../ui/LoadingSpinner'
import { format } from 'date-fns'
import { ptBR } from 'date-fns/locale'

interface ContactHistoryItem {
  id: string
  event_type: string
  event_type_display: string
  title: string
  description?: string
  metadata?: Record<string, any>
  created_by_name?: string
  created_at: string
  is_editable: boolean
  related_conversation?: string
  related_campaign?: string
  related_message?: string
}

interface ContactHistoryProps {
  contactId: string
  onClose?: () => void
}

const EVENT_ICONS: Record<string, any> = {
  note: FileText,
  message_sent: Send,
  message_received: MessageSquare,
  campaign_message_sent: Send,
  campaign_message_delivered: CheckCircle,
  campaign_message_read: CheckCircle,
  campaign_message_failed: XCircle,
  department_transfer: ArrowRight,
  assigned_to: User,
  status_changed: Clock,
  contact_created: Plus,
  contact_updated: Edit,
}

const EVENT_COLORS: Record<string, string> = {
  note: 'bg-blue-100 text-blue-700 border-blue-200',
  message_sent: 'bg-green-100 text-green-700 border-green-200',
  message_received: 'bg-purple-100 text-purple-700 border-purple-200',
  campaign_message_sent: 'bg-indigo-100 text-indigo-700 border-indigo-200',
  campaign_message_delivered: 'bg-teal-100 text-teal-700 border-teal-200',
  campaign_message_read: 'bg-emerald-100 text-emerald-700 border-emerald-200',
  campaign_message_failed: 'bg-red-100 text-red-700 border-red-200',
  department_transfer: 'bg-yellow-100 text-yellow-700 border-yellow-200',
  assigned_to: 'bg-orange-100 text-orange-700 border-orange-200',
  status_changed: 'bg-gray-100 text-gray-700 border-gray-200',
  contact_created: 'bg-cyan-100 text-cyan-700 border-cyan-200',
  contact_updated: 'bg-blue-100 text-blue-700 border-blue-200',
}

export default function ContactHistory({ contactId, onClose }: ContactHistoryProps) {
  const [history, setHistory] = useState<ContactHistoryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [showAddNote, setShowAddNote] = useState(false)
  const [editingNote, setEditingNote] = useState<ContactHistoryItem | null>(null)
  const [noteTitle, setNoteTitle] = useState('')
  const [noteDescription, setNoteDescription] = useState('')

  useEffect(() => {
    fetchHistory()
  }, [contactId])

  const fetchHistory = async () => {
    try {
      setLoading(true)
      const response = await api.get(`/contacts/history/?contact_id=${contactId}`)
      setHistory(response.data.results || response.data)
    } catch (error: any) {
      console.error('Erro ao buscar histórico:', error)
      showErrorToast('Erro ao carregar histórico do contato')
    } finally {
      setLoading(false)
    }
  }

  const handleAddNote = async () => {
    if (!noteTitle.trim()) {
      showErrorToast('Título é obrigatório')
      return
    }

    try {
      await api.post('/contacts/history/', {
        contact_id: contactId,
        title: noteTitle,
        description: noteDescription,
      })
      showSuccessToast('Anotação adicionada com sucesso')
      setNoteTitle('')
      setNoteDescription('')
      setShowAddNote(false)
      fetchHistory()
    } catch (error: any) {
      console.error('Erro ao adicionar anotação:', error)
      showErrorToast(error.response?.data?.detail || 'Erro ao adicionar anotação')
    }
  }

  const handleEditNote = async () => {
    if (!editingNote || !noteTitle.trim()) {
      return
    }

    try {
      await api.patch(`/contacts/history/${editingNote.id}/`, {
        title: noteTitle,
        description: noteDescription,
      })
      showSuccessToast('Anotação atualizada com sucesso')
      setEditingNote(null)
      setNoteTitle('')
      setNoteDescription('')
      fetchHistory()
    } catch (error: any) {
      console.error('Erro ao editar anotação:', error)
      showErrorToast(error.response?.data?.detail || 'Erro ao editar anotação')
    }
  }

  const handleDeleteNote = async (noteId: string) => {
    if (!confirm('Tem certeza que deseja excluir esta anotação?')) {
      return
    }

    try {
      await api.delete(`/contacts/history/${noteId}/`)
      showSuccessToast('Anotação excluída com sucesso')
      fetchHistory()
    } catch (error: any) {
      console.error('Erro ao excluir anotação:', error)
      showErrorToast(error.response?.data?.detail || 'Erro ao excluir anotação')
    }
  }

  const startEdit = (item: ContactHistoryItem) => {
    setEditingNote(item)
    setNoteTitle(item.title)
    setNoteDescription(item.description || '')
    setShowAddNote(true)
  }

  const cancelEdit = () => {
    setEditingNote(null)
    setNoteTitle('')
    setNoteDescription('')
    setShowAddNote(false)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <LoadingSpinner />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900">Histórico do Contato</h3>
        <div className="flex gap-2">
          {!showAddNote && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setShowAddNote(true)
                setEditingNote(null)
                setNoteTitle('')
                setNoteDescription('')
              }}
            >
              <Plus className="h-4 w-4 mr-1" />
              Nova Anotação
            </Button>
          )}
          {onClose && (
            <Button variant="outline" size="sm" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>

      {/* Form de Anotação */}
      {showAddNote && (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Título *
            </label>
            <input
              type="text"
              value={noteTitle}
              onChange={(e) => setNoteTitle(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Ex: Cliente interessado em produto X"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Descrição
            </label>
            <textarea
              value={noteDescription}
              onChange={(e) => setNoteDescription(e.target.value)}
              rows={3}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Detalhes da anotação..."
            />
          </div>
          <div className="flex gap-2">
            <Button
              size="sm"
              onClick={editingNote ? handleEditNote : handleAddNote}
            >
              {editingNote ? 'Salvar' : 'Adicionar'}
            </Button>
            <Button variant="outline" size="sm" onClick={cancelEdit}>
              Cancelar
            </Button>
          </div>
        </div>
      )}

      {/* Timeline */}
      <div className="space-y-4">
        {history.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <Clock className="h-12 w-12 mx-auto mb-2 text-gray-400" />
            <p>Nenhum evento no histórico ainda</p>
          </div>
        ) : (
          history.map((item, index) => {
            const Icon = EVENT_ICONS[item.event_type] || Clock
            const colorClass = EVENT_COLORS[item.event_type] || 'bg-gray-100 text-gray-700 border-gray-200'

            return (
              <div key={item.id} className="relative pl-8 pb-4">
                {/* Linha vertical */}
                {index < history.length - 1 && (
                  <div className="absolute left-3 top-8 bottom-0 w-0.5 bg-gray-200" />
                )}

                {/* Ícone */}
                <div className={`absolute left-0 top-1 w-6 h-6 rounded-full ${colorClass} flex items-center justify-center border-2`}>
                  <Icon className="h-3 w-3" />
                </div>

                {/* Conteúdo */}
                <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`text-xs px-2 py-1 rounded ${colorClass}`}>
                          {item.event_type_display}
                        </span>
                        <span className="text-xs text-gray-500">
                          {format(new Date(item.created_at), "dd/MM/yyyy 'às' HH:mm", { locale: ptBR })}
                        </span>
                      </div>
                      <h4 className="font-medium text-gray-900 mb-1">{item.title}</h4>
                      {item.description && (
                        <p className="text-sm text-gray-600 whitespace-pre-wrap">{item.description}</p>
                      )}
                      {item.created_by_name && (
                        <p className="text-xs text-gray-500 mt-1">
                          Por: {item.created_by_name}
                        </p>
                      )}
                    </div>

                    {/* Ações para anotações editáveis */}
                    {item.is_editable && (
                      <div className="flex gap-1 ml-2">
                        <button
                          onClick={() => startEdit(item)}
                          className="p-1 text-gray-400 hover:text-blue-600 transition-colors"
                          title="Editar"
                        >
                          <Edit className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => handleDeleteNote(item.id)}
                          className="p-1 text-gray-400 hover:text-red-600 transition-colors"
                          title="Excluir"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}

