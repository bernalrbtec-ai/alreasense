import { useState, useEffect } from 'react'
import { Plus, Edit, Trash2, Check, X } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import { api } from '../lib/api'
import { showSuccessToast, showErrorToast, showLoadingToast, updateToastSuccess, updateToastError } from '../lib/toastHelper'

interface Product {
  id: string
  name: string
  slug: string
  description: string
  icon: string
  addon_price: number | null
  is_active: boolean
}

interface PlanProduct {
  id?: string
  product: Product
  product_id: string
  is_included: boolean
  limit_value: number | null
  limit_unit: string | null
}

interface Plan {
  id: string
  name: string
  slug: string
  description: string
  price: number
  is_active: boolean
  sort_order: number
  products: PlanProduct[]
  product_count: number
  created_at: string
  updated_at: string
}

export default function PlansPage() {
  const [plans, setPlans] = useState<Plan[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingPlan, setEditingPlan] = useState<Plan | null>(null)
  const [formData, setFormData] = useState({
    name: '',
    slug: '',
    description: '',
    price: 0,
    sort_order: 0,
    is_active: true,
    plan_products: [] as PlanProduct[],
  })

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      setIsLoading(true)
      const [plansResponse, productsResponse] = await Promise.all([
        api.get('/billing/plans/'),
        api.get('/billing/products/')
      ])
      
      console.log('✅ Plans response:', plansResponse.data)
      console.log('✅ Products response:', productsResponse.data)
      
      setPlans(plansResponse.data.results || plansResponse.data)
      setProducts(productsResponse.data.results || productsResponse.data)
    } catch (error) {
      console.error('❌ Error fetching data:', error)
      setPlans([])
      setProducts([])
    } finally {
      setIsLoading(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    const toastId = showLoadingToast(editingPlan ? 'atualizar' : 'criar', 'Plano')
    
    try {
      setIsSaving(true)
      
      if (editingPlan) {
        await api.patch(`/billing/plans/${editingPlan.id}/`, formData)
        updateToastSuccess(toastId, 'atualizar', 'Plano')
      } else {
        await api.post('/billing/plans/', formData)
        updateToastSuccess(toastId, 'criar', 'Plano')
      }
      
      await fetchData()
      handleCloseModal()
    } catch (error: any) {
      console.error('❌ Error saving plan:', error)
      updateToastError(toastId, editingPlan ? 'atualizar' : 'criar', 'Plano', error)
    } finally {
      setIsSaving(false)
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Tem certeza que deseja excluir este plano?')) return
    
    const toastId = showLoadingToast('excluir', 'Plano')
    
    try {
      await api.delete(`/billing/plans/${id}/`)
      updateToastSuccess(toastId, 'excluir', 'Plano')
      await fetchData()
    } catch (error: any) {
      console.error('Error deleting plan:', error)
      updateToastError(toastId, 'excluir', 'Plano', error)
    }
  }

  const handleEdit = (plan: Plan) => {
    setEditingPlan(plan)
    setFormData({
      name: plan.name,
      slug: plan.slug,
      description: plan.description,
      price: plan.price,
      sort_order: plan.sort_order,
      is_active: plan.is_active,
      plan_products: plan.products || [],
    })
    setIsModalOpen(true)
  }

  const handleCloseModal = () => {
    setIsModalOpen(false)
    setEditingPlan(null)
    setFormData({
      name: '',
      slug: '',
      description: '',
      price: 0,
      sort_order: 0,
      is_active: true,
      plan_products: [],
    })
  }

  const generateSlug = (name: string) => {
    return name
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/[^a-z0-9\s-]/g, '')
      .replace(/\s+/g, '-')
      .replace(/-+/g, '-')
      .trim()
  }

  const handleNameChange = (name: string) => {
    setFormData({ 
      ...formData, 
      name,
      slug: editingPlan ? formData.slug : generateSlug(name)
    })
  }

  const addProduct = (productId: string) => {
    const product = products.find(p => p.id === productId)
    if (!product) return

    const newPlanProduct: PlanProduct = {
      product_id: productId,
      product: product,
      is_included: true,
      limit_value: null,
      limit_unit: null,
    }

    setFormData({
      ...formData,
      plan_products: [...formData.plan_products, newPlanProduct]
    })
  }

  const removeProduct = (index: number) => {
    const newProducts = formData.plan_products.filter((_, i) => i !== index)
    setFormData({ ...formData, plan_products: newProducts })
  }

  const updateProduct = (index: number, field: keyof PlanProduct, value: any) => {
    const newProducts = [...formData.plan_products]
    newProducts[index] = { ...newProducts[index], [field]: value }
    setFormData({ ...formData, plan_products: newProducts })
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
                  {plan.is_free ? 'Grátis' : `R$ ${Number(plan.price).toFixed(2)}`}
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
                  📦 Produtos: {plan.product_count} incluído(s)
                </p>
              </div>
              
              <div className="pt-3 border-t border-gray-200">
                <div className="space-y-2">
                  {Array.isArray(plan.products) && plan.products.length > 0 ? (
                    plan.products.map((planProduct, index) => (
                      <div key={index} className="flex items-center justify-between text-sm">
                        <div className="flex items-center">
                          <Check className="h-4 w-4 text-green-500 mr-2 flex-shrink-0" />
                          <span className="text-gray-600">{planProduct.product.name}</span>
                        </div>
                        <span className="text-gray-500 font-medium">
                          {planProduct.limit_value || 0} instâncias
                        </span>
                      </div>
                    ))
                  ) : (
                    <p className="text-sm text-gray-500">Nenhum produto incluído</p>
                  )}
                </div>
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
                          onChange={(e) => handleNameChange(e.target.value)}
                          className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                        />
                      </div>

                      <div>
                        <label htmlFor="slug" className="block text-sm font-medium text-gray-700">
                          Slug (identificador único)
                        </label>
                        <input
                          type="text"
                          id="slug"
                          required
                          value={formData.slug}
                          onChange={(e) => setFormData({ ...formData, slug: e.target.value })}
                          className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                        />
                      </div>
                    </div>

                    <div>
                      <label htmlFor="description" className="block text-sm font-medium text-gray-700">
                        Descrição
                      </label>
                      <textarea
                        id="description"
                        rows={3}
                        required
                        value={formData.description}
                        onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                        className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                      />
                    </div>

                    <div className="grid grid-cols-2 gap-4">
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

                      <div>
                        <label htmlFor="sort_order" className="block text-sm font-medium text-gray-700">
                          Ordem de Exibição
                        </label>
                        <input
                          type="number"
                          id="sort_order"
                          min="0"
                          value={formData.sort_order}
                          onChange={(e) => setFormData({ ...formData, sort_order: parseInt(e.target.value) })}
                          className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                        />
                      </div>
                    </div>

                    {/* Seção de Produtos */}
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Produtos Incluídos
                      </label>
                      <div className="space-y-3">
                        {formData.plan_products.map((planProduct, index) => (
                          <div key={index} className="border border-gray-200 rounded-lg p-4">
                            <div className="flex items-center justify-between mb-3">
                              <div className="flex items-center gap-2">
                                <input
                                  type="checkbox"
                                  checked={planProduct.is_included}
                                  onChange={(e) => updateProduct(index, 'is_included', e.target.checked)}
                                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                                />
                                <span className="font-medium">{planProduct.product.name}</span>
                              </div>
                              <Button
                                type="button"
                                variant="ghost"
                                size="icon"
                                onClick={() => removeProduct(index)}
                                className="text-red-600 hover:text-red-700"
                              >
                                <X className="h-4 w-4" />
                              </Button>
                            </div>
                            
                            {planProduct.is_included && (
                              <div className="space-y-3">
                                {/* Limite de Instâncias - Todos os produtos */}
                                <div>
                                  <label className="block text-xs font-medium text-gray-600 mb-1">
                                    Limite de Instâncias
                                  </label>
                                  <div className="grid grid-cols-2 gap-4">
                                    <input
                                      type="number"
                                      min="1"
                                      required
                                      value={planProduct.limit_value || ''}
                                      onChange={(e) => updateProduct(index, 'limit_value', e.target.value ? parseInt(e.target.value) : null)}
                                      className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm"
                                      placeholder="Ex: 5"
                                    />
                                    <input
                                      type="text"
                                      value="instâncias"
                                      readOnly
                                      className="block w-full rounded-md border-gray-300 bg-gray-50 text-sm text-gray-500"
                                    />
                                  </div>
                                  <p className="text-xs text-gray-500 mt-1">
                                    Número máximo de instâncias que o cliente pode cadastrar para este produto
                                  </p>
                                </div>
                                
                                {/* Limites específicos por produto */}
                                {planProduct.product.slug === 'sense' && (
                                  <div>
                                    <label className="block text-xs font-medium text-gray-600 mb-1">
                                      Limite de Análises (Adicional)
                                    </label>
                                    <div className="grid grid-cols-2 gap-4">
                                      <input
                                        type="number"
                                        min="1"
                                        value={planProduct.limit_unit || ''}
                                        onChange={(e) => updateProduct(index, 'limit_unit', e.target.value)}
                                        className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm"
                                        placeholder="Ex: 1000"
                                      />
                                      <input
                                        type="text"
                                        value="análises/mês"
                                        readOnly
                                        className="block w-full rounded-md border-gray-300 bg-gray-50 text-sm text-gray-500"
                                      />
                                    </div>
                                    <p className="text-xs text-gray-500 mt-1">
                                      Número máximo de análises de sentimento por mês
                                    </p>
                                  </div>
                                )}
                                
                                {planProduct.product.slug === 'api_public' && (
                                  <div>
                                    <label className="block text-xs font-medium text-gray-600 mb-1">
                                      Limite de Requests (Adicional)
                                    </label>
                                    <div className="grid grid-cols-2 gap-4">
                                      <input
                                        type="number"
                                        min="1"
                                        value={planProduct.limit_unit || ''}
                                        onChange={(e) => updateProduct(index, 'limit_unit', e.target.value)}
                                        className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm"
                                        placeholder="Ex: 10000"
                                      />
                                      <input
                                        type="text"
                                        value="requests/dia"
                                        readOnly
                                        className="block w-full rounded-md border-gray-300 bg-gray-50 text-sm text-gray-500"
                                      />
                                    </div>
                                    <p className="text-xs text-gray-500 mt-1">
                                      Número máximo de requests à API por dia
                                    </p>
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        ))}
                        
                        {/* Adicionar Produto */}
                        <div className="border-2 border-dashed border-gray-300 rounded-lg p-4">
                          <select
                            onChange={(e) => {
                              if (e.target.value) {
                                addProduct(e.target.value)
                                e.target.value = ''
                              }
                            }}
                            className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 text-sm"
                          >
                            <option value="">Selecionar produto para adicionar...</option>
                            {products
                              .filter(product => !formData.plan_products.some(pp => pp.product_id === product.id))
                              .map(product => (
                                <option key={product.id} value={product.id}>
                                  {product.name}
                                </option>
                              ))}
                          </select>
                        </div>
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

