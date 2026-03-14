/**
 * Página admin da Secretária: Configuração (prompt, modelo, teste) e Homologação (conversa real + teste).
 * Acesso travado por chave única (variável de ambiente no backend).
 * Modelo é definido apenas na aba Configuração (fonte da verdade).
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import { Link } from 'react-router-dom'
import { Lock, Send, Save, Loader2, MessageSquare, Settings, FlaskConical, Trash2, Edit, FileText, X, SlidersHorizontal } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Label } from '../components/ui/Label'
import { Input } from '../components/ui/Input'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import { api } from '../lib/api'

const BIA_KEY_STORAGE = 'bia_admin_key_valid'
/** Limite do prompt no gateway (~1 MB em texto típico). */
const MAX_PROMPT_LENGTH = 1_000_000

const DEFAULT_ADVANCED_OPTIONS = {
  temperature: 0.3,
  top_p: 0.85,
  top_k: 30,
  repeat_penalty: 1.15,
  min_p: 0.05,
} as const

interface SecretaryProfile {
  is_active: boolean
  signature_name: string
  prompt: string
  use_memory: boolean
  inbox_idle_minutes: number
  response_delay_seconds?: number
  form_data?: Record<string, unknown>
  advanced_options?: {
    temperature?: number
    top_p?: number
    top_k?: number
    repeat_penalty?: number
    min_p?: number
  } | null
}

interface AiSettings {
  n8n_ai_webhook_url: string
  agent_model?: string
  secretary_model?: string
  secretary_enabled?: boolean
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
  const [secretaryProfileErrors, setSecretaryProfileErrors] = useState<Record<string, string>>({})
  const [advancedOptionsModalOpen, setAdvancedOptionsModalOpen] = useState(false)
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
        const raw = profileRes.data
        const profile = raw
          ? {
              ...raw,
              advanced_options:
                raw.advanced_options != null && typeof raw.advanced_options === 'object' && !Array.isArray(raw.advanced_options)
                  ? raw.advanced_options
                  : undefined,
            }
          : raw
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

