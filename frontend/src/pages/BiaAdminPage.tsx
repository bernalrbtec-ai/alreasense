/**
 * Página admin da BIA: configuração do prompt, webhook e teste.
 * Acesso travado por chave única (BIA_ADMIN_ACCESS_KEY). Quem tiver a chave acessa.
 */
import { useState, useEffect, useCallback } from 'react'
import { Lock, Send, Save, Loader2 } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Label } from '../components/ui/Label'
import { Input } from '../components/ui/Input'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import { api } from '../lib/api'

const BIA_KEY_STORAGE = 'bia_admin_key_valid'

interface SecretaryProfile {
  is_active: boolean
  signature_name: string
  prompt: string
  use_memory: boolean
  inbox_idle_minutes: number
}

interface AiSettings {
  n8n_ai_webhook_url: string
  agent_model?: string
}

export default function BiaAdminPage() {
  const [keyValidated, setKeyValidated] = useState(() => !!sessionStorage.getItem(BIA_KEY_STORAGE))
  const [accessKey, setAccessKey] = useState('')
  const [keyError, setKeyError] = useState<string | null>(null)
  const [keyLoading, setKeyLoading] = useState(false)

  const [secretaryProfile, setSecretaryProfile] = useState<SecretaryProfile | null>(null)
  const [secretaryLoading, setSecretaryLoading] = useState(false)
  const [secretarySaving, setSecretarySaving] = useState(false)
  const [aiSettings, setAiSettings] = useState<AiSettings | null>(null)
  const [aiSettingsLoading, setAiSettingsLoading] = useState(false)

  const [promptDraft, setPromptDraft] = useState('')
  const [testMessage, setTestMessage] = useState('')
  const [testSystemPrompt, setTestSystemPrompt] = useState('')
  const [testMessages, setTestMessages] = useState<{ role: 'user' | 'assistant'; content: string }[]>([])
  const [testLoading, setTestLoading] = useState(false)
  const [testError, setTestError] = useState<string | null>(null)

  const verifyKey = useCallback(async () => {
    const key = accessKey.trim()
    if (!key) {
      setKeyError('Digite a chave de acesso.')
      return
    }
    setKeyLoading(true)
    setKeyError(null)
    try {
      const res = await api.post('/ai/bia-admin/verify-key/', { key })
      if (res.data?.valid) {
        sessionStorage.setItem(BIA_KEY_STORAGE, '1')
        setKeyValidated(true)
      } else {
        setKeyError('Chave inválida.')
      }
    } catch (e: any) {
      const msg = e.response?.data?.detail || 'Chave inválida.'
      setKeyError(msg)
    } finally {
      setKeyLoading(false)
    }
  }, [accessKey])

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const keyFromUrl = params.get('key')
    if (keyFromUrl) {
      setAccessKey(keyFromUrl)
    }
  }, [])

  useEffect(() => {
    if (!keyValidated) return
    const load = async () => {
      setSecretaryLoading(true)
      setAiSettingsLoading(true)
      try {
        const [profileRes, settingsRes] = await Promise.all([
          api.get('/ai/secretary/profile/'),
          api.get('/ai/settings/').catch(() => ({ data: null })),
        ])
        const profile = profileRes.data
        setSecretaryProfile(profile)
        setPromptDraft(profile?.prompt ?? '')
        if (settingsRes?.data) {
          setAiSettings(settingsRes.data)
        }
      } catch (e) {
        console.error(e)
      } finally {
        setSecretaryLoading(false)
        setAiSettingsLoading(false)
      }
    }
    load()
  }, [keyValidated])

  const handleSavePrompt = async () => {
    if (!secretaryProfile) return
    setSecretarySaving(true)
    try {
      const res = await api.put('/ai/secretary/profile/', { ...secretaryProfile, prompt: promptDraft })
      setSecretaryProfile(res.data)
    } catch (e: any) {
      console.error(e)
    } finally {
      setSecretarySaving(false)
    }
  }

  const handleSendTest = async () => {
    const message = testMessage.trim()
    if (!message || !aiSettings?.n8n_ai_webhook_url) {
      setTestError(aiSettings?.n8n_ai_webhook_url ? 'Digite uma mensagem.' : 'Configure o webhook em Configurações > IA.')
      return
    }
    setTestLoading(true)
    setTestError(null)
    setTestMessages((prev) => [...prev, { role: 'user', content: message }])
    setTestMessage('')
    try {
      const body: any = {
        message,
        model: aiSettings.agent_model || 'llama3.2',
        context: { action: 'model_test', model: aiSettings.agent_model || 'llama3.2' },
        messages: [...testMessages, { role: 'user', content: message }],
      }
      if (testSystemPrompt.trim()) body.prompt = testSystemPrompt.trim()
      const res = await api.post('/ai/gateway/test/', body)
      const data = res.data?.data || res.data
      const responseData = data?.response || res.data?.response || data
      const reply = responseData?.reply_text ?? responseData?.text ?? JSON.stringify(responseData || res.data, null, 2)
      setTestMessages((prev) => [...prev, { role: 'assistant', content: reply }])
    } catch (e: any) {
      const msg = e.response?.data?.error || e.response?.data?.detail || e.message || 'Erro ao testar.'
      setTestError(msg)
      setTestMessages((prev) => [...prev, { role: 'assistant', content: `Erro: ${msg}` }])
    } finally {
      setTestLoading(false)
    }
  }

  if (!keyValidated) {
    return (
      <div className="max-w-md mx-auto mt-12 p-6">
        <Card className="p-6">
          <div className="flex items-center gap-2 text-gray-700 mb-4">
            <Lock className="h-5 w-5" />
            <h1 className="text-xl font-semibold">Acesso à página BIA</h1>
          </div>
          <p className="text-sm text-gray-600 mb-4">
            Esta página é restrita. Digite a chave de acesso para configurar o prompt e testar a BIA.
          </p>
          <Label htmlFor="bia-key">Chave de acesso</Label>
          <Input
            id="bia-key"
            type="password"
            value={accessKey}
            onChange={(e) => setAccessKey(e.target.value)}
            placeholder="Chave única"
            className="mt-1 mb-3"
            onKeyDown={(e) => e.key === 'Enter' && verifyKey()}
          />
          {keyError && <p className="text-sm text-red-600 mb-3">{keyError}</p>}
          <Button onClick={verifyKey} disabled={keyLoading}>
            {keyLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            {keyLoading ? ' Verificando...' : 'Entrar'}
          </Button>
        </Card>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto p-4 md:p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">BIA – Configuração e teste</h1>
        <p className="text-sm text-gray-600 mt-1">
          Prompt da secretária, webhook e área de teste. Alterações do prompt são salvas no perfil da BIA.
        </p>
      </div>

      {/* Prompt e Webhook */}
      <Card className="p-6">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Configuração</h2>
        {secretaryLoading || aiSettingsLoading ? (
          <LoadingSpinner />
        ) : (
          <div className="space-y-4">
            <div>
              <Label htmlFor="bia-prompt">Prompt da BIA</Label>
              <textarea
                id="bia-prompt"
                value={promptDraft}
                onChange={(e) => setPromptDraft(e.target.value)}
                rows={12}
                className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-blue-500"
                placeholder="Instruções do sistema para a BIA..."
              />
              <Button onClick={handleSavePrompt} disabled={secretarySaving} className="mt-2">
                {secretarySaving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Save className="h-4 w-4 mr-2" />}
                Salvar prompt
              </Button>
            </div>
            <div>
              <Label>Webhook do Gateway IA</Label>
              <p className="text-sm text-gray-600 mt-1 font-mono bg-gray-50 px-2 py-1 rounded truncate">
                {aiSettings?.n8n_ai_webhook_url || 'Não configurado. Configure em Configurações > IA.'}
              </p>
            </div>
          </div>
        )}
      </Card>

      {/* Teste */}
      <Card className="p-6">
        <h2 className="text-lg font-medium text-gray-900 mb-4">Testar prompt</h2>
        <div className="space-y-3">
          <div>
            <Label>Prompt de sistema (opcional)</Label>
            <textarea
              value={testSystemPrompt}
              onChange={(e) => setTestSystemPrompt(e.target.value)}
              rows={2}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
              placeholder="Override do prompt para este teste..."
            />
          </div>
          <div className="flex gap-2">
            <textarea
              value={testMessage}
              onChange={(e) => setTestMessage(e.target.value)}
              rows={2}
              className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm"
              placeholder="Digite uma mensagem para testar..."
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  handleSendTest()
                }
              }}
            />
            <Button onClick={handleSendTest} disabled={testLoading || !testMessage.trim()}>
              {testLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            </Button>
          </div>
          {testError && <p className="text-sm text-red-600">{testError}</p>}
          <div className="min-h-[120px] rounded border border-gray-200 bg-gray-50 p-3 space-y-2">
            {testMessages.length === 0 ? (
              <p className="text-sm text-gray-500">Envie uma mensagem para testar.</p>
            ) : (
              testMessages.map((m, i) => (
                <div
                  key={i}
                  className={`text-sm ${m.role === 'user' ? 'text-right' : ''}`}
                >
                  <span className="font-medium text-gray-600">{m.role === 'user' ? 'Você' : 'BIA'}: </span>
                  <pre className="whitespace-pre-wrap font-sans inline">{m.content}</pre>
                </div>
              ))
            )}
          </div>
        </div>
      </Card>
    </div>
  )
}
