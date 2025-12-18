/**
 * Página de Integração - Documentação da Billing API
 * Mostra configurações, exemplos e guias de uso
 */
import { useState } from 'react'
import { 
  Book, 
  Code, 
  Settings, 
  Key, 
  Send, 
  CheckCircle, 
  AlertCircle,
  Copy,
  ExternalLink,
  FileText,
  Zap
} from 'lucide-react'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { api } from '../lib/api'
import { showSuccessToast } from '../lib/toastHelper'

export default function IntegracaoPage() {
  const [activeTab, setActiveTab] = useState<'overview' | 'config' | 'examples' | 'api-keys'>('overview')

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
    showSuccessToast('Copiado para a área de transferência!')
  }

  const tabs = [
    { id: 'overview', label: 'Visão Geral', icon: Book },
    { id: 'config', label: 'Configuração', icon: Settings },
    { id: 'examples', label: 'Exemplos', icon: Code },
    { id: 'api-keys', label: 'API Keys', icon: Key },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
          🔌 Integração - Billing API
        </h1>
        <p className="mt-2 text-gray-600 dark:text-gray-400">
          Documentação completa para integração de cobranças via WhatsApp
        </p>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200 dark:border-gray-700">
        <nav className="-mb-px flex space-x-8">
          {tabs.map((tab) => {
            const Icon = tab.icon
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`
                  flex items-center gap-2 py-4 px-1 border-b-2 font-medium text-sm
                  ${activeTab === tab.id
                    ? 'border-brand-500 text-brand-600 dark:text-brand-400'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-300'
                  }
                `}
              >
                <Icon className="h-4 w-4" />
                {tab.label}
              </button>
            )
          })}
        </nav>
      </div>

      {/* Content */}
      <div className="mt-6">
        {activeTab === 'overview' && <OverviewTab />}
        {activeTab === 'config' && <ConfigTab copyToClipboard={copyToClipboard} />}
        {activeTab === 'examples' && <ExamplesTab copyToClipboard={copyToClipboard} />}
        {activeTab === 'api-keys' && <APIKeysTab />}
      </div>
    </div>
  )
}

function OverviewTab() {
  return (
    <div className="space-y-6">
      <Card>
        <div className="p-6">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
            O que é a Billing API?
          </h2>
          <p className="text-gray-600 dark:text-gray-400 mb-4">
            A Billing API permite que sistemas externos (ERP, CRM, sistemas de cobrança) 
            enviem automaticamente mensagens de cobrança e notificações via WhatsApp através 
            de endpoints REST simples e seguros.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-6">
            <div className="p-4 bg-brand-50 dark:bg-brand-900/20 rounded-lg">
              <Send className="h-8 w-8 text-brand-600 mb-2" />
              <h3 className="font-semibold text-gray-900 dark:text-white mb-1">
                Envio Automático
              </h3>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Envie cobranças atrasadas, avisos de vencimento e notificações
              </p>
            </div>

            <div className="p-4 bg-green-50 dark:bg-green-900/20 rounded-lg">
              <Zap className="h-8 w-8 text-green-600 mb-2" />
              <h3 className="font-semibold text-gray-900 dark:text-white mb-1">
                Processamento Assíncrono
              </h3>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Processamento em background com filas e retry automático
              </p>
            </div>

            <div className="p-4 bg-purple-50 dark:bg-purple-900/20 rounded-lg">
              <Settings className="h-8 w-8 text-purple-600 mb-2" />
              <h3 className="font-semibold text-gray-900 dark:text-white mb-1">
                Configurável
              </h3>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Horário comercial, throttling e templates personalizados
              </p>
            </div>
          </div>
        </div>
      </Card>

      <Card>
        <div className="p-6">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
            Tipos de Envio
          </h2>
          <div className="space-y-4">
            <div className="flex items-start gap-4 p-4 bg-red-50 dark:bg-red-900/20 rounded-lg">
              <AlertCircle className="h-6 w-6 text-red-600 mt-1" />
              <div>
                <h3 className="font-semibold text-gray-900 dark:text-white">
                  Cobrança Atrasada (Overdue)
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                  Para faturas que já venceram. Calcula automaticamente os dias de atraso.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-4 p-4 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg">
              <AlertCircle className="h-6 w-6 text-yellow-600 mt-1" />
              <div>
                <h3 className="font-semibold text-gray-900 dark:text-white">
                  Cobrança a Vencer (Upcoming)
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                  Para avisos de vencimento próximo. Calcula automaticamente os dias até o vencimento.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-4 p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
              <CheckCircle className="h-6 w-6 text-blue-600 mt-1" />
              <div>
                <h3 className="font-semibold text-gray-900 dark:text-white">
                  Notificação/Aviso (Notification)
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                  Para notificações gerais. Funciona 24/7, sem restrição de horário comercial.
                </p>
              </div>
            </div>
          </div>
        </div>
      </Card>
    </div>
  )
}

