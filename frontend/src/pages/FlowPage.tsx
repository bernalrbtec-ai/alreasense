/**
 * Página de Fluxos: lista/botões por Inbox ou departamento.
 * Lista fluxos, CRUD de nós e arestas, preview e envio de teste.
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import {
  Plus,
  Edit,
  Trash2,
  MessageSquare,
  List,
  Building2,
  Inbox,
  Play,
  X,
} from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Input } from '../components/ui/Input'
import { Label } from '../components/ui/Label'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import ConfirmDialog from '../components/ui/ConfirmDialog'
import { api } from '../lib/api'
import { useAuthStore } from '../stores/authStore'

function getApiError(e: any): string {
  const data = e?.response?.data
  if (!data) return e?.message || 'Erro inesperado.'
  if (typeof data === 'string') return data
  const detail = data.detail
  if (detail !== undefined && detail !== null) {
    if (Array.isArray(detail)) return detail[0] ? String(detail[0]) : 'Erro na requisição.'
    if (typeof detail === 'object') return (detail as { message?: string }).message || JSON.stringify(detail)
    return String(detail)
  }
  const keys = Object.keys(data).filter((k) => k !== 'detail')
  if (keys.length === 0) return 'Erro na requisição.'
  const parts = keys.map((k) => {
    const v = data[k]
    const msg = Array.isArray(v) ? v[0] : String(v)
    return msg ? `${k}: ${msg}` : ''
  }).filter(Boolean)
  return parts.length ? parts.join(' ') : 'Erro na requisição.'
}

interface Flow {
  id: string
  name: string
  scope: string
  department: string | null
  department_name: string | null
  is_active: boolean
  nodes?: FlowNode[]
}

interface FlowNode {
  id: string
  flow: string
  node_type: 'list' | 'buttons'
  name: string
  order: number
  is_start: boolean
  body_text: string
  button_text: string
  header_text?: string
  footer_text?: string
  sections: Array<{ title: string; rows: Array<{ id: string; title: string; description?: string }> }>
  buttons: Array<{ id: string; title: string }>
  edges_out?: FlowEdge[]
}

interface FlowEdge {
  id: string
  from_node: string
  option_id: string
  to_node: string | null
  to_node_name: string | null
  target_department: string | null
  target_department_name: string | null
  target_action: string
}

interface DepartmentOption {
  id: string
  name: string
  color?: string
}

const defaultSectionsJson = '[{"title":"Opções","rows":[{"id":"op1","title":"Opção 1","description":""},{"id":"op2","title":"Opção 2","description":""}]}]'
const defaultButtonsJson = '[{"id":"btn1","title":"Botão 1"},{"id":"btn2","title":"Botão 2"}]'

export default function FlowPage() {
  const { user } = useAuthStore()
  const [flows, setFlows] = useState<Flow[]>([])
  const [departments, setDepartments] = useState<DepartmentOption[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedFlow, setSelectedFlow] = useState<Flow | null>(null)
  const [flowDetail, setFlowDetail] = useState<Flow | null>(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [newFlowName, setNewFlowName] = useState('')
  const [newFlowScope, setNewFlowScope] = useState<'inbox' | 'department'>('inbox')
  const [newFlowDepartmentId, setNewFlowDepartmentId] = useState<string | null>(null)
  const [testPhone, setTestPhone] = useState('')
  const [sendingTest, setSendingTest] = useState(false)
  const [creatingFlow, setCreatingFlow] = useState(false)
  const [detailLoading, setDetailLoading] = useState(false)
  const selectedFlowIdRef = useRef<string | null>(null)

  // Confirm delete
  const [confirmDeleteNode, setConfirmDeleteNode] = useState<FlowNode | null>(null)
  const [confirmDeleteEdge, setConfirmDeleteEdge] = useState<FlowEdge | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  // Node form (add / edit)
  const [nodeFormOpen, setNodeFormOpen] = useState(false)
  const [editingNode, setEditingNode] = useState<FlowNode | null>(null)
  const [nodeName, setNodeName] = useState('')
  const [nodeType, setNodeType] = useState<'list' | 'buttons'>('list')
  const [nodeOrder, setNodeOrder] = useState(0)
  const [nodeIsStart, setNodeIsStart] = useState(false)
  const [nodeBodyText, setNodeBodyText] = useState('')
  const [nodeButtonText, setNodeButtonText] = useState('')
  const [nodeHeaderText, setNodeHeaderText] = useState('')
  const [nodeFooterText, setNodeFooterText] = useState('')
  const [nodeSectionsJson, setNodeSectionsJson] = useState(defaultSectionsJson)
  const [nodeButtonsJson, setNodeButtonsJson] = useState(defaultButtonsJson)
  const [savingNode, setSavingNode] = useState(false)

  // Edge form (add / edit)
  const [edgeFormOpen, setEdgeFormOpen] = useState(false)
  const [edgeFromNodeId, setEdgeFromNodeId] = useState<string | null>(null)
  const [editingEdge, setEditingEdge] = useState<FlowEdge | null>(null)
  const [edgeOptionId, setEdgeOptionId] = useState('')
  const [edgeToNodeId, setEdgeToNodeId] = useState<string | null>(null)
  const [edgeTargetDepartmentId, setEdgeTargetDepartmentId] = useState<string | null>(null)
  const [edgeTargetAction, setEdgeTargetAction] = useState<string>('next')
  const [savingEdge, setSavingEdge] = useState(false)

  const fetchFlows = async () => {
    try {
      const { data } = await api.get('/chat/flows/')
      const list = Array.isArray(data) ? data : (data && Array.isArray((data as { results?: unknown }).results) ? (data as { results: Flow[] }).results : [])
      setFlows(list)
    } catch (e: any) {
      toast.error(getApiError(e))
    }
  }

  const fetchDepartments = async () => {
    try {
      const { data } = await api.get('/chat/flows/available_departments/')
      setDepartments(Array.isArray(data) ? data : [])
    } catch {
      setDepartments([])
    }
  }

  const fetchFlowDetail = useCallback(async (id: string) => {
    setDetailLoading(true)
    try {
      const { data } = await api.get(`/chat/flows/${id}/`)
      if (selectedFlowIdRef.current === id) setFlowDetail(data)
    } catch {
      if (selectedFlowIdRef.current === id) setFlowDetail(null)
    } finally {
      if (selectedFlowIdRef.current === id) setDetailLoading(false)
    }
  }, [])

  useEffect(() => {
    setLoading(true)
    Promise.all([fetchFlows(), fetchDepartments()]).finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    selectedFlowIdRef.current = selectedFlow?.id ?? null
    if (selectedFlow?.id) fetchFlowDetail(selectedFlow.id)
    else setFlowDetail(null)
  }, [selectedFlow?.id, fetchFlowDetail])

  const handleCreateFlow = async () => {
    if (!newFlowName.trim()) {
      toast.error('Nome do fluxo é obrigatório')
      return
    }
    if (newFlowScope === 'department' && !newFlowDepartmentId) {
      toast.error('Selecione o departamento')
      return
    }
    setCreatingFlow(true)
    try {
      const { data } = await api.post('/chat/flows/', {
        name: newFlowName.trim(),
        scope: newFlowScope,
        department: newFlowScope === 'department' ? newFlowDepartmentId : null,
        is_active: true,
      })
      const id = data?.id
      if (!id) {
        toast.error('Resposta inválida ao criar fluxo')
        return
      }
      toast.success('Fluxo criado')
      setCreateOpen(false)
      setNewFlowName('')
      setNewFlowScope('inbox')
      setNewFlowDepartmentId(null)
      await fetchFlows()
      setSelectedFlow({
        id: String(id),
        name: data?.name ?? '',
        scope: data?.scope ?? 'inbox',
        department: data?.department ?? null,
        department_name: data?.department_name ?? null,
        is_active: data?.is_active ?? true,
      })
      selectedFlowIdRef.current = String(id)
      fetchFlowDetail(String(id))
    } catch (e: any) {
      toast.error(getApiError(e))
    } finally {
      setCreatingFlow(false)
    }
  }

  const handleSendTest = async () => {
    if (!selectedFlow?.id || !testPhone.trim()) {
      toast.error('Selecione um fluxo e informe o número')
      return
    }
    setSendingTest(true)
    try {
      const { data } = await api.post(`/chat/flows/${selectedFlow.id}/send_test/`, {
        phone: testPhone.trim(),
      })
      toast.success(`Mensagem enfileirada (conversa ${data.conversation_id?.slice(0, 8)}…)`)
    } catch (e: any) {
      toast.error(getApiError(e))
    } finally {
      setSendingTest(false)
    }
  }

  const openAddNode = () => {
    setEditingNode(null)
    setNodeName('')
    setNodeType('list')
    setNodeOrder(flowDetail?.nodes?.length ?? 0)
    setNodeIsStart((flowDetail?.nodes?.length ?? 0) === 0)
    setNodeBodyText('')
    setNodeButtonText('Ver opções')
    setNodeHeaderText('')
    setNodeFooterText('')
    setNodeSectionsJson(defaultSectionsJson)
    setNodeButtonsJson(defaultButtonsJson)
    setNodeFormOpen(true)
  }

  const openEditNode = (n: FlowNode) => {
    setEditingNode(n)
    setNodeName(n.name)
    setNodeType(n.node_type)
    setNodeOrder(n.order)
    setNodeIsStart(n.is_start)
    setNodeBodyText(n.body_text || '')
    setNodeButtonText(n.button_text || '')
    setNodeHeaderText(n.header_text || '')
    setNodeFooterText(n.footer_text || '')
    setNodeSectionsJson(JSON.stringify(n.sections || [], null, 2))
    setNodeButtonsJson(JSON.stringify(n.buttons || [], null, 2))
    setNodeFormOpen(true)
  }

  const handleSaveNode = async () => {
    if (!selectedFlow?.id || !nodeName.trim()) {
      toast.error('Nome do nó é obrigatório')
      return
    }
    let sections: FlowNode['sections'] = []
    let buttons: FlowNode['buttons'] = []
    if (nodeType === 'list') {
      try {
        sections = JSON.parse(nodeSectionsJson) as FlowNode['sections']
        if (!Array.isArray(sections) || sections.length === 0) {
          toast.error('Seções: informe um array com ao menos uma seção')
          return
        }
        const hasRows = sections.every((sec) => sec && typeof sec === 'object' && Array.isArray(sec.rows) && sec.rows.length > 0)
        if (!hasRows) {
          toast.error('Cada seção deve ter ao menos uma linha (id e title)')
          return
        }
      } catch {
        toast.error('Seções: JSON inválido. Use o formato [{"title":"...","rows":[{"id":"...","title":"..."}]}]')
        return
      }
    } else {
      try {
        buttons = JSON.parse(nodeButtonsJson) as FlowNode['buttons']
        if (!Array.isArray(buttons) || buttons.length < 1 || buttons.length > 3) {
          toast.error('Botões: informe um array com 1 a 3 itens')
          return
        }
      } catch {
        toast.error('Botões: JSON inválido. Use o formato [{"id":"...","title":"..."}]')
        return
      }
    }
    setSavingNode(true)
    try {
      const payload = {
        flow: selectedFlow.id,
        node_type: nodeType,
        name: nodeName.trim(),
        order: nodeOrder,
        is_start: nodeIsStart,
        body_text: nodeBodyText.trim(),
        button_text: nodeType === 'list' ? nodeButtonText.trim() : '',
        header_text: nodeHeaderText.trim(),
        footer_text: nodeFooterText.trim(),
        sections: nodeType === 'list' ? sections : [],
        buttons: nodeType === 'buttons' ? buttons : [],
      }
      if (editingNode) {
        await api.patch(`/chat/flow-nodes/${editingNode.id}/`, payload)
        toast.success('Nó atualizado')
      } else {
        await api.post('/chat/flow-nodes/', payload)
        toast.success('Nó criado')
      }
      setNodeFormOpen(false)
      fetchFlowDetail(selectedFlow.id)
    } catch (e: any) {
      toast.error(getApiError(e))
    } finally {
      setSavingNode(false)
    }
  }

  const handleDeleteNodeClick = (node: FlowNode) => setConfirmDeleteNode(node)
  const handleDeleteNodeConfirm = async () => {
    const node = confirmDeleteNode
    setConfirmDeleteNode(null)
    if (!node || !selectedFlow?.id) return
    setDeletingId(node.id)
    try {
      await api.delete(`/chat/flow-nodes/${node.id}/`)
      toast.success('Nó excluído')
      fetchFlowDetail(selectedFlow.id)
    } catch (e: any) {
      toast.error(getApiError(e))
    } finally {
      setDeletingId(null)
    }
  }

  const openAddEdge = (fromNodeId: string) => {
    setEditingEdge(null)
    setEdgeFromNodeId(fromNodeId)
    setEdgeOptionId('')
    setEdgeToNodeId(null)
    setEdgeTargetDepartmentId(null)
    setEdgeTargetAction('next')
    setEdgeFormOpen(true)
  }

  const openEditEdge = (e: FlowEdge) => {
    setEditingEdge(e)
    setEdgeFromNodeId(e.from_node)
    setEdgeOptionId(e.option_id)
    setEdgeToNodeId(e.to_node || null)
    setEdgeTargetDepartmentId(e.target_department || null)
    setEdgeTargetAction(e.target_action || 'next')
    setEdgeFormOpen(true)
  }

  const handleSaveEdge = async () => {
    if (!edgeFromNodeId || !edgeOptionId.trim()) {
      toast.error('Nó de origem e ID da opção são obrigatórios')
      return
    }
    if (edgeTargetAction === 'next' && !edgeToNodeId) {
      toast.error('Selecione o próximo nó para ação "Próxima etapa"')
      return
    }
    if (edgeTargetAction === 'transfer' && !edgeTargetDepartmentId) {
      toast.error('Selecione o departamento para ação "Transferir"')
      return
    }
    setSavingEdge(true)
    try {
      const payload = {
        from_node: edgeFromNodeId,
        option_id: edgeOptionId.trim(),
        to_node: edgeTargetAction === 'next' ? edgeToNodeId : null,
        target_department: edgeTargetAction === 'transfer' ? edgeTargetDepartmentId : null,
        target_action: edgeTargetAction,
      }
      if (editingEdge) {
        await api.patch(`/chat/flow-edges/${editingEdge.id}/`, payload)
        toast.success('Aresta atualizada')
      } else {
        await api.post('/chat/flow-edges/', payload)
        toast.success('Aresta criada')
      }
      setEdgeFormOpen(false)
      if (selectedFlow?.id) fetchFlowDetail(selectedFlow.id)
    } catch (e: any) {
      toast.error(getApiError(e))
    } finally {
      setSavingEdge(false)
    }
  }

  const handleDeleteEdgeClick = (edge: FlowEdge) => setConfirmDeleteEdge(edge)
  const handleDeleteEdgeConfirm = async () => {
    const edge = confirmDeleteEdge
    setConfirmDeleteEdge(null)
    if (!edge || !selectedFlow?.id) return
    setDeletingId(edge.id)
    try {
      await api.delete(`/chat/flow-edges/${edge.id}/`)
      toast.success('Aresta excluída')
      fetchFlowDetail(selectedFlow.id)
    } catch (e: any) {
      toast.error(getApiError(e))
    } finally {
      setDeletingId(null)
    }
  }

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (nodeFormOpen) setNodeFormOpen(false)
        else if (edgeFormOpen) setEdgeFormOpen(false)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [nodeFormOpen, edgeFormOpen])

  const previewLines: string[] = []
  if (flowDetail?.nodes) {
    for (const node of flowDetail.nodes) {
      previewLines.push(`[${node.is_start ? 'Início' : 'Etapa'}] ${node.name} (${node.node_type})`)
      for (const edge of node.edges_out || []) {
        const dest = edge.to_node_name || edge.target_department_name || 'Encerrar'
        previewLines.push(`  -- ${edge.option_id} → ${dest}`)
      }
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <LoadingSpinner />
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100">Fluxos (lista e botões)</h1>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Novo fluxo
        </Button>
      </div>

      {createOpen && (
        <Card className="p-6">
          <h2 className="text-lg font-medium mb-4">Criar fluxo</h2>
          <div className="space-y-4">
            <div>
              <Label>Nome</Label>
              <Input
                value={newFlowName}
                onChange={(e) => setNewFlowName(e.target.value)}
                placeholder="Ex: Menu Inbox"
              />
            </div>
            <div>
              <Label>Escopo</Label>
              <div className="flex gap-4 mt-2">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    checked={newFlowScope === 'inbox'}
                    onChange={() => { setNewFlowScope('inbox'); setNewFlowDepartmentId(null) }}
                  />
                  <Inbox className="h-4 w-4" /> Inbox
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="radio"
                    checked={newFlowScope === 'department'}
                    onChange={() => setNewFlowScope('department')}
                  />
                  <Building2 className="h-4 w-4" /> Departamento
                </label>
              </div>
            </div>
            {newFlowScope === 'department' && (
              <div>
                <Label>Departamento</Label>
                <select
                  className="mt-1 w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2"
                  value={newFlowDepartmentId || ''}
                  onChange={(e) => setNewFlowDepartmentId(e.target.value || null)}
                >
                  <option value="">Selecione</option>
                  {departments.map((d) => (
                    <option key={d.id} value={d.id}>{d.name}</option>
                  ))}
                </select>
              </div>
            )}
            <div className="flex gap-2">
              <Button onClick={handleCreateFlow} disabled={creatingFlow}>
                {creatingFlow ? <LoadingSpinner size="sm" className="mr-1" /> : null}
                {creatingFlow ? 'Criando…' : 'Criar'}
              </Button>
              <Button variant="outline" onClick={() => setCreateOpen(false)} disabled={creatingFlow}>Cancelar</Button>
            </div>
          </div>
        </Card>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="p-4">
          <h3 className="font-medium mb-2">Fluxos</h3>
          {flows.length === 0 ? (
            <div className="text-center py-6 text-gray-500">
              <p className="text-sm mb-2">Nenhum fluxo ainda.</p>
              <Button size="sm" variant="outline" onClick={() => setCreateOpen(true)}>
                <Plus className="h-4 w-4 mr-1" /> Criar primeiro fluxo
              </Button>
            </div>
          ) : (
          <ul className="space-y-1">
            {flows.map((f) => (
              <li key={f.id}>
                <button
                  type="button"
                  onClick={() => setSelectedFlow(f)}
                  className={`w-full text-left px-3 py-2 rounded-lg text-sm ${
                    selectedFlow?.id === f.id
                      ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-200'
                      : 'hover:bg-gray-100 dark:hover:bg-gray-800'
                  }`}
                >
                  {f.name}
                  <span className="text-xs text-gray-500 ml-1">
                    {f.scope === 'inbox' ? 'Inbox' : (f.department_name || '')}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          )}
        </Card>

        <div className="md:col-span-2 space-y-4">
          {selectedFlow && detailLoading && (
            <Card className="p-8 flex items-center justify-center min-h-[200px]">
              <LoadingSpinner />
            </Card>
          )}
          {selectedFlow && !detailLoading && flowDetail && (
            <>
              <Card className="p-4">
                <h3 className="font-medium mb-2">Preview do fluxo</h3>
                <pre className="text-xs bg-gray-50 dark:bg-gray-900 p-3 rounded overflow-auto max-h-48">
                  {previewLines.length ? previewLines.join('\n') : 'Nenhum nó ainda. Adicione um nó abaixo.'}
                </pre>
              </Card>
              <Card className="p-4">
                <h3 className="font-medium mb-2">Enviar passo inicial (teste)</h3>
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                  Use um número que já tenha conversa no sistema.
                </p>
                <div className="flex gap-2">
                  <Input
                    placeholder="5511999999999"
                    value={testPhone}
                    onChange={(e) => setTestPhone(e.target.value)}
                    className="flex-1"
                  />
                  <Button onClick={handleSendTest} disabled={sendingTest}>
                    {sendingTest ? <LoadingSpinner size="sm" /> : <Play className="h-4 w-4 mr-1" />}
                    Enviar teste
                  </Button>
                </div>
              </Card>
              <Card className="p-4">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="font-medium">Nós ({flowDetail.nodes?.length || 0})</h3>
                  <Button size="sm" onClick={openAddNode}>
                    <Plus className="h-4 w-4 mr-1" /> Adicionar nó
                  </Button>
                </div>
                <ul className="space-y-3">
                  {(flowDetail.nodes || []).map((n) => (
                    <li key={n.id} className="border border-gray-200 dark:border-gray-700 rounded-lg p-3">
                      <div className="flex items-center justify-between">
                        <span className="flex items-center gap-2">
                          {n.node_type === 'list' ? <List className="h-4 w-4" /> : <MessageSquare className="h-4 w-4" />}
                          <span className="font-medium">{n.name}</span>
                          {n.is_start && <span className="text-xs bg-green-100 dark:bg-green-900/30 px-1.5 rounded">início</span>}
                        </span>
                        <div className="flex gap-1">
                          <Button size="sm" variant="outline" onClick={() => openEditNode(n)} aria-label={`Editar nó ${n.name}`}><Edit className="h-3 w-3" /></Button>
                          <Button size="sm" variant="outline" onClick={() => handleDeleteNodeClick(n)} disabled={deletingId === n.id} aria-label={`Excluir nó ${n.name}`}><Trash2 className="h-3 w-3 text-red-600" /></Button>
                        </div>
                      </div>
                      <div className="mt-2 pl-6">
                        <div className="text-xs text-gray-500 mb-1">Arestas (opção → destino)</div>
                        {(n.edges_out || []).length === 0 ? (
                          <span className="text-sm text-gray-400">Nenhuma aresta.</span>
                        ) : (
                          <ul className="space-y-1">
                            {(n.edges_out || []).map((e) => (
                              <li key={e.id} className="flex items-center justify-between text-sm">
                                <span><code className="bg-gray-100 dark:bg-gray-800 px-1 rounded">{e.option_id}</code> → {e.to_node_name || e.target_department_name || 'Encerrar'}</span>
                                <div className="flex gap-1">
                                  <button type="button" onClick={() => openEditEdge(e)} className="text-blue-600 dark:text-blue-400 hover:underline">Editar</button>
                                  <button type="button" onClick={() => handleDeleteEdgeClick(e)} disabled={deletingId === e.id} className="text-red-600 dark:text-red-400 hover:underline">Excluir</button>
                                </div>
                              </li>
                            ))}
                          </ul>
                        )}
                        <Button size="sm" variant="outline" className="mt-1" onClick={() => openAddEdge(n.id)}>
                          <Plus className="h-3 w-3 mr-1" /> Adicionar aresta
                        </Button>
                      </div>
                    </li>
                  ))}
                </ul>
              </Card>
            </>
          )}
          {!selectedFlow && !detailLoading && (
            <Card className="p-8 text-center text-gray-500">
              Selecione um fluxo na lista para ver o preview e editar nós e arestas, ou crie um novo fluxo.
            </Card>
          )}
        </div>
      </div>

      {/* Modal: Node form */}
      {nodeFormOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={() => setNodeFormOpen(false)}
          role="dialog"
          aria-modal="true"
          aria-labelledby="node-form-title"
        >
          <Card className="w-full max-w-lg max-h-[90vh] overflow-y-auto p-6" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h2 id="node-form-title" className="text-lg font-medium">{editingNode ? 'Editar nó' : 'Adicionar nó'}</h2>
              <button type="button" onClick={() => setNodeFormOpen(false)} className="text-gray-500 hover:text-gray-700" aria-label="Fechar"><X className="h-5 w-5" /></button>
            </div>
            <div className="space-y-3">
              <div>
                <Label>Nome interno</Label>
                <Input value={nodeName} onChange={(e) => setNodeName(e.target.value)} placeholder="ex: inicio, vendas" />
              </div>
              <div>
                <Label>Tipo</Label>
                <select
                  className="mt-1 w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2"
                  value={nodeType}
                  onChange={(e) => setNodeType(e.target.value as 'list' | 'buttons')}
                >
                  <option value="list">Lista</option>
                  <option value="buttons">Botões</option>
                </select>
              </div>
              <div className="flex gap-4">
                <div>
                  <Label>Ordem</Label>
                  <Input type="number" min={0} value={nodeOrder} onChange={(e) => setNodeOrder(parseInt(e.target.value, 10) || 0)} />
                </div>
                <label className="flex items-center gap-2 pt-6">
                  <input type="checkbox" checked={nodeIsStart} onChange={(e) => setNodeIsStart(e.target.checked)} />
                  <span className="text-sm">Nó inicial</span>
                </label>
              </div>
              <div>
                <Label>Corpo (texto da mensagem)</Label>
                <textarea
                  className="mt-1 w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 min-h-[60px]"
                  value={nodeBodyText}
                  onChange={(e) => setNodeBodyText(e.target.value)}
                  placeholder="Texto exibido antes da lista/botões"
                />
              </div>
              {nodeType === 'list' && (
                <div>
                  <Label>Texto do botão (lista)</Label>
                  <Input value={nodeButtonText} onChange={(e) => setNodeButtonText(e.target.value)} placeholder="Ex: Ver opções" />
                </div>
              )}
              <div>
                <Label>Header (opcional)</Label>
                <Input value={nodeHeaderText} onChange={(e) => setNodeHeaderText(e.target.value)} placeholder="Máx. 60 caracteres" />
              </div>
              <div>
                <Label>Footer (opcional)</Label>
                <Input value={nodeFooterText} onChange={(e) => setNodeFooterText(e.target.value)} placeholder="Máx. 60 caracteres" />
              </div>
              {nodeType === 'list' && (
                <div>
                  <Label>Seções (JSON)</Label>
                  <textarea
                    className="mt-1 w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 font-mono text-sm min-h-[100px]"
                    value={nodeSectionsJson}
                    onChange={(e) => setNodeSectionsJson(e.target.value)}
                    placeholder='[{"title":"...","rows":[{"id":"...","title":"...","description":"..."}]}]'
                  />
                </div>
              )}
              {nodeType === 'buttons' && (
                <div>
                  <Label>Botões (JSON, máx. 3)</Label>
                  <textarea
                    className="mt-1 w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 font-mono text-sm min-h-[80px]"
                    value={nodeButtonsJson}
                    onChange={(e) => setNodeButtonsJson(e.target.value)}
                    placeholder='[{"id":"...","title":"..."}]'
                  />
                </div>
              )}
            </div>
            <div className="flex gap-2 mt-4">
              <Button onClick={handleSaveNode} disabled={savingNode}>{savingNode ? <LoadingSpinner size="sm" /> : 'Salvar'}</Button>
              <Button variant="outline" onClick={() => setNodeFormOpen(false)}>Cancelar</Button>
            </div>
          </Card>
        </div>
      )}

      {/* Modal: Edge form */}
      {edgeFormOpen && flowDetail?.nodes && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={() => setEdgeFormOpen(false)}
          role="dialog"
          aria-modal="true"
          aria-labelledby="edge-form-title"
        >
          <Card className="w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h2 id="edge-form-title" className="text-lg font-medium">{editingEdge ? 'Editar aresta' : 'Adicionar aresta'}</h2>
              <button type="button" onClick={() => setEdgeFormOpen(false)} className="text-gray-500 hover:text-gray-700" aria-label="Fechar"><X className="h-5 w-5" /></button>
            </div>
            <div className="space-y-3">
              <div>
                <Label>Nó de origem</Label>
                <select
                  className="mt-1 w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2"
                  value={edgeFromNodeId || ''}
                  onChange={(e) => setEdgeFromNodeId(e.target.value || null)}
                  disabled={!!editingEdge}
                >
                  {flowDetail.nodes.map((n) => (
                    <option key={n.id} value={n.id}>{n.name}</option>
                  ))}
                </select>
              </div>
              <div>
                <Label>ID da opção (rowId / id do botão)</Label>
                <Input value={edgeOptionId} onChange={(e) => setEdgeOptionId(e.target.value)} placeholder="ex: op1, btn1" />
              </div>
              <div>
                <Label>Destino</Label>
                <select
                  className="mt-1 w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2"
                  value={edgeTargetAction}
                  onChange={(e) => setEdgeTargetAction(e.target.value)}
                >
                  <option value="next">Próxima etapa (outro nó)</option>
                  <option value="transfer">Transferir para departamento</option>
                  <option value="end">Encerrar conversa</option>
                </select>
              </div>
              {edgeTargetAction === 'next' && (
                <div>
                  <Label>Próximo nó</Label>
                  <select
                    className="mt-1 w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2"
                    value={edgeToNodeId || ''}
                    onChange={(e) => setEdgeToNodeId(e.target.value || null)}
                  >
                    <option value="">Selecione</option>
                    {flowDetail.nodes.filter((n) => n.id !== edgeFromNodeId).map((n) => (
                      <option key={n.id} value={n.id}>{n.name}</option>
                    ))}
                  </select>
                </div>
              )}
              {edgeTargetAction === 'transfer' && (
                <div>
                  <Label>Departamento</Label>
                  <select
                    className="mt-1 w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2"
                    value={edgeTargetDepartmentId || ''}
                    onChange={(e) => setEdgeTargetDepartmentId(e.target.value || null)}
                  >
                    <option value="">Selecione</option>
                    {departments.map((d) => (
                      <option key={d.id} value={d.id}>{d.name}</option>
                    ))}
                  </select>
                </div>
              )}
            </div>
            <div className="flex gap-2 mt-4">
              <Button onClick={handleSaveEdge} disabled={savingEdge}>{savingEdge ? <LoadingSpinner size="sm" /> : 'Salvar'}</Button>
              <Button variant="outline" onClick={() => setEdgeFormOpen(false)}>Cancelar</Button>
            </div>
          </Card>
        </div>
      )}

      <ConfirmDialog
        show={!!confirmDeleteNode}
        title="Excluir nó"
        message={confirmDeleteNode ? `Excluir o nó "${confirmDeleteNode.name}"? As arestas ligadas também serão removidas.` : ''}
        confirmText="Excluir"
        variant="danger"
        onConfirm={handleDeleteNodeConfirm}
        onCancel={() => setConfirmDeleteNode(null)}
      />
      <ConfirmDialog
        show={!!confirmDeleteEdge}
        title="Excluir aresta"
        message={confirmDeleteEdge ? `Excluir a aresta "${confirmDeleteEdge.option_id}"?` : ''}
        confirmText="Excluir"
        variant="danger"
        onConfirm={handleDeleteEdgeConfirm}
        onCancel={() => setConfirmDeleteEdge(null)}
      />
    </div>
  )
}