  const handleSaveSecretaryProfile = async (override?: Partial<SecretaryProfile> | null) => {
    if (!secretaryProfile) return
    const toSave = override != null ? { ...secretaryProfile, ...override } : secretaryProfile
    const errors: Record<string, string> = {}
    const mins = toSave.inbox_idle_minutes ?? 0
    if (mins < 0 || mins > 1440) errors.inbox_idle_minutes = 'Valor entre 0 e 1440.'
    const delaySec = toSave.response_delay_seconds ?? 0
    if (delaySec < 0 || delaySec > 120) errors.response_delay_seconds = 'Valor entre 0 e 120.'
    setSecretaryProfileErrors(errors)
    if (Object.keys(errors).length > 0) return
    setSecretarySaving(true)
    try {
      const payload = { ...toSave }
      if (payload.advanced_options && typeof payload.advanced_options === 'object') {
        const { num_ctx: _, ...rest } = payload.advanced_options as Record<string, unknown>
        payload.advanced_options = Object.keys(rest).length ? rest : null
      }
      const res = await api.put('/ai/secretary/profile/', payload)
      const saved = res.data
      setSecretaryProfile(
        saved
          ? {
              ...saved,
              advanced_options:
                saved.advanced_options != null && typeof saved.advanced_options === 'object' && !Array.isArray(saved.advanced_options)
                  ? saved.advanced_options
                  : undefined,
            }
          : saved
      )
      if (aiSettings) {
        const secretaryModel = (aiSettings.secretary_model ?? '').trim()
        await api.put('/ai/settings/', {
          ...aiSettings,
          secretary_model: secretaryModel,
          secretary_enabled: toSave.is_active,
        })
        const settingsRes = await api.get('/ai/settings/')
        if (settingsRes?.data) setAiSettings(settingsRes.data)
      }
    } catch (e: any) {
      const apiErrors = e.response?.data?.errors || {}
      if (apiErrors && typeof apiErrors === 'object') setSecretaryProfileErrors(apiErrors)
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
      // Config e Homologação: mesmo payload da produção (action=secretary, RAG, business_hours, departments, etc.)
      // para que o JSON enviado ao webhook seja idêntico em ambas as áreas e igual ao fluxo real.
      body.simulate_production = true
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
          <div className="flex items-center gap-2 text-gray-700 dark:text-gray-300 mb-4">
            <Lock className="h-5 w-5" />
            <h1 className="text-xl font-semibold">Acesso à página Secretária</h1>
          </div>
          <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
            Esta página é restrita. Digite a chave de acesso para configurar o prompt e testar a Secretária.
          </p>
          <Label htmlFor="secretary-key">Chave de acesso</Label>
          <Input
            id="secretary-key"
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
      <Label htmlFor="secretary-test-model">Modelo</Label>
      <select
        id="secretary-test-model"
        value={effectiveModel}
        onChange={(e) => setTestSelectedModel(e.target.value)}
        className="mt-1 block w-full rounded-lg border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 bg-white dark:bg-gray-800"
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
      {aiModelsLoading && <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Carregando modelos...</p>}
      {!aiModelsLoading && aiModelOptions.length === 0 && aiSettings?.n8n_ai_webhook_url && (
        <p className="text-xs text-amber-600 dark:text-amber-400 mt-1">Configure o webhook de modelos em Configurações &gt; IA.</p>
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
          className="flex-1 rounded-lg border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 bg-white dark:bg-gray-800 placeholder:text-gray-400 dark:placeholder:text-gray-500"
          placeholder="Digite uma mensagem para testar..."
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              handleSendTest('config')
            }
          }}
        />
        <Button onClick={() => handleSendTest('config')} disabled={testLoadingConfig || !testMessageConfig.trim()} className="flex-shrink-0" title="Enviar">
          {testLoadingConfig ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
        </Button>
      </div>
      {testErrorConfig && <p className="text-sm text-red-600 dark:text-red-400">{testErrorConfig}</p>}
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs text-gray-500 dark:text-gray-400">Histórico do teste</span>
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
      <div className="min-h-[140px] max-h-[280px] overflow-y-auto rounded border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-800 p-3 space-y-2">
        {testMessagesConfig.length === 0 ? (
          <p className="text-sm text-gray-500 dark:text-gray-400">Envie uma mensagem para testar.</p>
        ) : (
          testMessagesConfig.map((m, i) => (
            <div
              key={i}
              className={`text-sm rounded-lg px-3 py-2 max-w-[90%] ${
                m.role === 'user'
                  ? 'ml-auto bg-blue-100 dark:bg-blue-900/30 text-blue-900 dark:text-blue-200 border border-blue-200 dark:border-blue-700'
                  : 'mr-auto bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200 border border-gray-200 dark:border-gray-600'
              }`}
            >
              <span className="font-medium text-gray-600 dark:text-gray-400 block text-xs mb-0.5">{m.role === 'user' ? 'Você' : 'Secretária'}</span>
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
          className="flex-1 rounded-lg border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 bg-white dark:bg-gray-800 placeholder:text-gray-400 dark:placeholder:text-gray-500"
          placeholder="Digite uma mensagem para testar..."
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              handleSendTest('homolog')
            }
          }}
        />
        <Button onClick={() => handleSendTest('homolog')} disabled={testLoadingHomolog || !testMessageHomolog.trim()} className="flex-shrink-0" title="Enviar">
          {testLoadingHomolog ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
        </Button>
      </div>
      {testErrorHomolog && <p className="text-sm text-red-600 dark:text-red-400">{testErrorHomolog}</p>}
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs text-gray-500 dark:text-gray-400">Histórico do teste</span>
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
      <div className="min-h-[140px] max-h-[280px] overflow-y-auto rounded border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-800 p-3 space-y-2">
        {testMessagesHomolog.length === 0 ? (
          <p className="text-sm text-gray-500 dark:text-gray-400">Envie uma mensagem para testar.</p>
        ) : (
          testMessagesHomolog.map((m, i) => (
            <div
              key={i}
              className={`text-sm rounded-lg px-3 py-2 max-w-[90%] ${
                m.role === 'user'
                  ? 'ml-auto bg-blue-100 dark:bg-blue-900/30 text-blue-900 dark:text-blue-200 border border-blue-200 dark:border-blue-700'
                  : 'mr-auto bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200 border border-gray-200 dark:border-gray-600'
              }`}
            >
              <span className="font-medium text-gray-600 dark:text-gray-400 block text-xs mb-0.5">{m.role === 'user' ? 'Você' : 'Secretária'}</span>
              <pre className="whitespace-pre-wrap font-sans text-left">{m.content}</pre>
            </div>
          ))
        )}
      </div>
    </div>
  )

  /** Área de teste na Config: só modelo + chat (usa sempre o prompt da Secretária). */
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
        <p className="text-xs text-gray-500 dark:text-gray-400 mt-0 mb-1">
          Vazio: usa o prompt da Configuração. Preenchido: usa só este texto no teste.
        </p>
        <textarea
          value={testSystemPrompt}
          onChange={(e) => setTestSystemPrompt(e.target.value)}
          rows={2}
          className="mt-1 block w-full rounded-lg border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 bg-white dark:bg-gray-800 placeholder:text-gray-400 dark:placeholder:text-gray-500"
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
          <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Secretária – Configuração e Homologação</h1>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
            Configure o prompt e o modelo na aba Configuração. Use Homologação para testar com conversa real.
          </p>
        </div>
        <div className="flex rounded-lg border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-800 p-1" role="tablist" aria-label="Abas Secretária">
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'config'}
            aria-controls="secretary-tab-config"
            id="secretary-tab-config-trigger"
            onClick={() => setActiveTab('config')}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              activeTab === 'config'
                ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 shadow-sm'
                : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100'
            }`}
          >
            <Settings className="h-4 w-4" aria-hidden />
            Configuração
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'homolog'}
            aria-controls="secretary-tab-homolog"
            id="secretary-tab-homolog-trigger"
            onClick={() => setActiveTab('homolog')}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              activeTab === 'homolog'
                ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 shadow-sm'
                : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100'
            }`}
          >
            <FlaskConical className="h-4 w-4" aria-hidden />
            Homologação
          </button>
        </div>
      </div>

