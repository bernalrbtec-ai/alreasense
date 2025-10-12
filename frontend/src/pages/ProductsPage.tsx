import { useState, useEffect } from 'react'
import { Plus, Edit, Trash2, Check, X, Package, Zap, DollarSign } from 'lucide-react'
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
  created_at: string
  updated_at: string
}

export default function ProductsPage() {
  const [products, setProducts] = useState<Product[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingProduct, setEditingProduct] = useState<Product | null>(null)
  const [formData, setFormData] = useState({
    name: '',
    slug: '',
    description: '',
    icon: 'Package',
    addon_price: null as number | null,
    is_active: true,
  })

  useEffect(() => {
    fetchProducts()
  }, [])

  const fetchProducts = async () => {
    try {
      setIsLoading(true)
      console.log('🔍 Fetching products from /billing/products/')
      const response = await api.get('/billing/products/')
      console.log('✅ Products response:', response.data)
      setProducts(response.data.results || response.data)
    } catch (error) {
      console.error('❌ Error fetching products:', error)
      setProducts([])
    } finally {
      setIsLoading(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    const toastId = showLoadingToast(editingProduct ? 'atualizar' : 'criar', 'Produto')
    
    try {
      setIsSaving(true)
      
      if (editingProduct) {
        await api.patch(`/billing/products/${editingProduct.id}/`, formData)
        updateToastSuccess(toastId, 'atualizar', 'Produto')
      } else {
        await api.post('/billing/products/', formData)
        updateToastSuccess(toastId, 'criar', 'Produto')
      }
      
      await fetchProducts()
      handleCloseModal()
    } catch (error: any) {
      console.error('❌ Error saving product:', error)
      updateToastError(toastId, editingProduct ? 'atualizar' : 'criar', 'Produto', error)
    } finally {
      setIsSaving(false)
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Tem certeza que deseja excluir este produto?')) return
    
    const toastId = showLoadingToast('excluir', 'Produto')
    
    try {
      await api.delete(`/billing/products/${id}/`)
      updateToastSuccess(toastId, 'excluir', 'Produto')
      await fetchProducts()
    } catch (error: any) {
      console.error('Error deleting product:', error)
      updateToastError(toastId, 'excluir', 'Produto', error)
    }
  }

  const handleEdit = (product: Product) => {
    setEditingProduct(product)
    setFormData({
      name: product.name,
      slug: product.slug,
      description: product.description,
      icon: product.icon,
      addon_price: product.addon_price,
      is_active: product.is_active,
    })
    setIsModalOpen(true)
  }

  const handleCloseModal = () => {
    setIsModalOpen(false)
    setEditingProduct(null)
    setFormData({
      name: '',
      slug: '',
      description: '',
      icon: 'Package',
      addon_price: null,
      is_active: true,
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
      slug: editingProduct ? formData.slug : generateSlug(name)
    })
  }

  const getIconComponent = (iconName: string) => {
    const icons: { [key: string]: any } = {
      Package,
      Zap,
      DollarSign,
    }
    return icons[iconName] || Package
  }

  if (isLoading && (!Array.isArray(products) || products.length === 0)) {
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
          <h1 className="text-2xl font-bold text-gray-900">Produtos</h1>
          <p className="mt-1 text-sm text-gray-500">
            Gerencie os produtos da plataforma
          </p>
        </div>
        <Button onClick={() => setIsModalOpen(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Novo Produto
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {Array.isArray(products) && products.map((product) => {
          const IconComponent = getIconComponent(product.icon)
          return (
            <Card key={product.id} className={`p-6 relative ${!product.is_active ? 'opacity-60 border-gray-300' : 'border-blue-200'}`}>
              {/* Status Badge */}
              <div className="absolute top-4 right-4 flex gap-2">
                {product.is_active ? (
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
                {product.addon_price && (
                  <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
                    Add-on
                  </span>
                )}
              </div>

              <div className="mb-4 pr-24">
                <div className="flex items-center gap-3 mb-2">
                  <div className="p-2 bg-blue-100 rounded-lg">
                    <IconComponent className="h-6 w-6 text-blue-600" />
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-gray-900">{product.name}</h3>
                  </div>
                </div>
                
                <p className="text-sm text-gray-600 mb-3">{product.description}</p>
                
                {product.addon_price && (
                  <div className="flex items-center gap-2 text-sm">
                    <DollarSign className="h-4 w-4 text-green-600" />
                    <span className="font-medium text-green-600">
                      R$ {Number(product.addon_price).toFixed(2)}/mês
                    </span>
                  </div>
                )}
              </div>
            
              <div className="mt-4 pt-4 border-t border-gray-200 flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleEdit(product)}
                  className="flex-1"
                >
                  <Edit className="h-3 w-3 mr-1" />
                  Editar
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleDelete(product.id)}
                  className="text-red-600 hover:text-red-700 hover:border-red-300"
                >
                  <Trash2 className="h-3 w-3" />
                </Button>
              </div>
            </Card>
          )
        })}
      </div>

      {(!Array.isArray(products) || products.length === 0) && !isLoading && (
        <Card className="p-12">
          <div className="text-center">
            <Package className="mx-auto h-12 w-12 text-gray-400" />
            <h3 className="mt-2 text-sm font-medium text-gray-900">Nenhum produto cadastrado</h3>
            <p className="mt-1 text-sm text-gray-500">
              Comece criando um novo produto
            </p>
            <div className="mt-6">
              <Button onClick={() => setIsModalOpen(true)}>
                <Plus className="h-4 w-4 mr-2" />
                Criar Primeiro Produto
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
                    {editingProduct ? 'Editar Produto' : 'Novo Produto'}
                  </h3>
                  
                  <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label htmlFor="name" className="block text-sm font-medium text-gray-700">
                          Nome do Produto
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
                        <p className="mt-1 text-xs text-gray-500">
                          Usado para identificar o produto no sistema
                        </p>
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
                        <label htmlFor="icon" className="block text-sm font-medium text-gray-700">
                          Ícone
                        </label>
                        <select
                          id="icon"
                          value={formData.icon}
                          onChange={(e) => setFormData({ ...formData, icon: e.target.value })}
                          className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                        >
                          <option value="Package">Package</option>
                          <option value="Zap">Zap</option>
                          <option value="DollarSign">DollarSign</option>
                        </select>
                      </div>

                      <div>
                        <label htmlFor="addon_price" className="block text-sm font-medium text-gray-700">
                          Preço Add-on (R$)
                        </label>
                        <input
                          type="number"
                          id="addon_price"
                          step="0.01"
                          min="0"
                          value={formData.addon_price || ''}
                          onChange={(e) => setFormData({ 
                            ...formData, 
                            addon_price: e.target.value ? parseFloat(e.target.value) : null 
                          })}
                          className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                          placeholder="Deixe vazio se não for add-on"
                        />
                        <p className="mt-1 text-xs text-gray-500">
                          Preço adicional por mês (opcional)
                        </p>
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
                        Produto ativo
                      </label>
                    </div>
                  </div>
                </div>

                <div className="bg-gray-50 px-4 py-3 sm:flex sm:flex-row-reverse sm:px-6 gap-2">
                  <Button type="submit" disabled={isSaving}>
                    <Check className="h-4 w-4 mr-2" />
                    {isSaving ? 'Salvando...' : 'Salvar'}
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
