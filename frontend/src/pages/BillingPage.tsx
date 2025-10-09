import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import billingService, { BillingSummary, TenantProduct, Plan } from '../services/billing'
import { useAuthStore } from '../stores/authStore'
import { CreditCard, Calendar, CheckCircle, Package, Zap, Plus } from 'lucide-react'
import LoadingSpinner from '../components/ui/LoadingSpinner'

export default function BillingPage() {
  const [summary, setSummary] = useState<BillingSummary | null>(null)
  const [products, setProducts] = useState<TenantProduct[]>([])
  const [availablePlans, setAvailablePlans] = useState<Plan[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const { user } = useAuthStore()

  useEffect(() => {
    fetchBillingData()
  }, [])

  const fetchBillingData = async () => {
    try {
      setIsLoading(true)
      const [summaryData, productsData, plansData] = await Promise.all([
        billingService.getBillingSummary(),
        billingService.getTenantProducts(),
        billingService.getPlans()
      ])
      setSummary(summaryData)
      setProducts(productsData)
      setAvailablePlans(plansData)
    } catch (error) {
      console.error('Failed to fetch billing data:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleSelectPlan = async (planId: string) => {
    try {
      await billingService.selectPlan(planId)
      await fetchBillingData()
    } catch (error) {
      console.error('Failed to select plan:', error)
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
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Billing & Planos</h1>
        <p className="text-gray-600">
          Gerencie seu plano e produtos ativos
        </p>
      </div>

      {/* Resumo do Plano Atual */}
      {summary && (
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
                <p className="text-lg font-semibold">{summary.plan.name}</p>
              </div>
              <div>
                <p className="text-sm font-medium text-gray-500">Valor Mensal</p>
                <p className="text-lg font-semibold text-blue-600">
                  R$ {Number(summary.monthly_total || 0).toFixed(2)}
                </p>
              </div>
              <div>
                <p className="text-sm font-medium text-gray-500">Produtos Ativos</p>
                <p className="text-lg font-semibold">{summary.active_products_count}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Produtos Ativos */}
      {products && products.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold mb-4">Seus Produtos Ativos</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {products.map((tenantProduct) => (
              <Card key={tenantProduct.id}>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Package className="h-4 w-4" />
                    {tenantProduct.product.name}
                    {tenantProduct.is_addon && (
                      <span className="text-xs bg-purple-100 text-purple-800 px-2 py-0.5 rounded">
                        Add-on
                      </span>
                    )}
                  </CardTitle>
                  <CardDescription className="text-xs">
                    {tenantProduct.product.description}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {tenantProduct.is_addon && tenantProduct.addon_price && (
                    <p className="text-sm font-medium text-gray-700">
                      R$ {Number(tenantProduct.addon_price).toFixed(2)}/mês
                    </p>
                  )}
                  <p className="text-xs text-gray-500 mt-2">
                    Ativo desde {new Date(tenantProduct.activated_at).toLocaleDateString('pt-BR')}
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      )}

      {/* Planos Disponíveis */}
      {availablePlans && availablePlans.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold mb-4">Planos Disponíveis</h2>
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
            {availablePlans.map((plan) => {
              const isCurrentPlan = summary?.plan.name === plan.name
              
              return (
                <Card key={plan.id} className={isCurrentPlan ? 'ring-2 ring-blue-500' : ''}>
                  <CardHeader>
                    <CardTitle className="flex items-center justify-between">
                      <span>{plan.name}</span>
                      {isCurrentPlan && (
                        <span className="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded">
                          Atual
                        </span>
                      )}
                    </CardTitle>
                    <div className="text-3xl font-bold text-blue-600">
                      R$ {Number(plan.price || 0).toFixed(2)}
                      <span className="text-sm font-normal text-gray-500">/mês</span>
                    </div>
                    <CardDescription className="text-xs">
                      {plan.description}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2 mb-4">
                      <p className="text-sm font-medium text-gray-700">
                        {plan.product_count} produto(s) incluído(s)
                      </p>
                    </div>
                    
                    {!isCurrentPlan && user?.is_staff && (
                      <Button 
                        className="w-full" 
                        size="sm"
                        onClick={() => handleSelectPlan(plan.id)}
                      >
                        <Zap className="h-4 w-4 mr-2" />
                        Selecionar Plano
                      </Button>
                    )}
                  </CardContent>
                </Card>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
