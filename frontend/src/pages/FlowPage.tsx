/**
 * Página de Fluxos: integração Typebot por Inbox ou departamento.
 * Lista fluxos, vincula Typebot (Public ID + URL base), escopo e envio de teste.
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Plus, Edit, Trash2, Building2, Inbox, Play, X, Zap, MessageSquare, ChevronDown, ChevronUp, HelpCircle } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Input } from '../components/ui/Input'
import { Label } from '../components/ui/Label'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import ConfirmDialog from '../components/ui/ConfirmDialog'
import { api } from '../lib/api'

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

function isValidHttpUrl(s: string): boolean {
  const t = (s || '').trim()
  if (!t) return false
  try {
    const u = new URL(t)
    return u.protocol === 'http:' || u.protocol === 'https:'
  } catch {
    return false
  }
}

async function validateTypebotConfig(api: any, typebot_public_id: string, typebot_base_url: string): Promise<{ valid: boolean; detail?: string }> {
  const pid = (typebot_public_id || '').trim()
  const base = (typebot_base_url || '').trim()
  if (!pid) return { valid: false, detail: 'Public ID do Typebot é obrigatório.' }
  if (base && !isValidHttpUrl(base)) return { valid: false, detail: 'URL base do Typebot deve ser uma URL válida (ex: https://typebot.co).' }
  try {
    const { data, status: resStatus } = await api.post('/chat/flows/validate_typebot/', {
      typebot_public_id: pid,
      typebot_base_url: base || undefined,
    })
    if (resStatus >= 200 && resStatus < 300 && data?.valid === true) return { valid: true }
    return { valid: false, detail: (data?.detail as string) || 'Typebot não pôde ser validado.' }
  } catch (e: any) {
    const detail = e?.response?.data?.detail ?? getApiError(e)
    return { valid: false, detail }
  }
}

interface WhatsAppInstanceOption {
  id: string
  friendly_name: string
  instance_name: string
}

interface Flow {
  id: string
  name: string
  description?: string | null
  scope: string
  department: string | null
  department_name: string | null
  whatsapp_instance?: string | null
  whatsapp_instance_name?: string | null
  typebot_public_id?: string | null
  typebot_base_url?: string | null
  typebot_prefilled_extra?: Record<string, string> | null
  typebot_internal_id?: string | null
  typebot_api_key?: string | null
  is_active: boolean
  nodes?: FlowNode[]
}

interface FlowNode {
  id: string
  flow: string
  node_type: 'list' | 'buttons' | 'message' | 'image' | 'file' | 'delay'
  name: string
  order: number
  is_start: boolean
  body_text: string
  button_text: string
  header_text?: string
  footer_text?: string
  sections: Array<{ title: string; rows: Array<{ id: string; title: string; description?: string }> }>
  buttons: Array<{ id: string; title: string }>
  media_url?: string
  position_x?: number | null
  position_y?: number | null
  delay_seconds?: number | null
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

type SectionForm = { title: string; rows: { id: string; title: string; description: string }[] }
type ButtonForm = { id: string; title: string }

const defaultSections: SectionForm[] = [{ title: 'Opções', rows: [{ id: 'op1', title: 'Opção 1', description: '' }, { id: 'op2', title: 'Opção 2', description: '' }] }]
const defaultButtons: ButtonForm[] = [{ id: 'btn1', title: 'Botão 1' }, { id: 'btn2', title: 'Botão 2' }]

function parseSectionsSafe(val: unknown): SectionForm[] {
  if (!Array.isArray(val) || val.length === 0) return defaultSections
  return val.slice(0, 10).map((sec) => {
    const s = sec && typeof sec === 'object' && sec !== null ? sec as Record<string, unknown> : {}
    const rows = Array.isArray(s.rows) ? s.rows.slice(0, 10).map((r: unknown) => {
      const row = r && typeof r === 'object' && r !== null ? r as Record<string, unknown> : {}
      return { id: String(row.id ?? ''), title: String(row.title ?? ''), description: String(row.description ?? '') }
    }) : []
    return { title: String(s.title ?? ''), rows: rows.length ? rows : [{ id: 'op1', title: '', description: '' }] }
  })
}
function parseButtonsSafe(val: unknown): ButtonForm[] {
  if (!Array.isArray(val) || val.length === 0) return defaultButtons
  return val.slice(0, 3).map((b: unknown) => {
    const o = b && typeof b === 'object' && b !== null ? b as Record<string, unknown> : {}
    return { id: String(o.id ?? ''), title: String(o.title ?? '') }
  })
}

const FLOW_TYPEBOT_FAQ: { pergunta: string; resposta: string }[] = [
  { pergunta: 'Quais variáveis o Sense envia ao Typebot?', resposta: 'conversation_id, contact_phone, contact_name, tenant_id, department_id (se houver); mais as variáveis extras (JSON) configuradas no fluxo.' },
  { pergunta: 'O que são variáveis extras?', resposta: 'JSON no cadastro do fluxo enviado em todo startChat. Use no Typebot variáveis com o mesmo nome. Opção "Carregar variáveis" usa ID interno + API key e aplica ao JSON.' },
  { pergunta: 'O que são instruções no texto?', resposta: 'Trechos no formato #{"chave": valor} numa mensagem de texto. O Sense executa a ação e remove o trecho antes de enviar ao WhatsApp (o cliente não vê).' },
  { pergunta: 'Como encerrar a conversa pelo Typebot?', resposta: 'Inclua #{"closeTicket": true} (ou encerrar, closeConversation com valor truthy) no texto. Pode estar na mesma mensagem da despedida.' },
  { pergunta: 'Como transferir para um departamento?', resposta: 'Inclua #{"transferTo": "Nome do Departamento"}. O nome deve ser igual ao cadastrado no Sense (Configurações > Departamentos). Maiúsculas/minúsculas não importam.' },
  { pergunta: 'O nome do departamento pode ter espaços?', resposta: 'Sim. Use o nome completo como cadastrado (ex.: "Suporte Técnico", "Atendimento Comercial"). Apenas espaços no início e no fim são ignorados.' },
  { pergunta: 'Webhook como alternativa', resposta: 'Para enviar variáveis de volta ao Sense ou encerrar via variável, use o bloco Webhook apontando para POST /api/chat/webhooks/typebot/ (documentação no guia).' },
  { pergunta: 'Onde ver mais?', resposta: 'Guia completo na documentação do projeto (FLUXOS_TYPEBOT_GUIA) ou com o suporte.' },
]

export default function FlowPage() {
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
  const [confirmDeleteFlow, setConfirmDeleteFlow] = useState<Flow | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  // Edit flow modal
  const [editFlowOpen, setEditFlowOpen] = useState(false)
  const [editFlowName, setEditFlowName] = useState('')
  const [editFlowDescription, setEditFlowDescription] = useState('')
  const [editFlowScope, setEditFlowScope] = useState<'inbox' | 'department'>('inbox')
  const [editFlowDepartmentId, setEditFlowDepartmentId] = useState<string | null>(null)
  const [editFlowInstanceId, setEditFlowInstanceId] = useState<string | null>(null)
  const [editTypebotPublicId, setEditTypebotPublicId] = useState('')
  const [editTypebotBaseUrl, setEditTypebotBaseUrl] = useState('')
  const [editTypebotPrefilledExtra, setEditTypebotPrefilledExtra] = useState('')
  const [editTypebotInternalId, setEditTypebotInternalId] = useState('')
  const [editTypebotApiKey, setEditTypebotApiKey] = useState('')
  const [typebotVariablesList, setTypebotVariablesList] = useState<Array<{ id: string; name: string }>>([])
  const [typebotVariableValues, setTypebotVariableValues] = useState<Record<string, string>>({})
  const [loadingTypebotVariables, setLoadingTypebotVariables] = useState(false)
  const [editFlowVarsExpanded, setEditFlowVarsExpanded] = useState(false)
  const [flowFaqExpanded, setFlowFaqExpanded] = useState(false)
  const [savingFlow, setSavingFlow] = useState(false)
  const [flowInstances, setFlowInstances] = useState<WhatsAppInstanceOption[]>([])
  const [newFlowInstanceId, setNewFlowInstanceId] = useState<string | null>(null)
  const [newFlowTypebotPublicId, setNewFlowTypebotPublicId] = useState('')
  const [newFlowTypebotBaseUrl, setNewFlowTypebotBaseUrl] = useState('')
  const [newFlowTypebotPrefilledExtra, setNewFlowTypebotPrefilledExtra] = useState('')

  // Node form (add / edit)
  const [nodeFormOpen, setNodeFormOpen] = useState(false)
  const [editingNode, setEditingNode] = useState<FlowNode | null>(null)
  const [nodeName, setNodeName] = useState('')
  const [nodeType, setNodeType] = useState<'list' | 'buttons' | 'message' | 'image' | 'file' | 'delay'>('list')
  const [nodeOrder, setNodeOrder] = useState(0)
  const [nodeIsStart, setNodeIsStart] = useState(false)
  const [nodeBodyText, setNodeBodyText] = useState('')
  const [nodeButtonText, setNodeButtonText] = useState('')
  const [nodeHeaderText, setNodeHeaderText] = useState('')
  const [nodeFooterText, setNodeFooterText] = useState('')
  const [nodeSections, setNodeSections] = useState<SectionForm[]>(defaultSections)
  const [nodeButtons, setNodeButtons] = useState<ButtonForm[]>(defaultButtons)
  const [nodeMediaUrl, setNodeMediaUrl] = useState('')
  const [nodeDelaySeconds, setNodeDelaySeconds] = useState(5)
  const [savingNode, setSavingNode] = useState(false)
  const [pendingDropPosition, setPendingDropPosition] = useState<{ x: number; y: number } | null>(null)
  const [isDraggingFromPalette, setIsDraggingFromPalette] = useState(false)

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

  const fetchFlowInstances = async () => {
    try {
      const { data } = await api.get('/chat/flows/available_instances/')
      setFlowInstances(Array.isArray(data) ? data : [])
    } catch {
      setFlowInstances([])
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
    Promise.all([fetchFlows(), fetchDepartments(), fetchFlowInstances()]).finally(() => setLoading(false))
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
    const pid = newFlowTypebotPublicId.trim()
    const base = newFlowTypebotBaseUrl.trim()
    if (!pid) {
      toast.error('Public ID do Typebot é obrigatório')
      return
    }
    if (base && !isValidHttpUrl(base)) {
      toast.error('URL base do Typebot deve ser uma URL válida (ex: https://typebot.co)')
      return
    }
    setCreatingFlow(true)
    try {
      const validation = await validateTypebotConfig(api, pid, base)
      if (!validation.valid) {
        toast.error(validation.detail ?? 'Typebot não pôde ser validado')
        setCreatingFlow(false)
        return
      }
      let prefilledExtra: Record<string, string> = {}
      try {
        const raw = newFlowTypebotPrefilledExtra.trim()
        if (raw) {
          const parsed = JSON.parse(raw)
          if (typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)) {
            prefilledExtra = Object.fromEntries(
              Object.entries(parsed).filter(([, v]) => v != null).map(([k, v]) => [String(k).trim(), String(v)])
            )
          }
        }
      } catch {
        toast.error('Variáveis extras: JSON inválido')
        setCreatingFlow(false)
        return
      }
      const { data } = await api.post('/chat/flows/', {
        name: newFlowName.trim(),
        scope: newFlowScope,
        department: newFlowScope === 'department' ? newFlowDepartmentId : null,
        whatsapp_instance: newFlowInstanceId || null,
        typebot_public_id: pid || null,
        typebot_base_url: base || null,
        typebot_prefilled_extra: prefilledExtra,
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
      setNewFlowInstanceId(null)
      setNewFlowTypebotPublicId('')
      setNewFlowTypebotBaseUrl('')
      setNewFlowTypebotPrefilledExtra('')
      await fetchFlows()
      setSelectedFlow({
        id: String(id),
        name: data?.name ?? '',
        scope: data?.scope ?? 'inbox',
        department: data?.department ?? null,
        department_name: data?.department_name ?? null,
        whatsapp_instance: data?.whatsapp_instance ?? null,
        whatsapp_instance_name: data?.whatsapp_instance_name ?? null,
        typebot_public_id: data?.typebot_public_id ?? null,
        typebot_base_url: data?.typebot_base_url ?? null,
        typebot_prefilled_extra: data?.typebot_prefilled_extra ?? null,
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

  const openEditFlow = () => {
    if (!selectedFlow) return
    setEditFlowName(selectedFlow.name)
    setEditFlowDescription(selectedFlow.description ?? '')
    setEditFlowScope((selectedFlow.scope as 'inbox' | 'department') || 'inbox')
    setEditFlowDepartmentId(selectedFlow.department || null)
    setEditFlowInstanceId(selectedFlow.whatsapp_instance ?? null)
    setEditTypebotPublicId(selectedFlow.typebot_public_id ?? '')
    setEditTypebotBaseUrl(selectedFlow.typebot_base_url ?? '')
    setEditTypebotInternalId(flowDetail?.typebot_internal_id ?? selectedFlow.typebot_internal_id ?? '')
    setEditTypebotApiKey(flowDetail?.typebot_api_key ?? selectedFlow.typebot_api_key ?? '')
    setTypebotVariablesList([])
    setTypebotVariableValues({})
    setEditFlowVarsExpanded(false)
    try {
      const extra = selectedFlow.typebot_prefilled_extra
      setEditTypebotPrefilledExtra(typeof extra === 'object' && extra !== null ? JSON.stringify(extra, null, 2) : '{}')
    } catch {
      setEditTypebotPrefilledExtra('{}')
    }
    setEditFlowOpen(true)
  }

  const handleSaveFlow = async () => {
    if (!selectedFlow?.id || savingFlow) return
    const name = editFlowName.trim()
    if (!name) {
      toast.error('Nome do fluxo é obrigatório')
      return
    }
    if (editFlowScope === 'department' && !editFlowDepartmentId) {
      toast.error('Selecione o departamento')
      return
    }
    const pid = editTypebotPublicId.trim()
    const base = editTypebotBaseUrl.trim()
    if (!pid) {
      toast.error('Public ID do Typebot é obrigatório')
      return
    }
    if (base && !isValidHttpUrl(base)) {
      toast.error('URL base do Typebot deve ser uma URL válida (ex: https://typebot.co)')
      return
    }
    setSavingFlow(true)
    try {
      const validation = await validateTypebotConfig(api, pid, base)
      if (!validation.valid) {
        toast.error(validation.detail ?? 'Typebot não pôde ser validado')
        setSavingFlow(false)
        return
      }
      let prefilledExtra: Record<string, string> | null = null
      try {
        const raw = editTypebotPrefilledExtra.trim()
        if (raw) {
          const parsed = JSON.parse(raw)
          if (typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)) {
            prefilledExtra = Object.fromEntries(
              Object.entries(parsed).filter(([, v]) => v != null).map(([k, v]) => [String(k).trim(), String(v)])
            )
          }
        }
      } catch {
        toast.error('Variáveis extras: JSON inválido')
        setSavingFlow(false)
        return
      }
      const { data } = await api.patch(`/chat/flows/${selectedFlow.id}/`, {
        name,
        description: (editFlowDescription || '').trim(),
        scope: editFlowScope,
        department: editFlowScope === 'department' ? editFlowDepartmentId : null,
        whatsapp_instance: editFlowInstanceId || null,
        typebot_public_id: pid || null,
        typebot_base_url: base || null,
        typebot_prefilled_extra: prefilledExtra || {},
        typebot_internal_id: editTypebotInternalId.trim() || null,
        typebot_api_key: editTypebotApiKey.trim() || null,
      })
      toast.success('Fluxo atualizado')
      setEditFlowOpen(false)
      await fetchFlows()
      setSelectedFlow({
        id: data?.id ?? selectedFlow.id,
        name: data?.name ?? name,
        description: (data?.description ?? editFlowDescription ?? '') || '',
        scope: data?.scope ?? editFlowScope,
        department: data?.department ?? null,
        department_name: data?.department_name ?? null,
        whatsapp_instance: data?.whatsapp_instance ?? null,
        whatsapp_instance_name: data?.whatsapp_instance_name ?? null,
        typebot_public_id: data?.typebot_public_id ?? null,
        typebot_base_url: data?.typebot_base_url ?? null,
        typebot_prefilled_extra: data?.typebot_prefilled_extra ?? null,
        typebot_internal_id: data?.typebot_internal_id ?? null,
        typebot_api_key: data?.typebot_api_key ?? null,
        is_active: data?.is_active ?? selectedFlow.is_active,
      })
      selectedFlowIdRef.current = selectedFlow.id
      await fetchFlowDetail(selectedFlow.id)
    } catch (e: any) {
      toast.error(getApiError(e))
    } finally {
      setSavingFlow(false)
    }
  }

  const handleDeleteFlowClick = () => selectedFlow && setConfirmDeleteFlow(selectedFlow)
  const handleDeleteFlowConfirm = async () => {
    const flow = confirmDeleteFlow
    setConfirmDeleteFlow(null)
    if (!flow?.id) return
    setDeletingId(flow.id)
    try {
      await api.delete(`/chat/flows/${flow.id}/`)
      toast.success('Fluxo excluído')
      await fetchFlows()
      setSelectedFlow(null)
      setFlowDetail(null)
      selectedFlowIdRef.current = null
    } catch (e: any) {
      toast.error(getApiError(e))
    } finally {
      setDeletingId(null)
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

  /** Sugere nome único para nova etapa (ex: mensagem_1, lista_1, etapa_2). */
  const suggestNodeName = useCallback(
    (nodeType: 'message' | 'list' | 'buttons' | 'image' | 'file' | 'delay', isStart: boolean): string => {
      const nodes = flowDetail?.nodes ?? []
      const prefix = isStart ? 'inicio' : { message: 'mensagem', list: 'lista', buttons: 'botoes', image: 'imagem', file: 'arquivo', delay: 'timer' }[nodeType]
      const existing = new Set(nodes.map((n) => n.name))
      for (let i = 1; i <= (nodes.length + 5); i++) {
        const name = `${prefix}_${i}`
        if (!existing.has(name)) return name
      }
      return `${prefix}_${Date.now().toString(36)}`
    },
    [flowDetail?.nodes]
  )

  const closeNodeForm = useCallback(() => {
    setNodeFormOpen(false)
    setPendingDropPosition(null)
  }, [])

  const openAddNode = () => {
    setPendingDropPosition(null)
    setEditingNode(null)
    setNodeName('')
    setNodeType('list')
    setNodeOrder(flowDetail?.nodes?.length ?? 0)
    setNodeIsStart((flowDetail?.nodes?.length ?? 0) === 0)
    setNodeBodyText('')
    setNodeButtonText('Ver opções')
    setNodeHeaderText('')
    setNodeFooterText('')
    setNodeSections(defaultSections)
    setNodeButtons(defaultButtons)
    setNodeMediaUrl('')
    setNodeDelaySeconds(5)
    setNodeFormOpen(true)
  }

  /** Abre o modal "Adicionar etapa" após soltar um bloco da paleta no canvas; POST só ao salvar. */
  const openAddNodeFromDrop = useCallback(
    (position: { x: number; y: number }, nodeType: 'message' | 'list' | 'buttons' | 'image' | 'file' | 'delay', isStart: boolean) => {
      setIsDraggingFromPalette(false)
      const nodes = flowDetail?.nodes ?? []
      const nextOrder = nodes.length === 0 ? 0 : Math.max(...nodes.map((n) => n.order), 0) + 1
      setPendingDropPosition(position)
      setEditingNode(null)
      setNodeType(nodeType)
      setNodeOrder(nextOrder)
      setNodeIsStart(isStart)
      setNodeName(suggestNodeName(nodeType, isStart))
      setNodeBodyText('')
      setNodeButtonText('Ver opções')
      setNodeHeaderText('')
      setNodeFooterText('')
      setNodeSections(defaultSections)
      setNodeButtons(defaultButtons)
      setNodeMediaUrl('')
      setNodeFormOpen(true)
    },
    [flowDetail?.nodes, suggestNodeName]
  )

  const openEditNode = (n: FlowNode) => {
    setPendingDropPosition(null)
    setEditingNode(n)
    setNodeName(n.name)
    setNodeType(n.node_type)
    setNodeOrder(n.order)
    setNodeIsStart(n.is_start)
    setNodeBodyText(n.body_text || '')
    setNodeButtonText(n.button_text || '')
    setNodeHeaderText(n.header_text || '')
    setNodeFooterText(n.footer_text || '')
    setNodeSections(parseSectionsSafe(n.sections))
    setNodeButtons(parseButtonsSafe(n.buttons))
    setNodeMediaUrl(n.media_url || '')
    setNodeDelaySeconds(typeof n.delay_seconds === 'number' ? n.delay_seconds : 5)
    setNodeFormOpen(true)
  }

  const handleSaveNode = async () => {
    if (!selectedFlow?.id || !nodeName.trim()) {
      toast.error('Nome da etapa é obrigatório')
      return
    }
    let sections: FlowNode['sections'] = []
    let buttons: FlowNode['buttons'] = []
    if (nodeType === 'list') {
      if (nodeSections.length === 0) {
        toast.error('Adicione ao menos uma seção')
        return
      }
      const ids = new Set<string>()
      for (const sec of nodeSections) {
        if (!sec.title.trim()) {
          toast.error('Cada seção precisa de um título')
          return
        }
        if (!sec.rows.length) {
          toast.error('Cada seção precisa de ao menos uma linha')
          return
        }
        for (const row of sec.rows) {
          if (!row.id.trim() || !row.title.trim()) {
            toast.error('Cada linha precisa de id e título')
            return
          }
          if (ids.has(row.id.trim())) {
            toast.error(`ID duplicado: "${row.id}". Use ids únicos.`)
            return
          }
          ids.add(row.id.trim())
        }
      }
      sections = nodeSections.slice(0, 10).map((sec) => ({
        title: sec.title.trim(),
        rows: sec.rows.slice(0, 10).map((r) => ({ id: r.id.trim(), title: r.title.trim(), description: (r.description || '').trim() })),
      }))
    } else if (nodeType === 'buttons') {
      if (nodeButtons.length < 1 || nodeButtons.length > 3) {
        toast.error('Informe entre 1 e 3 botões')
        return
      }
      const ids = new Set<string>()
      for (const b of nodeButtons) {
        if (!b.id.trim() || !b.title.trim()) {
          toast.error('Cada botão precisa de id e título')
          return
        }
        if (ids.has(b.id.trim())) {
          toast.error(`ID duplicado: "${b.id}". Use ids únicos.`)
          return
        }
        ids.add(b.id.trim())
      }
      buttons = nodeButtons.slice(0, 3).map((b) => ({ id: b.id.trim(), title: b.title.trim() }))
    }
    if (nodeType === 'message' && !nodeBodyText.trim()) {
      toast.error('Texto da mensagem é obrigatório')
      return
    }
    if ((nodeType === 'image' || nodeType === 'file') && !nodeMediaUrl.trim()) {
      toast.error('URL da mídia é obrigatória para este tipo')
      return
    }
    if (nodeType === 'delay') {
      const sec = parseInt(String(nodeDelaySeconds), 10)
      if (Number.isNaN(sec) || sec < 1 || sec > 86400) {
        toast.error('Timer: informe entre 1 e 86400 segundos (máx. 24h)')
        return
      }
    }
    setSavingNode(true)
    try {
      const payload: Record<string, unknown> = {
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
      if (nodeType === 'image' || nodeType === 'file') payload.media_url = nodeMediaUrl.trim()
      if (nodeType === 'delay') payload.delay_seconds = Math.min(86400, Math.max(1, parseInt(String(nodeDelaySeconds), 10) || 5))
      if (pendingDropPosition) {
        payload.position_x = pendingDropPosition.x
        payload.position_y = pendingDropPosition.y
      }
      if (editingNode) {
        await api.patch(`/chat/flow-nodes/${editingNode.id}/`, payload)
        toast.success('Etapa atualizada')
      } else {
        await api.post('/chat/flow-nodes/', payload)
        toast.success('Etapa criada')
      }
      closeNodeForm()
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
      toast.success('Etapa excluída')
      fetchFlowDetail(selectedFlow.id)
    } catch (e: any) {
      toast.error(getApiError(e))
    } finally {
      setDeletingId(null)
    }
  }

  const openAddEdge = (fromNodeId: string) => {
    const fromNode = flowDetail?.nodes?.find((n) => n.id === fromNodeId)
    let suggestedOptionId = ''
    if (fromNode?.node_type === 'list' && fromNode.sections?.length) {
      const firstRow = fromNode.sections[0]?.rows?.[0]
      if (firstRow?.id) suggestedOptionId = firstRow.id
    } else if (fromNode?.node_type === 'buttons' && fromNode.buttons?.length) {
      if (fromNode.buttons[0]?.id) suggestedOptionId = fromNode.buttons[0].id
    } else if (fromNode?.node_type === 'message') {
      suggestedOptionId = '1' // texto que o usuário deve digitar para avançar
    } else if (fromNode?.node_type === 'delay') {
      suggestedOptionId = 'next' // timer tem uma única saída
    }
    if (!suggestedOptionId) suggestedOptionId = 'opcao1'
    setEditingEdge(null)
    setEdgeFromNodeId(fromNodeId)
    setEdgeOptionId(suggestedOptionId)
    setEdgeToNodeId(null)
    setEdgeTargetDepartmentId(null)
    setEdgeTargetAction('next')
    setEdgeFormOpen(true)
  }

  /** Abre o modal de conexão ao soltar uma conexão do Handle no canvas (de source → target). */
  const openAddEdgeFromConnect = useCallback(
    (fromNodeId: string, toNodeId: string) => {
      if (!flowDetail?.nodes) return
      const fromNode = flowDetail.nodes.find((n) => n.id === fromNodeId)
      let suggestedOptionId = 'ok'
      if (fromNode?.node_type === 'list' && fromNode.sections?.length) {
        const firstRow = fromNode.sections[0]?.rows?.[0]
        if (firstRow?.id) suggestedOptionId = firstRow.id
      } else if (fromNode?.node_type === 'buttons' && fromNode.buttons?.length) {
        if (fromNode.buttons[0]?.id) suggestedOptionId = fromNode.buttons[0].id
      } else if (fromNode?.node_type === 'message') {
        suggestedOptionId = '1'
      } else if (fromNode?.node_type === 'delay') {
        suggestedOptionId = 'next'
      }
      setEditingEdge(null)
      setEdgeFromNodeId(fromNodeId)
      setEdgeOptionId(suggestedOptionId)
      setEdgeToNodeId(toNodeId)
      setEdgeTargetDepartmentId(null)
      setEdgeTargetAction('next')
      setEdgeFormOpen(true)
    },
    [flowDetail?.nodes]
  )

  const handleCanvasNodeClick = useCallback(
    (nodeId: string) => {
      const node = flowDetail?.nodes?.find((n) => n.id === nodeId)
      if (node) openEditNode(node)
    },
    [flowDetail?.nodes]
  )

  const handleCanvasConnect = useCallback(
    (params: { source: string; target: string }) => openAddEdgeFromConnect(params.source, params.target),
    [openAddEdgeFromConnect]
  )

  const handleCanvasNodeDragStop = useCallback(
    async (nodeId: string, position: { x: number; y: number }) => {
      if (!selectedFlow?.id) return
      try {
        await api.patch(`/chat/flow-nodes/${nodeId}/`, {
          position_x: position.x,
          position_y: position.y,
        })
        await fetchFlowDetail(selectedFlow.id)
        toast.success('Posição salva')
      } catch (e: any) {
        toast.error(getApiError(e))
      }
    },
    [selectedFlow?.id, fetchFlowDetail]
  )

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
    if (savingEdge) return
    if (!edgeFromNodeId) {
      toast.error('Selecione a etapa de origem')
      return
    }
    if (!edgeOptionId.trim()) {
      toast.error('Informe a opção (ex.: id da linha da lista ou do botão)')
      return
    }
    if (edgeTargetAction === 'next' && !edgeToNodeId) {
      toast.error('Selecione a próxima etapa para ação "Próxima etapa"')
      return
    }
    if (edgeTargetAction === 'transfer' && !edgeTargetDepartmentId) {
      toast.error('Selecione o departamento para ação "Transferir"')
      return
    }

    // Validação extra: para listas/botões, a opção precisa existir no nó de origem
    const fromNode = flowDetail?.nodes?.find((n) => n.id === edgeFromNodeId)
    if (fromNode && edgeOptionId.trim()) {
      const optionIdTrimmed = edgeOptionId.trim()
      if (fromNode.node_type === 'list') {
        const validIds = (fromNode.sections || []).flatMap((sec) => (sec.rows || []).map((r) => r.id))
        if (validIds.length > 0 && !validIds.includes(optionIdTrimmed)) {
          toast.error('Para listas, use um ID de linha existente (campo "id" da opção).')
          return
        }
      } else if (fromNode.node_type === 'buttons') {
        const validIds = (fromNode.buttons || []).map((b) => b.id)
        if (validIds.length > 0 && !validIds.includes(optionIdTrimmed)) {
          toast.error('Para botões, use um ID de botão existente (campo "id" do botão).')
          return
        }
      }
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
        toast.success('Conexão atualizada')
      } else {
        await api.post('/chat/flow-edges/', payload)
        toast.success('Conexão criada')
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
      toast.success('Conexão excluída')
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
        if (nodeFormOpen) closeNodeForm()
        else if (edgeFormOpen) setEdgeFormOpen(false)
        else if (editFlowOpen) setEditFlowOpen(false)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [nodeFormOpen, edgeFormOpen, editFlowOpen, closeNodeForm])

  const previewLines: string[] = []
  if (flowDetail?.nodes) {
    for (const node of flowDetail.nodes) {
      previewLines.push(`[${node.is_start ? 'Início' : 'Etapa'}] ${node.name} (${node.node_type})`)
      for (const edge of node.edges_out || []) {
        const dest = edge.target_action === 'transfer'
          ? (edge.target_department_name ? `Transferir: ${edge.target_department_name}` : 'Transferir')
          : edge.target_action === 'end'
            ? 'Encerrar'
            : edge.to_node_name
              ? `Próxima: ${edge.to_node_name}`
              : 'Próxima etapa'
        previewLines.push(`  -- ${edge.option_id} → ${dest}`)
      }
    }
  }

  if (loading) {
    return (
      <div className="max-w-5xl mx-auto p-6 space-y-6 animate-fade-in">
        <div className="flex items-center justify-between">
          <div className="h-8 w-56 rounded-lg bg-gray-200 dark:bg-gray-700 animate-pulse" />
          <div className="h-10 w-32 rounded-lg bg-gray-200 dark:bg-gray-700 animate-pulse" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Card className="p-4">
            <div className="h-5 w-20 rounded bg-gray-200 dark:bg-gray-700 animate-pulse mb-4" />
            <div className="space-y-2">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-10 rounded-lg bg-gray-100 dark:bg-gray-800 animate-pulse" />
              ))}
            </div>
          </Card>
          <div className="md:col-span-2 space-y-4">
            <Card className="p-4 h-[420px] flex items-center justify-center">
              <LoadingSpinner />
            </Card>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-gray-900 dark:text-gray-100 tracking-tight">Fluxos</h1>
        <Button onClick={() => setCreateOpen(true)} className="transition-all duration-200 hover:scale-[1.02] active:scale-[0.98]">
          <Plus className="h-4 w-4 mr-2" />
          Novo fluxo
        </Button>
      </div>

      <AnimatePresence>
      {createOpen && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          exit={{ opacity: 0, height: 0 }}
          transition={{ duration: 0.2 }}
          className="overflow-hidden"
        >
        <Card className="p-6 rounded-xl border-gray-200/80 dark:border-gray-700/80 shadow-sm">
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
            <div>
              <Label>Instância WhatsApp (enviar/responder por)</Label>
              <select
                className="mt-1 w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2"
                value={newFlowInstanceId || ''}
                onChange={(e) => setNewFlowInstanceId(e.target.value || null)}
              >
                <option value="">Usar instância da conversa</option>
                {flowInstances.map((i) => (
                  <option key={i.id} value={i.id}>{i.friendly_name}</option>
                ))}
              </select>
              <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">Opcional. Se escolher, o fluxo sempre envia por essa instância.</p>
            </div>
            <div className="border-t border-gray-200 dark:border-gray-700 pt-3">
              <Label className="text-accent-600 dark:text-accent-400">Typebot (fluxo executado pelo Typebot)</Label>
              <Input
                className="mt-1"
                value={newFlowTypebotPublicId}
                onChange={(e) => setNewFlowTypebotPublicId(e.target.value)}
                placeholder="Public ID do Typebot (Share &gt; API)"
              />
                <Input
                  className="mt-2"
                  value={newFlowTypebotBaseUrl}
                  onChange={(e) => setNewFlowTypebotBaseUrl(e.target.value)}
                  placeholder="URL base da API (vazio = typebot.io)"
                />
                <Label className="mt-2 block text-xs text-gray-500 dark:text-gray-400">Variáveis extras (JSON)</Label>
                <textarea
                  className="mt-0.5 w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm font-mono min-h-[50px]"
                  value={newFlowTypebotPrefilledExtra}
                  onChange={(e) => setNewFlowTypebotPrefilledExtra(e.target.value)}
                  placeholder='{"campanha": "black-friday"}'
                  rows={2}
                />
              <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">Opcional. Preencha o Public ID para o fluxo ser executado pelo Typebot via API (startChat/continueChat). Variáveis extras são enviadas em prefilledVariables.</p>
            </div>
            <div className="flex gap-2">
              <Button onClick={handleCreateFlow} disabled={creatingFlow}>
                {creatingFlow ? <LoadingSpinner size="sm" className="mr-1" /> : null}
                {creatingFlow ? 'Criando…' : 'Criar'}
              </Button>
              <Button variant="outline" onClick={() => setCreateOpen(false)} disabled={creatingFlow}>Cancelar</Button>
            </div>
          </div>
        </Card>
        </motion.div>
      )}
      </AnimatePresence>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="p-4 rounded-xl border-gray-200/80 dark:border-gray-700/80 shadow-sm transition-shadow hover:shadow-md">
          <h3 className="font-medium mb-3 text-gray-900 dark:text-gray-100">Fluxos</h3>
          {flows.length === 0 ? (
            <div className="text-center py-8 text-gray-500 dark:text-gray-400">
              <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-gray-100 dark:bg-gray-800 mb-3">
                <Zap className="h-6 w-6 text-gray-400 dark:text-gray-500" />
              </div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Nenhum fluxo ainda</p>
              <p className="text-xs mb-4">Crie o primeiro para vincular um fluxo Typebot ao Inbox ou a um departamento.</p>
              <Button size="sm" variant="outline" onClick={() => setCreateOpen(true)} className="rounded-lg">
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
                  className={`w-full text-left px-3 py-2.5 rounded-xl text-sm transition-all duration-200 ${
                    selectedFlow?.id === f.id
                      ? 'bg-accent-100 dark:bg-accent-900/30 text-accent-800 dark:text-accent-200 font-medium shadow-sm'
                      : 'hover:bg-gray-100 dark:hover:bg-gray-800/80 text-gray-700 dark:text-gray-300'
                  }`}
                >
                  <span className="block truncate">{f.name}</span>
                  <span className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 block">
                    {f.scope === 'inbox' ? 'Inbox' : (f.department_name || 'Departamento')}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          )}
        </Card>

        <div className="md:col-span-2 space-y-4">
          {selectedFlow && detailLoading && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="space-y-4"
            >
              <Card className="p-4 rounded-xl border-gray-200/80 dark:border-gray-700/80 h-[420px] flex items-center justify-center">
                <div className="flex flex-col items-center gap-3">
                  <LoadingSpinner />
                  <span className="text-sm text-gray-500 dark:text-gray-400">Carregando fluxo…</span>
                </div>
              </Card>
              <Card className="p-4 rounded-xl">
                <div className="h-4 w-32 rounded bg-gray-200 dark:bg-gray-700 animate-pulse mb-3" />
                <div className="space-y-2">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="h-12 rounded-lg bg-gray-100 dark:bg-gray-800 animate-pulse" />
                  ))}
                </div>
              </Card>
            </motion.div>
          )}
          <AnimatePresence mode="wait">
          {selectedFlow && !detailLoading && flowDetail && (
            <motion.div
              key={flowDetail.id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.2 }}
              className="space-y-4"
            >
              <Card className="p-4 rounded-xl border-gray-200/80 dark:border-gray-700/80 shadow-sm transition-shadow hover:shadow-md">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-medium text-gray-900 dark:text-gray-100">{flowDetail.name}</h3>
                  <div className="flex gap-2">
                    <Button size="sm" variant="outline" onClick={openEditFlow} aria-label="Editar fluxo">
                      <Edit className="h-3 w-3 mr-1" /> Editar fluxo
                    </Button>
                    <Button size="sm" variant="outline" onClick={handleDeleteFlowClick} disabled={!!deletingId} aria-label="Excluir fluxo" className="text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20">
                      <Trash2 className="h-3 w-3 mr-1" /> Excluir fluxo
                    </Button>
                  </div>
                </div>
                <div className="space-y-3 text-sm">
                  <p className="text-gray-600 dark:text-gray-400">
                    <strong>Vinculado a:</strong>{' '}
                    {flowDetail.scope === 'inbox' ? 'Inbox' : flowDetail.department_name ? `Departamento ${flowDetail.department_name}` : 'Departamento'}
                  </p>
                  {flowDetail.whatsapp_instance_name ? (
                    <p className="text-gray-600 dark:text-gray-400"><strong>Instância WhatsApp:</strong> {flowDetail.whatsapp_instance_name}</p>
                  ) : (
                    <p className="text-gray-500 dark:text-gray-500">Instância: usar da conversa</p>
                  )}
                  <div className="border-t border-gray-200 dark:border-gray-700 pt-3">
                    <p className="font-medium text-gray-900 dark:text-gray-100 mb-1">Integração Typebot</p>
                    <p className="text-gray-600 dark:text-gray-400">
                      Public ID: <code className="bg-gray-100 dark:bg-gray-800 px-1 rounded text-xs">{(flowDetail.typebot_public_id || '').trim() || '—'}</code>
                      {((flowDetail.typebot_base_url || '').trim()) ? (
                        <> · URL base: <code className="bg-gray-100 dark:bg-gray-800 px-1 rounded text-xs">{(flowDetail.typebot_base_url || '').trim()}</code></>
                      ) : (
                        <> · URL base: <span className="text-gray-500">typebot.io</span></>
                      )}
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
                      A edição do fluxo é feita no Typebot. As mensagens são enviadas ao WhatsApp automaticamente (startChat/continueChat).
                    </p>
                  </div>
                </div>
              </Card>
              <Card className="p-4 rounded-xl border-gray-200/80 dark:border-gray-700/80 shadow-sm">
                <h3 className="font-medium mb-2 text-gray-900 dark:text-gray-100 text-sm">Enviar passo inicial (teste)</h3>
                <div className="flex gap-2">
                  <Input
                    placeholder="5511999999999"
                    value={testPhone}
                    onChange={(e) => setTestPhone(e.target.value)}
                    className="flex-1 min-w-0"
                  />
                  <Button onClick={handleSendTest} disabled={sendingTest} size="sm">
                    {sendingTest ? <LoadingSpinner size="sm" /> : <Play className="h-4 w-4 mr-1" />}
                    Enviar teste
                  </Button>
                </div>
              </Card>
            </motion.div>
          )}
          </AnimatePresence>
          {!selectedFlow && !detailLoading && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.2 }}
            >
              <Card className="p-12 rounded-xl border border-dashed border-gray-200 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-900/30 text-center">
                <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gray-100 dark:bg-gray-800 mb-4">
                  <MessageSquare className="h-7 w-7 text-gray-400 dark:text-gray-500" />
                </div>
                <p className="text-gray-600 dark:text-gray-400 font-medium mb-1">Selecione um fluxo</p>
                <p className="text-sm text-gray-500 dark:text-gray-500 max-w-sm mx-auto">
                  Escolha um fluxo na lista ao lado para ver os dados da integração Typebot e enviar teste, ou crie um novo.
                </p>
              </Card>
            </motion.div>
          )}

          {/* FAQ Typebot – visível na tela inicial para consulta */}
          <Card className="rounded-xl border-gray-200/80 dark:border-gray-700/80 shadow-sm overflow-hidden">
            <button type="button" onClick={() => setFlowFaqExpanded((v) => !v)} className="flex items-center justify-between w-full p-4 text-left text-sm font-medium text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
              <span className="flex items-center gap-2">
                <HelpCircle className="h-4 w-4 text-accent-600 dark:text-accent-400" />
                Perguntas frequentes – Typebot no Sense
              </span>
              {flowFaqExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </button>
            {flowFaqExpanded && (
              <ul className="px-4 pb-4 pt-0 space-y-3 text-sm text-gray-600 dark:text-gray-400 border-t border-gray-100 dark:border-gray-700/80">
                {(FLOW_TYPEBOT_FAQ || []).map((item, i) => (
                  <li key={i} className="pt-3 first:pt-3">
                    <p className="font-medium text-gray-800 dark:text-gray-200">{item.pergunta}</p>
                    <p className="mt-0.5">{item.resposta}</p>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>

      {/* Modal: Node form */}
      <AnimatePresence>
      {nodeFormOpen && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm"
          onClick={closeNodeForm}
          role="dialog"
          aria-modal="true"
          aria-labelledby="node-form-title"
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.98 }}
            transition={{ duration: 0.2 }}
            className="w-full max-w-lg max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
          <Card className="p-6 rounded-2xl border-gray-200/80 dark:border-gray-700/80 shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <h2 id="node-form-title" className="text-lg font-semibold text-gray-900 dark:text-gray-100">{editingNode ? 'Editar etapa' : 'Adicionar etapa'}</h2>
              <button type="button" onClick={closeNodeForm} className="p-1.5 rounded-lg text-gray-500 hover:text-gray-700 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors" aria-label="Fechar"><X className="h-5 w-5" /></button>
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
                  onChange={(e) => setNodeType(e.target.value as 'list' | 'buttons' | 'message' | 'image' | 'file' | 'delay')}
                >
                  <option value="message">Mensagem (texto)</option>
                  <option value="list">Lista</option>
                  <option value="buttons">Botões</option>
                  <option value="image">Imagem</option>
                  <option value="file">Arquivo</option>
                  <option value="delay">Timer (espera em segundos)</option>
                </select>
              </div>
              {nodeType === 'delay' && (
                <div>
                  <Label>Espera (segundos)</Label>
                  <Input
                    type="number"
                    min={1}
                    max={86400}
                    value={nodeDelaySeconds}
                    onChange={(e) => setNodeDelaySeconds(parseInt(e.target.value, 10) || 1)}
                    placeholder="5"
                  />
                  <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">O fluxo aguarda esse tempo e segue para a próxima etapa (1 a 86400 s = máx. 24h).</p>
                </div>
              )}
              <div className="flex gap-4">
                <div>
                  <Label>Ordem</Label>
                  <Input type="number" min={0} value={nodeOrder} onChange={(e) => setNodeOrder(parseInt(e.target.value, 10) || 0)} />
                </div>
                <label className="flex items-center gap-2 pt-6">
                  <input type="checkbox" checked={nodeIsStart} onChange={(e) => setNodeIsStart(e.target.checked)} />
                  <span className="text-sm">Etapa inicial</span>
                </label>
              </div>
              {(nodeType === 'message' || nodeType === 'list' || nodeType === 'buttons') && (
                <div>
                  <Label>Corpo (texto da mensagem)</Label>
                  <textarea
                    className="mt-1 w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 min-h-[60px]"
                    value={nodeBodyText}
                    onChange={(e) => setNodeBodyText(e.target.value)}
                    placeholder="Texto exibido antes da lista/botões"
                  />
                </div>
              )}
              {(nodeType === 'image' || nodeType === 'file') && (
                <div>
                  <Label>URL da mídia</Label>
                  <Input value={nodeMediaUrl} onChange={(e) => setNodeMediaUrl(e.target.value)} placeholder="https://..." />
                </div>
              )}
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
                  <Label>Seções (máx. 10 seções, 10 linhas cada)</Label>
                  <div className="space-y-3 mt-1">
                    {nodeSections.map((sec, si) => (
                      <div key={si} className="border border-gray-200 dark:border-gray-700 rounded-lg p-3 space-y-2">
                        <div className="flex gap-2 items-center">
                          <Input value={sec.title} onChange={(e) => setNodeSections((prev) => prev.map((s, i) => i === si ? { ...s, title: e.target.value } : s))} placeholder="Título da seção" className="flex-1" />
                          {nodeSections.length > 1 && (
                            <Button type="button" size="sm" variant="outline" onClick={() => setNodeSections((prev) => prev.filter((_, i) => i !== si))}>Remover</Button>
                          )}
                        </div>
                        {sec.rows.map((row, ri) => (
                          <div key={ri} className="flex gap-2 items-center pl-2">
                            <Input value={row.id} onChange={(e) => setNodeSections((prev) => prev.map((s, i) => i === si ? { ...s, rows: s.rows.map((r, j) => j === ri ? { ...r, id: e.target.value } : r) } : s))} placeholder="id" className="w-24" />
                            <Input value={row.title} onChange={(e) => setNodeSections((prev) => prev.map((s, i) => i === si ? { ...s, rows: s.rows.map((r, j) => j === ri ? { ...r, title: e.target.value } : r) } : s))} placeholder="Título" className="flex-1" />
                            <Input value={row.description} onChange={(e) => setNodeSections((prev) => prev.map((s, i) => i === si ? { ...s, rows: s.rows.map((r, j) => j === ri ? { ...r, description: e.target.value } : r) } : s))} placeholder="Descrição (opcional)" className="flex-1" />
                            {sec.rows.length > 1 && (
                              <Button type="button" size="sm" variant="outline" onClick={() => setNodeSections((prev) => prev.map((s, i) => i === si ? { ...s, rows: s.rows.filter((_, j) => j !== ri) } : s))}>−</Button>
                            )}
                          </div>
                        ))}
                        {sec.rows.length < 10 && (
                          <Button type="button" size="sm" variant="outline" className="ml-2" onClick={() => setNodeSections((prev) => prev.map((s, i) => i === si ? { ...s, rows: [...s.rows, { id: `op${s.rows.length + 1}`, title: '', description: '' }] } : s))}>+ Linha</Button>
                        )}
                      </div>
                    ))}
                    {nodeSections.length < 10 && (
                      <Button type="button" size="sm" variant="outline" onClick={() => setNodeSections((prev) => [...prev, { title: '', rows: [{ id: 'op1', title: '', description: '' }] }])}>+ Seção</Button>
                    )}
                  </div>
                </div>
              )}
              {nodeType === 'buttons' && (
                <div>
                  <Label>Botões (1 a 3)</Label>
                  <div className="space-y-2 mt-1">
                    {nodeButtons.map((btn, bi) => (
                      <div key={bi} className="flex gap-2 items-center">
                        <Input value={btn.id} onChange={(e) => setNodeButtons((prev) => prev.map((b, i) => i === bi ? { ...b, id: e.target.value } : b))} placeholder="id" className="w-28" />
                        <Input value={btn.title} onChange={(e) => setNodeButtons((prev) => prev.map((b, i) => i === bi ? { ...b, title: e.target.value } : b))} placeholder="Título do botão" className="flex-1" />
                        {nodeButtons.length > 1 && (
                          <Button type="button" size="sm" variant="outline" onClick={() => setNodeButtons((prev) => prev.filter((_, i) => i !== bi))}>Remover</Button>
                        )}
                      </div>
                    ))}
                    {nodeButtons.length < 3 && (
                      <Button type="button" size="sm" variant="outline" onClick={() => setNodeButtons((prev) => [...prev, { id: `btn${prev.length + 1}`, title: '' }])}>+ Botão</Button>
                    )}
                  </div>
                </div>
              )}
            </div>
            <div className="flex gap-2 mt-4">
              <Button onClick={handleSaveNode} disabled={savingNode}>{savingNode ? <LoadingSpinner size="sm" /> : 'Salvar'}</Button>
              <Button variant="outline" onClick={closeNodeForm}>Cancelar</Button>
            </div>
          </Card>
          </motion.div>
        </motion.div>
      )}
      </AnimatePresence>

      {/* Modal: Edge form */}
      <AnimatePresence>
      {edgeFormOpen && flowDetail?.nodes && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm"
          onClick={() => setEdgeFormOpen(false)}
          role="dialog"
          aria-modal="true"
          aria-labelledby="edge-form-title"
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.98 }}
            transition={{ duration: 0.2 }}
            onClick={(e) => e.stopPropagation()}
          >
          <Card className="w-full max-w-md p-6 rounded-2xl border-gray-200/80 dark:border-gray-700/80 shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <h2 id="edge-form-title" className="text-lg font-semibold text-gray-900 dark:text-gray-100">{editingEdge ? 'Editar conexão' : 'Conectar'}</h2>
              <button type="button" onClick={() => setEdgeFormOpen(false)} className="p-1.5 rounded-lg text-gray-500 hover:text-gray-700 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors" aria-label="Fechar"><X className="h-5 w-5" /></button>
            </div>
            <div className="space-y-3">
              <div>
                <Label>Etapa de origem</Label>
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
                <Label>
                  {(flowDetail?.nodes?.find((n) => n.id === edgeFromNodeId) as FlowNode | undefined)?.node_type === 'message'
                    ? 'Texto que o usuário deve digitar'
                    : 'Opção (id da linha ou do botão)'}
                </Label>
                <Input
                  value={edgeOptionId}
                  onChange={(e) => setEdgeOptionId(e.target.value)}
                  placeholder={
                    (flowDetail?.nodes?.find((n) => n.id === edgeFromNodeId) as FlowNode | undefined)?.node_type === 'message'
                      ? 'ex: 1, ok, próximo'
                      : 'ex: opcao1, btn1'
                  }
                />
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                  {(flowDetail?.nodes?.find((n) => n.id === edgeFromNodeId) as FlowNode | undefined)?.node_type === 'message'
                    ? 'Quando o usuário enviar essa mensagem de texto, o fluxo avança para o destino.'
                    : 'Deve coincidir com o id de uma linha da lista ou de um botão na etapa de origem.'}
                </p>
              </div>
              <div>
                <Label>O que acontece quando o usuário escolhe esta opção?</Label>
                <select
                  className="mt-1 w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2"
                  value={edgeTargetAction}
                  onChange={(e) => setEdgeTargetAction(e.target.value)}
                >
                  <option value="next">Ir para outra etapa do fluxo</option>
                  <option value="transfer">Transferir para departamento</option>
                  <option value="end">Encerrar conversa</option>
                </select>
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                  {edgeTargetAction === 'next' && 'O fluxo continua em outra etapa (ex.: menu, resposta).'}
                  {edgeTargetAction === 'transfer' && 'A conversa é enviada para outro departamento.'}
                  {edgeTargetAction === 'end' && 'A conversa é finalizada.'}
                </p>
              </div>
              {edgeTargetAction === 'next' && (
                <div>
                  <Label>Próxima etapa</Label>
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
                  <Label>Transferir para qual departamento?</Label>
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
          </motion.div>
        </motion.div>
      )}
      </AnimatePresence>

      <ConfirmDialog
        show={!!confirmDeleteNode}
        title="Excluir etapa"
        message={confirmDeleteNode ? `Excluir a etapa "${confirmDeleteNode.name}"? As conexões ligadas também serão removidas.` : ''}
        confirmText="Excluir"
        variant="danger"
        onConfirm={handleDeleteNodeConfirm}
        onCancel={() => setConfirmDeleteNode(null)}
      />
      <ConfirmDialog
        show={!!confirmDeleteEdge}
        title="Excluir conexão"
        message={confirmDeleteEdge ? `Excluir a conexão "${confirmDeleteEdge.option_id}"?` : ''}
        confirmText="Excluir"
        variant="danger"
        onConfirm={handleDeleteEdgeConfirm}
        onCancel={() => setConfirmDeleteEdge(null)}
      />
      <ConfirmDialog
        show={!!confirmDeleteFlow}
        title="Excluir fluxo"
        message={confirmDeleteFlow ? `Excluir o fluxo "${confirmDeleteFlow.name}"? O vínculo com o Typebot será removido.` : ''}
        confirmText="Excluir"
        variant="danger"
        onConfirm={handleDeleteFlowConfirm}
        onCancel={() => setConfirmDeleteFlow(null)}
      />

      {/* Modal: Edit flow */}
      <AnimatePresence>
      {editFlowOpen && selectedFlow && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
          onClick={() => setEditFlowOpen(false)}
          role="dialog"
          aria-modal="true"
          aria-labelledby="edit-flow-title"
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.98 }}
            transition={{ duration: 0.2 }}
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-lg max-h-[90vh] flex flex-col"
          >
            <Card className="flex flex-col rounded-2xl border border-gray-200 dark:border-gray-700 shadow-2xl overflow-hidden">
              {/* Header fixo */}
              <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700 bg-gray-50/80 dark:bg-gray-800/80 shrink-0">
                <h2 id="edit-flow-title" className="text-xl font-semibold text-gray-900 dark:text-gray-100">Editar fluxo</h2>
                <button type="button" onClick={() => setEditFlowOpen(false)} className="p-2 rounded-xl text-gray-500 hover:text-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors" aria-label="Fechar"><X className="h-5 w-5" /></button>
              </div>

              {/* Conteúdo rolável */}
              <div className="overflow-y-auto overscroll-contain px-6 py-5 space-y-6">
                {/* Seção: Geral */}
                <section className="space-y-3">
                  <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 uppercase tracking-wide">Geral</h3>
                  <div className="space-y-3">
                    <div>
                      <Label className="mb-1 block">Nome</Label>
                      <Input
                        value={editFlowName}
                        onChange={(e) => setEditFlowName(e.target.value)}
                        placeholder="Ex: Menu Inbox"
                        className="rounded-lg"
                      />
                    </div>
                    <div>
                      <Label className="mb-1 block">Descrição breve (opcional)</Label>
                      <Input
                        value={editFlowDescription}
                        onChange={(e) => setEditFlowDescription(e.target.value)}
                        placeholder="Ex: Menu de abertura de chamados"
                        className="rounded-lg"
                      />
                      <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">Exibida ao escolher o fluxo no chat.</p>
                    </div>
                    <div>
                      <Label className="mb-2 block">Escopo</Label>
                      <div className="flex gap-6">
                        <label className="flex items-center gap-2 cursor-pointer group">
                          <input type="radio" checked={editFlowScope === 'inbox'} onChange={() => { setEditFlowScope('inbox'); setEditFlowDepartmentId(null) }} className="text-accent-600" />
                          <Inbox className="h-4 w-4 text-gray-500 group-hover:text-gray-700 dark:group-hover:text-gray-300" /> <span>Inbox</span>
                        </label>
                        <label className="flex items-center gap-2 cursor-pointer group">
                          <input type="radio" checked={editFlowScope === 'department'} onChange={() => setEditFlowScope('department')} className="text-accent-600" />
                          <Building2 className="h-4 w-4 text-gray-500 group-hover:text-gray-700 dark:group-hover:text-gray-300" /> <span>Departamento</span>
                        </label>
                      </div>
                    </div>
                    {editFlowScope === 'department' && (
                      <div>
                        <Label className="mb-1 block">Departamento</Label>
                        <select className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm" value={editFlowDepartmentId || ''} onChange={(e) => setEditFlowDepartmentId(e.target.value || null)}>
                          <option value="">Selecione</option>
                          {departments.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
                        </select>
                      </div>
                    )}
                    <div>
                      <Label className="mb-1 block">Instância WhatsApp</Label>
                      <select className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm" value={editFlowInstanceId || ''} onChange={(e) => setEditFlowInstanceId(e.target.value || null)}>
                        <option value="">Usar instância da conversa</option>
                        {flowInstances.map((i) => <option key={i.id} value={i.id}>{i.friendly_name}</option>)}
                      </select>
                      <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">Opcional. Define por qual instância o fluxo envia.</p>
                    </div>
                  </div>
                </section>

                {/* Seção: Typebot */}
                <section className="space-y-3 rounded-xl bg-gray-50 dark:bg-gray-800/50 p-4 border border-gray-100 dark:border-gray-700/50">
                  <h3 className="text-sm font-medium text-accent-600 dark:text-accent-400 flex items-center gap-2">
                    <Zap className="h-4 w-4" /> Typebot
                  </h3>
                  <div className="space-y-3">
                    <div>
                      <Label className="mb-1 block text-gray-700 dark:text-gray-300">Public ID</Label>
                      <Input value={editTypebotPublicId} onChange={(e) => setEditTypebotPublicId(e.target.value)} placeholder="Ex: my-typebot-7l6svuv" className="rounded-lg font-mono text-sm" />
                      <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">No Typebot: Share &gt; API</p>
                    </div>
                    <div>
                      <Label className="mb-1 block text-gray-700 dark:text-gray-300">URL base da API</Label>
                      <Input value={editTypebotBaseUrl} onChange={(e) => setEditTypebotBaseUrl(e.target.value)} placeholder="Vazio = typebot.io" className="rounded-lg font-mono text-sm" />
                    </div>
                  </div>

                  {/* Variáveis: bloco recolhível */}
                  <div className="pt-2 border-t border-gray-200 dark:border-gray-600">
                    <button type="button" onClick={() => setEditFlowVarsExpanded((v) => !v)} className="flex items-center justify-between w-full py-1.5 text-left text-sm font-medium text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-200">
                      <span>Variáveis (opcional)</span>
                      {editFlowVarsExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                    </button>
                    {editFlowVarsExpanded && (
                      <div className="mt-3 space-y-3">
                        <p className="text-xs text-gray-500 dark:text-gray-400">ID interno = ID na URL ao editar o typebot. API key = no Typebot: avatar (canto inferior esquerdo) &rarr; Settings &amp; Members &rarr; My account &rarr; API tokens &rarr; Create.</p>
                        <div className="grid grid-cols-1 gap-2">
                          <Input value={editTypebotInternalId} onChange={(e) => setEditTypebotInternalId(e.target.value)} placeholder="ID interno (ex.: da URL ao editar)" className="rounded-lg text-sm" />
                          <Input type="password" autoComplete="off" value={editTypebotApiKey} onChange={(e) => setEditTypebotApiKey(e.target.value)} placeholder="API key (Settings & Members > My account > API tokens)" className="rounded-lg text-sm" />
                        </div>
                        <Button type="button" variant="outline" size="sm" disabled={loadingTypebotVariables || !editTypebotInternalId.trim() || !editTypebotApiKey.trim()} onClick={async () => { if (!selectedFlow?.id) return; setLoadingTypebotVariables(true); try { const { data } = await api.post(`/chat/flows/${selectedFlow.id}/fetch_typebot_variables/`, { typebot_internal_id: editTypebotInternalId.trim(), typebot_api_key: editTypebotApiKey.trim() }); setTypebotVariablesList(data?.variables ?? []); const prev: Record<string, string> = {}; try { const extra = JSON.parse(editTypebotPrefilledExtra || '{}'); if (typeof extra === 'object' && extra !== null) Object.assign(prev, extra); } catch { /* ignore */ } setTypebotVariableValues(prev); if ((data?.variables?.length ?? 0) > 0) toast.success(`${data.variables.length} variável(is). Preencha e clique em Aplicar.`); else toast.info('Nenhuma variável neste fluxo.'); } catch (e: any) { toast.error(e?.response?.data?.detail ?? 'Falha ao carregar'); } finally { setLoadingTypebotVariables(false); } }}>
                          {loadingTypebotVariables ? <LoadingSpinner size="sm" className="mr-1" /> : null}{loadingTypebotVariables ? 'Carregando…' : 'Carregar variáveis'}
                        </Button>
                        {typebotVariablesList.length > 0 && (
                          <div className="space-y-2 rounded-lg bg-white dark:bg-gray-800/80 p-3 border border-gray-200 dark:border-gray-600">
                            <p className="text-xs font-medium text-gray-600 dark:text-gray-400">Valores para cada variável</p>
                            {typebotVariablesList.map((v) => (
                              <div key={v.id} className="flex gap-2 items-center">
                                <span className="text-xs font-mono text-gray-500 dark:text-gray-400 w-28 shrink-0 truncate" title={v.name}>{v.name}</span>
                                <Input className="flex-1 text-sm rounded-lg" value={typebotVariableValues[v.name] ?? ''} onChange={(e) => setTypebotVariableValues((prev) => ({ ...prev, [v.name]: e.target.value }))} placeholder="valor" />
                              </div>
                            ))}
                            <Button type="button" variant="outline" size="sm" onClick={() => { const extra: Record<string, string> = {}; typebotVariablesList.forEach((v) => { const val = (typebotVariableValues[v.name] ?? '').trim(); if (val) extra[v.name] = val; }); try { const current = JSON.parse(editTypebotPrefilledExtra || '{}'); const merged = typeof current === 'object' && current !== null ? { ...current, ...extra } : extra; setEditTypebotPrefilledExtra(JSON.stringify(merged, null, 2)); toast.success('Aplicado ao JSON.'); } catch { setEditTypebotPrefilledExtra(JSON.stringify(extra, null, 2)); toast.success('Aplicado ao JSON.'); } }}>Aplicar ao JSON</Button>
                          </div>
                        )}
                        <div>
                          <Label className="mb-1 block text-xs text-gray-600 dark:text-gray-400">Variáveis extras (JSON)</Label>
                          <textarea className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm font-mono min-h-[72px]" value={editTypebotPrefilledExtra} onChange={(e) => setEditTypebotPrefilledExtra(e.target.value)} placeholder='{"campanha": "black-friday"}' rows={3} />
                        </div>
                      </div>
                    )}
                  </div>
                </section>
              </div>

              {/* Footer fixo */}
              <div className="flex gap-3 px-6 py-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-800/50 shrink-0">
                <Button onClick={handleSaveFlow} disabled={savingFlow} className="min-w-[100px]">
                  {savingFlow ? <LoadingSpinner size="sm" className="mr-1" /> : null}{savingFlow ? 'Salvando…' : 'Salvar'}
                </Button>
                <Button variant="outline" onClick={() => setEditFlowOpen(false)} disabled={savingFlow}>Cancelar</Button>
              </div>
            </Card>
          </motion.div>
        </motion.div>
      )}
      </AnimatePresence>
    </div>
  )
}
