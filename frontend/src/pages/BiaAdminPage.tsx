/**
 * Página admin da BIA: configuração do prompt, webhook e teste.
 * Acesso travado por chave única (BIA_ADMIN_ACCESS_KEY).
 * Layout: colunas lado a lado (config | teste BIA).
 * Opção de carregar conversa real do banco e enviá-la no prompt do teste.
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import { Lock, Send, Save, Loader2, MessageSquare } from 'lucide-react'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Label } from '../components/ui/Label'
import { Input } from '../components/ui/Input'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import { api } from '../lib/api'

const BIA_KEY_STORAGE = 'bia_admin_key_valid'
/** Limite do prompt no gateway (backend rejeita acima disso). */
const MAX_PROMPT_LENGTH = 10000

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
  const [testMessage, setTestMessage] = useState('')
  const [testSystemPrompt, setTestSystemPrompt] = useState('')
  const [testMessages, setTestMessages] = useState<{ role: 'user' | 'assistant'; content: string }[]>([])
  const [testLoading, setTestLoading] = useState(false)
  const [testError, setTestError] = useState<string | null>(null)

  const [conversations, setConversations] = useState<ConversationOption[]>([])
  const [conversationsLoading, setConversationsLoading] = useState(false)
  const [selectedConversationId, setSelectedConversationId] = useState<string>('')
  const [loadedConversationText, setLoadedConversationText] = useState<string>('')
  const [messagesLoading, setMessagesLoading] = useState(false)

  const pollingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const pollingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

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
    const clearPolling = () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current)
        pollingIntervalRef.current = null
      }
      if (pollingTimeoutRef.current) {
        clearTimeout(pollingTimeoutRef.current)
        pollingTimeoutRef.current = null
      }
      setTestLoading(false)
    }
    const finishWithMessage = (content: string) => {
      setTestMessages((prev) => {
        const rest = prev.slice(0, -1)
        return [...rest, { role: 'assistant' as const, content }]
      })
      clearPolling()
    }
    try {
      let prompt = testSystemPrompt.trim()
      if (loadedConversationText.trim()) {
        prompt = (prompt ? prompt + '\n\n' : '') + '---\nConversa real (contexto):\n' + loadedConversationText.trim()
      }
      if (prompt.length > MAX_PROMPT_LENGTH) {
        prompt = prompt.slice(0, MAX_PROMPT_LENGTH)
        setTestError(`Prompt truncado a ${MAX_PROMPT_LENGTH} caracteres (limite do backend).`)
      }
      const body: any = {
        message,
        model: aiSettings.agent_model || 'llama3.2',
        context: { action: 'model_test', model: aiSettings.agent_model || 'llama3.2' },
        messages: [...testMessages, { role: 'user', content: message }],
      }
      if (prompt) body.prompt = prompt
      const res = await api.post('/ai/gateway/test/', body)

      if (res.data?.deferred && res.data?.job_id) {
        setTestMessages((prev) => [...prev, { role: 'assistant', content: 'Deixe-me pensar...' }])
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
      setTestMessages((prev) => [...prev, { role: 'assistant', content: reply }])
      setTestError(null)
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
    <div className="max-w-[1600px] mx-auto p-4 md:p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">BIA – Configuração e teste</h1>
        <p className="text-sm text-gray-600 mt-1">
          Prompt da secretária, webhook e área de teste. Alterações do prompt são salvas no perfil da BIA.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Coluna 1: Configuração */}
        <Card className="p-6 h-fit">
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
                  onChange={(e) => {
                    setPromptDraft(e.target.value)
                    if (saveError) setSaveError(null)
                  }}
                  rows={10}
                  className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:ring-blue-500"
                  placeholder="Instruções do sistema para a BIA..."
                />
                <Button onClick={handleSavePrompt} disabled={secretarySaving} className="mt-2">
                  {secretarySaving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Save className="h-4 w-4 mr-2" />}
                  Salvar prompt
                </Button>
                {saveError && <p className="text-sm text-red-600 mt-2">{saveError}</p>}
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

        {/* Coluna 2: Conversa real no prompt */}
        <Card className="p-6">
            <h2 className="text-lg font-medium text-gray-900 mb-4 flex items-center gap-2">
              <MessageSquare className="h-5 w-5" />
              Conversa real no prompt
            </h2>
            <p className="text-sm text-gray-600 mb-4">
              Selecione uma conversa do banco. Ela será carregada e enviada como contexto no prompt ao testar a BIA abaixo.
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
                    <option key={c.id} value={c.id}>
                      {c.contact_name || c.contact_phone || c.id}
                    </option>
                  ))}
                </select>
                {conversationsLoading && (
                  <p className="text-xs text-gray-500 mt-1">Carregando conversas...</p>
                )}
              </div>
              {messagesLoading && selectedConversationId && (
                <p className="text-sm text-gray-500 flex items-center gap-1">
                  <Loader2 className="h-4 w-4 animate-spin" /> Carregando mensagens...
                </p>
              )}
              {loadedConversationText && !messagesLoading && (
                <>
                  <div className="rounded border border-gray-200 bg-gray-50 p-3 max-h-[200px] overflow-y-auto">
                    <Label className="text-gray-700 text-xs">Conversa carregada (será enviada no prompt)</Label>
                    <pre className="mt-1 text-sm whitespace-pre-wrap font-sans">{loadedConversationText}</pre>
                  </div>
                  {loadedConversationText.length > 8000 && (
                    <p className="text-xs text-amber-600">
                      Conversa longa: pode ser truncada no envio (máx. {MAX_PROMPT_LENGTH.toLocaleString()} caracteres).
                    </p>
                  )}
                </>
              )}
            </div>
        </Card>

        {/* Coluna 3: Testar prompt BIA */}
        <Card className="p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-4">Testar prompt (BIA)</h2>
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
            <div className="min-h-[140px] max-h-[220px] overflow-y-auto rounded border border-gray-200 bg-gray-50 p-3 space-y-2">
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
    </div>
  )
}
