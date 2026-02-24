/**
 * Página admin da BIA: Configuração (prompt, modelo, teste) e Homologação (conversa real + teste).
 * Acesso travado por chave única (BIA_ADMIN_ACCESS_KEY).
 * Modelo é definido apenas na aba Configuração (fonte da verdade).
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import { Lock, Send, Save, Loader2, MessageSquare, Settings, FlaskConical, Trash2 } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Label } from '../components/ui/Label'
import { Input } from '../components/ui/Input'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import { api } from '../lib/api'

const BIA_KEY_STORAGE = 'bia_admin_key_valid'
/** Limite do prompt no gateway (~1 MB em texto típico). */
const MAX_PROMPT_LENGTH = 1_000_000

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

interface ConversationOption {
  id: string
  contact_name: string | null
  contact_phone: string | null
  last_message_at?: string | null
  department_name?: string | null
  created_at?: string | null
  updated_at?: string | null
}

function formatDateTime(iso?: string | null): string {
  if (!iso) return '–'
  try {
    const d = new Date(iso)
    return d.toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
  } catch {
    return iso
  }
}

export default function BiaAdminPage() {
  const [keyValidated, setKeyValidated] = useState(() => !!sessionStorage.getItem(BIA_KEY_STORAGE))
  const [accessKey, setAccessKey] = useState('')
  const [keyError, setKeyError] = useState<string | null>(null)
  const [keyLoading, setKeyLoading] = useState(false)

  const [secretaryProfile, setSecretaryProfile] = useState<SecretaryProfile | null>(null)
  const [secretaryLoading, setSecretaryLoading] = useState(false)
  const [secretarySaving, setSecretarySaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [aiSettings, setAiSettings] = useState<AiSettings | null>(null)
  const [aiSettingsLoading, setAiSettingsLoading] = useState(false)

  const [promptDraft, setPromptDraft] = useState('')
  const [testSystemPrompt, setTestSystemPrompt] = useState('')
  // Estado independente por aba: Config e Homolog têm histórico de teste separado.
  const [testMessageConfig, setTestMessageConfig] = useState('')
  const [testMessagesConfig, setTestMessagesConfig] = useState<{ role: 'user' | 'assistant'; content: string }[]>([])
  const [testLoadingConfig, setTestLoadingConfig] = useState(false)
  const [testErrorConfig, setTestErrorConfig] = useState<string | null>(null)
  const [testMessageHomolog, setTestMessageHomolog] = useState('')
  const [testMessagesHomolog, setTestMessagesHomolog] = useState<{ role: 'user' | 'assistant'; content: string }[]>([])
  const [testLoadingHomolog, setTestLoadingHomolog] = useState(false)
  const [testErrorHomolog, setTestErrorHomolog] = useState<string | null>(null)
  const [aiModelOptions, setAiModelOptions] = useState<string[]>([])
  const [testSelectedModel, setTestSelectedModel] = useState<string>('')
  const [aiModelsLoading, setAiModelsLoading] = useState(false)

  const [conversations, setConversations] = useState<ConversationOption[]>([])
  const [conversationsLoading, setConversationsLoading] = useState(false)
  const [selectedConversationId, setSelectedConversationId] = useState<string>('')
  const [loadedConversationText, setLoadedConversationText] = useState<string>('')
  const [messagesLoading, setMessagesLoading] = useState(false)

  const pollingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const pollingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const [activeTab, setActiveTab] = useState<'config' | 'homolog'>('config')

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

  // Cancelar polling ao sair da página
  useEffect(() => {
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current)
        pollingIntervalRef.current = null
      }
      if (pollingTimeoutRef.current) {
        clearTimeout(pollingTimeoutRef.current)
        pollingTimeoutRef.current = null
      }
    }
  }, [])

  // Auto-verificar chave quando vier na URL (uma vez)
  const didAutoVerify = useRef(false)
  useEffect(() => {
    if (keyValidated || keyLoading || didAutoVerify.current) return
    const params = new URLSearchParams(window.location.search)
    const keyFromUrl = params.get('key')?.trim()
    if (!keyFromUrl) return
    didAutoVerify.current = true
    setKeyError(null)
    setKeyLoading(true)
    api
      .post('/ai/bia-admin/verify-key/', { key: keyFromUrl })
      .then((res) => {
        if (res.data?.valid) {
          sessionStorage.setItem(BIA_KEY_STORAGE, '1')
          setKeyValidated(true)
        } else {
          setKeyError('Chave inválida.')
        }
      })
      .catch((e: any) => {
        setKeyError(e.response?.data?.detail || 'Chave inválida.')
      })
      .finally(() => setKeyLoading(false))
  }, [keyValidated, keyLoading])

  useEffect(() => {
    if (!keyValidated) return
    const load = async () => {
      setSecretaryLoading(true)
      setAiSettingsLoading(true)
      setAiModelsLoading(true)
      try {
        const [profileRes, settingsRes] = await Promise.all([
          api.get('/ai/secretary/profile/'),
          api.get('/ai/settings/').catch(() => ({ data: null })),
        ])
        const profile = profileRes.data
        setSecretaryProfile(profile)
        setPromptDraft(profile?.prompt ?? '')
        const settings = settingsRes?.data
        if (settings) {
          setAiSettings(settings)
        }
        try {
          const modelsRes = await api.get('/ai/models/')
          const models = Array.isArray(modelsRes.data?.models) ? modelsRes.data.models : []
          setAiModelOptions(models)
          if (models.length > 0 && settings?.agent_model && models.includes(settings.agent_model)) {
            setTestSelectedModel(settings.agent_model)
          } else if (models.length > 0) {
            setTestSelectedModel(models[0])
          } else if (settings?.agent_model) {
            setTestSelectedModel(settings.agent_model)
          }
        } catch {
          setAiModelOptions([])
          if (settings?.agent_model) setTestSelectedModel(settings.agent_model)
        }
      } catch (e) {
        console.error(e)
      } finally {
        setSecretaryLoading(false)
        setAiSettingsLoading(false)
        setAiModelsLoading(false)
      }
    }
    load()
  }, [keyValidated])

  useEffect(() => {
    if (!keyValidated) return
    const loadConversations = async () => {
      setConversationsLoading(true)
      try {
        const res = await api.get('/chat/conversations/', {
          params: { ordering: '-last_message_at', page_size: 100 },
        })
        const list = res.data?.results ?? res.data ?? []
        setConversations(Array.isArray(list) ? list : [])
      } catch (e) {
        console.error(e)
        setConversations([])
      } finally {
        setConversationsLoading(false)
      }
    }
    loadConversations()
  }, [keyValidated])

  useEffect(() => {
    if (!selectedConversationId) {
      setLoadedConversationText('')
      return
    }
    let cancelled = false
    const loadMessages = async () => {
      setMessagesLoading(true)
      setLoadedConversationText('')
      try {
        const [msgRes, convRes] = await Promise.all([
          api.get(`/chat/conversations/${selectedConversationId}/messages/`, {
            params: { limit: 500, offset: 0 },
          }),
          api.get(`/chat/conversations/${selectedConversationId}/`).catch(() => ({ data: null })),
        ])
        if (cancelled) return
        const conv = convRes.data
        const headerParts: string[] = []
        headerParts.push(`Departamento: ${conv?.department_name ?? '–'}`)
        headerParts.push(`Início: ${formatDateTime(conv?.created_at)}`)
        headerParts.push(`Última atividade: ${formatDateTime(conv?.updated_at ?? conv?.last_message_at)}`)
        const header = headerParts.join(' | ')
        const list = msgRes.data?.results ?? msgRes.data ?? []
        const msgs = Array.isArray(list) ? list : []
        const sorted = [...msgs].sort(
          (a: { created_at?: string }, b: { created_at?: string }) =>
            new Date(a.created_at || 0).getTime() - new Date(b.created_at || 0).getTime()
        )
        const lines = sorted.map(
          (m: { direction?: string; content?: string; sender_name?: string; created_at?: string }) => {
            const time = formatDateTime(m.created_at)
            const role = m.direction === 'incoming' ? 'Cliente' : 'Atendente'
            const name = (m.sender_name || '').trim()
            const label = name ? `${role} (${name})` : role
            const content = (m.content || '').trim() || '(sem texto)'
            return `[${time}] ${label}: ${content}`
          }
        )
        setLoadedConversationText([header, '', ...lines].join('\n'))
      } catch (e) {
        if (!cancelled) setLoadedConversationText('')
        console.error(e)
      } finally {
        if (!cancelled) setMessagesLoading(false)
      }
    }
    loadMessages()
    return () => {
      cancelled = true
    }
  }, [selectedConversationId])

  const handleSavePrompt = async () => {
    if (!secretaryProfile) return
    setSecretarySaving(true)
    setSaveError(null)
    try {
      const res = await api.put('/ai/secretary/profile/', { ...secretaryProfile, prompt: promptDraft })
      setSecretaryProfile(res.data)
      setPromptDraft(res.data.prompt ?? promptDraft)
    } catch (e: any) {
      const msg = e.response?.data?.errors?.prompt || e.response?.data?.detail || e.message || 'Erro ao salvar.'
      setSaveError(msg)
    } finally {
      setSecretarySaving(false)
    }
  }

  const POLL_INTERVAL_MS = 2500
  const POLL_MAX_MS = 5 * 60 * 1000 // 5 min

  type TestTab = 'config' | 'homolog'

  const handleSendTest = async (tab: TestTab) => {
    const isConfig = tab === 'config'
    const message = (isConfig ? testMessageConfig : testMessageHomolog).trim()
    const setMessage = isConfig ? setTestMessageConfig : setTestMessageHomolog
    const messages = isConfig ? testMessagesConfig : testMessagesHomolog
    const setMessages = isConfig ? setTestMessagesConfig : setTestMessagesHomolog
    const setError = isConfig ? setTestErrorConfig : setTestErrorHomolog
    const setLoading = isConfig ? setTestLoadingConfig : setTestLoadingHomolog

    if (!message || !aiSettings?.n8n_ai_webhook_url) {
      setError(aiSettings?.n8n_ai_webhook_url ? 'Digite uma mensagem.' : 'Configure o webhook em Configurações > IA.')
      return
    }
    setLoading(true)
    setError(null)
    setMessages((prev) => [...prev, { role: 'user', content: message }])
    setMessage('')
    const clearPolling = () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current)
        pollingIntervalRef.current = null
      }
      if (pollingTimeoutRef.current) {
        clearTimeout(pollingTimeoutRef.current)
        pollingTimeoutRef.current = null
      }
      setLoading(false)
    }
    const finishWithMessage = (content: string) => {
      setMessages((prev) => {
        const rest = prev.slice(0, -1)
        return [...rest, { role: 'assistant' as const, content }]
      })
      clearPolling()
    }
    try {
      // Config: sempre promptDraft. Homolog: testSystemPrompt ou promptDraft + conversa real.
      const testPrompt = isConfig ? '' : testSystemPrompt.trim()
      const defaultPrompt = (promptDraft ?? '').trim()
      let prompt = testPrompt || defaultPrompt
      if (!isConfig && loadedConversationText.trim()) {
        prompt = (prompt ? prompt + '\n\n' : '') + '---\nConversa real (contexto):\n' + loadedConversationText.trim()
      }
      if (prompt.length > MAX_PROMPT_LENGTH) {
        prompt = prompt.slice(0, MAX_PROMPT_LENGTH)
        setError(`Prompt truncado a ${MAX_PROMPT_LENGTH} caracteres (limite do backend).`)
      }
      const model = testSelectedModel || aiSettings?.agent_model || 'llama3.2'
      const body: any = {
        message,
        model,
        context: { action: 'model_test', model },
        messages: [...messages, { role: 'user', content: message }],
      }
      if (prompt.length > 0) body.prompt = prompt
      // Teste da aba Configuração = mesmo payload da produção (secretary + RAG + business_hours + company_context)
      if (tab === 'config') body.simulate_production = true
      const res = await api.post('/ai/gateway/test/', body)

      if (res.data?.deferred && res.data?.job_id) {
        setMessages((prev) => [...prev, { role: 'assistant', content: 'Deixe-me pensar...' }])
        const jobId = res.data.job_id as string
        const startedAt = Date.now()
        const poll = async () => {
          if (Date.now() - startedAt > POLL_MAX_MS) {
            finishWithMessage('Tempo esgotado. Resultado não disponível.')
            return
          }
          try {
            const r = await api.get(`/ai/gateway/test/result/${jobId}/`)
            const st = r.data?.status
            if (st === 'completed') {
              const resp = r.data?.response || {}
              const reply = resp.reply_text ?? resp.text ?? JSON.stringify(resp, null, 2)
              finishWithMessage(String(reply))
              return
            }
            if (st === 'failed') {
              finishWithMessage(`Erro: ${r.data?.error || 'Falha no processamento.'}`)
              return
            }
          } catch (e: any) {
            if (e.response?.status === 404) {
              finishWithMessage('Resultado expirado ou não encontrado.')
              return
            }
          }
        }
        pollingIntervalRef.current = setInterval(poll, POLL_INTERVAL_MS)
        setTimeout(() => poll(), 400)
        pollingTimeoutRef.current = setTimeout(() => {
          if (pollingIntervalRef.current) {
            finishWithMessage('Tempo esgotado. Resultado não disponível.')
          }
        }, POLL_MAX_MS)
        return
      }

      const data = res.data?.data || res.data
      const responseData = data?.response || res.data?.response || data
      const reply = responseData?.reply_text ?? responseData?.text ?? JSON.stringify(responseData || res.data, null, 2)
      setMessages((prev) => [...prev, { role: 'assistant', content: reply }])
      setError(null)
    } catch (e: any) {
      const msg = e.response?.data?.error || e.response?.data?.detail || e.message || 'Erro ao testar.'
      setError(msg)
      setMessages((prev) => [...prev, { role: 'assistant', content: `Erro: ${msg}` }])
    } finally {
      setLoading(false)
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

  const effectiveModel = testSelectedModel || aiSettings?.agent_model || 'llama3.2'

  const modelSelect = (
    <div>
      <Label htmlFor="bia-test-model">Modelo</Label>
      <select
        id="bia-test-model"
        value={effectiveModel}
        onChange={(e) => setTestSelectedModel(e.target.value)}
        className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm bg-white"
        disabled={aiModelsLoading}
      >
        {aiModelOptions.length === 0 ? (
          <option value={aiSettings?.agent_model || 'llama3.2'}>{aiSettings?.agent_model || 'llama3.2'}</option>
        ) : (
          aiModelOptions.map((m) => (
            <option key={m} value={m}>{m}</option>
          ))
        )}
      </select>
      {aiModelsLoading && <p className="text-xs text-gray-500 mt-1">Carregando modelos...</p>}
      {!aiModelsLoading && aiModelOptions.length === 0 && aiSettings?.n8n_ai_webhook_url && (
        <p className="text-xs text-amber-600 mt-1">Configure o webhook de modelos em Configurações &gt; IA.</p>
      )}
    </div>
  )

  /** Chat da aba Configuração (histórico independente). */
  const testAreaChatConfig = (
    <div className="space-y-3">
      <div className="flex gap-2">
        <textarea
          value={testMessageConfig}
          onChange={(e) => setTestMessageConfig(e.target.value)}
          rows={2}
          className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm"
          placeholder="Digite uma mensagem para testar..."
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              handleSendTest('config')
            }
          }}
        />
        <Button onClick={() => handleSendTest('config')} disabled={testLoadingConfig || !testMessageConfig.trim()}>
          {testLoadingConfig ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
        </Button>
      </div>
      {testErrorConfig && <p className="text-sm text-red-600">{testErrorConfig}</p>}
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs text-gray-500">Histórico do teste</span>
        {testMessagesConfig.length > 0 && (
          <Button
            type="button"
            variant="outline"
            disabled={testLoadingConfig}
            onClick={() => { setTestMessagesConfig([]); setTestErrorConfig(null) }}
            className="text-xs"
            aria-label="Limpar histórico do chat"
          >
            <Trash2 className="h-3.5 w-3.5 mr-1" />
            Limpar histórico
          </Button>
        )}
      </div>
      <div className="min-h-[140px] max-h-[280px] overflow-y-auto rounded border border-gray-200 bg-gray-50 p-3 space-y-2">
        {testMessagesConfig.length === 0 ? (
          <p className="text-sm text-gray-500">Envie uma mensagem para testar.</p>
        ) : (
          testMessagesConfig.map((m, i) => (
            <div
              key={i}
              className={`text-sm rounded-lg px-3 py-2 max-w-[90%] ${
                m.role === 'user'
                  ? 'ml-auto bg-blue-100 text-blue-900 border border-blue-200'
                  : 'mr-auto bg-white text-gray-800 border border-gray-200'
              }`}
            >
              <span className="font-medium text-gray-600 block text-xs mb-0.5">{m.role === 'user' ? 'Você' : 'BIA'}</span>
              <pre className="whitespace-pre-wrap font-sans text-left">{m.content}</pre>
            </div>
          ))
        )}
      </div>
    </div>
  )

  /** Chat da aba Homologação (histórico independente). */
  const testAreaChatHomolog = (
    <div className="space-y-3">
      <div className="flex gap-2">
        <textarea
          value={testMessageHomolog}
          onChange={(e) => setTestMessageHomolog(e.target.value)}
          rows={2}
          className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm"
          placeholder="Digite uma mensagem para testar..."
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              handleSendTest('homolog')
            }
          }}
        />
        <Button onClick={() => handleSendTest('homolog')} disabled={testLoadingHomolog || !testMessageHomolog.trim()}>
          {testLoadingHomolog ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
        </Button>
      </div>
      {testErrorHomolog && <p className="text-sm text-red-600">{testErrorHomolog}</p>}
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs text-gray-500">Histórico do teste</span>
        {testMessagesHomolog.length > 0 && (
          <Button
            type="button"
            variant="outline"
            disabled={testLoadingHomolog}
            onClick={() => { setTestMessagesHomolog([]); setTestErrorHomolog(null) }}
            className="text-xs"
            aria-label="Limpar histórico do chat"
          >
            <Trash2 className="h-3.5 w-3.5 mr-1" />
            Limpar histórico
          </Button>
        )}
      </div>
      <div className="min-h-[140px] max-h-[280px] overflow-y-auto rounded border border-gray-200 bg-gray-50 p-3 space-y-2">
        {testMessagesHomolog.length === 0 ? (
          <p className="text-sm text-gray-500">Envie uma mensagem para testar.</p>
        ) : (
          testMessagesHomolog.map((m, i) => (
            <div
              key={i}
              className={`text-sm rounded-lg px-3 py-2 max-w-[90%] ${
                m.role === 'user'
                  ? 'ml-auto bg-blue-100 text-blue-900 border border-blue-200'
                  : 'mr-auto bg-white text-gray-800 border border-gray-200'
              }`}
            >
              <span className="font-medium text-gray-600 block text-xs mb-0.5">{m.role === 'user' ? 'Você' : 'BIA'}</span>
              <pre className="whitespace-pre-wrap font-sans text-left">{m.content}</pre>
            </div>
          ))
        )}
      </div>
    </div>
  )

  /** Área de teste na Config: só modelo + chat (usa sempre o prompt da BIA). */
  const testAreaConfig = (
    <div className="space-y-4">
      {modelSelect}
      {testAreaChatConfig}
    </div>
  )

  /** Área de teste na Homologação: modelo + prompt opcional + chat. */
  const testAreaHomolog = (
    <div className="space-y-4">
      {modelSelect}
      <div>
        <Label>Prompt de sistema (opcional)</Label>
        <p className="text-xs text-gray-500 mt-0 mb-1">
          Vazio: usa o prompt da Configuração. Preenchido: usa só este texto no teste.
        </p>
        <textarea
          value={testSystemPrompt}
          onChange={(e) => setTestSystemPrompt(e.target.value)}
          rows={2}
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
          placeholder="Deixe vazio para usar o prompt da Configuração"
        />
      </div>
      {testAreaChatHomolog}
    </div>
  )

  return (
    <div className="max-w-[1600px] mx-auto p-4 md:p-6 space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">BIA – Configuração e Homologação</h1>
          <p className="text-sm text-gray-600 mt-1">
            Configure o prompt e o modelo na aba Configuração. Use Homologação para testar com conversa real.
          </p>
        </div>
        <div className="flex rounded-lg border border-gray-200 bg-gray-50 p-1" role="tablist" aria-label="Abas BIA">
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'config'}
            aria-controls="bia-tab-config"
            id="bia-tab-config-trigger"
            onClick={() => setActiveTab('config')}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              activeTab === 'config'
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            <Settings className="h-4 w-4" aria-hidden />
            Configuração
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'homolog'}
            aria-controls="bia-tab-homolog"
            id="bia-tab-homolog-trigger"
            onClick={() => setActiveTab('homolog')}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              activeTab === 'homolog'
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            <FlaskConical className="h-4 w-4" aria-hidden />
            Homologação
          </button>
        </div>
      </div>

      {activeTab === 'config' && (
        <div id="bia-tab-config" role="tabpanel" aria-labelledby="bia-tab-config-trigger" className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card className="p-6">
            <h2 className="text-lg font-medium text-gray-900 mb-4">Prompt da BIA</h2>
            {secretaryLoading || aiSettingsLoading ? (
              <LoadingSpinner />
            ) : (
              <div className="space-y-4">
                <div>
                  <Label htmlFor="bia-prompt">Instruções do sistema</Label>
                  <textarea
                    id="bia-prompt"
                    value={promptDraft}
                    onChange={(e) => {
                      setPromptDraft(e.target.value)
                      if (saveError) setSaveError(null)
                    }}
                    rows={12}
                    className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-blue-500"
                    placeholder="Instruções do sistema para a BIA..."
                  />
                  <Button onClick={handleSavePrompt} disabled={secretarySaving} className="mt-2">
                    {secretarySaving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Save className="h-4 w-4 mr-2" />}
                    Salvar prompt
                  </Button>
                  {saveError && <p className="text-sm text-red-600 mt-2">{saveError}</p>}
                </div>
              </div>
            )}
          </Card>
          <Card className="p-6">
            <h2 className="text-lg font-medium text-gray-900 mb-4">AREA DE TESTE DO MODELO</h2>
            <p className="text-sm text-gray-600 mb-4">
              O teste usa o webhook definido em Configurações &gt; IA.
            </p>
            {aiSettingsLoading ? (
              <LoadingSpinner />
            ) : (
              testAreaConfig
            )}
          </Card>
        </div>
      )}

      {activeTab === 'homolog' && (
        <div id="bia-tab-homolog" role="tabpanel" aria-labelledby="bia-tab-homolog-trigger" className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card className="p-6">
            <h2 className="text-lg font-medium text-gray-900 mb-4">Testar com contexto</h2>
            <p className="text-sm text-gray-600 mb-4">
              Escolha o modelo, opcionalmente um prompt só para o teste, e envie uma mensagem. A conversa real selecionada à direita será enviada como contexto no prompt (se houver).
            </p>
            {testAreaHomolog}
          </Card>
          <Card className="p-6">
            <h2 className="text-lg font-medium text-gray-900 mb-4 flex items-center gap-2">
              <MessageSquare className="h-5 w-5" />
              Conversa real no prompt
            </h2>
            <p className="text-sm text-gray-600 mb-4">
              Selecione uma conversa. Ela será enviada como contexto no prompt ao testar ao lado.
            </p>
            <div className="space-y-3">
              <div>
                <Label>Conversa</Label>
                <select
                  value={selectedConversationId}
                  onChange={(e) => setSelectedConversationId(e.target.value)}
                  className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm bg-white"
                  disabled={conversationsLoading}
                >
                  <option value="">Nenhuma (só prompt de sistema)</option>
                  {conversations.map((c) => (
                    <option key={c.id} value={c.id}>{c.contact_name || c.contact_phone || c.id}</option>
                  ))}
                </select>
                {conversationsLoading && <p className="text-xs text-gray-500 mt-1">Carregando conversas...</p>}
              </div>
              {messagesLoading && selectedConversationId && (
                <p className="text-sm text-gray-500 flex items-center gap-1">
                  <Loader2 className="h-4 w-4 animate-spin" /> Carregando mensagens...
                </p>
              )}
              {!selectedConversationId && !conversationsLoading && (
                <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2">
                  Nenhuma conversa selecionada. O teste usará só o prompt de sistema.
                </p>
              )}
            </div>
          </Card>
        </div>
      )}
    </div>
  )
}