function ConfigTab({ copyToClipboard }: { copyToClipboard: (text: string) => void }) {
  const baseUrl = window.location.origin.replace(':5173', ':8000') // Ajusta para backend

  return (
    <div className="space-y-6">
      <Card>
        <div className="p-6">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
            Configuração Inicial
          </h2>

          <div className="space-y-6">
            <div>
              <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
                1. Habilitar API para o Tenant
              </h3>
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
                A API precisa estar habilitada no BillingConfig do tenant:
              </p>
              <div className="bg-gray-900 text-green-400 p-4 rounded-lg font-mono text-sm overflow-x-auto">
                <div className="flex items-center justify-between mb-2">
                  <span>Python (Django Shell)</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => copyToClipboard(`from apps.billing.billing_api import BillingConfig
from apps.tenancy.models import Tenant

tenant = Tenant.objects.get(name="Nome do Tenant")
config, _ = BillingConfig.objects.get_or_create(
    tenant=tenant,
    defaults={'api_enabled': True}
)
config.api_enabled = True
config.save()`)}
                  >
                    <Copy className="h-4 w-4" />
                  </Button>
                </div>
                <pre>{`from apps.billing.billing_api import BillingConfig
from apps.tenancy.models import Tenant

tenant = Tenant.objects.get(name="Nome do Tenant")
config, _ = BillingConfig.objects.get_or_create(
    tenant=tenant,
    defaults={'api_enabled': True}
)
config.api_enabled = True
config.save()`}</pre>
              </div>
            </div>

            <div>
              <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
                2. Criar API Key
              </h3>
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
                Gere uma API Key para autenticação:
              </p>
              <div className="bg-gray-900 text-green-400 p-4 rounded-lg font-mono text-sm overflow-x-auto">
                <div className="flex items-center justify-between mb-2">
                  <span>Python (Django Shell)</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => copyToClipboard(`from apps.billing.billing_api import BillingAPIKey
from apps.tenancy.models import Tenant

tenant = Tenant.objects.get(name="Nome do Tenant")
api_key = BillingAPIKey.objects.create(
    tenant=tenant,
    name="ERP Principal"
)
print(f"API Key: {api_key.key}")`)}
                  >
                    <Copy className="h-4 w-4" />
                  </Button>
                </div>
                <pre>{`from apps.billing.billing_api import BillingAPIKey
from apps.tenancy.models import Tenant

tenant = Tenant.objects.get(name="Nome do Tenant")
api_key = BillingAPIKey.objects.create(
    tenant=tenant,
    name="ERP Principal"
)
print(f"API Key: {api_key.key}")`}</pre>
              </div>
            </div>

            <div>
              <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
                3. Criar Template
              </h3>
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
                Crie um template de mensagem com variações:
              </p>
              <div className="bg-gray-900 text-green-400 p-4 rounded-lg font-mono text-sm overflow-x-auto">
                <div className="flex items-center justify-between mb-2">
                  <span>Python (Django Shell)</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => copyToClipboard(`from apps.billing.billing_api import BillingTemplate, BillingTemplateVariation
from apps.tenancy.models import Tenant

tenant = Tenant.objects.get(name="Nome do Tenant")
template = BillingTemplate.objects.create(
    tenant=tenant,
    name="Cobrança Atrasada Padrão",
    template_type='overdue'
)

BillingTemplateVariation.objects.create(
    template=template,
    name="Variação 1",
    template_text="Olá {{nome_cliente}}, sua fatura de {{valor}} está atrasada há {{dias_atraso}} dias.",
    order=1
)`)}
                  >
                    <Copy className="h-4 w-4" />
                  </Button>
                </div>
                <pre>{`from apps.billing.billing_api import BillingTemplate, BillingTemplateVariation
from apps.tenancy.models import Tenant

tenant = Tenant.objects.get(name="Nome do Tenant")
template = BillingTemplate.objects.create(
    tenant=tenant,
    name="Cobrança Atrasada Padrão",
    template_type='overdue'
)

BillingTemplateVariation.objects.create(
    template=template,
    name="Variação 1",
    template_text="Olá {{nome_cliente}}, sua fatura de {{valor}} está atrasada há {{dias_atraso}} dias.",
    order=1
)`}</pre>
              </div>
            </div>
          </div>
        </div>
      </Card>

      <Card>
        <div className="p-6">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
            Configurações Disponíveis
          </h2>
          <div className="space-y-3">
            <div className="flex items-start gap-3">
              <CheckCircle className="h-5 w-5 text-green-500 mt-0.5" />
              <div>
                <p className="font-medium text-gray-900 dark:text-white">Throttling</p>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Configure mensagens por minuto (padrão: 20/min)
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <CheckCircle className="h-5 w-5 text-green-500 mt-0.5" />
              <div>
                <p className="font-medium text-gray-900 dark:text-white">Horário Comercial</p>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Respeita horário comercial (pausa/retoma automático)
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <CheckCircle className="h-5 w-5 text-green-500 mt-0.5" />
              <div>
                <p className="font-medium text-gray-900 dark:text-white">Rate Limiting</p>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Limite de requisições por hora por API Key
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <CheckCircle className="h-5 w-5 text-green-500 mt-0.5" />
              <div>
                <p className="font-medium text-gray-900 dark:text-white">Retry Automático</p>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Retry automático em caso de falha temporária
                </p>
              </div>
            </div>
          </div>
        </div>
      </Card>
    </div>
  )
}

