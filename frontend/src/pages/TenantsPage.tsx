import { useState, useEffect } from 'react'
import { Plus, Edit, Trash2, Check, X, Mail, Phone, Bell } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Input } from '../components/ui/Input'
import { Select } from '../components/ui/select'
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
  admin_user?: {
    id: string
    first_name: string
    last_name: string
    email: string
    phone: string
  } | null
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
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [deletingTenant, setDeletingTenant] = useState<Tenant | null>(null)
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
    setFieldErrors({})

    const errors: Record<string, string> = {}

    if (!editingTenant) {
      if (formData.admin_password !== formData.admin_password_confirm) {
        errors.admin_password_confirm = 'As senhas não coincidem'
      }
      if (formData.admin_password.length < 6) {
        errors.admin_password = 'A senha deve ter pelo menos 6 caracteres'
      }
      if (!formData.admin_email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.admin_email)) {
        errors.admin_email = 'Email inválido'
      }
      if (!formData.notify_email && !formData.notify_whatsapp) {
        showErrorToast('salvar', 'Cliente', { message: 'Selecione pelo menos uma forma de receber notificações' })
        return
      }
    } else {
      if (formData.admin_password && formData.admin_password.length < 6) {
        errors.admin_password = 'A senha deve ter pelo menos 6 caracteres'
      }
      if (formData.admin_password !== formData.admin_password_confirm) {
        errors.admin_password_confirm = 'As senhas não coincidem'
      }
      if (formData.admin_email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.admin_email)) {
        errors.admin_email = 'Email inválido'
      }
    }

    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors)
      return
    }

    const toastId = showLoadingToast(editingTenant ? 'atualizar' : 'criar', 'Cliente')
    setIsSubmitting(true)

    try {
      if (editingTenant) {
        const updateData: any = {
          name: formData.name,
          plan: formData.plan,
          status: formData.status,
        }
        const hasAdminFields =
          (formData.admin_first_name || '').trim() ||
          (formData.admin_last_name || '').trim() ||
          (formData.admin_email || '').trim() ||
          (formData.admin_phone || '').trim() ||
          (formData.admin_password || '').trim()
        if (hasAdminFields) {
          updateData.admin_user = {}
          const fn = (formData.admin_first_name || '').trim()
          const ln = (formData.admin_last_name || '').trim()
          const em = (formData.admin_email || '').trim()
          const ph = (formData.admin_phone || '').trim()
          if (fn) updateData.admin_user.first_name = fn
          if (ln) updateData.admin_user.last_name = ln
          if (em) updateData.admin_user.email = em
          if (ph) updateData.admin_user.phone = ph
          if (formData.admin_password) updateData.admin_user.password = formData.admin_password
        }
        await api.patch(`/tenants/tenants/${editingTenant.id}/`, updateData)
        updateToastSuccess(toastId, 'atualizar', 'Cliente')
      } else {
        await api.post('/tenants/tenants/', formData)
        updateToastSuccess(toastId, 'criar', 'Cliente')
      }
      fetchData()
      handleCloseModal()
    } catch (error: any) {
      console.error('Error saving tenant:', error)
      updateToastError(toastId, editingTenant ? 'atualizar' : 'salvar', 'Cliente', error)
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleDeleteClick = (tenant: Tenant) => {
    setDeletingTenant(tenant)
  }

  const handleCancelDelete = () => {
    setDeletingTenant(null)
  }

  const handleConfirmDelete = async () => {
    if (!deletingTenant) return
    const id = deletingTenant.id
    const toastId = showLoadingToast('excluir', 'Cliente')
    try {
      await api.delete(`/tenants/tenants/${id}/`)
      updateToastSuccess(toastId, 'excluir', 'Cliente')
      setDeletingTenant(null)
      fetchData()
    } catch (error: any) {
      console.error('Error deleting tenant:', error)
      updateToastError(toastId, 'excluir', 'Cliente', error)
    }
  }

  const handleEdit = (tenant: Tenant) => {
    setEditingTenant(tenant)
    setFieldErrors({})
    setFormData({
      name: tenant.name,
      plan: tenant.current_plan?.slug || 'starter',
      status: tenant.status,
      admin_first_name: tenant.admin_user?.first_name || '',
      admin_last_name: tenant.admin_user?.last_name || '',
      admin_email: tenant.admin_user?.email || '',
      admin_phone: tenant.admin_user?.phone || '',
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
    setFieldErrors({})
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
        return 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200'
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
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Clientes</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Gerencie os clientes (tenants) da plataforma
          </p>
        </div>
        <Button onClick={() => { setFieldErrors({}); setIsModalOpen(true) }}>
          <Plus className="h-4 w-4 mr-2" />
          Novo Cliente
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.isArray(tenants) && tenants.map((tenant) => (
          <Card key={tenant.id} className="p-6">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100">{tenant.name}</h3>
                <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">ID: {tenant.id.slice(0, 8)}...</p>
                <div className="mt-2 flex items-center gap-2">
                  <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${getStatusColor(tenant.status)}`}>
                    {getStatusLabel(tenant.status)}
                  </span>
                  <span className="text-xs text-gray-500 dark:text-gray-400">
                    Plano: {tenant.current_plan?.name || 'Sem Plano'}
                  </span>
                </div>
                {tenant.monthly_total && (
                  <div className="mt-1 text-sm font-medium text-blue-600">
                    R$ {Number(tenant.monthly_total).toFixed(2)}/mês
                  </div>
                )}
                {tenant.user_count !== undefined && (
                  <div className="mt-3 text-sm text-gray-600 dark:text-gray-400">
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
                  onClick={() => handleDeleteClick(tenant)}
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
          <p className="text-gray-500 dark:text-gray-400">Nenhum cliente cadastrado</p>
        </div>
      )}

      {/* Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-full items-end justify-center p-4 text-center sm:items-center sm:p-0">
            <div className="fixed inset-0 bg-gray-500 dark:bg-black/50 bg-opacity-75 transition-opacity" onClick={handleCloseModal} />
            
            <div className="relative transform overflow-hidden rounded-lg bg-white dark:bg-gray-800 text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-2xl flex flex-col max-h-[90vh]">
              <form onSubmit={handleSubmit} className="flex flex-col min-h-0">
                <div className="flex-none px-4 pt-5 sm:p-6 pb-2 border-b border-gray-200 dark:border-gray-600">
                  <h3 className="text-lg font-medium leading-6 text-gray-900 dark:text-gray-100">
                    {editingTenant ? 'Editar Cliente' : 'Novo Cliente'}
                  </h3>
                </div>
                
                <div className="flex-1 min-h-0 overflow-y-auto px-4 py-4 sm:px-6 space-y-4">
                  {/* Dados do Cliente */}
                  <div className="pb-4 border-b border-gray-200 dark:border-gray-600">
                    <h4 className="text-sm font-medium text-gray-900 dark:text-gray-100 mb-3">Dados do Cliente</h4>
                    <div className="space-y-3">
                      <div>
                        <label htmlFor="name" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                          Nome da Empresa *
                        </label>
                        <Input
                          type="text"
                          id="name"
                          required
                          value={formData.name}
                          onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                          className="mt-1"
                        />
                      </div>
                      <div>
                        <label htmlFor="plan" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                          Plano *
                        </label>
                        <Select
                          id="plan"
                          required
                          value={formData.plan}
                          onChange={(e) => setFormData({ ...formData, plan: e.target.value })}
                          className="mt-1"
                        >
                          {plans.map((plan) => (
                            <option key={plan.id} value={plan.slug}>
                              {plan.name} - R$ {Number(plan.price).toFixed(2)}
                            </option>
                          ))}
                        </Select>
                      </div>
                      <div>
                        <label htmlFor="status" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                          Status *
                        </label>
                        <Select
                          id="status"
                          required
                          value={formData.status}
                          onChange={(e) => setFormData({ ...formData, status: e.target.value as 'active' | 'suspended' | 'trial' })}
                          className="mt-1"
                        >
                          <option value="active">Ativo</option>
                          <option value="trial">Trial</option>
                          <option value="suspended">Suspenso</option>
                        </Select>
                      </div>
                    </div>
                  </div>
                  
                  {/* Dados do Usuário Principal */}
                  <div className="pt-2">
                    <h4 className="text-sm font-medium text-gray-900 dark:text-gray-100 mb-3">
                      {editingTenant ? 'Usuário Principal (Admin) - Edição' : 'Usuário Principal (Admin)'}
                    </h4>
                    <div className="space-y-3">
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label htmlFor="admin_first_name" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                            Nome {!editingTenant && '*'}
                          </label>
                          <Input
                            type="text"
                            id="admin_first_name"
                            required={!editingTenant}
                            value={formData.admin_first_name}
                            onChange={(e) => {
                              setFormData({ ...formData, admin_first_name: e.target.value })
                              setFieldErrors((prev) => ({ ...prev, admin_email: undefined, admin_password: undefined, admin_password_confirm: undefined }))
                            }}
                            className="mt-1"
                            placeholder={editingTenant ? 'Manter vazio para não alterar' : ''}
                          />
                        </div>
                        <div>
                          <label htmlFor="admin_last_name" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                            Sobrenome {!editingTenant && '*'}
                          </label>
                          <Input
                            type="text"
                            id="admin_last_name"
                            required={!editingTenant}
                            value={formData.admin_last_name}
                            onChange={(e) => {
                              setFormData({ ...formData, admin_last_name: e.target.value })
                              setFieldErrors((prev) => ({ ...prev, admin_email: undefined, admin_password: undefined, admin_password_confirm: undefined }))
                            }}
                            className="mt-1"
                            placeholder={editingTenant ? 'Manter vazio para não alterar' : ''}
                          />
                        </div>
                      </div>
                      <div>
                        <label htmlFor="admin_email" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                          <Mail className="inline h-4 w-4 mr-1" />
                          Email {!editingTenant && '*'}
                        </label>
                        <Input
                          type="email"
                          id="admin_email"
                          required={!editingTenant}
                          value={formData.admin_email}
                          onChange={(e) => {
                            setFormData({ ...formData, admin_email: e.target.value })
                            setFieldErrors((prev) => ({ ...prev, admin_email: undefined }))
                          }}
                          className="mt-1"
                          placeholder={editingTenant ? 'Novo email (opcional)' : 'usuario@exemplo.com'}
                        />
                        {fieldErrors.admin_email && (
                          <p className="mt-1 text-sm text-red-600 dark:text-red-400">{fieldErrors.admin_email}</p>
                        )}
                      </div>
                      <div>
                        <label htmlFor="admin_phone" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                          <Phone className="inline h-4 w-4 mr-1" />
                          Telefone
                        </label>
                        <Input
                          type="tel"
                          id="admin_phone"
                          value={formData.admin_phone}
                          onChange={(e) => setFormData({ ...formData, admin_phone: e.target.value })}
                          className="mt-1"
                          placeholder={editingTenant ? 'Novo telefone (opcional)' : '(11) 99999-9999'}
                        />
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label htmlFor="admin_password" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                            {editingTenant ? 'Nova Senha (opcional)' : 'Senha *'}
                          </label>
                          <Input
                            type="password"
                            id="admin_password"
                            required={!editingTenant}
                            value={formData.admin_password}
                            onChange={(e) => {
                              setFormData({ ...formData, admin_password: e.target.value })
                              setFieldErrors((prev) => ({ ...prev, admin_password: undefined, admin_password_confirm: undefined }))
                            }}
                            className="mt-1"
                            placeholder={editingTenant ? 'Deixe vazio para manter a senha atual' : 'Mínimo 6 caracteres'}
                          />
                          {fieldErrors.admin_password && (
                            <p className="mt-1 text-sm text-red-600 dark:text-red-400">{fieldErrors.admin_password}</p>
                          )}
                        </div>
                        <div>
                          <label htmlFor="admin_password_confirm" className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                            {editingTenant ? 'Confirmar Nova Senha' : 'Confirmar Senha *'}
                          </label>
                          <Input
                            type="password"
                            id="admin_password_confirm"
                            required={!editingTenant}
                            value={formData.admin_password_confirm}
                            onChange={(e) => {
                              setFormData({ ...formData, admin_password_confirm: e.target.value })
                              setFieldErrors((prev) => ({ ...prev, admin_password_confirm: undefined }))
                            }}
                            className="mt-1"
                            placeholder={editingTenant ? 'Deixe vazio se não alterar a senha' : 'Digite novamente'}
                          />
                          {fieldErrors.admin_password_confirm && (
                            <p className="mt-1 text-sm text-red-600 dark:text-red-400">{fieldErrors.admin_password_confirm}</p>
                          )}
                        </div>
                      </div>
                      {!editingTenant && (
                        <div>
                          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
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
                              <span className="ml-2 text-sm text-gray-700 dark:text-gray-300">Email</span>
                            </label>
                            <label className="flex items-center">
                              <input
                                type="checkbox"
                                checked={formData.notify_whatsapp}
                                onChange={(e) => setFormData({ ...formData, notify_whatsapp: e.target.checked })}
                                className="rounded border-gray-300 text-blue-600 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                              />
                              <span className="ml-2 text-sm text-gray-700 dark:text-gray-300">WhatsApp</span>
                            </label>
                          </div>
                          <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                            Selecione pelo menos uma opção
                          </p>
                        </div>
                      )}
                      {editingTenant && (
                        <div className="bg-blue-50 dark:bg-blue-900/20 p-3 rounded-lg">
                          <p className="text-sm text-blue-700 dark:text-blue-200">
                            💡 <strong>Dica:</strong> Deixe os campos vazios para manter as informações atuais.
                            Para alterar apenas o email ou senha, preencha apenas os campos desejados.
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex-none bg-gray-50 dark:bg-gray-700/50 px-4 py-3 sm:flex sm:flex-row-reverse sm:px-6 gap-2 border-t border-gray-200 dark:border-gray-600">
                  <Button type="submit" disabled={isSubmitting}>
                    {isSubmitting ? (
                      <LoadingSpinner size="sm" className="mr-2" />
                    ) : (
                      <Check className="h-4 w-4 mr-2" />
                    )}
                    Salvar
                  </Button>
                  <Button type="button" variant="outline" onClick={handleCloseModal} disabled={isSubmitting}>
                    <X className="h-4 w-4 mr-2" />
                    Cancelar
                  </Button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* Modal de confirmação de exclusão */}
      {deletingTenant && (
        <div className="fixed inset-0 z-[60] overflow-y-auto">
          <div className="flex min-h-full items-end justify-center p-4 text-center sm:items-center sm:p-0">
            <div className="fixed inset-0 bg-gray-500 dark:bg-black/50 bg-opacity-75 transition-opacity" onClick={handleCancelDelete} />
            <div className="relative transform overflow-hidden rounded-lg bg-white dark:bg-gray-800 text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-md">
              <div className="bg-white dark:bg-gray-800 px-4 pb-4 pt-5 sm:p-6">
                <h3 className="text-lg font-medium leading-6 text-gray-900 dark:text-gray-100">
                  Excluir cliente?
                </h3>
                <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
                  Tem certeza que deseja excluir <strong>{deletingTenant.name}</strong>? Esta ação não pode ser desfeita.
                </p>
              </div>
              <div className="bg-gray-50 dark:bg-gray-700/50 px-4 py-3 sm:flex sm:flex-row-reverse sm:px-6 gap-2">
                <Button
                  type="button"
                  className="bg-red-600 hover:bg-red-700 text-white"
                  onClick={handleConfirmDelete}
                >
                  Excluir
                </Button>
                <Button type="button" variant="outline" onClick={handleCancelDelete}>
                  <X className="h-4 w-4 mr-2" />
                  Cancelar
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

