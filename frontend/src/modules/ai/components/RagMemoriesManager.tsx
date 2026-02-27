import { useState, useEffect, useCallback } from 'react'
import { Check, X, Edit, RefreshCw, Search, FileText } from 'lucide-react'
import { Button } from '../../../components/ui/Button'
import { Card } from '../../../components/ui/Card'
import { Input } from '../../../components/ui/Input'
import { Label } from '../../../components/ui/Label'
import LoadingSpinner from '../../../components/ui/LoadingSpinner'
import { toast } from 'sonner'
import { api } from '../../../lib/api'
import { showErrorToast, showLoadingToast, updateToastSuccess, updateToastError } from '../../../lib/toastHelper'

export interface ConversationSummaryItem {
  id: number
  conversation_id: string
  contact_phone: string
  contact_name: string
  contact_tags?: string[]
  content: string
  metadata: Record<string, unknown>
  status: 'pending' | 'approved' | 'rejected'
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

  const [editModalOpen, setEditModalOpen] = useState(false)
  const [editItem, setEditItem] = useState<ConversationSummaryItem | null>(null)
  const [editContent, setEditContent] = useState('')
  const [editSubmitting, setEditSubmitting] = useState(false)

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
    setReprocessSubmitting(true)
    try {
      const payload: { scope: string; contact_phone?: string } = { scope: reprocessScope }
      if (reprocessScope === 'contact') payload.contact_phone = reprocessContactPhone.trim()
      const { data } = await api.post<{ status: string; enqueued: number; total_eligible: number }>('ai/summaries/reprocess/', payload)
      toast.success(`${data.enqueued} conversa(s) enfileirada(s). Total elegível: ${data.total_eligible}`)
      setReprocessModalOpen(false)
      setReprocessScope('all')
      setReprocessContactPhone('')
      fetchList(offset)
    } catch (e: any) {
      showErrorToast('iniciar', 'Reprocessamento', e)
    } finally {
      setReprocessSubmitting(false)
    }
  }

  return (
    <div className="space-y-4">
      <Card className="p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-2">RAG e Lembranças</h3>
        <p className="text-sm text-gray-600 mb-4">
          Resumos de conversas para revisão. Aprove para enviar ao repositório de memória (Bia). Reprovar remove da memória se já estava aprovado.
        </p>

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
        <div className="flex flex-wrap gap-2 mb-4">
          <Button variant="default" size="sm" onClick={handleSearch}>
            <Search className="h-4 w-4 mr-1" />
            Buscar
          </Button>
          <Button variant="outline" size="sm" onClick={() => setReprocessModalOpen(true)}>
            <RefreshCw className="h-4 w-4 mr-1" />
            Reprocessar
          </Button>
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
                        }`}>
                          {item.status === 'pending' ? 'Pendente' : item.status === 'approved' ? 'Aprovado' : 'Reprovado'}
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
    </div>
  )
}