function ExamplesTab({ copyToClipboard }: { copyToClipboard: (text: string) => void }) {
  const baseUrl = window.location.origin.replace(':5173', ':8000')

  const examples = [
    {
      title: 'Cobrança Atrasada (Overdue)',
      description: 'Envia mensagem para fatura atrasada',
      method: 'POST',
      endpoint: '/api/billing/v1/billing/send/overdue',
      code: `curl -X POST ${baseUrl}/api/billing/v1/billing/send/overdue \\
  -H "X-Billing-API-Key: sua-api-key-aqui" \\
  -H "Content-Type: application/json" \\
  -d '{
    "template_type": "overdue",
    "contacts": [
      {
        "nome": "João Silva",
        "telefone": "+5511999999999",
        "valor": "R$ 150,00",
        "data_vencimento": "2025-01-15",
        "valor_total": "R$ 150,00"
      }
    ],
    "external_id": "fatura-12345"
  }'`
    },
    {
      title: 'Cobrança a Vencer (Upcoming)',
      description: 'Envia aviso de vencimento próximo',
      method: 'POST',
      endpoint: '/api/billing/v1/billing/send/upcoming',
      code: `curl -X POST ${baseUrl}/api/billing/v1/billing/send/upcoming \\
  -H "X-Billing-API-Key: sua-api-key-aqui" \\
  -H "Content-Type: application/json" \\
  -d '{
    "template_type": "upcoming",
    "contacts": [
      {
        "nome": "Maria Santos",
        "telefone": "+5511888888888",
        "valor": "R$ 200,00",
        "data_vencimento": "2025-01-25"
      }
    ],
    "external_id": "aviso-67890"
  }'`
    },
    {
      title: 'Notificação (Notification)',
      description: 'Envia notificação geral (24/7)',
      method: 'POST',
      endpoint: '/api/billing/v1/billing/send/notification',
      code: `curl -X POST ${baseUrl}/api/billing/v1/billing/send/notification \\
  -H "X-Billing-API-Key: sua-api-key-aqui" \\
  -H "Content-Type: application/json" \\
  -d '{
    "template_type": "notification",
    "contacts": [
      {
        "nome": "Pedro Costa",
        "telefone": "+5511777777777",
        "titulo": "Pagamento Confirmado",
        "mensagem": "Seu pagamento de R$ 150,00 foi confirmado com sucesso!"
      }
    ],
    "external_id": "notif-11111"
  }'`
    },
    {
      title: 'Consultar Status da Fila',
      description: 'Verifica o status de processamento',
      method: 'GET',
      endpoint: '/api/billing/v1/billing/queue/{queue_id}/status',
      code: `curl -X GET ${baseUrl}/api/billing/v1/billing/queue/{queue_id}/status \\
  -H "X-Billing-API-Key: sua-api-key-aqui"`
    },
    {
      title: 'Listar Contatos de Campanha',
      description: 'Lista todos os contatos de uma campanha',
      method: 'GET',
      endpoint: '/api/billing/v1/billing/campaign/{campaign_id}/contacts',
      code: `curl -X GET ${baseUrl}/api/billing/v1/billing/campaign/{campaign_id}/contacts?status=sent \\
  -H "X-Billing-API-Key: sua-api-key-aqui"`
    }
  ]

  return (
    <div className="space-y-6">
      {examples.map((example, idx) => (
        <Card key={idx}>
          <div className="p-6">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-1">
                  {example.title}
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  {example.description}
                </p>
              </div>
              <span className="px-2 py-1 text-xs font-medium rounded bg-brand-100 text-brand-700 dark:bg-brand-900 dark:text-brand-300">
                {example.method}
              </span>
            </div>

            <div className="mb-3">
              <p className="text-sm font-mono text-gray-600 dark:text-gray-400">
                {example.endpoint}
              </p>
            </div>

            <div className="bg-gray-900 text-green-400 p-4 rounded-lg font-mono text-sm overflow-x-auto">
              <div className="flex items-center justify-between mb-2">
                <span className="text-gray-400">cURL</span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => copyToClipboard(example.code)}
                >
                  <Copy className="h-4 w-4" />
                </Button>
              </div>
              <pre className="whitespace-pre-wrap">{example.code}</pre>
            </div>
          </div>
        </Card>
      ))}

      <Card>
        <div className="p-6">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            Exemplo em Python
          </h3>
          <div className="bg-gray-900 text-green-400 p-4 rounded-lg font-mono text-sm overflow-x-auto">
            <div className="flex items-center justify-between mb-2">
              <span>Python</span>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => copyToClipboard(`import requests

API_KEY = "sua-api-key-aqui"
BASE_URL = "${baseUrl}"

# Enviar cobrança atrasada
response = requests.post(
    f"{BASE_URL}/api/billing/v1/billing/send/overdue",
    headers={
        "X-Billing-API-Key": API_KEY,
        "Content-Type": "application/json"
    },
    json={
        "template_type": "overdue",
        "contacts": [
            {
                "nome": "João Silva",
                "telefone": "+5511999999999",
                "valor": "R$ 150,00",
                "data_vencimento": "2025-01-15"
            }
        ],
        "external_id": "fatura-12345"
    }
)

print(response.json())`)}
              >
                <Copy className="h-4 w-4" />
              </Button>
            </div>
            <pre>{`import requests

API_KEY = "sua-api-key-aqui"
BASE_URL = "${baseUrl}"

# Enviar cobrança atrasada
response = requests.post(
    f"{BASE_URL}/api/billing/v1/billing/send/overdue",
    headers={
        "X-Billing-API-Key": API_KEY,
        "Content-Type": "application/json"
    },
    json={
        "template_type": "overdue",
        "contacts": [
            {
                "nome": "João Silva",
                "telefone": "+5511999999999",
                "valor": "R$ 150,00",
                "data_vencimento": "2025-01-15"
            }
        ],
        "external_id": "fatura-12345"
    }
)

print(response.json())`}</pre>
          </div>
        </div>
      </Card>
    </div>
  )
}

