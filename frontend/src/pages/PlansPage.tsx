import { useState, useEffect } from 'react'
import { Plus, Edit, Trash2, Check, X } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import { api } from '../lib/api'

interface Plan {
  id: string
  name: string
  price: number
  billing_cycle_days: number
  is_free: boolean
  max_connections: number
  max_messages_per_month: number
  features: string[]
  is_active: boolean
}

export default function PlansPage() {
  const [plans, setPlans] = useState<Plan[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingPlan, setEditingPlan] = useState<Plan | null>(null)
  const [formData, setFormData] = useState({
    name: '',
    price: 0,
    billing_cycle_days: 30,
    is_free: false,
    max_connections: 1,
    max_messages_per_month: 1000,
    features: [''],
    is_active: true,
  })

  useEffect(() => {
    fetchPlans()
  }, [])

  const fetchPlans = async () => {
    try {
      setIsLoading(true)
      console.log('🔍 Fetching plans from /billing/plans/')
      const response = await api.get('/billing/plans/')
      console.log('✅ Plans response:', response.data)
      setPlans(response.data.results || response.data)
    } catch (error) {
      console.error('❌ Error fetching plans:', error)
      setPlans([])
    } finally {
      setIsLoading(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      setIsSaving(true)
      if (editingPlan) {
        await api.patch(`/billing/plans/${editingPlan.id}/`, formData)
      } else {
        await api.post('/billing/plans/', formData)
      }
      await fetchPlans()
      handleCloseModal()
      alert(editingPlan ? 'Plano atualizado com sucesso!' : 'Plano criado com sucesso!')
    } catch (error: any) {
      console.error('Error saving plan:', error)
      alert(error.response?.data?.detail || 'Erro ao salvar plano')
    } finally {
      setIsSaving(false)
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Tem certeza que deseja excluir este plano?')) return
    try {
      await api.delete(`/billing/plans/${id}/`)
      await fetchPlans()
      alert('Plano excluído com sucesso!')
    } catch (error: any) {
      console.error('Error deleting plan:', error)
      alert(error.response?.data?.detail || 'Erro ao excluir plano')
    }
  }

  const handleEdit = (plan: Plan) => {
    setEditingPlan(plan)
    setFormData({
      name: plan.name,
      price: plan.price,
      billing_cycle_days: plan.billing_cycle_days,
      is_free: plan.is_free,
      max_connections: plan.max_connections,
      max_messages_per_month: plan.max_messages_per_month,
      features: plan.features,
      is_active: plan.is_active,
    })
    setIsModalOpen(true)
  }

  const handleCloseModal = () => {
    setIsModalOpen(false)
    setEditingPlan(null)
    setFormData({
      name: '',
      price: 0,
      billing_cycle_days: 30,
      is_free: false,
      max_connections: 1,
      max_messages_per_month: 1000,
      features: [''],
      is_active: true,
    })
  }

  const addFeature = () => {
    setFormData({ ...formData, features: [...formData.features, ''] })
  }

  const removeFeature = (index: number) => {
    const newFeatures = formData.features.filter((_, i) => i !== index)
    setFormData({ ...formData, features: newFeatures })
  }

  const updateFeature = (index: number, value: string) => {
    const newFeatures = [...formData.features]
    newFeatures[index] = value
    setFormData({ ...formData, features: newFeatures })
  }

  if (isLoading && (!Array.isArray(plans) || plans.length === 0)) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Planos</h1>
          <p className="mt-1 text-sm text-gray-500">
            Gerencie os planos de assinatura da plataforma
          </p>
        </div>
        <Button onClick={() => setIsModalOpen(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Novo Plano
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
        {Array.isArray(plans) && plans.map((plan) => (
          <Card key={plan.id} className={`p-6 relative ${!plan.is_active ? 'opacity-60 border-gray-300' : 'border-blue-200'}`}>
            {/* Status Badge */}
            <div className="absolute top-4 right-4 flex gap-2">
              {plan.is_active ? (
                <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                  <span className="w-2 h-2 rounded-full bg-green-500 mr-1.5 animate-pulse"></span>
                  Ativo
                </span>
              ) : (
                <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                  <span className="w-2 h-2 rounded-full bg-gray-500 mr-1.5"></span>
                  Inativo
                </span>
              )}
              {plan.is_free && (
                <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                  Gratuito
                </span>
              )}
            </div>

            <div className="mb-4 pr-24">
              <h3 className="text-lg font-bold text-gray-900">{plan.name}</h3>
              <div className="mt-2">
                <p className="text-3xl font-bold text-blue-600">
                  {plan.is_free ? 'Grátis' : `R$ ${plan.price.toFixed(2)}`}
                </p>
                {!plan.is_free && (
                  <p className="text-xs text-gray-500 mt-1">
                    Cobrança a cada {plan.billing_cycle_days} dias
                  </p>
                )}
              </div>
            </div>
            
            <div className="space-y-3">
              <div className="text-sm text-gray-600 space-y-1">
                <p className="font-medium">
                  📱 Conexões: {plan.max_connections === -1 ? 'Ilimitadas' : plan.max_connections}
                </p>
                <p className="font-medium">
                  💬 Mensagens: {plan.max_messages_per_month === -1 ? 'Ilimitadas' : plan.max_messages_per_month.toLocaleString()}/{plan.billing_cycle_days} dias
                </p>
              </div>
              
              <div className="pt-3 border-t border-gray-200">
                <ul className="space-y-2">
                  {Array.isArray(plan.features) && plan.features.map((feature, index) => (
                    <li key={index} className="flex items-start text-sm text-gray-600">
                      <Check className="h-4 w-4 text-green-500 mr-2 flex-shrink-0 mt-0.5" />
                      {feature}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
            
            <div className="mt-4 pt-4 border-t border-gray-200 flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleEdit(plan)}
                className="flex-1"
              >
                <Edit className="h-3 w-3 mr-1" />
                Editar
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleDelete(plan.id)}
                className="text-red-600 hover:text-red-700 hover:border-red-300"
              >
                <Trash2 className="h-3 w-3" />
              </Button>
            </div>
          </Card>
        ))}
      </div>

      {(!Array.isArray(plans) || plans.length === 0) && !isLoading && (
        <Card className="p-12">
          <div className="text-center">
            <svg
              className="mx-auto h-12 w-12 text-gray-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
            <h3 className="mt-2 text-sm font-medium text-gray-900">Nenhum plano cadastrado</h3>
            <p className="mt-1 text-sm text-gray-500">
              Comece criando um novo plano de assinatura
            </p>
            <div className="mt-6">
              <Button onClick={() => setIsModalOpen(true)}>
                <Plus className="h-4 w-4 mr-2" />
                Criar Primeiro Plano
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-full items-end justify-center p-4 text-center sm:items-center sm:p-0">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" onClick={handleCloseModal} />
            
            <div className="relative transform overflow-hidden rounded-lg bg-white text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-2xl">
              <form onSubmit={handleSubmit}>
                <div className="bg-white px-4 pb-4 pt-5 sm:p-6 sm:pb-4">
                  <h3 className="text-lg font-medium leading-6 text-gray-900 mb-4">
                    {editingPlan ? 'Editar Plano' : 'Novo Plano'}
                  </h3>
                  
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label htmlFor="name" className="block text-sm font-medium text-gray-700">
                          Nome do Plano
                        </label>
                        <input
                          type="text"
                          id="name"
                          required
                          value={formData.name}
                          onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                          className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                        />
                      </div>

                      <div>
                        <label htmlFor="price" className="block text-sm font-medium text-gray-700">
                          Preço (R$)
                        </label>
                        <input
                          type="number"
                          id="price"
                          step="0.01"
                          min="0"
                          required
                          value={formData.price}
                          onChange={(e) => setFormData({ ...formData, price: parseFloat(e.target.value) })}
                          className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                          disabled={formData.is_free}
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label htmlFor="billing_cycle_days" className="block text-sm font-medium text-gray-700">
                          Ciclo de Cobrança (dias)
                        </label>
                        <input
                          type="number"
                          id="billing_cycle_days"
                          min="1"
                          required
                          value={formData.billing_cycle_days}
                          onChange={(e) => setFormData({ ...formData, billing_cycle_days: parseInt(e.target.value) })}
                          className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                          disabled={formData.is_free}
                        />
                        <p className="mt-1 text-xs text-gray-500">
                          Padrão: 30 dias (mensal)
                        </p>
                      </div>

                      <div className="flex items-center pt-6">
                        <input
                          type="checkbox"
                          id="is_free"
                          checked={formData.is_free}
                          onChange={(e) => {
                            const isFree = e.target.checked
                            setFormData({ 
                              ...formData, 
                              is_free: isFree,
                              price: isFree ? 0 : formData.price,
                            })
                          }}
                          className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                        />
                        <label htmlFor="is_free" className="ml-2 block text-sm text-gray-900">
                          Plano Gratuito (não gera cobrança)
                        </label>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label htmlFor="max_connections" className="block text-sm font-medium text-gray-700">
                          Máx. Conexões (-1 = ilimitado)
                        </label>
                        <input
                          type="number"
                          id="max_connections"
                          min="-1"
                          required
                          value={formData.max_connections}
                          onChange={(e) => setFormData({ ...formData, max_connections: parseInt(e.target.value) })}
                          className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                        />
                      </div>

                      <div>
                        <label htmlFor="max_messages" className="block text-sm font-medium text-gray-700">
                          Máx. Mensagens/Mês (-1 = ilimitado)
                        </label>
                        <input
                          type="number"
                          id="max_messages"
                          min="-1"
                          required
                          value={formData.max_messages_per_month}
                          onChange={(e) => setFormData({ ...formData, max_messages_per_month: parseInt(e.target.value) })}
                          className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                        />
                      </div>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Funcionalidades
                      </label>
                      <div className="space-y-2">
                        {Array.isArray(formData.features) && formData.features.map((feature, index) => (
                          <div key={index} className="flex gap-2">
                            <input
                              type="text"
                              value={feature}
                              onChange={(e) => updateFeature(index, e.target.value)}
                              className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                              placeholder="Digite uma funcionalidade"
                            />
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon"
                              onClick={() => removeFeature(index)}
                            >
                              <X className="h-4 w-4" />
                            </Button>
                          </div>
                        ))}
                        <Button type="button" variant="outline" onClick={addFeature} className="w-full">
                          <Plus className="h-4 w-4 mr-2" />
                          Adicionar Funcionalidade
                        </Button>
                      </div>
                    </div>

                    <div className="flex items-center">
                      <input
                        type="checkbox"
                        id="is_active"
                        checked={formData.is_active}
                        onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                        className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                      />
                      <label htmlFor="is_active" className="ml-2 block text-sm text-gray-900">
                        Plano ativo
                      </label>
                    </div>
                  </div>
                </div>

                <div className="bg-gray-50 px-4 py-3 sm:flex sm:flex-row-reverse sm:px-6 gap-2">
                  <Button type="submit">
                    <Check className="h-4 w-4 mr-2" />
                    Salvar
                  </Button>
                  <Button type="button" variant="outline" onClick={handleCloseModal}>
                    <X className="h-4 w-4 mr-2" />
                    Cancelar
                  </Button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

