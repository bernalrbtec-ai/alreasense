import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { api } from '../lib/api'
import { useAuthStore } from '../stores/authStore'
import { formatCurrency, formatDate } from '../lib/utils'
import { CreditCard, Calendar, CheckCircle, AlertCircle, ExternalLink } from 'lucide-react'

interface BillingInfo {
  current_plan: string
  plan_limits: {
    connections: number
    retention_days: number
    price: number
  }
  next_billing_date: string
  status: string
  has_payment_method: boolean
  current_period_end: string | null
}

export default function BillingPage() {
  const [billingInfo, setBillingInfo] = useState<BillingInfo | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const { user } = useAuthStore()

  useEffect(() => {
    fetchBillingInfo()
  }, [])

  const fetchBillingInfo = async () => {
    try {
      setIsLoading(true)
      const response = await api.get('/billing/info/')
      setBillingInfo(response.data)
    } catch (error) {
      console.error('Failed to fetch billing info:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleUpgrade = async (plan: string) => {
    try {
      const response = await api.post('/billing/checkout/', { plan })
      // Redirect to Stripe checkout
      window.location.href = response.data.checkout_url
    } catch (error) {
      console.error('Failed to create checkout session:', error)
    }
  }

  const handleManageBilling = async () => {
    try {
      const response = await api.post('/billing/portal/')
      // Redirect to Stripe customer portal
      window.location.href = response.data.portal_url
    } catch (error) {
      console.error('Failed to create portal session:', error)
    }
  }

  const plans = [
    {
      name: 'Starter',
      id: 'starter',
      price: 199,
      connections: 1,
      retention: '30 dias',
      features: ['1 conexão WhatsApp', 'Retenção de 30 dias', 'Suporte por email']
    },
    {
      name: 'Pro',
      id: 'pro',
      price: 499,
      connections: 3,
      retention: '180 dias',
      features: ['3 conexões WhatsApp', 'Retenção de 180 dias', 'Suporte prioritário', 'Relatórios avançados']
    },
    {
      name: 'Scale',
      id: 'scale',
      price: 999,
      connections: 6,
      retention: '365 dias',
      features: ['6 conexões WhatsApp', 'Retenção de 1 ano', 'Suporte dedicado', 'API personalizada']
    },
    {
      name: 'Enterprise',
      id: 'enterprise',
      price: 0,
      connections: 'Ilimitado',
      retention: '2 anos',
      features: ['Conexões ilimitadas', 'Retenção de 2 anos', 'Suporte 24/7', 'SLA garantido', 'Customizações']
    }
  ]

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  if (!billingInfo) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">Não foi possível carregar as informações de billing</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Billing</h1>
        <p className="text-gray-600">
          Gerencie seu plano e informações de pagamento
        </p>
      </div>

      {/* Current Plan */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CreditCard className="h-5 w-5" />
            Plano Atual
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div>
              <p className="text-sm font-medium text-gray-500">Plano</p>
              <p className="text-lg font-semibold capitalize">{billingInfo.current_plan}</p>
            </div>
            <div>
              <p className="text-sm font-medium text-gray-500">Próxima Cobrança</p>
              <p className="text-lg font-semibold">
                {billingInfo.next_billing_date ? formatDate(billingInfo.next_billing_date) : 'N/A'}
              </p>
            </div>
            <div>
              <p className="text-sm font-medium text-gray-500">Status</p>
              <div className="flex items-center gap-2">
                {billingInfo.status === 'active' ? (
                  <CheckCircle className="h-5 w-5 text-green-600" />
                ) : (
                  <AlertCircle className="h-5 w-5 text-red-600" />
                )}
                <span className="text-lg font-semibold capitalize">{billingInfo.status}</span>
              </div>
            </div>
          </div>

          <div className="mt-4 pt-4 border-t">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">
                  Método de pagamento {billingInfo.has_payment_method ? 'configurado' : 'não configurado'}
                </p>
              </div>
              <Button variant="outline" onClick={handleManageBilling}>
                <ExternalLink className="h-4 w-4 mr-2" />
                Gerenciar Pagamento
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Plan Limits */}
      <Card>
        <CardHeader>
          <CardTitle>Limites do Plano</CardTitle>
          <CardDescription>
            Recursos disponíveis no seu plano atual
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="text-center p-4 bg-gray-50 rounded-lg">
              <p className="text-2xl font-bold text-blue-600">
                {billingInfo.plan_limits.connections === -1 ? '∞' : billingInfo.plan_limits.connections}
              </p>
              <p className="text-sm text-gray-600">Conexões WhatsApp</p>
            </div>
            <div className="text-center p-4 bg-gray-50 rounded-lg">
              <p className="text-2xl font-bold text-green-600">
                {billingInfo.plan_limits.retention_days}
              </p>
              <p className="text-sm text-gray-600">Dias de Retenção</p>
            </div>
            <div className="text-center p-4 bg-gray-50 rounded-lg">
              <p className="text-2xl font-bold text-purple-600">
                {formatCurrency(billingInfo.plan_limits.price)}
              </p>
              <p className="text-sm text-gray-600">Por Mês</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Available Plans */}
      <div>
        <h2 className="text-lg font-semibold mb-4">Planos Disponíveis</h2>
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {plans.map((plan) => {
            const isCurrentPlan = plan.id === billingInfo.current_plan
            const isEnterprise = plan.id === 'enterprise'
            
            return (
              <Card key={plan.id} className={isCurrentPlan ? 'ring-2 ring-blue-500' : ''}>
                <CardHeader>
                  <CardTitle className="flex items-center justify-between">
                    {plan.name}
                    {isCurrentPlan && (
                      <span className="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded">
                        Atual
                      </span>
                    )}
                  </CardTitle>
                  <div className="text-3xl font-bold">
                    {isEnterprise ? 'Sob consulta' : formatCurrency(plan.price)}
                    {!isEnterprise && <span className="text-sm font-normal text-gray-500">/mês</span>}
                  </div>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-2 mb-4">
                    <li className="flex items-center text-sm">
                      <CheckCircle className="h-4 w-4 text-green-600 mr-2" />
                      {plan.connections} conexões WhatsApp
                    </li>
                    <li className="flex items-center text-sm">
                      <CheckCircle className="h-4 w-4 text-green-600 mr-2" />
                      Retenção de {plan.retention}
                    </li>
                    {plan.features.slice(2).map((feature, index) => (
                      <li key={index} className="flex items-center text-sm">
                        <CheckCircle className="h-4 w-4 text-green-600 mr-2" />
                        {feature}
                      </li>
                    ))}
                  </ul>
                  
                  {!isCurrentPlan && (
                    <Button 
                      className="w-full" 
                      variant={isEnterprise ? "outline" : "default"}
                      onClick={() => handleUpgrade(plan.id)}
                    >
                      {isEnterprise ? 'Contatar Vendas' : 'Fazer Upgrade'}
                    </Button>
                  )}
                </CardContent>
              </Card>
            )
          })}
        </div>
      </div>
    </div>
  )
}
