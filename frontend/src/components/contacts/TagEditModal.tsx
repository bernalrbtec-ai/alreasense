import { useState, useEffect } from 'react'
import { X, Save, Trash2, AlertTriangle } from 'lucide-react'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { api } from '../../lib/api'
import { showSuccessToast, showErrorToast, showLoadingToast, updateToastSuccess, updateToastError } from '../../lib/toastHelper'

interface Tag {
  id: string
  name: string
  color: string
  description?: string
  contact_count?: number
}

const normalizeTagName = (value: string) => value.trim().replace(/\s+/g, ' ')

interface TagEditModalProps {
  tag: Tag | null
  isOpen: boolean
  onClose: () => void
  onSuccess: () => void
  onDelete: (tag: Tag, deleteContacts: boolean, migrateToTagId?: string) => void
  availableTags?: Tag[]
}

export default function TagEditModal({ tag, isOpen, onClose, onSuccess, onDelete, availableTags = [] }: TagEditModalProps) {
  const [name, setName] = useState('')
  const [color, setColor] = useState('#3B82F6')
  const [description, setDescription] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [deleteOption, setDeleteOption] = useState<'remove' | 'migrate' | 'delete'>('remove')
  const [migrateToTagId, setMigrateToTagId] = useState<string>('')

  useEffect(() => {
    if (tag && isOpen) {
      setName(tag.name)
      setColor(tag.color)
      setDescription(tag.description || '')
      setShowDeleteConfirm(false)
      setDeleteOption('remove')
      setMigrateToTagId('')
    }
  }, [tag, isOpen])

  if (!isOpen || !tag) return null

  const handleSave = async () => {
    if (!name.trim()) {
      showErrorToast('salvar', 'Tag', new Error('Nome da tag é obrigatório'))
      return
    }

    const normalizedName = normalizeTagName(name)
    const hasDuplicate = availableTags.some(
      (availableTag) =>
        availableTag.id !== tag?.id &&
        normalizeTagName(availableTag.name).toLowerCase() === normalizedName.toLowerCase()
    )

    if (hasDuplicate) {
      showErrorToast('salvar', 'Tag', new Error(`A tag "${normalizedName}" já existe. Escolha um nome diferente.`))
      return
    }

    setIsSaving(true)
    const toastId = showLoadingToast('atualizar', 'Tag')

    try {
      await api.put(`/contacts/tags/${tag.id}/`, {
        name: normalizedName,
        color,
        description: description.trim() || ''
      })

      updateToastSuccess(toastId, 'atualizar', 'Tag')
      onSuccess()
      onClose()
    } catch (error: any) {
      updateToastError(toastId, 'atualizar', 'Tag', error)
    } finally {
      setIsSaving(false)
    }
  }

  const handleDeleteClick = () => {
    setShowDeleteConfirm(true)
  }

  const handleConfirmDelete = () => {
    const deleteContacts = deleteOption === 'delete'
    const migrateId = deleteOption === 'migrate' ? migrateToTagId : undefined
    onDelete(tag, deleteContacts, migrateId)
    setShowDeleteConfirm(false)
    onClose()
  }

  // Filtrar tags disponíveis (excluir a tag atual)
  const tagsToMigrate = availableTags
    .filter(t => t.id !== tag?.id)
    .sort((a, b) =>
      normalizeTagName(a.name).localeCompare(normalizeTagName(b.name), 'pt-BR', { sensitivity: 'base' })
    )

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <Card className="max-w-md w-full">
        <div className="p-6">
          {/* Header */}
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-bold">Editar Tag</h2>
            <button
              onClick={onClose}
              className="text-gray-500 hover:text-gray-700 transition-colors"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          {!showDeleteConfirm ? (
            <>
              {/* Form */}
              <div className="space-y-4">
                {/* Nome */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Nome da Tag *
                  </label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    placeholder="Ex: VIP, Cliente Premium"
                  />
                </div>

                {/* Cor */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Cor
                  </label>
                  <div className="flex items-center gap-3">
                    <input
                      type="color"
                      value={color}
                      onChange={(e) => setColor(e.target.value)}
                      className="h-10 w-20 border border-gray-300 rounded cursor-pointer"
                    />
                    <input
                      type="text"
                      value={color}
                      onChange={(e) => setColor(e.target.value)}
                      className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm"
                      placeholder="#3B82F6"
                    />
                  </div>
                </div>

                {/* Descrição */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Descrição (opcional)
                  </label>
                  <textarea
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    rows={3}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    placeholder="Descrição da tag..."
                  />
                </div>

                {/* Info */}
                {tag.contact_count !== undefined && (
                  <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
                    <p className="text-sm text-blue-700">
                      <strong>{tag.contact_count}</strong> contato{tag.contact_count !== 1 ? 's' : ''} com esta tag
                    </p>
                  </div>
                )}
              </div>

              {/* Actions */}
              <div className="flex justify-between items-center mt-6 pt-4 border-t">
                <Button
                  variant="outline"
                  onClick={handleDeleteClick}
                  className="text-red-600 hover:bg-red-50 border-red-300"
                >
                  <Trash2 className="h-4 w-4 mr-2" />
                  Excluir Tag
                </Button>
                <div className="flex gap-2">
                  <Button variant="outline" onClick={onClose}>
                    Cancelar
                  </Button>
                  <Button
                    onClick={handleSave}
                    disabled={!name.trim() || isSaving}
                  >
                    <Save className="h-4 w-4 mr-2" />
                    {isSaving ? 'Salvando...' : 'Salvar'}
                  </Button>
                </div>
              </div>
            </>
          ) : (
            <>
              {/* Confirmação de Exclusão */}
              <div className="space-y-4">
                <div className="flex items-start gap-3 p-4 bg-red-50 border border-red-200 rounded-lg">
                  <AlertTriangle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <h3 className="font-semibold text-red-900 mb-1">
                      Confirmar Exclusão
                    </h3>
                    <p className="text-sm text-red-700">
                      Você está prestes a excluir a tag <strong>"{tag.name}"</strong>.
                    </p>
                  </div>
                </div>

                {tag.contact_count !== undefined && tag.contact_count > 0 && (
                  <div className="space-y-3">
                    <p className="text-sm text-gray-700">
                      Esta tag está associada a <strong>{tag.contact_count} contato{tag.contact_count !== 1 ? 's' : ''}</strong>.
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

                      {tagsToMigrate.length > 0 && (
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
                                {tagsToMigrate.map((t) => (
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
                            <strong>{tag.contact_count} contato{tag.contact_count !== 1 ? 's' : ''}</strong> serão excluído{tag.contact_count !== 1 ? 's' : ''} permanentemente
                          </div>
                        </div>
                      </label>
                    </div>
                  </div>
                )}

                {tag.contact_count === 0 && (
                  <p className="text-sm text-gray-600">
                    Esta tag não possui contatos associados. A exclusão será permanente.
                  </p>
                )}
              </div>

              {/* Actions */}
              <div className="flex justify-end gap-2 mt-6 pt-4 border-t">
                <Button variant="outline" onClick={() => setShowDeleteConfirm(false)}>
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
            </>
          )}
        </div>
      </Card>
    </div>
  )
}

