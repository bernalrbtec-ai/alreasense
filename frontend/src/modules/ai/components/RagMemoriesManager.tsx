import { useState, useEffect, useCallback, useRef, Fragment } from 'react'
import { Check, X, Edit, RefreshCw, Search, FileText, ChevronDown, ChevronRight, Save, Layers, Expand, Star } from 'lucide-react'
import { Button } from '../../../components/ui/Button'
import { Card } from '../../../components/ui/Card'
import { Input } from '../../../components/ui/Input'
import { Label } from '../../../components/ui/Label'
import LoadingSpinner from '../../../components/ui/LoadingSpinner'
import { toast } from 'sonner'
import { api } from '../../../lib/api'
import { showErrorToast, showLoadingToast, updateToastSuccess, updateToastError } from '../../../lib/toastHelper'
import { useAuthStore } from '../../../stores/authStore'

export interface ConversationSummaryItem {
  id: number
  conversation_id: string
  contact_phone: string
  contact_name: string
  contact_tags?: string[]
  content: string
  metadata: Record<string, unknown>
  status: 'pending' | 'approved' | 'rejected'
  status_display?: string
  is_auto_approved?: boolean
  is_auto_rejected?: boolean
  is_consolidated?: boolean
  reviewed_at: string | null
  reviewed_by_id: number | null
  created_at: string
  updated_at: string
}

interface PaginatedResponse {
  count: number
  next: string | null
  previous: string | null
  results: ConversationSummaryItem[]
  consolidated_content_by_contact?: Record<string, string>
}

const STATUS_OPTIONS: { value: '' | 'pending' | 'approved' | 'rejected'; label: string }[] = [
  { value: '', label: 'Todos' },
  { value: 'pending', label: 'Pendente' },
  { value: 'approved', label: 'Aprovado' },
  { value: 'rejected', label: 'Reprovado' },
]

/** Valor 1-5 válido para satisfação (para média e estrelas). */
function parseSatisfactionValue(value: unknown): number | null {
  if (value == null || value === '') return null
  const n = typeof value === 'number' ? value : Number(value)
  if (Number.isNaN(n) || n < 1 || n > 5) return null
  return Math.round(n)
}

/** Média da satisfação (1-5) de uma lista de itens; null se nenhum válido. Valor inteiro para estrelas. */
function averageSatisfactionValue(summaries: ConversationSummaryItem[]): number | null {
  const values = summaries.map((s) => parseSatisfactionValue(s.metadata?.satisfaction)).filter((n): n is number => n !== null)
  if (values.length === 0) return null
  const avg = values.reduce((a, b) => a + b, 0) / values.length
  return Math.round(avg)
}

/** Renderiza 5 estrelas para satisfação 1-5; "—" se inválido. */
function SatisfactionStars({ value }: { value: unknown }) {
  const n = parseSatisfactionValue(value)
  if (n === null) return <span className="text-gray-400 dark:text-gray-500">—</span>
  return (
    <span className="inline-flex items-center gap-0.5" title={`Satisfação: ${n}`} aria-label={`Satisfação: ${n} de 5`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <Star
          key={i}
          className={`h-4 w-4 shrink-0 ${i <= n ? 'fill-amber-400 text-amber-500 dark:fill-amber-500 dark:text-amber-400' : 'text-gray-300 dark:text-gray-600'}`}
          strokeWidth={i <= n ? 0 : 1.5}
        />
      ))}
    </span>
  )
}

/** Extrai texto de resumo de um objeto (summary, resumo, text, content). */
function getSummaryFromPayload(parsed: Record<string, unknown>): string {
  for (const key of ['summary', 'resumo', 'text', 'content']) {
    const v = parsed[key]
    if (typeof v === 'string' && v.trim()) return v.trim()
  }
  return ''
}

/** Normaliza conteúdo para exibir no modal de edição: sempre string; se for objeto ou JSON válido, formata. */
function normalizeContentForEdit(content: unknown): string {
  if (content == null) return ''
  if (typeof content === 'object') return JSON.stringify(content, null, 2)
  let s = String(content).trim()
  if (!s) return ''
  // Tenta parsear JSON (algumas respostas vêm com BOM ou espaços)
  const toTry = [s, s.replace(/^\uFEFF/, '')]
  for (const str of toTry) {
    try {
      const parsed = JSON.parse(str) as unknown
      return JSON.stringify(parsed, null, 2)
    } catch {
      /* continua */
    }
  }
  return s
}

/** Prévia do conteúdo para a lista: se for JSON/objeto com summary/resumo/text/content, usa esse texto; senão trunca. */
function getContentPreview(content: unknown, maxLen: number): { text: string; title: string } {
  const raw = content == null ? '' : typeof content === 'string' ? content : JSON.stringify(content)
  const full = raw.trim() || '—'
  let parsed: Record<string, unknown> | null = null
  if (typeof content === 'object' && content !== null) {
    parsed = content as Record<string, unknown>
  } else {
    try {
      parsed = JSON.parse(raw.replace(/^\uFEFF/, '')) as Record<string, unknown>
    } catch {
      /* não é JSON */
    }
  }
  const summary = parsed ? getSummaryFromPayload(parsed) : ''
  if (summary) {
    const text = summary.length > maxLen ? `${summary.slice(0, maxLen)}…` : summary
    return { text, title: full }
  }
  const text = full === '—' ? '—' : (full.length > maxLen ? `${full.slice(0, maxLen)}…` : full)
  return { text, title: full }
}

/** Agrupa resumos por contato; cada grupo ordenado por conversa mais recente primeiro. */
function groupSummariesByContact(items: ConversationSummaryItem[]): { contactKey: string; contactLabel: string; contactPhone: string; contactTags: string[]; hasConsolidation: boolean; mostRecentAt: string; summaries: ConversationSummaryItem[] }[] {
  const byContact = new Map<string, ConversationSummaryItem[]>()
  for (const item of items) {
    const key = (item.contact_phone || '').trim() || `no-phone-${item.id}`
    if (!byContact.has(key)) byContact.set(key, [])
    byContact.get(key)!.push(item)
  }
  const groups: { contactKey: string; contactLabel: string; contactPhone: string; contactTags: string[]; hasConsolidation: boolean; mostRecentAt: string; summaries: ConversationSummaryItem[] }[] = []
  for (const [contactKey, summaries] of byContact) {
    const sorted = [...summaries].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    const mostRecent = sorted[0]
    const dateStr = (mostRecent.metadata?.closed_at as string) || mostRecent.created_at
    const d = dateStr ? new Date(dateStr) : null
    const mostRecentAt = d ? d.toLocaleString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit', day: '2-digit', month: '2-digit', year: 'numeric' }) : '—'
    const contactLabel = mostRecent.contact_name || mostRecent.contact_phone || 'Sem nome'
    const contactTags = Array.isArray(mostRecent.contact_tags) ? mostRecent.contact_tags : []
    const hasConsolidation = summaries.some((s) => s.is_consolidated)
    groups.push({ contactKey, contactLabel, contactPhone: mostRecent.contact_phone || '', contactTags, hasConsolidation, mostRecentAt, summaries: sorted })
  }
  groups.sort((a, b) => {
    const tA = new Date(a.summaries[0]?.created_at ?? 0).getTime()
    const tB = new Date(b.summaries[0]?.created_at ?? 0).getTime()
    return tB - tA
  })
  return groups
}