      {activeTab === 'config' && (
        <div id="secretary-tab-config" role="tabpanel" aria-labelledby="secretary-tab-config-trigger" className="space-y-6">
          {/* Card Secretária IA em primeiro */}
          <Card className="p-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-1">
                  {secretaryProfile?.signature_name?.trim()
                    ? `Assistente – ${secretaryProfile.signature_name.trim()}`
                    : 'Assistente'}
                </h2>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Ativar ou desativar a secretária virtual. Configure os dados da empresa em Planos.
                </p>
              </div>
              {secretaryLoading ? (
                <LoadingSpinner />
              ) : (
                <div className="flex items-center gap-3">
                  {secretaryProfile?.is_active && (
                    <span className="px-3 py-1 bg-green-100 text-green-700 rounded-full text-sm font-medium">
                      Ativa
                    </span>
                  )}
                  <Link to="/billing/company">
                    <Button variant="outline">
                      <Edit className="h-4 w-4 mr-2" />
                      Editar dados da empresa
                    </Button>
                  </Link>
                </div>
              )}
            </div>
            {secretaryProfile && !secretaryLoading && (
              <>
              <div className="mt-6 space-y-8">
                {/* Identidade e ativação */}
                <section className="space-y-4">
                  <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <Label htmlFor="secretary_signature_name">Nome da secretária</Label>
                      <Input
                        id="secretary_signature_name"
                        type="text"
                        value={secretaryProfile.signature_name ?? ''}
                        onChange={(e) => setSecretaryProfile({ ...secretaryProfile, signature_name: e.target.value })}
                        placeholder="Ex: Bia, Ana, Assistente"
                        maxLength={100}
                        className="mt-1 max-w-xs"
                      />
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                        Nome exibido nas mensagens. Use <code className="px-1 py-0.5 bg-gray-200 dark:bg-gray-700 rounded text-xs">{'{{nome}}'}</code> no prompt para referenciar esse nome.
                      </p>
                    </div>
                    <div className="flex items-center justify-between sm:justify-end gap-4 p-4 bg-gray-50 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-600 sm:min-w-[280px]">
                      <div>
                        <Label className="text-base font-semibold text-gray-900 dark:text-gray-100">Ativar assistente</Label>
                        <p className="text-sm text-gray-600 dark:text-gray-400 mt-0.5">
                          Responde no Inbox quando habilitada.
                        </p>
                      </div>
                      <label className="relative inline-flex items-center cursor-pointer flex-shrink-0">
                        <input
                          type="checkbox"
                          checked={secretaryProfile.is_active}
                          disabled={secretarySaving}
                          onChange={(e) => {
                            const isActive = e.target.checked
                            setSecretaryProfile((prev) => (prev ? { ...prev, is_active: isActive } : prev))
                            handleSaveSecretaryProfile({ is_active: isActive })
                          }}
                          className="sr-only peer"
                        />
                        <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600" />
                      </label>
                    </div>
                  </div>
                </section>

                {/* Modelo e tempo */}
                <section>
                  <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">Modelo e tempo de resposta</h3>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                      <Label htmlFor="secretary_model">Modelo do assistente</Label>
                      <select
                        id="secretary_model"
                        value={aiSettings?.secretary_model ?? ''}
                        onChange={(e) => setAiSettings((prev) => (prev ? { ...prev, secretary_model: e.target.value } : prev))}
                        className="mt-1 block w-full rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm bg-white dark:bg-gray-800 focus:border-blue-500 focus:ring-blue-500"
                        disabled={!aiSettings || aiModelOptions.length === 0}
                      >
                        <option value="">Padrão (modelo do agente)</option>
                        {aiSettings?.secretary_model && !aiModelOptions.includes(aiSettings.secretary_model) && (
                          <option value={aiSettings.secretary_model}>{aiSettings.secretary_model}</option>
                        )}
                        {aiModelOptions.map((option) => (
                          <option key={option} value={option}>{option}</option>
                        ))}
                      </select>
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                        Se não escolher, usa o mesmo modelo do agente.
                      </p>
                    </div>
                    <div>
                      <Label htmlFor="secretary_inbox_idle_minutes">Fechar Inbox sem resposta (min)</Label>
                      <Input
                        id="secretary_inbox_idle_minutes"
                        type="number"
                        min={0}
                        max={1440}
                        value={secretaryProfile.inbox_idle_minutes ?? 0}
                        onChange={(e) => setSecretaryProfile({ ...secretaryProfile, inbox_idle_minutes: Number(e.target.value) || 0 })}
                        className={`mt-1 ${secretaryProfileErrors.inbox_idle_minutes ? 'border-red-500' : ''}`}
                      />
                      {secretaryProfileErrors.inbox_idle_minutes && (
                        <p className="text-xs text-red-600 mt-1">{secretaryProfileErrors.inbox_idle_minutes}</p>
                      )}
                    </div>
                    <div>
                      <Label htmlFor="secretary_response_delay_seconds">Aguardar antes de responder (seg)</Label>
                      <Input
                        id="secretary_response_delay_seconds"
                        type="number"
                        min={0}
                        max={120}
                        value={secretaryProfile.response_delay_seconds ?? 0}
                        onChange={(e) => setSecretaryProfile({ ...secretaryProfile, response_delay_seconds: Number(e.target.value) || 0 })}
                        className={`mt-1 ${secretaryProfileErrors.response_delay_seconds ? 'border-red-500' : ''}`}
                      />
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                        0 = imediato. Só na primeira interação; depois as respostas são imediatas.
                      </p>
                      {secretaryProfileErrors.response_delay_seconds && (
                        <p className="text-xs text-red-600 mt-1">{secretaryProfileErrors.response_delay_seconds}</p>
                      )}
                    </div>
                  </div>
                </section>

                {/* Opções */}
                <section className="pt-6 border-t border-gray-200 dark:border-gray-600 space-y-4">
                  <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">Opções</h3>
                  <div className="flex flex-wrap items-center gap-6">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={secretaryProfile.use_memory}
                        onChange={(e) => setSecretaryProfile({ ...secretaryProfile, use_memory: e.target.checked })}
                        className="rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500"
                      />
                      <span className="text-sm text-gray-700 dark:text-gray-300">Usar memória por contato</span>
                    </label>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => setAdvancedOptionsModalOpen(true)}
                      className="flex items-center gap-2"
                    >
                      <SlidersHorizontal className="h-4 w-4" />
                      Configurações avançadas do modelo
                    </Button>
                  </div>
                </section>

                  {advancedOptionsModalOpen && secretaryProfile && (() => {
                    const o = secretaryProfile.advanced_options
                    const safeAdv = (o != null && typeof o === 'object' && !Array.isArray(o))
                      ? { ...DEFAULT_ADVANCED_OPTIONS, ...o }
                      : { ...DEFAULT_ADVANCED_OPTIONS }
                    return (
                      <div className="fixed inset-0 bg-black/50 dark:bg-black/60 flex items-center justify-center z-50 p-4" onClick={() => setAdvancedOptionsModalOpen(false)}>
                        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col border border-gray-200 dark:border-gray-700" onClick={e => e.stopPropagation()}>
                          <div className="p-4 border-b border-gray-200 dark:border-gray-600 flex items-center justify-between flex-shrink-0">
                            <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Configurações avançadas do modelo</h3>
                            <button
                              type="button"
                              onClick={() => setAdvancedOptionsModalOpen(false)}
                              className="text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 p-1 rounded"
                              aria-label="Fechar"
                            >
                              <X className="h-5 w-5" />
                            </button>
                          </div>
                          <div className="p-4 overflow-y-auto flex-1">
                            <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
                              Parâmetros de geração da IA. Os valores padrão já são adequados para uma secretária objetiva.
                            </p>
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                              <div>
                                <Label htmlFor="modal_adv_temperature" className="text-gray-700 dark:text-gray-300">Criatividade (temperature)</Label>
                                <Input
                                  id="modal_adv_temperature"
                                  type="number"
                                  min={0}
                                  max={1}
                                  step={0.05}
                                  value={safeAdv.temperature}
                                  onChange={(e) => setSecretaryProfile({
                                    ...secretaryProfile,
                                    advanced_options: { ...safeAdv, temperature: Number(e.target.value) || 0 },
                                  })}
                                  className="mt-1 max-w-[8rem]"
                                />
                                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">0.2–0.4 = mais objetiva; maior = mais criativa.</p>
                              </div>
                              <div>
                                <Label htmlFor="modal_adv_top_p" className="text-gray-700 dark:text-gray-300">top_p</Label>
                                <Input
                                  id="modal_adv_top_p"
                                  type="number"
                                  min={0.1}
                                  max={1}
                                  step={0.05}
                                  value={safeAdv.top_p}
                                  onChange={(e) => setSecretaryProfile({
                                    ...secretaryProfile,
                                    advanced_options: { ...safeAdv, top_p: Number(e.target.value) || 0.85 },
                                  })}
                                  className="mt-1 max-w-[8rem]"
                                />
                                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">Nucleus sampling; mais baixo = mais conservador.</p>
                              </div>
                              <div>
                                <Label htmlFor="modal_adv_top_k" className="text-gray-700 dark:text-gray-300">top_k</Label>
                                <Input
                                  id="modal_adv_top_k"
                                  type="number"
                                  min={1}
                                  max={100}
                                  value={safeAdv.top_k}
                                  onChange={(e) => setSecretaryProfile({
                                    ...secretaryProfile,
                                    advanced_options: { ...safeAdv, top_k: Number(e.target.value) || 30 },
                                  })}
                                  className="mt-1 max-w-[8rem]"
                                />
                                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">Limita opções de tokens; 20–40 = mais obediente.</p>
                              </div>
                              <div>
                                <Label htmlFor="modal_adv_repeat_penalty" className="text-gray-700 dark:text-gray-300">repeat_penalty</Label>
                                <Input
                                  id="modal_adv_repeat_penalty"
                                  type="number"
                                  min={0.8}
                                  max={2}
                                  step={0.05}
                                  value={safeAdv.repeat_penalty}
                                  onChange={(e) => setSecretaryProfile({
                                    ...secretaryProfile,
                                    advanced_options: { ...safeAdv, repeat_penalty: Number(e.target.value) || 1.15 },
                                  })}
                                  className="mt-1 max-w-[8rem]"
                                />
                                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">Reduz repetições e enrolação.</p>
                              </div>
                              <div>
                                <Label htmlFor="modal_adv_min_p" className="text-gray-700 dark:text-gray-300">min_p</Label>
                                <Input
                                  id="modal_adv_min_p"
                                  type="number"
                                  min={0}
                                  max={0.5}
                                  step={0.01}
                                  value={safeAdv.min_p}
                                  onChange={(e) => setSecretaryProfile({
                                    ...secretaryProfile,
                                    advanced_options: { ...safeAdv, min_p: Number(e.target.value) || 0.05 },
                                  })}
                                  className="mt-1 max-w-[8rem]"
                                />
                                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">Filtra tokens improváveis; ajuda em consistência.</p>
                              </div>
                            </div>
                            <div className="mt-4 flex flex-wrap gap-2">
                              <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                onClick={() => {
                                  setSecretaryProfile({ ...secretaryProfile, advanced_options: null })
                                  handleSaveSecretaryProfile({ advanced_options: null })
                                  setAdvancedOptionsModalOpen(false)
                                }}
                                disabled={secretarySaving}
                              >
                                Restaurar valores padrão
                              </Button>
                              <Button type="button" variant="outline" size="sm" onClick={() => setAdvancedOptionsModalOpen(false)}>
                                Fechar
                              </Button>
                            </div>
                          </div>
                        </div>
                      </div>
                    )
                  })()}
                </div>
                <div className="flex justify-end">
                  <Button onClick={() => handleSaveSecretaryProfile()} disabled={secretarySaving}>
                    <Save className="h-4 w-4 mr-2" />
                    {secretarySaving ? 'Salvando...' : 'Salvar'}
                  </Button>
                </div>
              </>
            )}
          </Card>

          {/* Prompt da Secretária e área de teste abaixo */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card className="p-6 border border-gray-200 dark:border-gray-600">
              <div className="flex items-center gap-3 mb-4">
                <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-indigo-100 dark:bg-indigo-900/40 flex items-center justify-center">
                  <FileText className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Prompt da Secretária</h2>
                  <p className="text-xs text-gray-500 dark:text-gray-400">Instruções do sistema</p>
                </div>
              </div>
              {secretaryLoading || aiSettingsLoading ? (
                <LoadingSpinner />
              ) : (
                <div className="space-y-4">
                  <div>
                    <Label htmlFor="secretary-prompt" className="text-gray-700 dark:text-gray-300">Conteúdo do prompt</Label>
                    <textarea
                      id="secretary-prompt"
                      value={promptDraft}
                      onChange={(e) => {
                        setPromptDraft(e.target.value)
                        if (saveError) setSaveError(null)
                      }}
                      rows={12}
                      className="mt-1 block w-full rounded-lg border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm text-gray-900 dark:text-gray-100 bg-white dark:bg-gray-800 placeholder:text-gray-400 dark:placeholder:text-gray-500 focus:border-blue-500 focus:ring-blue-500"
                      placeholder="Instruções do sistema para a Secretária..."
                    />
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      Use <code className="px-1 py-0.5 bg-gray-200 dark:bg-gray-700 rounded">{'{{nome}}'}</code> no texto para inserir o nome da secretária (ex: &quot;Você se chama {'{{nome}}'}.&quot;).
                    </p>
                    <Button onClick={handleSavePrompt} disabled={secretarySaving} className="mt-2">
                      {secretarySaving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Save className="h-4 w-4 mr-2" />}
                      Salvar prompt
                    </Button>
                    {saveError && <p className="text-sm text-red-600 dark:text-red-400 mt-2">{saveError}</p>}
                  </div>
                </div>
              )}
            </Card>
            <Card className="p-6 border border-gray-200 dark:border-gray-600">
              <div className="flex items-center gap-3 mb-4">
                <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-amber-100 dark:bg-amber-900/40 flex items-center justify-center">
                  <FlaskConical className="h-5 w-5 text-amber-600 dark:text-amber-400" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Área de teste do modelo</h2>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    O teste usa o webhook definido em Configurações &gt; IA.
                  </p>
                </div>
              </div>
              {aiSettingsLoading ? (
                <LoadingSpinner />
              ) : (
                testAreaConfig
              )}
            </Card>
          </div>
        </div>
      )}

