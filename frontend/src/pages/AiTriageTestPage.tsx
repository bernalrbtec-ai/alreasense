import { useEffect, useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { api } from '../lib/api'
import { formatDate } from '../lib/utils'

interface TriageHistoryItem {
  id: number
  conversation_id: string | null
  message_id: string | null
  action: string
  model_name: string
  prompt_version: string
  latency_ms: number | null
  status: string
  result: Record<string, unknown>
  created_at: string
}

export default function AiTriageTestPage() {
  const [message, setMessage] = useState('')
  const [prompt, setPrompt] = useState('')
  const [contextJson, setContextJson] = useState('{"company_info":{}}')
  const [response, setResponse] = useState<Record<string, unknown> | null>(null)
  const [history, setHistory] = useState<TriageHistoryItem[]>([])
  const [error, setError] = useState<string | null>(null)
  const [isRunning, setIsRunning] = useState(false)
  const [audioFile, setAudioFile] = useState<File | null>(null)
  const [transcriptionResponse, setTranscriptionResponse] = useState<Record<string, unknown> | null>(null)
  const [transcriptionError, setTranscriptionError] = useState<string | null>(null)
  const [isTranscribing, setIsTranscribing] = useState(false)

  const loadHistory = async () => {
    try {
      const res = await api.get('/ai/triage/history/?limit=20')
      setHistory(res.data.results || [])
    } catch (err) {
      console.error('Failed to load triage history', err)
    }
  }

  useEffect(() => {
    loadHistory()
  }, [])

  const runTest = async () => {
    setError(null)
    setResponse(null)

    let parsedContext: Record<string, unknown> = {}
    try {
      parsedContext = contextJson ? JSON.parse(contextJson) : {}
    } catch {
      setError('Contexto JSON invalido.')
      return
    }

    if (!message.trim()) {
      setError('Mensagem e obrigatoria.')
      return
    }

    try {
      setIsRunning(true)
      const res = await api.post('/ai/triage/test/', {
        message,
        prompt,
        context: parsedContext,
      })
      setResponse(res.data)
      await loadHistory()
    } catch (err) {
      console.error('Failed to run triage test', err)
      setError('Falha ao executar o teste.')
    } finally {
      setIsRunning(false)
    }
  }

  const runTranscriptionTest = async () => {
    setTranscriptionError(null)
    setTranscriptionResponse(null)

    if (!audioFile) {
      setTranscriptionError('Selecione um arquivo de audio.')
      return
    }

    try {
      setIsTranscribing(true)
      const formData = new FormData()
      formData.append('file', audioFile)
      const res = await api.post('/ai/transcribe/test/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setTranscriptionResponse(res.data)
      setAudioFile(null)
    } catch (err) {
      console.error('Failed to run transcription test', err)
      setTranscriptionError('Falha ao executar a transcricao.')
    } finally {
      setIsTranscribing(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">IA Triagem</h1>
        <p className="text-gray-600">
          Teste de prompt e historico de triagem
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Teste de Prompt</CardTitle>
          <CardDescription>
            Envie uma mensagem e um prompt opcional para validar a resposta da IA.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">Mensagem</label>
            <textarea
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              className="mt-1 w-full rounded-md border border-gray-300 p-2 text-sm"
              rows={4}
              placeholder="Digite a mensagem do cliente..."
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Prompt (opcional)</label>
            <textarea
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              className="mt-1 w-full rounded-md border border-gray-300 p-2 text-sm"
              rows={4}
              placeholder="Cole o prompt aqui (opcional)..."
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700">Contexto (JSON)</label>
            <textarea
              value={contextJson}
              onChange={(event) => setContextJson(event.target.value)}
              className="mt-1 w-full rounded-md border border-gray-300 p-2 text-sm font-mono"
              rows={4}
            />
          </div>
          {error && (
            <div className="text-sm text-red-600">{error}</div>
          )}
          <Button onClick={runTest} disabled={isRunning}>
            {isRunning ? 'Executando...' : 'Executar teste'}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Teste de Transcricao de Audio</CardTitle>
          <CardDescription>
            Envie um audio para validar a transcricao via N8N.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">Arquivo de audio</label>
            <input
              type="file"
              accept="audio/*"
              onChange={(event) => setAudioFile(event.target.files?.[0] || null)}
              className="mt-1 block w-full text-sm text-gray-700"
            />
          </div>
          {transcriptionError && (
            <div className="text-sm text-red-600">{transcriptionError}</div>
          )}
          <Button onClick={runTranscriptionTest} disabled={isTranscribing}>
            {isTranscribing ? 'Transcrevendo...' : 'Executar transcricao'}
          </Button>
          {transcriptionResponse && (
            <pre className="whitespace-pre-wrap rounded-md bg-gray-50 p-3 text-sm">
              {JSON.stringify(transcriptionResponse, null, 2)}
            </pre>
          )}
        </CardContent>
      </Card>

      {response && (
        <Card>
          <CardHeader>
            <CardTitle>Resposta</CardTitle>
            <CardDescription>Resultado retornado pelo N8N</CardDescription>
          </CardHeader>
          <CardContent>
            <pre className="whitespace-pre-wrap rounded-md bg-gray-50 p-3 text-sm">
              {JSON.stringify(response, null, 2)}
            </pre>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Historico recente</CardTitle>
          <CardDescription>Ultimas execucoes de triagem</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {history.length === 0 ? (
            <div className="text-sm text-gray-500">Nenhuma triagem registrada.</div>
          ) : (
            <div className="space-y-3">
              {history.map((item) => (
                <div key={item.id} className="rounded-md border border-gray-200 p-3 text-sm">
                  <div className="flex items-center justify-between">
                    <div className="font-medium">{item.action}</div>
                    <div className="text-gray-500">{formatDate(item.created_at)}</div>
                  </div>
                  <div className="text-gray-600">
                    Status: {item.status} • Latencia: {item.latency_ms ?? 0} ms
                  </div>
                  <div className="mt-2 rounded-md bg-gray-50 p-2 font-mono text-xs">
                    {JSON.stringify(item.result, null, 2)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
