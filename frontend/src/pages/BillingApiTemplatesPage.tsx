/**
 * Página de gerenciamento de Templates de Billing API
 */
import { useState, useEffect } from 'react'
import { Plus, FileText, Edit, Trash2, CheckCircle, XCircle, Eye, EyeOff } from 'lucide-react'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import { showLoadingToast, updateToastSuccess, updateToastError, showSuccessToast, showErrorToast } from '../lib/toastHelper'
import billingApiService, { BillingTemplate } from '../services/billingApi'
import { useAuthStore } from '../stores/authStore'

export default function BillingApiTemplatesPage() {
  const { user } = useAuthStore()
  const [templates, setTemplates] = useState<BillingTemplate[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [editingTemplate, setEditingTemplate] = useState<BillingTemplate | null>(null)
  const [formData, setFormData] = useState({
    name: '',
    template_type: 'overdue' as 'overdue' | 'upcoming' | 'notification',
    description: '',
    is_active: true
  })
  const [expandedTemplates, setExpandedTemplates] = useState<Set<string>>(new Set())

  useEffect(() => {
    fetchTemplates()
  }, [])

  const fetchTemplates = async () => {
    try {
      setLoading(true)
      const data = await billingApiService.getTemplates()
      setTemplates(data)
    } catch (error: any) {
      showErrorToast('Erro ao buscar Templates', error.response?.data?.message || error.message)
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!user?.tenant_id) {
      showErrorToast('Erro', 'Tenant ID não encontrado')
      return
    }

    const toastId = showLoadingToast('Criando Template...')

    try {
      await billingApiService.createTemplate({
        ...formData,
        tenant_id: user.tenant_id
      })
      updateToastSuccess(toastId, 'Template criado com sucesso!')
      setShowCreateModal(false)
      setFormData({ name: '', template_type: 'overdue', description: '', is_active: true })
      fetchTemplates()
    } catch (error: any) {
      updateToastError(toastId, 'Erro ao criar Template', error.response?.data?.message || error.message)
    }
  }

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editingTemplate) return

    const toastId = showLoadingToast('Atualizando Template...')

    try {
      await billingApiService.updateTemplate(editingTemplate.id, formData)
      updateToastSuccess(toastId, 'Template atualizado com sucesso!')
      setEditingTemplate(null)
      setFormData({ name: '', template_type: 'overdue', description: '', is_active: true })
      fetchTemplates()
    } catch (error: any) {
      updateToastError(toastId, 'Erro ao atualizar Template', error.response?.data?.message || error.message)
    }
  }

  const handleDelete = async (templateId: string) => {
    if (!confirm('Tem certeza que deseja deletar este Template?')) return

    const toastId = showLoadingToast('Deletando Template...')

    try {
      await billingApiService.deleteTemplate(templateId)
      updateToastSuccess(toastId, 'Template deletado com sucesso!')
      fetchTemplates()
    } catch (error: any) {
      updateToastError(toastId, 'Erro ao deletar Template', error.response?.data?.message || error.message)
    }
  }

  const toggleExpand = (templateId: string) => {
    const newExpanded = new Set(expandedTemplates)
    if (newExpanded.has(templateId)) {
      newExpanded.delete(templateId)
    } else {
      newExpanded.add(templateId)
    }
    setExpandedTemplates(newExpanded)
  }

  const startEdit = (template: BillingTemplate) => {
    setEditingTemplate(template)
    setFormData({
      name: template.name,
      template_type: template.template_type,
      description: template.description || '',
      is_active: template.is_active
    })
    setShowCreateModal(true)
  }

  const cancelEdit = () => {
    setEditingTemplate(null)
    setShowCreateModal(false)
    setFormData({ name: '', template_type: 'overdue', description: '', is_active: true })
  }

  const getTemplateTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      overdue: 'Cobrança Atrasada',
      upcoming: 'Aviso de Vencimento',
      notification: 'Notificação'
    }
    return labels[type] || type
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
            Templates de Billing API
          </h1>
          <p className="mt-2 text-gray-600 dark:text-gray-400">
            Gerencie templates de mensagens de cobrança
          </p>
        </div>
        <Button
          onClick={() => {
            setEditingTemplate(null)
            setFormData({ name: '', template_type: 'overdue', description: '', is_active: true })
            setShowCreateModal(true)
          }}
        >
          <Plus className="h-4 w-4 mr-2" />
          Novo Template
        </Button>
      </div>

      {/* Templates List */}
      {templates.length === 0 ? (
        <Card>
          <div className="p-12 text-center">
            <FileText className="h-16 w-16 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
              Nenhum template encontrado
            </h3>
            <p className="text-gray-600 dark:text-gray-400 mb-4">
              Crie seu primeiro template para começar a usar a Billing API
            </p>
            <Button onClick={() => setShowCreateModal(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Criar Template
            </Button>
          </div>
        </Card>
      ) : (
        <div className="space-y-4">
          {templates.map((template) => (
            <Card key={template.id}>
              <div className="p-6">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                        {template.name}
                      </h3>
                      <span className={`px-2 py-1 text-xs rounded ${
                        template.template_type === 'overdue' ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200' :
                        template.template_type === 'upcoming' ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200' :
                        'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
                      }`}>
                        {getTemplateTypeLabel(template.template_type)}
                      </span>
                      {template.is_active ? (
                        <CheckCircle className="h-5 w-5 text-green-500" />
                      ) : (
                        <XCircle className="h-5 w-5 text-gray-400" />
                      )}
                    </div>
                    {template.description && (
                      <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                        {template.description}
                      </p>
                    )}
                    <div className="flex items-center gap-4 text-sm text-gray-500 dark:text-gray-400">
                      <span>Usos: {template.total_uses || 0}</span>
                      <span>Variações: {template.variations?.length || 0}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => toggleExpand(template.id)}
                    >
                      {expandedTemplates.has(template.id) ? (
                        <EyeOff className="h-4 w-4" />
                      ) : (
                        <Eye className="h-4 w-4" />
                      )}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => startEdit(template)}
                    >
                      <Edit className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleDelete(template.id)}
                      className="text-red-600 hover:text-red-700"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>

                {/* Expanded Content */}
                {expandedTemplates.has(template.id) && (
                  <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
                    <div className="space-y-4">
                      <div>
                        <h4 className="text-sm font-semibold text-gray-900 dark:text-white mb-2">
                          Variações
                        </h4>
                        {template.variations && template.variations.length > 0 ? (
                          <div className="space-y-2">
                            {template.variations.map((variation) => (
                              <div
                                key={variation.id}
                                className="p-3 bg-gray-50 dark:bg-gray-800 rounded text-sm"
                              >
                                <div className="flex items-center justify-between mb-1">
                                  <span className="font-medium">{variation.name}</span>
                                  <span className="text-xs text-gray-500">
                                    Usado {variation.times_used || 0} vezes
                                  </span>
                                </div>
                                <p className="text-gray-600 dark:text-gray-400 text-xs">
                                  {variation.template_text.substring(0, 100)}
                                  {variation.template_text.length > 100 ? '...' : ''}
                                </p>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p className="text-sm text-gray-500">Nenhuma variação cadastrada</p>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Create/Edit Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <Card className="w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">
                {editingTemplate ? 'Editar Template' : 'Novo Template'}
              </h2>
              <form onSubmit={editingTemplate ? handleUpdate : handleCreate}>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Nome
                    </label>
                    <Input
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Tipo
                    </label>
                    <select
                      value={formData.template_type}
                      onChange={(e) => setFormData({ ...formData, template_type: e.target.value as any })}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                      required
                    >
                      <option value="overdue">Cobrança Atrasada</option>
                      <option value="upcoming">Aviso de Vencimento</option>
                      <option value="notification">Notificação</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Descrição
                    </label>
                    <Input
                      value={formData.description}
                      onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    />
                  </div>
                  <div className="flex items-center">
                    <input
                      type="checkbox"
                      id="is_active"
                      checked={formData.is_active}
                      onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                      className="mr-2"
                    />
                    <label htmlFor="is_active" className="text-sm text-gray-700 dark:text-gray-300">
                      Ativo
                    </label>
                  </div>
                </div>
                <div className="flex justify-end gap-3 mt-6">
                  <Button type="button" variant="outline" onClick={cancelEdit}>
                    Cancelar
                  </Button>
                  <Button type="submit">
                    {editingTemplate ? 'Atualizar' : 'Criar'}
                  </Button>
                </div>
              </form>
            </div>
          </Card>
        </div>
      )}
    </div>
  )
}

