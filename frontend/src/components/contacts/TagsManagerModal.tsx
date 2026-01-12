import { useState, useEffect } from 'react'
import { X, Plus, Edit, Trash2, Tag as TagIcon, AlertTriangle } from 'lucide-react'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { api } from '../../lib/api'
import { showSuccessToast, showErrorToast, showLoadingToast, updateToastSuccess, updateToastError } from '../../lib/toastHelper'
import TagEditModal from './TagEditModal'

interface Tag {
  id: string
  name: string
  color: string
  description?: string
  contact_count?: number
}

interface TagsManagerModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess?: () => void
}

export default function TagsManagerModal({ isOpen, onClose, onSuccess }: TagsManagerModalProps) {
  const [tags, setTags] = useState<Tag[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [editingTag, setEditingTag] = useState<Tag | null>(null)
  const [isTagEditModalOpen, setIsTagEditModalOpen] = useState(false)
  const [deletingTag, setDeletingTag] = useState<Tag | null>(null)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [deleteOption, setDeleteOption] = useState<'remove' | 'migrate' | 'delete'>('remove')
  const [migrateToTagId, setMigrateToTagId] = useState<string>('')
  const [newTagName, setNewTagName] = useState('')
  const [newTagColor, setNewTagColor] = useState('#3B82F6')

  useEffect(() => {
    if (isOpen) {
      fetchTags()
    }
  }, [isOpen])

  const fetchTags = async () => {
    setIsLoading(true)
    try {
      const response = await api.get('/contacts/tags/')
      setTags(response.data.results || response.data || [])
    } catch (error: any) {
      showErrorToast('carregar', 'Tags', error)
    } finally {
      setIsLoading(false)
    }
  }

  const createTag = async () => {
    if (!newTagName.trim()) {
      showErrorToast('criar', 'Tag', new Error('Nome da tag é obrigatório'))
      return
    }

    const toastId = showLoadingToast('criar', 'Tag')

    try {
      const response = await api.post('/contacts/tags/', {
        name: newTagName.trim(),
        color: newTagColor
      })
      
      setTags(prev => [...prev, response.data])
      setNewTagName('')
      setNewTagColor('#3B82F6')
      updateToastSuccess(toastId, 'criar', 'Tag')
    } catch (error: any) {
      updateToastError(toastId, 'criar', 'Tag', error)
    }
  }

  const handleEditTag = (tag: Tag) => {
    setEditingTag(tag)
    setIsTagEditModalOpen(true)
  }

  const handleDeleteClick = (tag: Tag) => {
    setDeletingTag(tag)
    setShowDeleteConfirm(true)
    setDeleteOption('remove')
    setMigrateToTagId('')
  }

  const handleConfirmDelete = async () => {
    if (!deletingTag) return

    const deleteContacts = deleteOption === 'delete'
    const migrateId = deleteOption === 'migrate' ? migrateToTagId : undefined
    
    const toastId = showLoadingToast('excluir', 'Tag')
    
    try {
      let url = `/contacts/tags/${deletingTag.id}/delete_with_options/?delete_contacts=${deleteContacts}`
      if (migrateId) {
        url = `/contacts/tags/${deletingTag.id}/delete_with_options/?migrate_to_tag_id=${migrateId}`
      }
      
      await api.delete(url)
      
      setTags(prev => prev.filter(t => t.id !== deletingTag.id))
      updateToastSuccess(toastId, 'excluir', 'Tag')
      setShowDeleteConfirm(false)
      setDeletingTag(null)
      onSuccess?.()
    } catch (error: any) {
      updateToastError(toastId, 'excluir', 'Tag', error)
    }
  }

  const handleDeleteTag = async (tag: Tag, deleteContacts: boolean, migrateToTagId?: string) => {
    const toastId = showLoadingToast('excluir', 'Tag')
    
    try {
      let url = `/contacts/tags/${tag.id}/delete_with_options/?delete_contacts=${deleteContacts}`
      if (migrateToTagId) {
        url = `/contacts/tags/${tag.id}/delete_with_options/?migrate_to_tag_id=${migrateToTagId}`
      }
      
      await api.delete(url)
      
      setTags(prev => prev.filter(t => t.id !== tag.id))
      updateToastSuccess(toastId, 'excluir', 'Tag')
      onSuccess?.()
    } catch (error: any) {
      updateToastError(toastId, 'excluir', 'Tag', error)
    }
  }

  const handleTagEditSuccess = () => {
    fetchTags()
    onSuccess?.()
  }

  if (!isOpen) return null

  return (
    <>
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
        <Card className="max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col">
          <div className="p-6 flex-shrink-0 border-b">
            <div className="flex justify-between items-center mb-4">
              <div>
                <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
                  <TagIcon className="h-6 w-6 text-blue-600" />
                  Gerenciar Tags
                </h2>
                <p className="text-sm text-gray-500 mt-1">
                  Crie, edite e exclua tags do sistema
                </p>
              </div>
              <button
                onClick={onClose}
                className="text-gray-500 hover:text-gray-700 transition-colors"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Criar Nova Tag */}
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
              <h3 className="text-sm font-medium text-gray-700 mb-3">Criar Nova Tag</h3>
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="Nome da tag"
                  value={newTagName}
                  onChange={(e) => setNewTagName(e.target.value)}
                  onKeyPress={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault()
                      createTag()
                    }
                  }}
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                <input
                  type="color"
                  value={newTagColor}
                  onChange={(e) => setNewTagColor(e.target.value)}
                  className="w-16 h-10 border border-gray-300 rounded-lg cursor-pointer"
                  title="Cor da tag"
                />
                <Button
                  onClick={createTag}
                  disabled={!newTagName.trim()}
                  className="flex items-center gap-2"
                >
                  <Plus className="h-4 w-4" />
                  Criar
                </Button>
              </div>
            </div>
          </div>

          {/* Lista de Tags */}
          <div className="flex-1 overflow-y-auto p-6">
            {isLoading ? (
              <div className="text-center py-8">
                <p className="text-gray-500">Carregando tags...</p>
              </div>
            ) : tags.length === 0 ? (
              <div className="text-center py-8">
                <TagIcon className="h-12 w-12 text-gray-400 mx-auto mb-3" />
                <p className="text-gray-500">Nenhuma tag cadastrada</p>
                <p className="text-sm text-gray-400 mt-1">
                  Crie sua primeira tag usando o formulário acima
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {tags.map((tag) => (
                  <div
                    key={tag.id}
                    className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-2 flex-1">
                        <div
                          className="w-4 h-4 rounded-full"
                          style={{ backgroundColor: tag.color }}
                        />
                        <div className="flex-1">
                          <h4 className="font-medium text-gray-900">{tag.name}</h4>
                          {tag.description && (
                            <p className="text-sm text-gray-500 mt-1">{tag.description}</p>
                          )}
                        </div>
                      </div>
                      <div className="flex gap-1">
                        <button
                          onClick={() => handleEditTag(tag)}
                          className="p-1.5 text-gray-600 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors"
                          title="Editar tag"
                        >
                          <Edit className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => handleDeleteClick(tag)}
                          className="p-1.5 text-gray-600 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                          title="Excluir tag"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </div>
                    {tag.contact_count !== undefined && (
                      <div className="text-xs text-gray-500 mt-2">
                        {tag.contact_count} contato{tag.contact_count !== 1 ? 's' : ''}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="p-6 border-t flex justify-end">
            <Button variant="outline" onClick={onClose}>
              Fechar
            </Button>
          </div>
        </Card>
      </div>

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
        availableTags={tags}
      />

      {/* Delete Confirmation Modal */}
      {deletingTag && showDeleteConfirm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-[60]">
          <Card className="max-w-md w-full">
            <div className="p-6">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-xl font-bold">Confirmar Exclusão</h2>
                <button
                  onClick={() => {
                    setShowDeleteConfirm(false)
                    setDeletingTag(null)
                  }}
                  className="text-gray-500 hover:text-gray-700 transition-colors"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              <div className="space-y-4">
                <div className="flex items-start gap-3 p-4 bg-red-50 border border-red-200 rounded-lg">
                  <AlertTriangle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <h3 className="font-semibold text-red-900 mb-1">
                      Confirmar Exclusão
                    </h3>
                    <p className="text-sm text-red-700">
                      Você está prestes a excluir a tag <strong>"{deletingTag.name}"</strong>.
                    </p>
                  </div>
                </div>

                {deletingTag.contact_count !== undefined && deletingTag.contact_count > 0 && (
                  <div className="space-y-3">
                    <p className="text-sm text-gray-700">
                      Esta tag está associada a <strong>{deletingTag.contact_count} contato{deletingTag.contact_count !== 1 ? 's' : ''}</strong>.
                      O que deseja fazer?
                    </p>

                    <div className="space-y-2">
                      <label className="flex items-start gap-3 p-3 border rounded-lg cursor-pointer hover:bg-gray-50">
                        <input
                          type="radio"
                          name="deleteOption"
                          checked={deleteOption === 'remove'}
                          onChange={() => setDeleteOption('remove')}
                          className="mt-1"
                        />
                        <div>
                          <div className="font-medium text-gray-900">
                            Apenas remover a tag
                          </div>
                          <div className="text-sm text-gray-500">
                            Os contatos serão mantidos, apenas a tag será removida deles
                          </div>
                        </div>
                      </label>

                      {tags.filter(t => t.id !== deletingTag.id).length > 0 && (
                        <label className="flex items-start gap-3 p-3 border border-blue-300 rounded-lg cursor-pointer hover:bg-blue-50">
                          <input
                            type="radio"
                            name="deleteOption"
                            checked={deleteOption === 'migrate'}
                            onChange={() => setDeleteOption('migrate')}
                            className="mt-1"
                          />
                          <div className="flex-1">
                            <div className="font-medium text-blue-900">
                              Migrar contatos para outra tag
                            </div>
                            <div className="text-sm text-blue-700 mb-2">
                              Os contatos receberão a tag escolhida antes da exclusão
                            </div>
                            {deleteOption === 'migrate' && (
                              <select
                                value={migrateToTagId}
                                onChange={(e) => setMigrateToTagId(e.target.value)}
                                className="w-full px-3 py-2 border border-blue-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
                                required
                              >
                                <option value="">Selecione uma tag...</option>
                                {tags.filter(t => t.id !== deletingTag.id).map((t) => (
                                  <option key={t.id} value={t.id}>
                                    {t.name}
                                  </option>
                                ))}
                              </select>
                            )}
                          </div>
                        </label>
                      )}

                      <label className="flex items-start gap-3 p-3 border border-red-300 rounded-lg cursor-pointer hover:bg-red-50">
                        <input
                          type="radio"
                          name="deleteOption"
                          checked={deleteOption === 'delete'}
                          onChange={() => setDeleteOption('delete')}
                          className="mt-1"
                        />
                        <div>
                          <div className="font-medium text-red-900">
                            Excluir tag e todos os contatos
                          </div>
                          <div className="text-sm text-red-700">
                            <strong>{deletingTag.contact_count} contato{deletingTag.contact_count !== 1 ? 's' : ''}</strong> serão excluído{deletingTag.contact_count !== 1 ? 's' : ''} permanentemente
                          </div>
                        </div>
                      </label>
                    </div>
                  </div>
                )}

                {deletingTag.contact_count === 0 && (
                  <p className="text-sm text-gray-600">
                    Esta tag não possui contatos associados. A exclusão será permanente.
                  </p>
                )}
              </div>

              <div className="flex justify-end gap-2 mt-6 pt-4 border-t">
                <Button
                  variant="outline"
                  onClick={() => {
                    setShowDeleteConfirm(false)
                    setDeletingTag(null)
                  }}
                >
                  Cancelar
                </Button>
                <Button
                  onClick={handleConfirmDelete}
                  className="bg-red-600 hover:bg-red-700 text-white"
                  disabled={deleteOption === 'migrate' && !migrateToTagId}
                >
                  <Trash2 className="h-4 w-4 mr-2" />
                  Confirmar Exclusão
                </Button>
              </div>
            </div>
          </Card>
        </div>
      )}
    </>
  )
}
