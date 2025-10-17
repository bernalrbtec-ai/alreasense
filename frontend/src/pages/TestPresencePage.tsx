import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Label } from '../components/ui/Label'
import { api } from '../lib/api'
import { MessageSquare, Send } from 'lucide-react'

interface Instance {
  id: string
  friendly_name: string
  instance_name: string
  status: string
}

export default function TestPresencePage() {
  const [instances, setInstances] = useState<Instance[]>([])
  const [selectedInstance, setSelectedInstance] = useState('')
  const [phone, setPhone] = useState('+5517')
  const [typingSeconds, setTypingSeconds] = useState(3.0)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)

  useEffect(() => {
    fetchInstances()
  }, [])

  const fetchInstances = async () => {
    try {
      const response = await api.get('/campaigns/test-presence/instances/')
      if (response.data.success) {
        setInstances(response.data.instances)
        if (response.data.instances.length > 0) {
          setSelectedInstance(response.data.instances[0].id)
        }
      }
    } catch (error) {
      console.error('Erro ao buscar instâncias:', error)
    }
  }

  const handleTest = async () => {
    if (!selectedInstance || !phone) {
      alert('Preencha todos os campos!')
      return
    }

    setLoading(true)
    setResult(null)

    try {
      const response = await api.post('/campaigns/test-presence/', {
        instance_id: selectedInstance,
        phone: phone,
        typing_seconds: typingSeconds
      })

      setResult(response.data)
      console.log('📊 Resultado do teste:', response.data)
    } catch (error: any) {
      console.error('Erro ao testar presença:', error)
      setResult({
        success: false,
        error: error.response?.data?.error || error.message
      })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">🧪 Teste de Presença (Status Digitando)</h1>
        <p className="text-gray-600">Teste o envio de status "digitando" via Evolution API</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MessageSquare className="h-5 w-5" />
            Configurar Teste
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label htmlFor="instance">Instância WhatsApp</Label>
            <select
              id="instance"
              value={selectedInstance}
              onChange={(e) => setSelectedInstance(e.target.value)}
              className="w-full mt-1 px-3 py-2 border border-gray-300 rounded-md"
            >
              <option value="">Selecione uma instância</option>
              {instances.map((instance) => (
                <option key={instance.id} value={instance.id}>
                  {instance.friendly_name} ({instance.status})
                </option>
              ))}
            </select>
          </div>

          <div>
            <Label htmlFor="phone">Número de Telefone (com código país)</Label>
            <Input
              id="phone"
              type="text"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="+5517999999999"
            />
          </div>

          <div>
            <Label htmlFor="seconds">Tempo Digitando (segundos)</Label>
            <Input
              id="seconds"
              type="number"
              step="0.5"
              min="1"
              max="10"
              value={typingSeconds}
              onChange={(e) => setTypingSeconds(parseFloat(e.target.value))}
            />
          </div>

          <Button
            onClick={handleTest}
            disabled={loading}
            className="w-full"
          >
            <Send className="h-4 w-4 mr-2" />
            {loading ? 'Enviando...' : 'Enviar Status Digitando'}
          </Button>
        </CardContent>
      </Card>

      {result && (
        <Card>
          <CardHeader>
            <CardTitle className={result.success ? 'text-green-600' : 'text-red-600'}>
              {result.success ? '✅ Teste Realizado' : '❌ Erro no Teste'}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {result.success && (
                <>
                  {/* Request */}
                  <div>
                    <h3 className="font-semibold text-lg mb-2">📤 Request Enviado:</h3>
                    <div className="bg-gray-50 p-4 rounded-lg space-y-2">
                      <div>
                        <strong>URL:</strong>
                        <pre className="bg-white p-2 rounded mt-1 text-xs overflow-x-auto">
                          {result.request.url}
                        </pre>
                      </div>
                      <div>
                        <strong>Method:</strong> {result.request.method}
                      </div>
                      <div>
                        <strong>Headers:</strong>
                        <pre className="bg-white p-2 rounded mt-1 text-xs overflow-x-auto">
                          {JSON.stringify(result.request.headers, null, 2)}
                        </pre>
                      </div>
                      <div>
                        <strong>Body:</strong>
                        <pre className="bg-white p-2 rounded mt-1 text-xs overflow-x-auto">
                          {JSON.stringify(result.request.body, null, 2)}
                        </pre>
                      </div>
                    </div>
                  </div>

                  {/* Response */}
                  <div>
                    <h3 className="font-semibold text-lg mb-2">📥 Response Recebido:</h3>
                    <div className="bg-gray-50 p-4 rounded-lg space-y-2">
                      <div>
                        <strong>Status Code:</strong>
                        <span className={`ml-2 px-2 py-1 rounded ${
                          result.response.status_code === 200 || result.response.status_code === 201
                            ? 'bg-green-100 text-green-800'
                            : 'bg-red-100 text-red-800'
                        }`}>
                          {result.response.status_code}
                        </span>
                      </div>
                      <div>
                        <strong>Response Headers:</strong>
                        <pre className="bg-white p-2 rounded mt-1 text-xs overflow-x-auto">
                          {JSON.stringify(result.response.headers, null, 2)}
                        </pre>
                      </div>
                      <div>
                        <strong>Response Body:</strong>
                        <pre className="bg-white p-2 rounded mt-1 text-xs overflow-x-auto">
                          {result.response.body_json
                            ? JSON.stringify(result.response.body_json, null, 2)
                            : result.response.body}
                        </pre>
                      </div>
                    </div>
                  </div>
                </>
              )}

              {!result.success && (
                <div className="bg-red-50 p-4 rounded-lg">
                  <strong>Erro:</strong>
                  <pre className="mt-2 text-xs overflow-x-auto">
                    {result.error}
                  </pre>
                  {result.traceback && (
                    <>
                      <strong className="block mt-4">Traceback:</strong>
                      <pre className="mt-2 text-xs overflow-x-auto">
                        {result.traceback}
                      </pre>
                    </>
                  )}
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      <Card className="bg-blue-50">
        <CardContent className="pt-6">
          <h3 className="font-semibold mb-2">ℹ️ Como usar:</h3>
          <ol className="list-decimal list-inside space-y-1 text-sm">
            <li>Selecione uma instância WhatsApp ativa</li>
            <li>Digite o número completo com código do país (ex: +5517999999999)</li>
            <li>Escolha quantos segundos o status "digitando" deve aparecer</li>
            <li>Clique em "Enviar Status Digitando"</li>
            <li>Verifique no WhatsApp do destinatário se apareceu "digitando..."</li>
            <li>Veja os logs completos abaixo (request e response)</li>
          </ol>
        </CardContent>
      </Card>
    </div>
  )
}