function APIKeysTab() {
  return (
    <div className="space-y-6">
      <Card>
        <div className="p-6">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
            Gerenciar API Keys
          </h2>
          <p className="text-gray-600 dark:text-gray-400 mb-4">
            Acesse a página de API Keys para criar e gerenciar suas chaves de autenticação.
          </p>
          <Button onClick={() => window.location.href = '/billing-api/keys'}>
            <Key className="h-4 w-4 mr-2" />
            Ir para API Keys
          </Button>
        </div>
      </Card>

      <Card>
        <div className="p-6">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
            Segurança
          </h2>
          <div className="space-y-3">
            <div className="flex items-start gap-3">
              <AlertCircle className="h-5 w-5 text-yellow-500 mt-0.5" />
              <div>
                <p className="font-medium text-gray-900 dark:text-white">Mantenha sua API Key segura</p>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Nunca compartilhe sua API Key publicamente ou em repositórios Git
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <AlertCircle className="h-5 w-5 text-yellow-500 mt-0.5" />
              <div>
                <p className="font-medium text-gray-900 dark:text-white">Use variáveis de ambiente</p>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Armazene a API Key em variáveis de ambiente, nunca hardcoded
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <CheckCircle className="h-5 w-5 text-green-500 mt-0.5" />
              <div>
                <p className="font-medium text-gray-900 dark:text-white">IPs Permitidos</p>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Configure IPs permitidos para maior segurança
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <CheckCircle className="h-5 w-5 text-green-500 mt-0.5" />
              <div>
                <p className="font-medium text-gray-900 dark:text-white">Expiração</p>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Configure data de expiração para API Keys temporárias
                </p>
              </div>
            </div>
          </div>
        </div>
      </Card>
    </div>
  )
}