      {activeTab === 'homolog' && (
        <div id="secretary-tab-homolog" role="tabpanel" aria-labelledby="secretary-tab-homolog-trigger" className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card className="p-6">
            <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-4">Testar com contexto</h2>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
              Escolha o modelo, opcionalmente um prompt só para o teste, e envie uma mensagem. A conversa real selecionada à direita será enviada como contexto no prompt (se houver).
            </p>
            {testAreaHomolog}
          </Card>
          <Card className="p-6">
            <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-4 flex items-center gap-2">
              <MessageSquare className="h-5 w-5" />
              Conversa real no prompt
            </h2>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
              Selecione uma conversa. Ela será enviada como contexto no prompt ao testar ao lado.
            </p>
            <div className="space-y-3">
              <div>
                <Label>Conversa</Label>
                <select
                  value={selectedConversationId}
                  onChange={(e) => setSelectedConversationId(e.target.value)}
                  className="mt-1 block w-full rounded-md border border-gray-300 dark:border-gray-600 px-3 py-2 text-sm bg-white dark:bg-gray-800"
                  disabled={conversationsLoading}
                >
                  <option value="">Nenhuma (só prompt de sistema)</option>
                  {conversations.map((c) => (
                    <option key={c.id} value={c.id}>{c.contact_name || c.contact_phone || c.id}</option>
                  ))}
                </select>
                {conversationsLoading && <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Carregando conversas...</p>}
              </div>
              {messagesLoading && selectedConversationId && (
                <p className="text-sm text-gray-500 dark:text-gray-400 flex items-center gap-1">
                  <Loader2 className="h-4 w-4 animate-spin" /> Carregando mensagens...
                </p>
              )}
              {!selectedConversationId && !conversationsLoading && (
                <p className="text-xs text-amber-700 dark:text-amber-200 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg px-3 py-2">
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