export function RagMemoriesManager() {
  const [items, setItems] = useState<ConversationSummaryItem[]>([])
  const [consolidatedContentByContact, setConsolidatedContentByContact] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [count, setCount] = useState(0)
  const [nextUrl, setNextUrl] = useState<string | null>(null)
  const [prevUrl, setPrevUrl] = useState<string | null>(null)

  const [status, setStatus] = useState<'' | 'pending' | 'approved' | 'rejected'>('')
  const [contactPhone, setContactPhone] = useState('')
  const [contactName, setContactName] = useState('')
  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')
  const [limit] = useState(20)
  const [offset, setOffset] = useState(0)

  const [reprocessModalOpen, setReprocessModalOpen] = useState(false)
  const [reprocessScope, setReprocessScope] = useState<'all' | 'contact'>('all')
  const [reprocessSummaryStatus, setReprocessSummaryStatus] = useState<'all' | 'approved' | 'pending' | 'rejected'>('all')
  const [reprocessContactPhone, setReprocessContactPhone] = useState('')
  const [reprocessSubmitting, setReprocessSubmitting] = useState(false)
  const [reprocessNotifyOptions, setReprocessNotifyOptions] = useState<{ has_smtp: boolean; has_whatsapp: boolean } | null>(null)
  const [reprocessNotifyWhatsapp, setReprocessNotifyWhatsapp] = useState(false)
  const [reprocessNotifyWhatsappPhone, setReprocessNotifyWhatsappPhone] = useState('')
  const [reprocessNotifyEmail, setReprocessNotifyEmail] = useState(false)
  const [reprocessNotifyEmailAddress, setReprocessNotifyEmailAddress] = useState('')

  const [reprocessJobId, setReprocessJobId] = useState<string | null>(null)
  const [reprocessJobData, setReprocessJobData] = useState<{
    status: string; total: number; processed: number;
    approved: number; rejected: number; percent: number;
    notify_whatsapp_requested?: boolean; notify_email_requested?: boolean;
  } | null>(null)
  const [reprocessProgressDismissed, setReprocessProgressDismissed] = useState(false)
  const { user: authUser } = useAuthStore()
  const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const pollErrorCountRef = useRef(0)

  const [editModalOpen, setEditModalOpen] = useState(false)
  const [editItem, setEditItem] = useState<ConversationSummaryItem | null>(null)
  const [editContent, setEditContent] = useState('')
  const [editSubmitting, setEditSubmitting] = useState(false)

  const [selectedSummaryIds, setSelectedSummaryIds] = useState<number[]>([])
  const [consolidateModalOpen, setConsolidateModalOpen] = useState(false)
  const [consolidateSubmitting, setConsolidateSubmitting] = useState(false)
  const [consolidateByContactModalOpen, setConsolidateByContactModalOpen] = useState(false)
  const [consolidateByContactSubmitting, setConsolidateByContactSubmitting] = useState(false)
  const [consolidateAllModalOpen, setConsolidateAllModalOpen] = useState(false)
  const [consolidateAllSubmitting, setConsolidateAllSubmitting] = useState(false)
  const [consolidatedFullModalContent, setConsolidatedFullModalContent] = useState<string | null>(null)
  const [collapsedContactKeys, setCollapsedContactKeys] = useState<Set<string>>(new Set())

  const toggleContactCollapsed = useCallback((contactKey: string) => {
    setCollapsedContactKeys((prev) => {
      const next = new Set(prev)
      if (next.has(contactKey)) next.delete(contactKey)
      else next.add(contactKey)
      return next
    })
  }, [])

  useEffect(() => {
    if (consolidatedFullModalContent === null) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setConsolidatedFullModalContent(null)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [consolidatedFullModalContent])

  const [autoApproveOpen, setAutoApproveOpen] = useState(false)
  const [autoApproveConfig, setAutoApproveConfig] = useState<{
    enabled: boolean
    criteria: Record<string, { enabled: boolean; value?: number }>
    criterion_defaults?: Record<string, { label: string; type: string; default: unknown }>
    reject_enabled?: boolean
    reject_criteria?: Record<string, { enabled: boolean; value?: number }>
    reject_criterion_defaults?: Record<string, { label: string; type: string; default: unknown }>
  } | null>(null)
  const [autoApproveLoading, setAutoApproveLoading] = useState(false)
  const [autoApproveSaving, setAutoApproveSaving] = useState(false)

  const fetchAutoApproveConfig = useCallback(async () => {
    setAutoApproveLoading(true)
    try {
      const { data } = await api.get<{
        enabled: boolean
        criteria: Record<string, { enabled: boolean; value?: number }>
        criterion_defaults?: Record<string, { label: string; type: string; default: unknown }>
        reject_enabled?: boolean
        reject_criteria?: Record<string, { enabled: boolean; value?: number }>
        reject_criterion_defaults?: Record<string, { label: string; type: string; default: unknown }>
      }>('ai/summaries/auto-approve-config/')
      setAutoApproveConfig(data)
    } catch (e) {
      showErrorToast('carregar', 'Fluxo de Controle', e)
    } finally {
      setAutoApproveLoading(false)
    }
  }, [])

  useEffect(() => {
    if (autoApproveOpen && !autoApproveConfig && !autoApproveLoading) {
      fetchAutoApproveConfig()
    }
  }, [autoApproveOpen, autoApproveConfig, autoApproveLoading, fetchAutoApproveConfig])

  useEffect(() => {
    if (reprocessModalOpen) {
      setReprocessNotifyOptions(null)
      setReprocessNotifyWhatsapp(false)
      setReprocessNotifyEmail(false)
      setReprocessNotifyWhatsappPhone(authUser?.phone ?? '')
      setReprocessNotifyEmailAddress(authUser?.email ?? '')
      api.get<{ has_smtp: boolean; has_whatsapp: boolean }>('ai/summaries/reprocess/notify-options/')
        .then(({ data }) => setReprocessNotifyOptions(data))
        .catch(() => setReprocessNotifyOptions({ has_smtp: false, has_whatsapp: false }))
    }
  }, [reprocessModalOpen, authUser?.phone, authUser?.email])

  const stopPolling = useCallback(() => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current)
      pollIntervalRef.current = null
    }
    pollErrorCountRef.current = 0
  }, [])

  const startPolling = useCallback((jobId: string) => {
    stopPolling()
    pollIntervalRef.current = setInterval(async () => {
      try {
        const { data } = await api.get<{
          status: string; total: number; processed: number;
          approved: number; rejected: number; percent: number
        }>(`ai/summaries/reprocess/${jobId}/status/`)
        setReprocessJobData(data)
        if (data.status === 'done' || data.status === 'stale') {
          setReprocessProgressDismissed(false)
          stopPolling()
        }
        pollErrorCountRef.current = 0
      } catch {
        pollErrorCountRef.current += 1
        if (pollErrorCountRef.current >= 3) {
          stopPolling()
          setReprocessJobData((prev) => prev ? { ...prev, status: 'error' } : prev)
        }
      }
    }, 4000)
  }, [stopPolling])

  useEffect(() => {
    return () => { stopPolling() }
  }, [stopPolling])

  const handleSaveAutoApproveConfig = async () => {
    if (!autoApproveConfig) return
    setAutoApproveSaving(true)
    try {
      const payload: { enabled: boolean; criteria: Record<string, { enabled: boolean; value?: number }>; reject_enabled?: boolean; reject_criteria?: Record<string, { enabled: boolean; value?: number }> } = {
        enabled: autoApproveConfig.enabled,
        criteria: autoApproveConfig.criteria,
      }
      if (autoApproveConfig.reject_enabled !== undefined) payload.reject_enabled = autoApproveConfig.reject_enabled
      if (autoApproveConfig.reject_criteria !== undefined) payload.reject_criteria = autoApproveConfig.reject_criteria
      await api.patch('ai/summaries/auto-approve-config/', payload)
      toast.success('Fluxo de Controle salvo.')
    } catch (e: any) {
      showErrorToast('salvar', 'Fluxo de Controle', e)
    } finally {
      setAutoApproveSaving(false)
    }
  }

  const fetchList = useCallback(async (off = 0, options?: { clearOnError?: boolean }) => {
    const clearOnError = options?.clearOnError !== false
    setLoading(true)
    try {
      const params: Record<string, string | number> = { limit, offset: off }
      if (status) params.status = status
      if (contactPhone.trim()) params.contact_phone = contactPhone.trim()
      if (contactName.trim()) params.contact_name = contactName.trim()
      if (fromDate) params.from_date = fromDate
      if (toDate) params.to_date = toDate
      const { data } = await api.get<PaginatedResponse>('ai/summaries/', { params })
      setItems(data.results ?? [])
      setConsolidatedContentByContact(data.consolidated_content_by_contact ?? {})
      setCount(data.count)
      setNextUrl(data.next)
      setPrevUrl(data.previous)
    } catch (e) {
      showErrorToast('carregar', 'Resumos', e)
      if (clearOnError) {
        setItems([])
        setConsolidatedContentByContact({})
        setCount(0)
        setNextUrl(null)
        setPrevUrl(null)
      }
    } finally {
      setLoading(false)
    }
  }, [limit, status, contactPhone, contactName, fromDate, toDate])

  useEffect(() => {
    if (reprocessJobData?.status === 'done' || reprocessJobData?.status === 'stale') {
      fetchList(0)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reprocessJobData?.status])

  useEffect(() => {
    fetchList(offset)
  }, [fetchList, offset])

  // Iniciar todos os contatos retraídos; expandir só ao clicar
  useEffect(() => {
    const groups = groupSummariesByContact(items)
    setCollapsedContactKeys(new Set(groups.map((g) => g.contactKey)))
  }, [items])

  const handleSearch = () => {
    setOffset(0)
    fetchList(0)
  }

  const handleApprove = async (item: ConversationSummaryItem) => {
    const toastId = showLoadingToast('atualizar', 'Resumo')
    try {
      const { data } = await api.patch<ConversationSummaryItem>(`ai/summaries/${item.id}/`, { action: 'approve' })
      updateToastSuccess(toastId, 'atualizar', 'Resumo')
      setItems((prev) => prev.map((i) => (i.id === item.id ? { ...i, ...data } : i)))
      await fetchList(offset, { clearOnError: false })
    } catch (e) {
      updateToastError(toastId, 'atualizar', 'Resumo', e)
    }
  }

  const handleReject = async (item: ConversationSummaryItem) => {
    const toastId = showLoadingToast('atualizar', 'Resumo')
    try {
      const { data } = await api.patch<ConversationSummaryItem>(`ai/summaries/${item.id}/`, { action: 'reject' })
      updateToastSuccess(toastId, 'atualizar', 'Resumo')
      setItems((prev) => prev.map((i) => (i.id === item.id ? { ...i, ...data } : i)))
      await fetchList(offset, { clearOnError: false })
    } catch (e) {
      updateToastError(toastId, 'atualizar', 'Resumo', e)
    }
  }

  const openEditModal = (item: ConversationSummaryItem) => {
    setEditItem(item)
    setEditContent(normalizeContentForEdit(item.content))
    setEditModalOpen(true)
  }

  const handleEditSubmit = async () => {
    if (!editItem) return
    setEditSubmitting(true)
    try {
      await api.patch(`ai/summaries/${editItem.id}/`, { action: 'edit', content: editContent })
      toast.success('Resumo atualizado')
      setEditModalOpen(false)
      setEditItem(null)
      fetchList(offset)
    } catch (e) {
      showErrorToast('salvar', 'Resumo', e)
    } finally {
      setEditSubmitting(false)
    }
  }

  const handleReprocessSubmit = async () => {
    if (reprocessScope === 'contact' && !reprocessContactPhone.trim()) {
      toast.error('Informe o telefone do contato para reprocessar por contato.')
      return
    }
    if (reprocessNotifyWhatsapp && !reprocessNotifyWhatsappPhone.trim()) {
      toast.error('Marque "Notificar por WhatsApp" apenas se informar o número para envio.')
      return
    }
    if (reprocessNotifyEmail && !reprocessNotifyEmailAddress.trim()) {
      toast.error('Marque "Notificar por Email" apenas se informar o email para envio.')
      return
    }
    setReprocessSubmitting(true)
    try {
      const payload: { scope: string; summary_status?: string; contact_phone?: string; notify_whatsapp_phone?: string; notify_email?: string } = { scope: reprocessScope }
      if (reprocessSummaryStatus !== 'all') payload.summary_status = reprocessSummaryStatus
      if (reprocessScope === 'contact') payload.contact_phone = reprocessContactPhone.trim()
      if (reprocessNotifyWhatsapp && reprocessNotifyWhatsappPhone.trim()) payload.notify_whatsapp_phone = reprocessNotifyWhatsappPhone.trim()
      if (reprocessNotifyEmail && reprocessNotifyEmailAddress.trim()) payload.notify_email = reprocessNotifyEmailAddress.trim()
      const { data } = await api.post<{ status: string; enqueued: number; total_eligible: number; job_id?: string }>('ai/summaries/reprocess/', payload)
      setReprocessModalOpen(false)
      setReprocessScope('all')
      setReprocessSummaryStatus('all')
      setReprocessContactPhone('')
      setReprocessNotifyWhatsapp(false)
      setReprocessNotifyWhatsappPhone('')
      setReprocessNotifyEmail(false)
      setReprocessNotifyEmailAddress('')
      if (data.job_id && data.enqueued > 0) {
        setReprocessProgressDismissed(false)
        setReprocessJobId(data.job_id)
        setReprocessJobData({ status: 'running', total: data.enqueued, processed: 0, approved: 0, rejected: 0, percent: 0 })
        startPolling(data.job_id)
      } else {
        toast.success(`${data.enqueued} conversa(s) enfileirada(s). Total elegível: ${data.total_eligible}`)
        fetchList(offset)
      }
    } catch (e: any) {
      showErrorToast('iniciar', 'Reprocessamento', e)
    } finally {
      setReprocessSubmitting(false)
    }
  }

  const handleCloseJobModal = () => {
    stopPolling()
    setReprocessJobId(null)
    setReprocessJobData(null)
    setReprocessProgressDismissed(false)
    fetchList(0)
  }

  const toggleSummarySelection = (id: number, approved: boolean) => {
    if (!approved) return
    setSelectedSummaryIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    )
  }

  const handleConsolidateConfirm = async () => {
    if (selectedSummaryIds.length < 2) return
    setConsolidateSubmitting(true)
    try {
      const { data } = await api.post<{ ok: boolean; message: string; summaries_count?: number }>('ai/summaries/consolidate/', { summary_ids: selectedSummaryIds })
      const n = data.summaries_count ?? selectedSummaryIds.length
      toast.success(`${n} resumo(s) consolidado(s) em uma memória para o contato.`)
      setConsolidateModalOpen(false)
      setSelectedSummaryIds([])
      fetchList(offset)
    } catch (e: any) {
      const msg = e?.response?.data?.error || 'Erro ao consolidar.'
      toast.error(msg)
    } finally {
      setConsolidateSubmitting(false)
    }
  }

  const handleConsolidateByContactConfirm = async () => {
    const phone = contactPhone.trim()
    if (!phone) return
    setConsolidateByContactSubmitting(true)
    try {
      const { data } = await api.post<{ ok: boolean; message: string; summaries_count?: number }>('ai/summaries/consolidate-by-contact/', { contact_phone: phone })
      const n = data.summaries_count ?? 0
      toast.success(n ? `${n} resumo(s) consolidado(s) em uma memória para este contato.` : 'Resumos consolidados com sucesso.')
      setConsolidateByContactModalOpen(false)
      fetchList(offset)
    } catch (e: any) {
      const msg = e?.response?.data?.error || 'Erro ao consolidar.'
      toast.error(msg)
    } finally {
      setConsolidateByContactSubmitting(false)
    }
  }

  const handleConsolidateAllConfirm = async () => {
    setConsolidateAllSubmitting(true)
    try {
      const { data } = await api.post<{ ok: boolean; contacts_consolidated: number; contacts_failed: number; message: string }>('ai/summaries/consolidate-all/')
      const ok = data.contacts_consolidated ?? 0
      const fail = data.contacts_failed ?? 0
      if (fail > 0) {
        toast.success(`${ok} contato(s) consolidado(s). ${fail} falha(s).`)
      } else {
        toast.success(ok ? `${ok} contato(s) consolidado(s).` : 'Nenhum contato com 2+ aprovados para consolidar.')
      }
      setConsolidateAllModalOpen(false)
      fetchList(offset)
    } catch (e: any) {
      const msg = e?.response?.data?.error || 'Erro ao consolidar todos.'
      toast.error(msg)
    } finally {
      setConsolidateAllSubmitting(false)
    }
  }

  const criterionOrder = ['min_words', 'max_words', 'min_messages', 'has_subject', 'no_placeholders', 'sentiment_not_negative', 'satisfaction_min', 'confidence_min']
  const rejectCriterionOrder = ['reject_confidence_below', 'reject_no_subject', 'reject_negative_sentiment', 'reject_min_words_below']

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <button
          type="button"
          onClick={() => setAutoApproveOpen((o) => !o)}
          className="flex items-center gap-2 w-full text-left font-medium text-gray-900 dark:text-gray-100"
        >
          {autoApproveOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          Fluxo de Controle
        </button>
        {autoApproveOpen && (
          <div className="mt-4 pt-4 border-t border-gray-200">
            {autoApproveLoading ? (
              <div className="flex justify-center py-4"><LoadingSpinner /></div>
            ) : autoApproveConfig ? (
              <div className="space-y-4">
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {/* Aprovação automática */}
                  <div className="rounded-lg border border-gray-200 bg-gray-50/50 p-4">
                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        id="auto-approve-enabled"
                        checked={autoApproveConfig.enabled}
                        onChange={(e) => setAutoApproveConfig((c) => c ? { ...c, enabled: e.target.checked } : c)}
                      />
                      <Label htmlFor="auto-approve-enabled" className="text-sm font-medium">Aprovação automática</Label>
                    </div>
                    <p className="text-xs text-gray-500 mt-1 ml-6">Resumos que passarem em <strong>todos</strong> os critérios marcados serão aprovados e enviados ao RAG.</p>
                    <div className="space-y-2 mt-3 ml-6">
                      {criterionOrder.map((cid) => {
                        const c = autoApproveConfig.criteria[cid]
                        const def = autoApproveConfig.criterion_defaults?.[cid]
                        if (!c) return null
                        const isNumber = def?.type === 'number'
                        return (
                          <div key={cid} className="grid grid-cols-[auto_minmax(0,1fr)_5rem] gap-2 items-center">
                            <input
                              type="checkbox"
                              id={`crit-${cid}`}
                              checked={c.enabled}
                              onChange={(e) => setAutoApproveConfig((cfg) => {
                                if (!cfg) return cfg
                                const next = { ...cfg.criteria[cid], enabled: e.target.checked }
                                return { ...cfg, criteria: { ...cfg.criteria, [cid]: next } }
                              })}
                            />
                            <Label htmlFor={`crit-${cid}`} className="text-sm truncate min-w-0">{def?.label ?? cid}</Label>
                            {isNumber ? (
                              <Input
                                type="number"
                                min={cid === 'confidence_min' ? 0 : cid === 'satisfaction_min' ? 1 : undefined}
                                max={cid === 'confidence_min' ? 1 : cid === 'satisfaction_min' ? 5 : undefined}
                                value={c.value ?? def?.default ?? ''}
                                onChange={(e) => {
                                  const raw = e.target.value
                                  const v = raw === '' ? undefined : Number(raw)
                                  const safe = (v !== undefined && !Number.isNaN(v)) ? v : undefined
                                  setAutoApproveConfig((cfg) => {
                                    if (!cfg) return cfg
                                    return { ...cfg, criteria: { ...cfg.criteria, [cid]: { ...cfg.criteria[cid], value: safe } } }
                                  })
                                }}
                                className="w-full min-w-0 text-sm"
                                disabled={!c.enabled}
                              />
                            ) : (
                              <span />
                            )}
                          </div>
                        )
                      })}
                    </div>
                  </div>
                  {/* Reprovação automática */}
                  <div className="rounded-lg border border-gray-200 bg-gray-50/50 p-4">
                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        id="reject-enabled"
                        checked={autoApproveConfig.reject_enabled ?? false}
                        onChange={(e) => setAutoApproveConfig((c) => c ? { ...c, reject_enabled: e.target.checked } : c)}
                      />
                      <Label htmlFor="reject-enabled" className="text-sm font-medium">Reprovação automática</Label>
                    </div>
                    <p className="text-xs text-gray-500 mt-1 ml-6">Resumos que falharem em <strong>qualquer</strong> critério marcado serão reprovados automaticamente.</p>
                    <div className="space-y-2 mt-3 ml-6">
                      {rejectCriterionOrder.map((cid) => {
                        const rej = (autoApproveConfig.reject_criteria || {})[cid]
                        const def = autoApproveConfig.reject_criterion_defaults?.[cid]
                        if (!rej && !def) return null
                        const c = rej || { enabled: false, value: def?.default as number | undefined }
                        const isNumber = def?.type === 'number'
                        return (
                          <div key={cid} className="grid grid-cols-[auto_minmax(0,1fr)_5rem] gap-2 items-center">
                            <input
                              type="checkbox"
                              id={`rej-${cid}`}
                              checked={c.enabled}
                              onChange={(e) => setAutoApproveConfig((cfg) => {
                                if (!cfg) return cfg
                                const reject_criteria = { ...(cfg.reject_criteria || {}), [cid]: { ...(cfg.reject_criteria?.[cid] || {}), enabled: e.target.checked } }
                                return { ...cfg, reject_criteria }
                              })}
                            />
                            <Label htmlFor={`rej-${cid}`} className="text-sm truncate min-w-0">{def?.label ?? cid}</Label>
                            {isNumber ? (
                              <Input
                                type="number"
                                min={cid === 'reject_confidence_below' ? 0 : undefined}
                                max={cid === 'reject_confidence_below' ? 1 : undefined}
                                step={cid === 'reject_confidence_below' ? 0.1 : undefined}
                                value={c.value ?? def?.default ?? ''}
                                onChange={(e) => {
                                  const raw = e.target.value
                                  const v = raw === '' ? undefined : Number(raw)
                                  const safe = (v !== undefined && !Number.isNaN(v)) ? v : undefined
                                  setAutoApproveConfig((cfg) => {
                                    if (!cfg) return cfg
                                    const reject_criteria = { ...(cfg.reject_criteria || {}), [cid]: { ...(cfg.reject_criteria?.[cid] || {}), value: safe } }
                                    return { ...cfg, reject_criteria }
                                  })
                                }}
                                className="w-full min-w-0 text-sm"
                                disabled={!c.enabled}
                              />
                            ) : (
                              <span />
                            )}
                          </div>
                        )
                      })}
                    </div>
                  </div>
                </div>
                <div className="flex justify-end pt-2">
                  <Button size="sm" onClick={handleSaveAutoApproveConfig} disabled={autoApproveSaving}>
                    <Save className="h-4 w-4 mr-1" />
                    {autoApproveSaving ? 'Salvando…' : 'Salvar'}
                  </Button>
                </div>
              </div>
            ) : (
              <p className="text-sm text-gray-500 dark:text-gray-400">Não foi possível carregar a configuração.</p>
            )}
          </div>
        )}
      </Card>

      <Card className="p-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h3 className="text-lg font-medium text-gray-900 dark:text-gray-100">Contexto</h3>
            <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
              Resumos de conversas para revisão. Aprove para enviar ao repositório de memória (Bia). Reprovar remove da memória se já estava aprovado.
            </p>
          </div>
          <div className="flex flex-col gap-1 ml-4 shrink-0">
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setConsolidateByContactModalOpen(true)}
                disabled={!contactPhone.trim()}
                title={!contactPhone.trim() ? 'Informe o telefone do contato no filtro' : 'Consolidar todos os aprovados deste contato'}
              >
                <Layers className="h-4 w-4 mr-1" />
                Consolidar este contato
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setConsolidateAllModalOpen(true)}
                title="Consolidar todos os contatos com 2+ aprovados"
              >
                <Layers className="h-4 w-4 mr-1" />
                Consolidar todos
              </Button>
              <Button variant="outline" size="sm" onClick={() => setReprocessModalOpen(true)} disabled={!!reprocessJobId}>
                <RefreshCw className="h-4 w-4 mr-1" />
                Reprocessar
              </Button>
              <Button variant="default" size="sm" onClick={handleSearch}>
                <Search className="h-4 w-4 mr-1" />
                Buscar
              </Button>
            </div>
            {reprocessJobId && reprocessJobData?.status === 'running' && reprocessProgressDismissed && (
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Reprocessando em background ({reprocessJobData.processed} de {reprocessJobData.total})…
              </p>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-3 mb-4">
          <div>
            <Label className="text-xs">Status</Label>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value as '' | 'pending' | 'approved' | 'rejected')}
              className="mt-1 block w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm"
            >
              {STATUS_OPTIONS.map((o) => (
                <option key={o.value || 'all'} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
          <div>
            <Label className="text-xs">Telefone</Label>
            <Input
              value={contactPhone}
              onChange={(e) => setContactPhone(e.target.value)}
              placeholder="Filtrar por telefone"
              className="mt-1"
            />
          </div>
          <div>
            <Label className="text-xs">Nome contato</Label>
            <Input
              value={contactName}
              onChange={(e) => setContactName(e.target.value)}
              placeholder="Filtrar por nome"
              className="mt-1"
            />
          </div>
          <div>
            <Label className="text-xs">De (data)</Label>
            <Input
              type="date"
              value={fromDate}
              onChange={(e) => setFromDate(e.target.value)}
              className="mt-1"
            />
          </div>
          <div>
            <Label className="text-xs">Até (data)</Label>
            <Input
              type="date"
              value={toDate}
              onChange={(e) => setToDate(e.target.value)}
              className="mt-1"
            />
          </div>
        </div>

        {loading ? (
          <div className="flex justify-center py-8">
            <LoadingSpinner />
          </div>
        ) : items.length === 0 ? (
          <p className="text-sm text-gray-500 dark:text-gray-400 py-6">Nenhum resumo encontrado.</p>
        ) : (
          <>
            <p className="text-sm text-gray-600 dark:text-gray-300 mb-2">Total: {count}</p>
            <div className="overflow-x-auto border border-gray-200 dark:border-gray-600 rounded-lg">
              <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-600">
                {(() => {
                  const groups = groupSummariesByContact(items)
                  return (
                    <>
                      <tbody className="bg-white dark:bg-gray-900 divide-y divide-gray-200 dark:divide-gray-600">
                        {groups.map((group) => {
                          const isCollapsed = collapsedContactKeys.has(group.contactKey)
                          return (
                            <Fragment key={group.contactKey}>
                              <tr className="bg-gray-50 dark:bg-gray-800 border-t border-gray-200 dark:border-gray-600 first:border-t-0">
                                <td className="px-3 py-2 w-10 align-middle">
                                  <button
                                    type="button"
                                    tabIndex={0}
                                    onClick={() => toggleContactCollapsed(group.contactKey)}
                                    onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleContactCollapsed(group.contactKey) } }}
                                    className="inline-flex p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-gray-300 dark:focus:ring-gray-500"
                                    aria-expanded={!isCollapsed}
                                    aria-label={isCollapsed ? 'Expandir detalhes do contato' : 'Retrair detalhes do contato'}
                                  >
                                    {isCollapsed ? <ChevronRight className="h-4 w-4 text-gray-600 dark:text-gray-400" /> : <ChevronDown className="h-4 w-4 text-gray-600 dark:text-gray-400" />}
                                  </button>
                                </td>
                                <td colSpan={6} className="px-3 py-2 text-sm font-medium text-gray-900 dark:text-gray-100">
                                  <div className="flex items-center justify-between gap-3 flex-wrap min-w-0">
                                    <div className="flex items-center gap-2 flex-wrap min-w-0">
                                      <span className="inline-flex px-2 py-0.5 rounded text-xs font-medium bg-gray-200 dark:bg-gray-600 text-gray-900 dark:text-gray-100 truncate max-w-[200px]" title={group.contactLabel}>
                                        {group.contactLabel}
                                      </span>
                                      {group.contactTags.length > 0 && (
                                        <span className="flex flex-wrap gap-1">
                                          {group.contactTags.map((tag) => (
                                            <span key={tag} className="inline-flex px-2 py-0.5 rounded text-xs font-medium bg-gray-200 dark:bg-gray-600 text-gray-800 dark:text-gray-200">
                                              {tag}
                                            </span>
                                          ))}
                                        </span>
                                      )}
                                    </div>
                                    <div className="flex items-center gap-2 shrink-0">
                                      <span className="text-gray-800 dark:text-gray-200 font-normal">Último resumo {group.mostRecentAt}</span>
                                      <SatisfactionStars value={averageSatisfactionValue(group.summaries)} />
                                    </div>
                                  </div>
                                </td>
                              </tr>
                      {!isCollapsed && group.hasConsolidation && (() => {
                        const consolidatedText = consolidatedContentByContact[group.contactPhone] ?? consolidatedContentByContact[group.contactKey] ?? ''
                        return (
                          <tr
                            key={`c-${group.contactKey}`}
                            className="bg-blue-50/50 dark:bg-blue-900/20"
                            role="row"
                            aria-label={`Conversa consolidada do contato ${group.contactLabel}, somente leitura`}
                          >
                            <td className="px-3 py-2 align-top" role="gridcell">
                              <span className="inline-flex text-blue-600 dark:text-blue-400" title="Memória consolidada (somente leitura)">
                                <Layers className="h-4 w-4" />
                              </span>
                            </td>
                            <td className="px-3 py-2 text-sm text-blue-700 dark:text-blue-300 align-top" role="gridcell">
                              <div className="flex items-center gap-1.5">
                                <Layers className="h-4 w-4 shrink-0" />
                                Conversa consolidada
                              </div>
                            </td>
                            <td className="px-3 py-2 text-sm text-gray-700 dark:text-gray-300 align-top max-w-md whitespace-pre-wrap" role="gridcell" title={consolidatedText ? (consolidatedText.length > 2000 ? `${consolidatedText.slice(0, 2000)}…` : consolidatedText) : undefined}>
                              {consolidatedText ? (
                                <>
                                  {consolidatedText.length > 400
                                    ? `${consolidatedText.slice(0, 400)}…`
                                    : consolidatedText}
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    className="mt-1.5 h-7 text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300"
                                    onClick={() => setConsolidatedFullModalContent(consolidatedText)}
                                    aria-label="Ver texto completo da conversa consolidada"
                                  >
                                    <Expand className="h-3.5 w-3.5 mr-1 inline" />
                                    Ver completo
                                  </Button>
                                </>
                              ) : '—'}
                            </td>
                            <td className="px-3 py-2 align-top" role="gridcell">
                              <span className="px-2 py-0.5 rounded text-xs font-medium bg-blue-100 dark:bg-blue-900/40 text-blue-800 dark:text-blue-200">
                                Consolidado
                              </span>
                            </td>
                            <td className="px-3 py-2 text-xs text-gray-700 dark:text-gray-300 align-top" role="gridcell">—</td>
                            <td className="px-3 py-2 text-xs text-gray-700 dark:text-gray-300 align-top" role="gridcell">—</td>
                            <td className="px-3 py-2 align-top" role="gridcell" />
                          </tr>
                        )
                      })()}
                      {!isCollapsed && (
                        <>
                      <tr key={`h-${group.contactKey}`} className="bg-gray-100 dark:bg-gray-700">
                        <td className="px-3 py-2 text-left text-xs font-medium text-gray-700 dark:text-gray-200 uppercase w-10">Consolidar</td>
                        <td className="px-3 py-2 text-left text-xs font-medium text-gray-700 dark:text-gray-200 uppercase">Contato / Conversa</td>
                        <td className="px-3 py-2 text-left text-xs font-medium text-gray-700 dark:text-gray-200 uppercase">Resumo</td>
                        <td className="px-3 py-2 text-left text-xs font-medium text-gray-700 dark:text-gray-200 uppercase">Status</td>
                        <td className="px-3 py-2 text-left text-xs font-medium text-gray-700 dark:text-gray-200 uppercase">Revisado</td>
                        <td className="px-3 py-2 text-left text-xs font-medium text-gray-700 dark:text-gray-200 uppercase">Satisfação</td>
                        <td className="px-3 py-2 text-right text-xs font-medium text-gray-700 dark:text-gray-200 uppercase">Ações</td>
                      </tr>
                      <tr key={`s-${group.contactKey}`} className="bg-gray-100 dark:bg-gray-700">
                        <td colSpan={7} className="px-3 py-1.5 text-xs font-medium text-gray-700 dark:text-gray-200">
                          Todas as conversas desse contato
                        </td>
                      </tr>
                      {group.summaries.map((item) => (
                        <tr key={item.id} className="dark:bg-gray-800/50">
                          <td className="px-3 py-2">
                            {item.status === 'approved' ? (
                              <input
                                type="checkbox"
                                checked={selectedSummaryIds.includes(item.id)}
                                onChange={() => toggleSummarySelection(item.id, true)}
                                title="Incluir na consolidação (mesmo contato)"
                              />
                            ) : (
                              <span className="text-gray-300 dark:text-gray-500">—</span>
                            )}
                          </td>
                          <td className="px-3 py-2 text-sm text-gray-800 dark:text-gray-200">
                            <div className="flex items-center gap-1.5">
                              {item.is_consolidated && (
                                <span className="inline-flex shrink-0 text-blue-600 dark:text-blue-400" title="Incluído na memória consolidada do contato">
                                  <Layers className="h-4 w-4" />
                                </span>
                              )}
                              {(item.metadata?.closed_at as string) || item.created_at
                                ? new Date((item.metadata?.closed_at as string) || item.created_at).toLocaleString('pt-BR')
                                : '—'}
                            </div>
                          </td>
                          <td className="px-3 py-2 text-sm text-gray-800 dark:text-gray-200 max-w-xs truncate" title={getContentPreview(item.content, 500).title}>
                            {getContentPreview(item.content, 120).text}
                          </td>
                          <td className="px-3 py-2">
                            <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                              item.status === 'approved' ? 'bg-green-100 dark:bg-green-900/40 text-green-800 dark:text-green-200' :
                              item.status === 'rejected' ? 'bg-red-100 dark:bg-red-900/40 text-red-800 dark:text-red-200' : 'bg-yellow-100 dark:bg-yellow-900/40 text-yellow-800 dark:text-yellow-200'
                            }`} title={item.is_auto_rejected ? (item.metadata?.auto_rejected_reason as string) || 'Reprovado automaticamente' : undefined}>
                              {item.status_display ?? (item.status === 'pending' ? 'Pendente' : item.status === 'approved' ? 'Aprovado' : 'Reprovado')}
                            </span>
                          </td>
                          <td className="px-3 py-2 text-xs text-gray-700 dark:text-gray-300">
                            {item.reviewed_at ? new Date(item.reviewed_at).toLocaleString('pt-BR') : '—'}
                          </td>
                          <td className="px-3 py-2 text-xs text-gray-800 dark:text-gray-200 tabular-nums">
                            <SatisfactionStars value={item.metadata?.satisfaction} />
                          </td>
                          <td className="px-3 py-2 text-right">
                            <div className="flex justify-end gap-1">
                              {item.status !== 'approved' && (
                                <Button variant="outline" size="sm" onClick={() => handleApprove(item)} title="Aprovar">
                                  <Check className="h-4 w-4" />
                                </Button>
                              )}
                              {item.status !== 'rejected' && (
                                <Button variant="outline" size="sm" onClick={() => handleReject(item)} title="Reprovar">
                                  <X className="h-4 w-4" />
                                </Button>
                              )}
                              <Button variant="outline" size="sm" onClick={() => openEditModal(item)} title="Editar">
                                <Edit className="h-4 w-4" />
                              </Button>
                            </div>
                          </td>
                        </tr>
                      ))}
                        </>
                      )}
                    </Fragment>
                            )
                          })}
                        </tbody>
                    </>
                  )
                })()}
              </table>
            </div>
            <div className="flex items-center justify-between mt-3">
              <span className="text-sm text-gray-600 dark:text-gray-300">
                Exibindo {items.length} de {count}
              </span>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!prevUrl}
                  onClick={() => setOffset((o) => Math.max(0, o - limit))}
                >
                  Anterior
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!nextUrl}
                  onClick={() => setOffset((o) => o + limit)}
                >
                  Próxima
                </Button>
              </div>
            </div>
          </>
        )}
      </Card>

      {/* Modal Reprocessar */}
      {reprocessModalOpen && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4">
            <div className="fixed inset-0 bg-black/50" onClick={() => { if (!reprocessSubmitting) { setReprocessModalOpen(false); setReprocessSummaryStatus('all') } }} aria-hidden />
            <div className="relative bg-white rounded-lg shadow-xl max-w-md w-full p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-3">Reprocessar resumos</h3>
              <div className="space-y-3 mb-6">
                <p className="text-sm text-gray-600">
                  Enfileira o pipeline de resumo para conversas fechadas. Se já existir resumo aprovado, ele será removido da memória antes de reprocessar.
                </p>
                <div>
                  <Label className="text-sm">Reprocessar</Label>
                  <select
                    value={reprocessSummaryStatus}
                    onChange={(e) => setReprocessSummaryStatus(e.target.value as 'all' | 'approved' | 'pending' | 'rejected')}
                    className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                  >
                    <option value="all">Todas</option>
                    <option value="approved">Aprovadas</option>
                    <option value="pending">Pendentes</option>
                    <option value="rejected">Reprovadas</option>
                  </select>
                  <p className="text-xs text-gray-500 mt-1">Filtra por status atual do resumo (ex.: apenas pendentes para revisar).</p>
                </div>
                <div>
                  <Label className="text-sm">Escopo</Label>
                  <select
                    value={reprocessScope}
                    onChange={(e) => setReprocessScope(e.target.value as 'all' | 'contact')}
                    className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                  >
                    <option value="all">Todos os contatos</option>
                    <option value="contact">Apenas um contato</option>
                  </select>
                </div>
                {reprocessScope === 'contact' && (
                  <div>
                    <Label className="text-sm">Telefone do contato (obrigatório)</Label>
                    <Input
                      value={reprocessContactPhone}
                      onChange={(e) => setReprocessContactPhone(e.target.value)}
                      placeholder="Ex: 5511999999999"
                      className="mt-1"
                    />
                  </div>
                )}
                <div className="border-t border-gray-200 pt-3 mt-3 space-y-3">
                  <p className="text-sm font-medium text-gray-700 dark:text-gray-300">Notificar quando concluir (opcional)</p>
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        id="reprocess-notify-whatsapp"
                        checked={reprocessNotifyWhatsapp}
                        onChange={(e) => setReprocessNotifyWhatsapp(e.target.checked)}
                        disabled={reprocessNotifyOptions === null || !reprocessNotifyOptions?.has_whatsapp}
                      />
                      <Label htmlFor="reprocess-notify-whatsapp" className="text-sm">
                        Notificar por WhatsApp
                        {reprocessNotifyOptions !== null && !reprocessNotifyOptions?.has_whatsapp && (
                          <span className="text-gray-400 ml-1">(não configurado)</span>
                        )}
                      </Label>
                    </div>
                    {reprocessNotifyWhatsapp && (
                      <Input
                        value={reprocessNotifyWhatsappPhone}
                        onChange={(e) => setReprocessNotifyWhatsappPhone(e.target.value)}
                        placeholder="Ex: 5511999999999"
                        className="ml-6 max-w-xs"
                      />
                    )}
                  </div>
                  {reprocessNotifyOptions?.has_smtp && (
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          id="reprocess-notify-email"
                          checked={reprocessNotifyEmail}
                          onChange={(e) => setReprocessNotifyEmail(e.target.checked)}
                        />
                        <Label htmlFor="reprocess-notify-email" className="text-sm">Notificar por Email</Label>
                      </div>
                      {reprocessNotifyEmail && (
                        <Input
                          type="email"
                          value={reprocessNotifyEmailAddress}
                          onChange={(e) => setReprocessNotifyEmailAddress(e.target.value)}
                          placeholder="seu@email.com"
                          className="ml-6 max-w-xs"
                        />
                      )}
                    </div>
                  )}
                </div>
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => { if (!reprocessSubmitting) { setReprocessModalOpen(false); setReprocessSummaryStatus('all') } }} disabled={reprocessSubmitting}>
                  Cancelar
                </Button>
                <Button onClick={handleReprocessSubmit} disabled={reprocessSubmitting}>
                  {reprocessSubmitting ? 'Enviando…' : 'Reprocessar'}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modal Consolidar */}
      {consolidateModalOpen && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4">
            <div className="fixed inset-0 bg-black/50" onClick={() => !consolidateSubmitting && setConsolidateModalOpen(false)} aria-hidden />
            <div className="relative bg-white rounded-lg shadow-xl max-w-md w-full p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-3">Consolidar memória</h3>
              <p className="text-sm text-gray-600 mb-4">
                Os {selectedSummaryIds.length} resumos selecionados serão unidos em uma única memória RAG para o contato.
                Apenas resumos <strong>aprovados do mesmo contato</strong> podem ser consolidados.
              </p>
              <p className="text-sm text-gray-500 mb-6">
                Os resumos individuais serão removidos do RAG e substituídos por um único documento com todos os atendimentos (mais recente no topo).
              </p>
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => !consolidateSubmitting && setConsolidateModalOpen(false)} disabled={consolidateSubmitting}>
                  Cancelar
                </Button>
                <Button onClick={handleConsolidateConfirm} disabled={consolidateSubmitting}>
                  {consolidateSubmitting ? 'Consolidando…' : 'Consolidar'}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modal Consolidar este contato */}
      {consolidateByContactModalOpen && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4">
            <div className="fixed inset-0 bg-black/50" onClick={() => !consolidateByContactSubmitting && setConsolidateByContactModalOpen(false)} aria-hidden />
            <div className="relative bg-white rounded-lg shadow-xl max-w-md w-full p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-3">Consolidar este contato</h3>
              <p className="text-sm text-gray-600 mb-4">
                Todos os resumos <strong>aprovados</strong> do contato com telefone &quot;{contactPhone.trim()}&quot; serão unidos em uma única memória RAG.
              </p>
              <p className="text-sm text-gray-500 mb-6">
                É necessário pelo menos 2 resumos aprovados para este contato. Os resumos individuais serão removidos do RAG e substituídos por um único documento (mais recente no topo).
              </p>
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => !consolidateByContactSubmitting && setConsolidateByContactModalOpen(false)} disabled={consolidateByContactSubmitting}>
                  Cancelar
                </Button>
                <Button onClick={handleConsolidateByContactConfirm} disabled={consolidateByContactSubmitting}>
                  {consolidateByContactSubmitting ? 'Consolidando…' : 'Consolidar'}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modal Consolidar todos */}
      {consolidateAllModalOpen && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4">
            <div className="fixed inset-0 bg-black/50" onClick={() => !consolidateAllSubmitting && setConsolidateAllModalOpen(false)} aria-hidden />
            <div className="relative bg-white rounded-lg shadow-xl max-w-md w-full p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-3">Consolidar todos</h3>
              <p className="text-sm text-gray-600 mb-4">
                Serão consolidados <strong>todos os contatos</strong> que tiverem 2 ou mais resumos aprovados. Cada contato terá uma única memória RAG.
              </p>
              <p className="text-sm text-gray-500 mb-6">
                A operação pode levar alguns segundos se houver muitos contatos. Contatos com 0 ou 1 aprovado serão ignorados.
              </p>
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => !consolidateAllSubmitting && setConsolidateAllModalOpen(false)} disabled={consolidateAllSubmitting}>
                  Cancelar
                </Button>
                <Button onClick={handleConsolidateAllConfirm} disabled={consolidateAllSubmitting}>
                  {consolidateAllSubmitting ? 'Consolidando…' : 'Consolidar todos'}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modal Ver completo (conversa consolidada) */}
      {consolidatedFullModalContent !== null && (
        <div className="fixed inset-0 z-50 overflow-y-auto" role="dialog" aria-modal="true" aria-labelledby="consolidated-full-modal-title">
          <div className="flex min-h-full items-center justify-center p-4">
            <div className="fixed inset-0 bg-black/50" onClick={() => setConsolidatedFullModalContent(null)} aria-hidden />
            <div className="relative bg-white rounded-lg shadow-xl max-w-3xl w-full max-h-[85vh] flex flex-col p-6">
              <h2 id="consolidated-full-modal-title" className="text-lg font-medium text-gray-900 mb-3">
                Conversa consolidada (completo)
              </h2>
              <div className="flex-1 min-h-0 overflow-y-auto rounded border border-gray-200 bg-gray-50/50 p-4">
                <pre className="text-sm text-gray-700 whitespace-pre-wrap font-sans">
                  {consolidatedFullModalContent}
                </pre>
              </div>
              <div className="flex justify-end mt-4 pt-3 border-t border-gray-200">
                <Button variant="outline" onClick={() => setConsolidatedFullModalContent(null)}>
                  Fechar
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modal Editar */}
      {editModalOpen && editItem && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4">
            <div className="fixed inset-0 bg-black/50" onClick={() => !editSubmitting && setEditModalOpen(false)} aria-hidden />
            <div className="relative bg-white rounded-lg shadow-xl max-w-lg w-full p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-3">Editar resumo</h3>
              <div className="rounded-md border border-gray-200 bg-gray-50 p-3 mb-4 text-sm text-gray-700 space-y-1">
                <div><span className="font-medium">Contato:</span> {editItem.contact_name || editItem.contact_phone || '—'}</div>
                <div><span className="font-medium">Data da conversa:</span> {(editItem.metadata?.closed_at as string) || editItem.created_at ? new Date((editItem.metadata?.closed_at as string) || editItem.created_at).toLocaleString('pt-BR') : '—'}</div>
                <div><span className="font-medium">Departamento:</span> {(editItem.metadata?.department_name as string) || '—'}</div>
                <div><span className="font-medium">Assunto:</span> {(editItem.metadata?.subject as string) || '—'}</div>
              </div>
              <div className="space-y-2 mb-6">
                <Label className="text-sm">Conteúdo</Label>
                <textarea
                  value={editContent}
                  onChange={(e) => setEditContent(e.target.value)}
                  rows={8}
                  className="block w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                  placeholder="Texto do resumo"
                />
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => !editSubmitting && setEditModalOpen(false)} disabled={editSubmitting}>
                  Cancelar
                </Button>
                <Button onClick={handleEditSubmit} disabled={editSubmitting}>
                  {editSubmitting ? 'Salvando…' : 'Salvar'}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modal de progresso/resultado do reprocessamento (oculto durante running se usuário clicou em Fechar/Sair) */}
      {reprocessJobId && reprocessJobData && (reprocessJobData.status !== 'running' || !reprocessProgressDismissed) && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4">
            <div className="fixed inset-0 bg-black/50" aria-hidden />
            <div className="relative bg-white rounded-lg shadow-xl max-w-md w-full p-6">
              {reprocessJobData.status === 'running' ? (
                <>
                  <h3 className="text-lg font-medium text-gray-900 mb-1">Reprocessando resumos…</h3>
                  <p className="text-sm text-gray-500 mb-4">
                    {reprocessJobData.processed} de {reprocessJobData.total} conversas processadas
                  </p>
                  <div className="w-full bg-gray-200 rounded-full h-2.5 mb-4">
                    <div
                      className="bg-blue-600 h-2.5 rounded-full transition-all duration-500"
                      style={{ width: `${reprocessJobData.total > 0 ? Math.round(reprocessJobData.processed / reprocessJobData.total * 100) : 0}%` }}
                    />
                  </div>
                  <div className="flex justify-center">
                    <LoadingSpinner />
                  </div>
                  <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded p-2 mt-4 mb-4">
                    Ao sair, o processo continua em background. O botão Reprocessar ficará desativado até o término.
                  </p>
                  <div className="flex justify-end">
                    <Button variant="outline" onClick={() => setReprocessProgressDismissed(true)}>
                      Fechar / Sair
                    </Button>
                  </div>
                </>
              ) : reprocessJobData.status === 'done' ? (
                <>
                  <h3 className="text-lg font-medium text-gray-900 mb-4">Reprocessamento concluído</h3>
                  <div className="grid grid-cols-2 gap-3 mb-6">
                    <div className="bg-gray-50 rounded-lg p-3 text-center">
                      <div className="text-2xl font-bold text-gray-900 dark:text-gray-100">{reprocessJobData.total}</div>
                      <div className="text-xs text-gray-500 mt-1">Total processado</div>
                    </div>
                    <div className="bg-green-50 rounded-lg p-3 text-center">
                      <div className="text-2xl font-bold text-green-700">{reprocessJobData.approved}</div>
                      <div className="text-xs text-gray-500 mt-1">Aprovadas</div>
                    </div>
                    <div className="bg-red-50 rounded-lg p-3 text-center">
                      <div className="text-2xl font-bold text-red-700">{reprocessJobData.rejected}</div>
                      <div className="text-xs text-gray-500 mt-1">Reprovadas</div>
                    </div>
                    <div className="bg-blue-50 rounded-lg p-3 text-center">
                      <div className="text-2xl font-bold text-blue-700">{reprocessJobData.percent}%</div>
                      <div className="text-xs text-gray-500 mt-1">Taxa de sucesso</div>
                    </div>
                  </div>
                  {(reprocessJobData.notify_whatsapp_requested || reprocessJobData.notify_email_requested) && (
                    <p className="text-xs text-gray-400 mb-4 text-center">
                      {reprocessJobData.notify_whatsapp_requested && reprocessJobData.notify_email_requested
                        ? 'Um relatório foi enviado por WhatsApp e email.'
                        : reprocessJobData.notify_whatsapp_requested
                          ? 'Um relatório foi enviado por WhatsApp.'
                          : 'Um relatório foi enviado por email.'}
                    </p>
                  )}
                  <div className="flex justify-end">
                    <Button onClick={handleCloseJobModal}>Fechar</Button>
                  </div>
                </>
              ) : (
                <>
                  <h3 className="text-lg font-medium text-gray-900 mb-2">
                    {reprocessJobData.status === 'stale' ? 'Reprocessamento demorou mais que o esperado' : 'Erro ao monitorar reprocessamento'}
                  </h3>
                  <p className="text-sm text-gray-500 mb-4">
                    {reprocessJobData.status === 'stale'
                      ? 'O processo ainda pode estar em execução. Verifique os resumos na lista após alguns minutos.'
                      : 'Não foi possível obter o status. O reprocessamento pode ter ocorrido normalmente.'}
                  </p>
                  <div className="flex justify-end">
                    <Button onClick={handleCloseJobModal}>Fechar</Button>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
