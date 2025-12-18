/**
 * Página de gerenciamento de API Keys
 */
import { useState, useEffect } from 'react'
import { Plus, Key, Copy, Trash2, Eye, EyeOff, CheckCircle, XCircle, Calendar } from 'lucide-react'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import { showLoadingToast, updateToastSuccess, updateToastError, showSuccessToast, showErrorToast } from '../lib/toastHelper'
import billingApiService, { BillingAPIKey } from '../services/billingApi'
import { api } from '../lib/api'

export default function BillingApiKeysPage() {
  const [keys, setKeys] = useState<BillingAPIKey[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [formData, setFormData] = useState({
    name: '',
    expires_at: '',
    allowed_ips: ''
  })
  const [visibleKeys, setVisibleKeys] = useState<Set<string>>(new Set())

  useEffect(() => {
    fetchKeys()
  }, [])

  const fetchKeys = async () => {
    try {
      setLoading(true)
      const data = await billingApiService.getAPIKeys()
      setKeys(data)
    } catch (error: any) {
      showErrorToast('Erro ao buscar API Keys', error.response?.data?.message || error.message)
      setKeys([])
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    const toastId = showLoadingToast('Criando API Key...')

    try {
      const allowedIps = formData.allowed_ips
        .split(',')
        .map(ip => ip.trim())
        .filter(ip => ip)

      const data = await billingApiService.createAPIKey({
        name: formData.name,
        expires_at: formData.expires_at || undefined,
        allowed_ips: allowedIps.length > 0 ? allowedIps : undefined
      })

      updateToastSuccess(toastId, 'API Key criada com sucesso!')
      setShowCreateModal(false)
      setFormData({ name: '', expires_at: '', allowed_ips: '' })
      fetchKeys()
    } catch (error: any) {
      updateToastError(toastId, 'Erro ao criar API Key', error.response?.data?.message || error.message)
    }
  }

  const handleDelete = async (keyId: string) => {
    if (!confirm('Tem certeza que deseja deletar esta API Key?')) return

    const toastId = showLoadingToast('Deletando API Key...')

    try {
      await billingApiService.deleteAPIKey(keyId)
      updateToastSuccess(toastId, 'API Key deletada com sucesso!')
      fetchKeys()
    } catch (error: any) {
      updateToastError(toastId, 'Erro ao deletar API Key', error.response?.data?.message || error.message)
    }
  }

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
    showSuccessToast('Copiado para a área de transferência!')
  }

  const toggleKeyVisibility = (keyId: string) => {
    const newVisible = new Set(visibleKeys)
    if (newVisible.has(keyId)) {
      newVisible.delete(keyId)
    } else {
      newVisible.add(keyId)
    }
    setVisibleKeys(newVisible)
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
            API Keys
          </h1>
          <p className="mt-2 text-gray-600 dark:text-gray-400">
            Gerencie suas chaves de API para integração externa
          </p>
        </div>
        <Button onClick={() => setShowCreateModal(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Nova API Key
        </Button>
      </div>

      {/* Keys List */}
      {keys.length === 0 ? (
        <Card>
          <div className="p-12 text-center">
            <Key className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
              Nenhuma API Key encontrada
            </h3>
            <p className="text-gray-600 dark:text-gray-400 mb-4">
              Crie sua primeira API Key para começar a usar a Billing API
            </p>
            <Button onClick={() => setShowCreateModal(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Criar API Key
            </Button>
          </div>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {keys.map((key) => (
            <Card key={key.id}>
              <div className="p-6">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                        {key.name}
                      </h3>
                      {key.is_active ? (
                        <span className="flex items-center gap-1 text-green-600 text-sm">
                          <CheckCircle className="h-4 w-4" />
                          Ativa
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-red-600 text-sm">
                          <XCircle className="h-4 w-4" />
                          Inativa
                        </span>
                      )}
                    </div>

                    <div className="space-y-2 text-sm text-gray-600 dark:text-gray-400">
                      <div className="flex items-center gap-2">
                        <Key className="h-4 w-4" />
                        <code className="bg-gray-100 dark:bg-gray-800 px-2 py-1 rounded">
                          {visibleKeys.has(key.id) ? key.key_masked : '••••••••••••'}
                        </code>
                        <button
                          onClick={() => toggleKeyVisibility(key.id)}
                          className="text-brand-600 hover:text-brand-700"
                        >
                          {visibleKeys.has(key.id) ? (
                            <EyeOff className="h-4 w-4" />
                          ) : (
                            <Eye className="h-4 w-4" />
                          )}
                        </button>
                        <button
                          onClick={() => copyToClipboard(key.key_masked || '')}
                          className="text-brand-600 hover:text-brand-700"
                        >
                          <Copy className="h-4 w-4" />
                        </button>
                      </div>

                      {key.expires_at && (
                        <div className="flex items-center gap-2">
                          <Calendar className="h-4 w-4" />
                          <span>Expira em: {new Date(key.expires_at).toLocaleDateString('pt-BR')}</span>
                        </div>
                      )}

                      {key.allowed_ips && key.allowed_ips.length > 0 && (
                        <div>
                          <span className="font-medium">IPs permitidos: </span>
                          {key.allowed_ips.join(', ')}
                        </div>
                      )}

                      <div>
                        <span className="font-medium">Total de requisições: </span>
                        {key.total_requests}
                      </div>

                      {key.last_used_at && (
                        <div>
                          <span className="font-medium">Último uso: </span>
                          {new Date(key.last_used_at).toLocaleString('pt-BR')}
                        </div>
                      )}
                    </div>
                  </div>

                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDelete(key.id)}
                    className="text-red-600 hover:text-red-700"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <Card className="w-full max-w-md m-4">
            <div className="p-6">
              <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
                Nova API Key
              </h2>
              <form onSubmit={handleCreate} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Nome
                  </label>
                  <Input
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder="Ex: ERP Principal"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Data de Expiração (opcional)
                  </label>
                  <Input
                    type="datetime-local"
                    value={formData.expires_at}
                    onChange={(e) => setFormData({ ...formData, expires_at: e.target.value })}
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    IPs Permitidos (opcional, separados por vírgula)
                  </label>
                  <Input
                    value={formData.allowed_ips}
                    onChange={(e) => setFormData({ ...formData, allowed_ips: e.target.value })}
                    placeholder="Ex: 192.168.1.1, 10.0.0.1"
                  />
                </div>

                <div className="flex gap-3 pt-4">
                  <Button type="submit" className="flex-1">
                    Criar
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => {
                      setShowCreateModal(false)
                      setFormData({ name: '', expires_at: '', allowed_ips: '' })
                    }}
                  >
                    Cancelar
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

