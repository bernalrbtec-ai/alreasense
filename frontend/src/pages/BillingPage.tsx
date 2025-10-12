import { useState, useEffect } from 'react'
import { Card } from '../components/ui/Card'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import { api } from '../lib/api'
import { useAuthStore } from '../stores/authStore'
import { 
  CreditCard, 
  Package, 
  Check, 
  Server,
  Users,
  MessageSquare,
  FlaskConical,
  Crown
} from 'lucide-react'

interface PlanProduct {
  product: {
    id: string
    slug: string
    name: string
    icon: string
    description: string
  }
  limit_value: number
  limit_unit: string
  is_included: boolean
}

interface Plan {
  id: string
  slug: string
  name: string
  description: string
  price: number
  products: PlanProduct[]
}

interface Tenant {
  id: string
  name: string
  current_plan?: Plan
  monthly_total: number
  status: string
}

export default function BillingPage() {
  const [tenant, setTenant] = useState<Tenant | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const { user } = useAuthStore()

  useEffect(() => {
    fetchTenantData()
  }, [])

  const fetchTenantData = async () => {
    try {
      setIsLoading(true)
      const response = await api.get('/tenants/tenants/current/')
      setTenant(response.data)
    } catch (error) {
      console.error('Error fetching tenant data:', error)
    } finally {
      setIsLoading(false)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  const getProductIcon = (slug: string) => {
    const icons: Record<string, any> = {
      flow: MessageSquare,
      sense: FlaskConical,
      api_public: Server,
      contacts: Users,
    }
    return icons[slug] || Package
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <CreditCard className="h-6 w-6" /> Meu Plano
        </h1>
        <p className="mt-1 text-sm text-gray-500">
          Confira os detalhes do seu plano atual e recursos disponíveis
        </p>
      </div>

      {tenant && tenant.current_plan ? (
        <>
          {/* Card do Plano Atual */}
          <Card className="overflow-hidden">
            <div className="bg-gradient-to-r from-blue-600 to-blue-700 p-6 text-white">
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <Crown className="h-5 w-5" />
                    <h2 className="text-2xl font-bold">{tenant.current_plan.name}</h2>
                  </div>
                  <p className="text-blue-100">{tenant.current_plan.description}</p>
                </div>
                <div className="text-right">
                  <div className="text-3xl font-bold">
                    R$ {Number(tenant.monthly_total || 0).toFixed(2)}<span className="text-lg">/mês</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="p-6">
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Package className="h-5 w-5 text-blue-600" />
                Produtos e Recursos Incluídos
              </h3>

              {tenant.current_plan.products && tenant.current_plan.products.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {tenant.current_plan.products.map((planProduct) => {
                    const IconComponent = getProductIcon(planProduct.product.slug)
                    
                    return (
                      <div
                        key={planProduct.product.id}
                        className="border border-gray-200 rounded-lg p-4 hover:border-blue-300 transition-colors"
                      >
                        <div className="flex items-start gap-3">
                          <div className="p-2 bg-blue-50 rounded-lg">
                            <IconComponent className="h-5 w-5 text-blue-600" />
                          </div>
                          <div className="flex-1">
                            <h4 className="font-semibold text-gray-900">
                              {planProduct.product.name}
                            </h4>
                            <p className="text-sm text-gray-600 mt-1">
                              {planProduct.product.description}
                            </p>
                            
                            {/* Limites */}
                            <div className="mt-3 space-y-1">
                              {/* Limite de Instâncias (sempre mostrar) */}
                              <div className="flex items-center gap-2 text-sm">
                                <Check className="h-4 w-4 text-green-600" />
                                <span className="text-gray-700">
                                  <strong>{planProduct.limit_value || 0}</strong> {planProduct.limit_unit || 'instâncias'}
                                </span>
                              </div>

                              {/* Limites específicos por produto */}
                              {planProduct.product.slug === 'flow' && (
                                <>
                                  <div className="flex items-center gap-2 text-sm">
                                    <Check className="h-4 w-4 text-green-600" />
                                    <span className="text-gray-700">Campanhas ilimitadas</span>
                                  </div>
                                  <div className="flex items-center gap-2 text-sm">
                                    <Check className="h-4 w-4 text-green-600" />
                                    <span className="text-gray-700">Contatos ilimitados</span>
                                  </div>
                                </>
                              )}

                              {planProduct.product.slug === 'sense' && (
                                <>
                                  <div className="flex items-center gap-2 text-sm">
                                    <Check className="h-4 w-4 text-green-600" />
                                    <span className="text-gray-700">Análise de sentimento</span>
                                  </div>
                                  <div className="flex items-center gap-2 text-sm">
                                    <Check className="h-4 w-4 text-green-600" />
                                    <span className="text-gray-700">Relatórios avançados</span>
                                  </div>
                                </>
                              )}

                              {planProduct.product.slug === 'api_public' && (
                                <>
                                  <div className="flex items-center gap-2 text-sm">
                                    <Check className="h-4 w-4 text-green-600" />
                                    <span className="text-gray-700">API REST completa</span>
                                  </div>
                                  <div className="flex items-center gap-2 text-sm">
                                    <Check className="h-4 w-4 text-green-600" />
                                    <span className="text-gray-700">Documentação Swagger</span>
                                  </div>
                                </>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              ) : (
                <div className="text-center py-8 text-gray-500">
                  <Package className="h-12 w-12 mx-auto mb-2 text-gray-400" />
                  <p>Nenhum produto incluído neste plano</p>
                </div>
              )}
            </div>
          </Card>

          {/* Informações Adicionais */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Status da Conta */}
            <Card className="p-6">
              <h3 className="text-lg font-semibold mb-4">Status da Conta</h3>
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-gray-600">Status</span>
                  <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                    tenant.status === 'active' 
                      ? 'bg-green-100 text-green-700'
                      : tenant.status === 'trial'
                      ? 'bg-blue-100 text-blue-700'
                      : 'bg-red-100 text-red-700'
                  }`}>
                    {tenant.status === 'active' && 'Ativo'}
                    {tenant.status === 'trial' && 'Trial'}
                    {tenant.status === 'suspended' && 'Suspenso'}
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-600">Empresa</span>
                  <span className="font-medium">{tenant.name}</span>
                </div>
              </div>
            </Card>

            {/* Próximas Ações */}
            <Card className="p-6">
              <h3 className="text-lg font-semibold mb-4">Precisa de Mais?</h3>
              <div className="space-y-3">
                <p className="text-sm text-gray-600">
                  Se você precisa de mais instâncias ou recursos, entre em contato com nosso time.
                </p>
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-sm text-gray-700">
                    <Check className="h-4 w-4 text-green-600" />
                    <span>Upgrade de plano disponível</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-gray-700">
                    <Check className="h-4 w-4 text-green-600" />
                    <span>Add-ons de instâncias extras</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-gray-700">
                    <Check className="h-4 w-4 text-green-600" />
                    <span>Suporte dedicado</span>
                  </div>
                </div>
              </div>
            </Card>
          </div>
        </>
      ) : (
        <Card className="p-8 text-center">
          <CreditCard className="h-16 w-16 mx-auto mb-4 text-gray-400" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            Nenhum plano ativo
          </h3>
          <p className="text-gray-600">
            Entre em contato com o administrador para ativar um plano
          </p>
        </Card>
      )}
    </div>
  )
}
