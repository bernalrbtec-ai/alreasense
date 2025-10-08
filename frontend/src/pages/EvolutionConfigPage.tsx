import { useState, useEffect } from 'react'
import { Save, TestTube, Check, X, AlertCircle } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import { api } from '../lib/api'

interface EvolutionConfig {
  base_url: string
  api_key: string
  webhook_url: string
  is_active: boolean
  last_check?: string
  status?: 'online' | 'offline' | 'error'
}

export default function EvolutionConfigPage() {
  const [config, setConfig] = useState<EvolutionConfig>({
    base_url: '',
    api_key: '',
    webhook_url: '',
    is_active: true,
  })
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [isTesting, setIsTesting] = useState(false)
  const [testResult, setTestResult] = useState<{
    success: boolean
    message: string
  } | null>(null)

  useEffect(() => {
    fetchConfig()
  }, [])

  const fetchConfig = async () => {
    try {
      setIsLoading(true)
      // TODO: Criar endpoint de configuração no backend
      // const response = await api.get('/admin/evolution-config/')
      // setConfig(response.data)
      
      // Mock data for now
      setConfig({
        base_url: 'https://evo.rbtec.com.br',
        api_key: '584B4A4A-0815-AC86-DC39-C38FC27E8E17',
        webhook_url: `${window.location.origin}/api/webhooks/evolution/`,
        is_active: true,
        last_check: new Date().toISOString(),
        status: 'online',
      })
    } catch (error) {
      console.error('Error fetching config:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      setIsSaving(true)
      // TODO: Implementar no backend
      // await api.post('/admin/evolution-config/', config)
      
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 1000))
      
      alert('Configuração salva com sucesso!')
    } catch (error) {
      console.error('Error saving config:', error)
      alert('Erro ao salvar configuração')
    } finally {
      setIsSaving(false)
    }
  }

  const handleTest = async () => {
    try {
      setIsTesting(true)
      setTestResult(null)
      
      // TODO: Implementar no backend
      // const response = await api.post('/admin/evolution-config/test/', config)
      
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 2000))
      
      setTestResult({
        success: true,
        message: 'Conexão com Evolution API estabelecida com sucesso!',
      })
    } catch (error) {
      setTestResult({
        success: false,
        message: 'Falha ao conectar com Evolution API. Verifique as credenciais.',
      })
    } finally {
      setIsTesting(false)
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
        <h1 className="text-2xl font-bold text-gray-900">Configuração Evolution API</h1>
        <p className="mt-1 text-sm text-gray-500">
          Configure a integração com o servidor Evolution API para ingestion de mensagens do WhatsApp
        </p>
      </div>

      {/* Status Card */}
      <Card className="p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`h-3 w-3 rounded-full ${
              config.status === 'online' ? 'bg-green-500' : 
              config.status === 'offline' ? 'bg-gray-400' : 
              'bg-red-500'
            }`} />
            <div>
              <h3 className="text-lg font-semibold text-gray-900">
                Status: {
                  config.status === 'online' ? 'Online' : 
                  config.status === 'offline' ? 'Offline' : 
                  'Erro'
                }
              </h3>
              {config.last_check && (
                <p className="text-sm text-gray-500">
                  Última verificação: {new Date(config.last_check).toLocaleString()}
                </p>
              )}
            </div>
          </div>
          <Button onClick={handleTest} disabled={isTesting}>
            <TestTube className={`h-4 w-4 mr-2 ${isTesting ? 'animate-pulse' : ''}`} />
            {isTesting ? 'Testando...' : 'Testar Conexão'}
          </Button>
        </div>
        
        {testResult && (
          <div className={`mt-4 p-4 rounded-md ${
            testResult.success ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'
          }`}>
            <div className="flex items-start gap-2">
              {testResult.success ? (
                <Check className="h-5 w-5 text-green-600 flex-shrink-0 mt-0.5" />
              ) : (
                <X className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
              )}
              <p className={`text-sm ${testResult.success ? 'text-green-800' : 'text-red-800'}`}>
                {testResult.message}
              </p>
            </div>
          </div>
        )}
      </Card>

      {/* Configuration Form */}
      <Card className="p-6">
        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label htmlFor="base_url" className="block text-sm font-medium text-gray-700">
              URL Base da Evolution API
            </label>
            <input
              type="url"
              id="base_url"
              required
              value={config.base_url}
              onChange={(e) => setConfig({ ...config, base_url: e.target.value })}
              placeholder="https://evo.rbtec.com.br"
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
            />
            <p className="mt-1 text-sm text-gray-500">
              URL do servidor Evolution API (sem trailing slash)
            </p>
          </div>

          <div>
            <label htmlFor="api_key" className="block text-sm font-medium text-gray-700">
              API Key
            </label>
            <input
              type="password"
              id="api_key"
              required
              value={config.api_key}
              onChange={(e) => setConfig({ ...config, api_key: e.target.value })}
              placeholder="Sua API Key"
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
            />
            <p className="mt-1 text-sm text-gray-500">
              Token de autenticação fornecido pela Evolution API
            </p>
          </div>

          <div>
            <label htmlFor="webhook_url" className="block text-sm font-medium text-gray-700">
              Webhook URL
            </label>
            <input
              type="url"
              id="webhook_url"
              readOnly
              value={config.webhook_url}
              className="mt-1 block w-full rounded-md border-gray-300 bg-gray-50 shadow-sm sm:text-sm"
            />
            <p className="mt-1 text-sm text-gray-500">
              Configure esta URL no servidor Evolution API para receber eventos
            </p>
          </div>

          <div className="flex items-center">
            <input
              type="checkbox"
              id="is_active"
              checked={config.is_active}
              onChange={(e) => setConfig({ ...config, is_active: e.target.checked })}
              className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
            />
            <label htmlFor="is_active" className="ml-2 block text-sm text-gray-900">
              Habilitar integração com Evolution API
            </label>
          </div>

          <div className="bg-blue-50 border border-blue-200 rounded-md p-4">
            <div className="flex items-start gap-2">
              <AlertCircle className="h-5 w-5 text-blue-600 flex-shrink-0 mt-0.5" />
              <div className="text-sm text-blue-800">
                <p className="font-medium mb-1">Instruções de configuração:</p>
                <ol className="list-decimal list-inside space-y-1 ml-2">
                  <li>Instale e configure seu servidor Evolution API</li>
                  <li>Obtenha a API Key do painel de administração</li>
                  <li>Configure o webhook URL no Evolution API apontando para esta plataforma</li>
                  <li>Teste a conexão antes de salvar</li>
                  <li>Certifique-se de que o firewall permite conexões do Evolution API</li>
                </ol>
              </div>
            </div>
          </div>

          <div className="flex justify-end gap-3">
            <Button type="button" variant="outline" onClick={fetchConfig}>
              Cancelar
            </Button>
            <Button type="submit" disabled={isSaving}>
              <Save className={`h-4 w-4 mr-2 ${isSaving ? 'animate-pulse' : ''}`} />
              {isSaving ? 'Salvando...' : 'Salvar Configuração'}
            </Button>
          </div>
        </form>
      </Card>

      {/* Documentation Links */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Recursos Úteis</h3>
        <div className="space-y-2 text-sm text-gray-600">
          <p>
            <a 
              href="https://github.com/EvolutionAPI/evolution-api" 
              target="_blank" 
              rel="noopener noreferrer"
              className="text-blue-600 hover:text-blue-700 hover:underline"
            >
              📚 Documentação oficial da Evolution API
            </a>
          </p>
          <p>
            <a 
              href="https://doc.evolution-api.com/" 
              target="_blank" 
              rel="noopener noreferrer"
              className="text-blue-600 hover:text-blue-700 hover:underline"
            >
              🚀 Guia de início rápido
            </a>
          </p>
          <p>
            <a 
              href="https://doc.evolution-api.com/v2/pt/integrations/webhook" 
              target="_blank" 
              rel="noopener noreferrer"
              className="text-blue-600 hover:text-blue-700 hover:underline"
            >
              🔗 Configuração de Webhooks
            </a>
          </p>
        </div>
      </Card>
    </div>
  )
}

