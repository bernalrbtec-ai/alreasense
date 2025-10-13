import { useState, useEffect } from 'react'
import { Save, TestTube, Check, X, AlertCircle } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import Toast from '../components/ui/Toast'
import { useToast } from '../hooks/useToast'
import { api } from '../lib/api'

interface EvolutionConfig {
  base_url: string
  api_key: string
  webhook_url: string
  is_active: boolean
  last_check?: string
  status?: 'active' | 'inactive' | 'error'
  last_error?: string | null
  instance_count?: number
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
  const { toast, showToast, hideToast } = useToast()
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
      const response = await api.get('/connections/evolution/config/')
      setConfig(response.data)
    } catch (error) {
      console.error('Error fetching config:', error)
      // Fallback to default values if API fails
      setConfig({
        base_url: 'https://evo.rbtec.com.br',
        api_key: '', // ✅ Empty API key - user must enter their own
        webhook_url: `${window.location.origin}/api/webhooks/evolution/`,
        is_active: true,
        last_check: undefined,
        status: 'inactive',
        last_error: 'Não foi possível carregar configuração',
        instance_count: 0,
      })
    } finally {
      setIsLoading(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      setIsSaving(true)
      console.log('🔧 Salvando configuração:', {
        base_url: config.base_url,
        api_key: config.api_key ? `${config.api_key.substring(0, 4)}...` : 'empty',
        is_active: config.is_active
      })
      const response = await api.post('/connections/evolution/config/', config)
      console.log('✅ Configuração salva:', response.data)
      setConfig(response.data)
      showToast('Configuração salva com sucesso!', 'success')
    } catch (error) {
      console.error('❌ Erro ao salvar configuração:', error)
      showToast('Erro ao salvar configuração', 'error')
    } finally {
      setIsSaving(false)
    }
  }

  const handleTest = async () => {
    try {
      setIsTesting(true)
      setTestResult(null)
      
      const response = await api.post('/connections/evolution/test/', {
        base_url: config.base_url,
        api_key: config.api_key,
      })
      
      if (response.data.success) {
        setTestResult({
          success: true,
          message: response.data.message,
        })
        // Update config with the response data
        setConfig(response.data.config)
      } else {
        setTestResult({
          success: false,
          message: response.data.message,
        })
      }
    } catch (error) {
      console.error('Error testing connection:', error)
      setTestResult({
        success: false,
        message: error.response?.data?.message || 'Falha ao conectar com Evolution API. Verifique as credenciais.',
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
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Servidor de Instância</h1>
        <p className="mt-1 text-sm text-gray-500">
          Configure a integração com o servidor Evolution API para ingestion de mensagens do WhatsApp
        </p>
      </div>

      {/* Status Card */}
      <Card className="p-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className={`h-4 w-4 rounded-full animate-pulse ${
              config.status === 'active' ? 'bg-green-500' : 
              config.status === 'inactive' ? 'bg-gray-400' : 
              'bg-red-500'
            }`} />
            <div>
              <h3 className="text-lg font-semibold text-gray-900">
                {config.status === 'active' ? '🟢 Conectado' : 
                 config.status === 'inactive' ? '⚪ Desconectado' : 
                 '🔴 Erro de Conexão'}
              </h3>
              {config.last_check && (
                <p className="text-sm text-gray-500">
                  Verificado em: {new Date(config.last_check).toLocaleString('pt-BR')}
                </p>
              )}
            </div>
          </div>
          <Button onClick={handleTest} disabled={isTesting} variant="outline">
            <TestTube className={`h-4 w-4 mr-2 ${isTesting ? 'animate-spin' : ''}`} />
            {isTesting ? 'Testando...' : 'Testar Novamente'}
          </Button>
        </div>

        {/* Connection Info */}
        {config.status === 'active' && config.instance_count !== undefined && (
          <div className="bg-green-50 border border-green-200 rounded-md p-4">
            <div className="flex items-center gap-2">
              <Check className="h-5 w-5 text-green-600" />
              <p className="text-sm text-green-800 font-medium">
                Conexão estabelecida com sucesso! 
                {config.instance_count > 0 && (
                  <span className="ml-1">
                    {config.instance_count} instância{config.instance_count !== 1 ? 's' : ''} encontrada{config.instance_count !== 1 ? 's' : ''}.
                  </span>
                )}
              </p>
            </div>
          </div>
        )}

        {/* Error Info */}
        {config.status === 'error' && config.last_error && (
          <div className="bg-red-50 border border-red-200 rounded-md p-4">
            <div className="flex items-start gap-2">
              <X className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm text-red-800 font-medium">Falha na conexão</p>
                <p className="text-sm text-red-700 mt-1">{config.last_error}</p>
              </div>
            </div>
          </div>
        )}
        
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
      <Card className="p-4">
        <form onSubmit={handleSubmit} className="space-y-4">
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

          <div className="flex justify-end gap-3 pt-2">
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

      {/* Toast Notification */}
      <Toast
        show={toast.show}
        message={toast.message}
        type={toast.type}
        onClose={hideToast}
      />
    </div>
  )
}

