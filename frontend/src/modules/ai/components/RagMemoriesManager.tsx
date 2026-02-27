import { useState, useEffect, useCallback, useRef } from 'react'
import { Check, X, Edit, RefreshCw, Search, FileText, ChevronDown, ChevronRight, Save } from 'lucide-react'
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
}

const STATUS_OPTIONS: { value: '' | 'pending' | 'approved' | 'rejected'; label: string }[] = [
  { value: '', label: 'Todos' },
  { value: 'pending', label: 'Pendente' },
  { value: 'approved', label: 'Aprovado' },
  { value: 'rejected', label: 'Reprovado' },
]

export function RagMemoriesManager() {
  const [items, setItems] = useState<ConversationSummaryItem[]>([])
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

  const [autoApproveOpen, setAutoApproveOpen] = useState(false)
  const [autoApproveConfig, setAutoApproveConfig] = useState<{ enabled: boolean; criteria: Record<string, { enabled: boolean; value?: number }>; criterion_defaults?: Record<string, { label: string; type: string; default: unknown }> } | null>(null)
  const [autoApproveLoading, setAutoApproveLoading] = useState(false)
  const [autoApproveSaving, setAutoApproveSaving] = useState(false)

  const fetchAutoApproveConfig = useCallback(async () => {
    setAutoApproveLoading(true)
    try {
      const { data } = await api.get<{ enabled: boolean; criteria: Record<string, { enabled: boolean; value?: number }>; criterion_defaults?: Record<string, { label: string; type: string; default: unknown }> }>('ai/summaries/auto-approve-config/')
      setAutoApproveConfig(data)
    } catch (e) {
      showErrorToast('carregar', 'Config. aprovação automática', e)
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
      await api.patch('ai/summaries/auto-approve-config/', { enabled: autoApproveConfig.enabled, criteria: autoApproveConfig.criteria })
      toast.success('Configuração de aprovação automática salva.')
    } catch (e: any) {
      showErrorToast('salvar', 'Config. aprovação automática', e)
    } finally {
      setAutoApproveSaving(false)
    }
  }

  const fetchList = useCallback(async (off = 0) => {
    setLoading(true)
    try {
      const params: Record<string, string | number> = { limit, offset: off }
      if (status) params.status = status
      if (contactPhone.trim()) params.contact_phone = contactPhone.trim()
      if (contactName.trim()) params.contact_name = contactName.trim()
      if (fromDate) params.from_date = fromDate
      if (toDate) params.to_date = toDate
      const { data } = await api.get<PaginatedResponse>('ai/summaries/', { params })
      setItems(data.results)
      setCount(data.count)
      setNextUrl(data.next)
      setPrevUrl(data.previous)
    } catch (e) {
      showErrorToast('carregar', 'Resumos', e)
      setItems([])
      setCount(0)
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

  const handleSearch = () => {
    setOffset(0)
    fetchList(0)
  }

  const handleApprove = async (item: ConversationSummaryItem) => {
    const toastId = showLoadingToast('atualizar', 'Resumo')
    try {
      await api.patch(`ai/summaries/${item.id}/`, { action: 'approve' })
      updateToastSuccess(toastId, 'atualizar', 'Resumo')
      fetchList(offset)
    } catch (e) {
      updateToastError(toastId, 'atualizar', 'Resumo', e)
    }
  }

  const handleReject = async (item: ConversationSummaryItem) => {
    const toastId = showLoadingToast('atualizar', 'Resumo')
    try {
      await api.patch(`ai/summaries/${item.id}/`, { action: 'reject' })
      updateToastSuccess(toastId, 'atualizar', 'Resumo')
      fetchList(offset)
    } catch (e) {
      updateToastError(toastId, 'atualizar', 'Resumo', e)
    }
  }

  const openEditModal = (item: ConversationSummaryItem) => {
    setEditItem(item)
    setEditContent(item.content)
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
      const payload: { scope: string; contact_phone?: string; notify_whatsapp_phone?: string; notify_email?: string } = { scope: reprocessScope }
      if (reprocessScope === 'contact') payload.contact_phone = reprocessContactPhone.trim()
      if (reprocessNotifyWhatsapp && reprocessNotifyWhatsappPhone.trim()) payload.notify_whatsapp_phone = reprocessNotifyWhatsappPhone.trim()
      if (reprocessNotifyEmail && reprocessNotifyEmailAddress.trim()) payload.notify_email = reprocessNotifyEmailAddress.trim()
      const { data } = await api.post<{ status: string; enqueued: number; total_eligible: number; job_id?: string }>('ai/summaries/reprocess/', payload)
      setReprocessModalOpen(false)
      setReprocessScope('all')
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

  const criterionOrder = ['min_words', 'max_words', 'min_messages', 'has_subject', 'no_placeholders', 'sentiment_not_negative', 'satisfaction_min', 'confidence_min']

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <button
          type="button"
          onClick={() => setAutoApproveOpen((o) => !o)}
          className="flex items-center gap-2 w-full text-left font-medium text-gray-900"
        >
          {autoApproveOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          Aprovação automática de resumos
        </button>
        {autoApproveOpen && (
          <div className="mt-4 pt-4 border-t border-gray-200">
            {autoApproveLoading ? (
              <div className="flex justify-center py-4"><LoadingSpinner /></div>
            ) : autoApproveConfig ? (
              <div className="space-y-4">
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="auto-approve-enabled"
                    checked={autoApproveConfig.enabled}
                    onChange={(e) => setAutoApproveConfig((c) => c ? { ...c, enabled: e.target.checked } : c)}
                  />
                  <Label htmlFor="auto-approve-enabled" className="text-sm">Ativar aprovação automática</Label>
                </div>
                <p className="text-xs text-gray-500">Quando ativo, resumos que passarem em todos os critérios marcados abaixo serão aprovados e enviados ao RAG automaticamente.</p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {criterionOrder.map((cid) => {
                    const c = autoApproveConfig.criteria[cid]
                    const def = autoApproveConfig.criterion_defaults?.[cid]
                    if (!c) return null
                    const isNumber = def?.type === 'number'
                    return (
                      <div key={cid} className="flex items-center gap-2 flex-wrap">
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
                        <Label htmlFor={`crit-${cid}`} className="text-sm flex-1">{def?.label ?? cid}</Label>
                        {isNumber && c.enabled && (
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
                            className="w-20 text-sm"
                          />
                        )}
                      </div>
                    )
                  })}
                </div>
                <Button size="sm" onClick={handleSaveAutoApproveConfig} disabled={autoApproveSaving}>
                  <Save className="h-4 w-4 mr-1" />
                  {autoApproveSaving ? 'Salvando…' : 'Salvar'}
                </Button>
              </div>
            ) : (
              <p className="text-sm text-gray-500">Não foi possível carregar a configuração.</p>
            )}
          </div>
        )}
      </Card>

      <Card className="p-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h3 className="text-lg font-medium text-gray-900">RAG e Lembranças</h3>
            <p className="text-sm text-gray-600 mt-1">
              Resumos de conversas para revisão. Aprove para enviar ao repositório de memória (Bia). Reprovar remove da memória se já estava aprovado.
            </p>
          </div>
          <div className="flex flex-col gap-1 ml-4 shrink-0">
            <div className="flex gap-2">
              <Button variant="default" size="sm" onClick={handleSearch}>
                <Search className="h-4 w-4 mr-1" />
                Buscar
              </Button>
              <Button variant="outline" size="sm" onClick={() => setReprocessModalOpen(true)} disabled={!!reprocessJobId}>
                <RefreshCw className="h-4 w-4 mr-1" />
                Reprocessar
              </Button>
            </div>
            {reprocessJobId && reprocessJobData?.status === 'running' && reprocessProgressDismissed && (
              <p className="text-xs text-gray-500">
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
          <p className="text-sm text-gray-500 py-6">Nenhum resumo encontrado.</p>
        ) : (
          <>
            <p className="text-sm text-gray-600 mb-2">Total: {count}</p>
            <div className="overflow-x-auto border border-gray-200 rounded-lg">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Contato / Conversa</th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Resumo</th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Revisado</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Ações</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {items.map((item) => (
                    <tr key={item.id}>
                      <td className="px-3 py-2 text-sm">
                        <div className="font-medium text-gray-900">{item.contact_name || item.contact_phone || '—'}</div>
                        <div className="text-gray-500">{item.contact_phone}</div>
                        {item.contact_tags && item.contact_tags.length > 0 ? (
                          <div className="flex flex-wrap gap-1 mt-1">
                            {item.contact_tags.map((tag) => (
                              <span key={tag} className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-700">
                                {tag}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <div className="text-xs text-gray-400 mt-1">—</div>
                        )}
                      </td>
                      <td className="px-3 py-2 text-sm text-gray-700 max-w-xs truncate" title={item.content}>
                        {item.content ? `${item.content.slice(0, 120)}${item.content.length > 120 ? '…' : ''}` : '—'}
                      </td>
                      <td className="px-3 py-2">
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                          item.status === 'approved' ? 'bg-green-100 text-green-800' :
                          item.status === 'rejected' ? 'bg-red-100 text-red-800' : 'bg-yellow-100 text-yellow-800'
                        }`} title={item.is_auto_rejected ? (item.metadata?.auto_rejected_reason as string) || 'Reprovado automaticamente' : undefined}>
                          {item.status_display ?? (item.status === 'pending' ? 'Pendente' : item.status === 'approved' ? 'Aprovado' : 'Reprovado')}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-xs text-gray-500">
                        {item.reviewed_at ? new Date(item.reviewed_at).toLocaleString('pt-BR') : '—'}
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
                </tbody>
              </table>
            </div>
            <div className="flex items-center justify-between mt-3">
              <span className="text-sm text-gray-600">
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
            <div className="fixed inset-0 bg-black/50" onClick={() => !reprocessSubmitting && setReprocessModalOpen(false)} aria-hidden />
            <div className="relative bg-white rounded-lg shadow-xl max-w-md w-full p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-3">Reprocessar resumos</h3>
              <div className="space-y-3 mb-6">
                <p className="text-sm text-gray-600">
                  Enfileira o pipeline de resumo para conversas fechadas. Se já existir resumo aprovado, ele será removido da memória antes de reprocessar.
                </p>
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
                  <p className="text-sm font-medium text-gray-700">Notificar quando concluir (opcional)</p>
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
                <Button variant="outline" onClick={() => !reprocessSubmitting && setReprocessModalOpen(false)} disabled={reprocessSubmitting}>
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

      {/* Modal Editar */}
      {editModalOpen && (
        <div className="fixed inset-0 z-50 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4">
            <div className="fixed inset-0 bg-black/50" onClick={() => !editSubmitting && setEditModalOpen(false)} aria-hidden />
            <div className="relative bg-white rounded-lg shadow-xl max-w-lg w-full p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-3">Editar resumo</h3>
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
                      <div className="text-2xl font-bold text-gray-900">{reprocessJobData.total}</div>
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
