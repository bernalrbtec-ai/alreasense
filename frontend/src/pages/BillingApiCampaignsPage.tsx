/**
 * Página de Campanhas de Billing API
 * Criar e monitorar campanhas de billing
 */
import { useState, useEffect } from 'react'
import { Plus, Send, Search, Eye, RefreshCw, CheckCircle, XCircle, Clock, AlertCircle } from 'lucide-react'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import { showLoadingToast, updateToastSuccess, updateToastError, showSuccessToast, showErrorToast } from '../lib/toastHelper'
import billingApiService, { SendBillingRequest, BillingContact } from '../services/billingApi'

interface Campaign {
  id: string
  external_id?: string
  billing_type: string
  total_contacts: number
  sent_contacts: number
  failed_contacts: number
  status: string
  created_at: string
}

export default function BillingApiCampaignsPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [formData, setFormData] = useState<SendBillingRequest>({
    template_type: 'overdue',
    contacts: [],
    external_id: ''
  })
  const [contactsText, setContactsText] = useState('')

  useEffect(() => {
    // TODO: Buscar campanhas quando endpoint estiver disponível
    setLoading(false)
  }, [])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    
    // Parse contacts from text (JSON format)
    let contacts: BillingContact[] = []
    try {
      contacts = JSON.parse(contactsText)
    } catch {
      showErrorToast('Formato JSON inválido nos contatos')
      return
    }

    if (contacts.length === 0) {
      showErrorToast('Adicione pelo menos um contato')
      return
    }

    const toastId = showLoadingToast('Criando campanha...')

    try {
      let response
      if (formData.template_type === 'overdue') {
        response = await billingApiService.sendOverdue({
          ...formData,
          contacts
        })
      } else if (formData.template_type === 'upcoming') {
        response = await billingApiService.sendUpcoming({
          ...formData,
          contacts
        })
      } else {
        response = await billingApiService.sendNotification({
          ...formData,
          contacts
        })
      }

      if (response.success) {
        updateToastSuccess(toastId, 'Campanha criada com sucesso!')
        setShowCreateModal(false)
        setFormData({ template_type: 'overdue', contacts: [], external_id: '' })
        setContactsText('')
        // TODO: Recarregar lista de campanhas
      } else {
        updateToastError(toastId, 'Erro ao criar campanha', response.message)
      }
    } catch (error: any) {
      updateToastError(toastId, 'Erro ao criar campanha', error.response?.data?.message || error.message)
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-5 w-5 text-green-500" />
      case 'running':
        return <RefreshCw className="h-5 w-5 text-brand-500 animate-spin" />
      case 'failed':
        return <XCircle className="h-5 w-5 text-red-500" />
      case 'paused':
        return <Clock className="h-5 w-5 text-yellow-500" />
      default:
        return <AlertCircle className="h-5 w-5 text-gray-500" />
    }
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
            Campanhas de Billing
          </h1>
          <p className="mt-2 text-gray-600 dark:text-gray-400">
            Crie e monitore campanhas de cobrança via WhatsApp
          </p>
        </div>
        <Button onClick={() => setShowCreateModal(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Nova Campanha
        </Button>
      </div>

      {/* Campaigns List */}
      {campaigns.length === 0 ? (
        <Card>
          <div className="p-12 text-center">
            <Send className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
              Nenhuma campanha encontrada
            </h3>
            <p className="text-gray-600 dark:text-gray-400 mb-4">
              Crie sua primeira campanha para começar a enviar cobranças
            </p>
            <Button onClick={() => setShowCreateModal(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Criar Campanha
            </Button>
          </div>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {campaigns.map((campaign) => (
            <Card key={campaign.id}>
              <div className="p-6">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      {getStatusIcon(campaign.status)}
                      <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                        {campaign.external_id || campaign.id}
                      </h3>
                      <span className="px-2 py-1 text-xs font-medium rounded bg-brand-100 text-brand-700">
                        {campaign.billing_type}
                      </span>
                    </div>

                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4">
                      <div>
                        <p className="text-sm text-gray-600 dark:text-gray-400">Total</p>
                        <p className="text-lg font-semibold text-gray-900 dark:text-white">
                          {campaign.total_contacts}
                        </p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-600 dark:text-gray-400">Enviadas</p>
                        <p className="text-lg font-semibold text-green-600">
                          {campaign.sent_contacts}
                        </p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-600 dark:text-gray-400">Falhas</p>
                        <p className="text-lg font-semibold text-red-600">
                          {campaign.failed_contacts}
                        </p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-600 dark:text-gray-400">Status</p>
                        <p className="text-lg font-semibold text-gray-900 dark:text-white capitalize">
                          {campaign.status}
                        </p>
                      </div>
                    </div>

                    <div className="mt-4 text-sm text-gray-500 dark:text-gray-400">
                      Criada em: {new Date(campaign.created_at).toLocaleString('pt-BR')}
                    </div>
                  </div>

                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      // TODO: Navegar para detalhes da campanha
                    }}
                  >
                    <Eye className="h-4 w-4 mr-2" />
                    Ver Detalhes
                  </Button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4 overflow-y-auto">
          <Card className="w-full max-w-2xl my-auto">
            <div className="p-6">
              <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
                Nova Campanha de Billing
              </h2>
              <form onSubmit={handleCreate} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Tipo de Template
                  </label>
                  <select
                    value={formData.template_type}
                    onChange={(e) => setFormData({ ...formData, template_type: e.target.value as any })}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
                    required
                  >
                    <option value="overdue">🔴 Cobrança Atrasada</option>
                    <option value="upcoming">🟡 Cobrança a Vencer</option>
                    <option value="notification">🔵 Notificação/Aviso</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    ID Externo (opcional)
                  </label>
                  <Input
                    value={formData.external_id}
                    onChange={(e) => setFormData({ ...formData, external_id: e.target.value })}
                    placeholder="Ex: fatura-12345"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    Contatos (JSON)
                  </label>
                  <textarea
                    value={contactsText}
                    onChange={(e) => setContactsText(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white font-mono text-sm"
                    rows={10}
                    placeholder={`[\n  {\n    "nome": "João Silva",\n    "telefone": "+5511999999999",\n    "valor": "R$ 150,00",\n    "data_vencimento": "2025-01-20"\n  }\n]`}
                    required
                  />
                  <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                    Formato JSON com array de contatos
                  </p>
                </div>

                <div className="flex gap-3 pt-4">
                  <Button type="submit" className="flex-1">
                    <Send className="h-4 w-4 mr-2" />
                    Criar Campanha
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => {
                      setShowCreateModal(false)
                      setFormData({ template_type: 'overdue', contacts: [], external_id: '' })
                      setContactsText('')
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

