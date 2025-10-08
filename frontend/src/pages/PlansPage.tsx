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
      // TODO: Criar endpoint de planos no backend
      // const response = await api.get('/billing/plans/')
      // setPlans(response.data.results || response.data)
      
      // Mock data for now
      setPlans([
        {
          id: '1',
          name: 'Free',
          price: 0,
          max_connections: 1,
          max_messages_per_month: 1000,
          features: ['1 conexão', '1.000 mensagens/mês', 'Suporte por email'],
          is_active: true,
        },
        {
          id: '2',
          name: 'Starter',
          price: 49.90,
          max_connections: 3,
          max_messages_per_month: 10000,
          features: ['3 conexões', '10.000 mensagens/mês', 'Suporte prioritário', 'Análise de sentimento'],
          is_active: true,
        },
        {
          id: '3',
          name: 'Pro',
          price: 149.90,
          max_connections: 10,
          max_messages_per_month: 50000,
          features: ['10 conexões', '50.000 mensagens/mês', 'Suporte 24/7', 'Análise completa', 'API access'],
          is_active: true,
        },
        {
          id: '4',
          name: 'Enterprise',
          price: 499.90,
          max_connections: -1,
          max_messages_per_month: -1,
          features: ['Conexões ilimitadas', 'Mensagens ilimitadas', 'Suporte dedicado', 'SLA garantido', 'Custom features'],
          is_active: true,
        },
      ])
    } catch (error) {
      console.error('Error fetching plans:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      // TODO: Implementar no backend
      // if (editingPlan) {
      //   await api.patch(`/billing/plans/${editingPlan.id}/`, formData)
      // } else {
      //   await api.post('/billing/plans/', formData)
      // }
      fetchPlans()
      handleCloseModal()
    } catch (error) {
      console.error('Error saving plan:', error)
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Tem certeza que deseja excluir este plano?')) return
    try {
      // await api.delete(`/billing/plans/${id}/`)
      fetchPlans()
    } catch (error) {
      console.error('Error deleting plan:', error)
    }
  }

  const handleEdit = (plan: Plan) => {
    setEditingPlan(plan)
    setFormData({
      name: plan.name,
      price: plan.price,
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

  if (isLoading) {
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
        {plans.map((plan) => (
          <Card key={plan.id} className={`p-6 ${!plan.is_active ? 'opacity-50' : ''}`}>
            <div className="flex items-start justify-between mb-4">
              <div>
                <h3 className="text-lg font-bold text-gray-900">{plan.name}</h3>
                <p className="mt-1 text-3xl font-bold text-blue-600">
                  R$ {plan.price.toFixed(2)}
                  <span className="text-sm font-normal text-gray-500">/mês</span>
                </p>
              </div>
              <div className="flex gap-1">
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => handleEdit(plan)}
                >
                  <Edit className="h-4 w-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => handleDelete(plan.id)}
                  className="text-red-600 hover:text-red-700"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
            
            <div className="space-y-2">
              <div className="text-sm text-gray-600">
                <p className="font-medium">Conexões: {plan.max_connections === -1 ? 'Ilimitadas' : plan.max_connections}</p>
                <p className="font-medium">
                  Mensagens: {plan.max_messages_per_month === -1 ? 'Ilimitadas' : plan.max_messages_per_month.toLocaleString()}/mês
                </p>
              </div>
              
              <div className="pt-4 border-t border-gray-200">
                <ul className="space-y-2">
                  {plan.features.map((feature, index) => (
                    <li key={index} className="flex items-start text-sm text-gray-600">
                      <Check className="h-4 w-4 text-green-500 mr-2 flex-shrink-0 mt-0.5" />
                      {feature}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
            
            {!plan.is_active && (
              <div className="mt-4 text-xs text-red-600 font-medium">
                Plano inativo
              </div>
            )}
          </Card>
        ))}
      </div>

      {plans.length === 0 && (
        <div className="text-center py-12">
          <p className="text-gray-500">Nenhum plano cadastrado</p>
        </div>
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
                        />
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
                        {formData.features.map((feature, index) => (
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

