import { useState, useEffect } from 'react'
import { Plus, Edit, Trash2, Check, X, Mail, Phone, Bell } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import { api } from '../lib/api'
import { showSuccessToast, showErrorToast, showLoadingToast, updateToastSuccess, updateToastError } from '../lib/toastHelper'

interface Tenant {
  id: string
  name: string
  current_plan?: {
    name: string
    slug: string
    price: number
  }
  status: 'active' | 'suspended' | 'trial'
  created_at: string
  user_count?: number
  message_count?: number
  monthly_total?: number
}

interface Plan {
  id: string
  slug: string
  name: string
  price: number
  is_active: boolean
}

interface TenantFormData {
  name: string
  plan: string
  status: 'active' | 'suspended' | 'trial'
  // Dados do usuário principal
  admin_first_name: string
  admin_last_name: string
  admin_email: string
  admin_phone: string
  admin_password: string
  admin_password_confirm: string
  notify_email: boolean
  notify_whatsapp: boolean
}

export default function TenantsPage() {
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [plans, setPlans] = useState<Plan[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingTenant, setEditingTenant] = useState<Tenant | null>(null)
  const [formData, setFormData] = useState<TenantFormData>({
    name: '',
    plan: '',
    status: 'active',
    admin_first_name: '',
    admin_last_name: '',
    admin_email: '',
    admin_phone: '',
    admin_password: '',
    admin_password_confirm: '',
    notify_email: true,
    notify_whatsapp: false,
  })

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      setIsLoading(true)
      // Buscar tenants e planos em paralelo
      const [tenantsResponse, plansResponse] = await Promise.all([
        api.get('/tenants/tenants/'),
        api.get('/billing/plans/')
      ])
      
      setTenants(tenantsResponse.data.results || tenantsResponse.data)
      const plansData = plansResponse.data.results || plansResponse.data
      setPlans(plansData)
      
      // Definir o primeiro plano como padrão se não houver plano selecionado
      if (plansData.length > 0 && !formData.plan) {
        setFormData(prev => ({ ...prev, plan: plansData[0].slug }))
      }
    } catch (error) {
      console.error('Error fetching data:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    // Validações apenas para novo cliente
    if (!editingTenant) {
      // Validar senhas
      if (formData.admin_password !== formData.admin_password_confirm) {
        showErrorToast('salvar', 'Cliente', { message: 'As senhas não coincidem' })
        return
      }
      
      if (formData.admin_password.length < 6) {
        showErrorToast('salvar', 'Cliente', { message: 'A senha deve ter pelo menos 6 caracteres' })
        return
      }
      
      // Validar email
      if (!formData.admin_email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.admin_email)) {
        showErrorToast('salvar', 'Cliente', { message: 'Email inválido' })
        return
      }
      
      // Validar se pelo menos uma forma de notificação está marcada
      if (!formData.notify_email && !formData.notify_whatsapp) {
        showErrorToast('salvar', 'Cliente', { message: 'Selecione pelo menos uma forma de receber notificações' })
        return
      }
    } else {
      // Validações para edição
      if (formData.admin_password && formData.admin_password.length < 6) {
        showErrorToast('atualizar', 'Cliente', { message: 'A senha deve ter pelo menos 6 caracteres' })
        return
      }
      
      if (formData.admin_password !== formData.admin_password_confirm) {
        showErrorToast('atualizar', 'Cliente', { message: 'As senhas não coincidem' })
        return
      }
      
      // Validar email se fornecido
      if (formData.admin_email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.admin_email)) {
        showErrorToast('atualizar', 'Cliente', { message: 'Email inválido' })
        return
      }
    }
    
    const toastId = showLoadingToast(editingTenant ? 'atualizar' : 'criar', 'Cliente')
    
    try {
      if (editingTenant) {
        // Edição - envia dados do tenant + dados do usuário (se fornecidos)
        const updateData: any = {
          name: formData.name,
          plan: formData.plan,
          status: formData.status,
        }
        
        // Adicionar dados do usuário apenas se fornecidos
        if (formData.admin_first_name || formData.admin_last_name || formData.admin_email || 
            formData.admin_phone || formData.admin_password) {
          updateData.admin_user = {}
          
          if (formData.admin_first_name) updateData.admin_user.first_name = formData.admin_first_name
          if (formData.admin_last_name) updateData.admin_user.last_name = formData.admin_last_name
          if (formData.admin_email) updateData.admin_user.email = formData.admin_email
          if (formData.admin_phone) updateData.admin_user.phone = formData.admin_phone
          if (formData.admin_password) updateData.admin_user.password = formData.admin_password
        }
        
        await api.patch(`/tenants/tenants/${editingTenant.id}/`, updateData)
        updateToastSuccess(toastId, 'atualizar', 'Cliente')
      } else {
        // Criação - envia tenant + usuário admin
        await api.post('/tenants/tenants/', formData)
        updateToastSuccess(toastId, 'criar', 'Cliente')
      }
      fetchData()
      handleCloseModal()
    } catch (error: any) {
      console.error('Error saving tenant:', error)
      updateToastError(toastId, editingTenant ? 'atualizar' : 'salvar', 'Cliente', error)
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Tem certeza que deseja excluir este cliente?')) return
    
    const toastId = showLoadingToast('excluir', 'Cliente')
    
    try {
      await api.delete(`/tenants/tenants/${id}/`)
      updateToastSuccess(toastId, 'excluir', 'Cliente')
      fetchData()
    } catch (error: any) {
      console.error('Error deleting tenant:', error)
      updateToastError(toastId, 'excluir', 'Cliente', error)
    }
  }

  const handleEdit = (tenant: Tenant) => {
    setEditingTenant(tenant)
    setFormData({
      name: tenant.name,
      plan: tenant.current_plan?.slug || 'starter',
      status: tenant.status,
      // Carregar dados do admin_user se disponíveis
      admin_first_name: (tenant as any).admin_user?.first_name || '',
      admin_last_name: (tenant as any).admin_user?.last_name || '',
      admin_email: (tenant as any).admin_user?.email || '',
      admin_phone: (tenant as any).admin_user?.phone || '',
      admin_password: '',
      admin_password_confirm: '',
      notify_email: true,
      notify_whatsapp: false,
    })
    setIsModalOpen(true)
  }

  const handleCloseModal = () => {
    setIsModalOpen(false)
    setEditingTenant(null)
    setFormData({
      name: '',
      plan: plans.length > 0 ? plans[0].slug : '',
      status: 'active',
      admin_first_name: '',
      admin_last_name: '',
      admin_email: '',
      admin_phone: '',
      admin_password: '',
      admin_password_confirm: '',
      notify_email: true,
      notify_whatsapp: false,
    })
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
        return 'bg-green-100 text-green-800'
      case 'suspended':
        return 'bg-red-100 text-red-800'
      case 'trial':
        return 'bg-yellow-100 text-yellow-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'active':
        return 'Ativo'
      case 'suspended':
        return 'Suspenso'
      case 'trial':
        return 'Trial'
      default:
        return status
    }
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
          <h1 className="text-2xl font-bold text-gray-900">Clientes</h1>
          <p className="mt-1 text-sm text-gray-500">
            Gerencie os clientes (tenants) da plataforma
          </p>
        </div>
        <Button onClick={() => setIsModalOpen(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Novo Cliente
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.isArray(tenants) && tenants.map((tenant) => (
          <Card key={tenant.id} className="p-6">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <h3 className="text-lg font-medium text-gray-900">{tenant.name}</h3>
                <p className="mt-1 text-sm text-gray-500">ID: {tenant.id.slice(0, 8)}...</p>
                <div className="mt-2 flex items-center gap-2">
                  <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${getStatusColor(tenant.status)}`}>
                    {getStatusLabel(tenant.status)}
                  </span>
                  <span className="text-xs text-gray-500">
                    Plano: {tenant.current_plan?.name || 'Sem Plano'}
                  </span>
                </div>
                {tenant.monthly_total && (
                  <div className="mt-1 text-sm font-medium text-blue-600">
                    R$ {Number(tenant.monthly_total).toFixed(2)}/mês
                  </div>
                )}
                {tenant.user_count !== undefined && (
                  <div className="mt-3 text-sm text-gray-600">
                    <p>{tenant.user_count} usuários</p>
                    <p>{tenant.message_count || 0} mensagens</p>
                  </div>
                )}
              </div>
              <div className="flex gap-2">
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => handleEdit(tenant)}
                >
                  <Edit className="h-4 w-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => handleDelete(tenant.id)}
                  className="text-red-600 hover:text-red-700"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </Card>
        ))}
      </div>

      {(!Array.isArray(tenants) || tenants.length === 0) && (
        <div className="text-center py-12">
          <p className="text-gray-500">Nenhum cliente cadastrado</p>
        </div>
      )}

      {/* Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-full items-end justify-center p-4 text-center sm:items-center sm:p-0">
            <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" onClick={handleCloseModal} />
            
            <div className="relative transform overflow-hidden rounded-lg bg-white text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-2xl max-h-[90vh] overflow-y-auto">
              <form onSubmit={handleSubmit}>
                <div className="bg-white px-4 pb-4 pt-5 sm:p-6 sm:pb-4">
                  <h3 className="text-lg font-medium leading-6 text-gray-900 mb-4">
                    {editingTenant ? 'Editar Cliente' : 'Novo Cliente'}
                  </h3>
                  
                  <div className="space-y-4">
                    {/* Dados do Cliente */}
                    <div className="pb-4 border-b">
                      <h4 className="text-sm font-medium text-gray-900 mb-3">Dados do Cliente</h4>
                      
                      <div className="space-y-3">
                        <div>
                          <label htmlFor="name" className="block text-sm font-medium text-gray-700">
                            Nome da Empresa *
                          </label>
                          <input
                            type="text"
                            id="name"
                            required
                            value={formData.name}
                            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                          />
                        </div>

                        <div>
                          <label htmlFor="plan" className="block text-sm font-medium text-gray-700">
                            Plano *
                          </label>
                          <select
                            id="plan"
                            required
                            value={formData.plan}
                            onChange={(e) => setFormData({ ...formData, plan: e.target.value })}
                            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                          >
                            {plans.map((plan) => (
                              <option key={plan.id} value={plan.slug}>
                                {plan.name} - R$ {Number(plan.price).toFixed(2)}
                              </option>
                            ))}
                          </select>
                        </div>

                        <div>
                          <label htmlFor="status" className="block text-sm font-medium text-gray-700">
                            Status *
                          </label>
                          <select
                            id="status"
                            required
                            value={formData.status}
                            onChange={(e) => setFormData({ ...formData, status: e.target.value as any })}
                            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                          >
                            <option value="active">Ativo</option>
                            <option value="trial">Trial</option>
                            <option value="suspended">Suspenso</option>
                          </select>
                        </div>
                      </div>
                    </div>
                    
                    {/* Dados do Usuário Principal */}
                    <div className="pt-2">
                        <h4 className="text-sm font-medium text-gray-900 mb-3">
                          {editingTenant ? 'Usuário Principal (Admin) - Edição' : 'Usuário Principal (Admin)'}
                        </h4>
                        
                        <div className="space-y-3">
                          <div className="grid grid-cols-2 gap-3">
                            <div>
                              <label htmlFor="admin_first_name" className="block text-sm font-medium text-gray-700">
                                Nome *
                              </label>
                              <input
                                type="text"
                                id="admin_first_name"
                                required
                                value={formData.admin_first_name}
                                onChange={(e) => setFormData({ ...formData, admin_first_name: e.target.value })}
                                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                                placeholder={editingTenant ? "Manter vazio para não alterar" : ""}
                              />
                            </div>
                            
                            <div>
                              <label htmlFor="admin_last_name" className="block text-sm font-medium text-gray-700">
                                Sobrenome *
                              </label>
                              <input
                                type="text"
                                id="admin_last_name"
                                required
                                value={formData.admin_last_name}
                                onChange={(e) => setFormData({ ...formData, admin_last_name: e.target.value })}
                                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                                placeholder={editingTenant ? "Manter vazio para não alterar" : ""}
                              />
                            </div>
                          </div>
                          
                          <div>
                            <label htmlFor="admin_email" className="block text-sm font-medium text-gray-700">
                              <Mail className="inline h-4 w-4 mr-1" />
                              Email *
                            </label>
                            <input
                              type="email"
                              id="admin_email"
                              required
                              value={formData.admin_email}
                              onChange={(e) => setFormData({ ...formData, admin_email: e.target.value })}
                              placeholder={editingTenant ? "Novo email (opcional)" : "usuario@exemplo.com"}
                              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                            />
                          </div>
                          
                          <div>
                            <label htmlFor="admin_phone" className="block text-sm font-medium text-gray-700">
                              <Phone className="inline h-4 w-4 mr-1" />
                              Telefone
                            </label>
                            <input
                              type="tel"
                              id="admin_phone"
                              value={formData.admin_phone}
                              onChange={(e) => setFormData({ ...formData, admin_phone: e.target.value })}
                              placeholder={editingTenant ? "Novo telefone (opcional)" : "(11) 99999-9999"}
                              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                            />
                          </div>
                          
                          <div className="grid grid-cols-2 gap-3">
                            <div>
                              <label htmlFor="admin_password" className="block text-sm font-medium text-gray-700">
                                {editingTenant ? "Nova Senha (opcional)" : "Senha *"}
                              </label>
                              <input
                                type="password"
                                id="admin_password"
                                required={!editingTenant}
                                value={formData.admin_password}
                                onChange={(e) => setFormData({ ...formData, admin_password: e.target.value })}
                                placeholder={editingTenant ? "Deixe vazio para manter a senha atual" : "Mínimo 6 caracteres"}
                                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                              />
                            </div>
                            
                            <div>
                              <label htmlFor="admin_password_confirm" className="block text-sm font-medium text-gray-700">
                                {editingTenant ? "Confirmar Nova Senha" : "Confirmar Senha *"}
                              </label>
                              <input
                                type="password"
                                id="admin_password_confirm"
                                required={!editingTenant}
                                value={formData.admin_password_confirm}
                                onChange={(e) => setFormData({ ...formData, admin_password_confirm: e.target.value })}
                                placeholder={editingTenant ? "Deixe vazio se não alterar a senha" : "Digite novamente"}
                                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
                              />
                            </div>
                          </div>
                          
                          {!editingTenant && (
                            <div>
                              <label className="block text-sm font-medium text-gray-700 mb-2">
                                <Bell className="inline h-4 w-4 mr-1" />
                                Receber Notificações Por: *
                              </label>
                              <div className="space-y-2">
                                <label className="flex items-center">
                                  <input
                                    type="checkbox"
                                    checked={formData.notify_email}
                                    onChange={(e) => setFormData({ ...formData, notify_email: e.target.checked })}
                                    className="rounded border-gray-300 text-blue-600 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                                  />
                                  <span className="ml-2 text-sm text-gray-700">Email</span>
                                </label>
                                
                                <label className="flex items-center">
                                  <input
                                    type="checkbox"
                                    checked={formData.notify_whatsapp}
                                    onChange={(e) => setFormData({ ...formData, notify_whatsapp: e.target.checked })}
                                    className="rounded border-gray-300 text-blue-600 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                                  />
                                  <span className="ml-2 text-sm text-gray-700">WhatsApp</span>
                                </label>
                              </div>
                              <p className="mt-1 text-xs text-gray-500">
                                Selecione pelo menos uma opção
                              </p>
                            </div>
                          )}
                          
                          {editingTenant && (
                            <div className="bg-blue-50 p-3 rounded-lg">
                              <p className="text-sm text-blue-700">
                                💡 <strong>Dica:</strong> Deixe os campos vazios para manter as informações atuais. 
                                Para alterar apenas o email ou senha, preencha apenas os campos desejados.
                              </p>
                            </div>
                          )}
                        </div>
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

