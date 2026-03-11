/**
 * Canvas de fluxo com React Flow: exibe etapas e conexões; clique para editar; arraste para reposicionar; conecte pelo Handle.
 */
import { useCallback, useMemo, useEffect, useRef } from 'react'
import {
  ReactFlow,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  Handle,
  Position,
  type Node,
  type Edge,
  type OnNodeClick,
  type OnConnect,
  type NodeDragHandler,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

export interface FlowNodeData {
  label: string
  id: string
  name: string
  node_type: string
  is_start: boolean
  edges_out?: Array<{ id: string; option_id: string; to_node_name: string | null; target_department_name: string | null; target_action: string }>
}

export interface FlowCanvasNode {
  id: string
  flow: string
  node_type: string
  name: string
  order: number
  is_start: boolean
  position_x?: number | null
  position_y?: number | null
  edges_out?: Array<{
    id: string
    option_id: string
    to_node: string | null
    to_node_name: string | null
    target_department_name: string | null
    target_action: string
  }>
}

const NODE_WIDTH = 180
const NODE_HEIGHT = 56
const GAP = 80

function buildLayout(nodes: FlowCanvasNode[]): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number }>()
  const sorted = [...nodes].sort((a, b) => a.order - b.order)
  sorted.forEach((n, i) => {
    positions.set(n.id, { x: 0, y: i * (NODE_HEIGHT + GAP) })
  })
  return positions
}

/** Usa position_x/position_y quando ambos não forem null; senão layout por order. */
function getPositions(nodes: FlowCanvasNode[]): Map<string, { x: number; y: number }> {
  const byOrder = buildLayout(nodes)
  const result = new Map<string, { x: number; y: number }>()
  nodes.forEach((n) => {
    const hasPosition = n.position_x != null && n.position_y != null
    result.set(n.id, hasPosition ? { x: Number(n.position_x), y: Number(n.position_y) } : (byOrder.get(n.id) ?? { x: 0, y: 0 }))
  })
  return result
}

function flowNodesToReactFlow(
  nodes: FlowCanvasNode[],
  positions: Map<string, { x: number; y: number }>
): Node<FlowNodeData>[] {
  return nodes.map((n) => {
    const pos = positions.get(n.id) ?? { x: 0, y: 0 }
    return {
      id: n.id,
      type: 'flowNode',
      position: pos,
      data: {
        label: n.is_start ? `● ${n.name}` : n.name,
        id: n.id,
        name: n.name,
        node_type: n.node_type,
        is_start: n.is_start,
        edges_out: n.edges_out ?? [],
      },
    }
  })
}

function flowEdgesToReactFlow(nodes: FlowCanvasNode[]): Edge[] {
  const edges: Edge[] = []
  const nodeIds = new Set(nodes.map((n) => n.id))
  nodes.forEach((n) => {
    (n.edges_out || []).forEach((e) => {
      const targetId = e.to_node && nodeIds.has(e.to_node) ? e.to_node : `virtual-${e.id}`
      edges.push({
        id: e.id,
        source: n.id,
        target: targetId,
        label: e.option_id,
        type: 'smoothstep',
      })
    })
  })
  return edges
}

function addVirtualTargetNodes(
  nodes: Node<FlowNodeData>[],
  edges: Edge[],
  positions: Map<string, { x: number; y: number }>
): { nodes: Node<FlowNodeData>[]; edges: Edge[] } {
  const virtualIds = new Set<string>()
  edges.forEach((e) => {
    if (e.target.startsWith('virtual-')) virtualIds.add(e.target)
  })
  const maxY = Math.max(0, ...nodes.map((n) => n.position.y))
  const virtualNodes: Node<FlowNodeData>[] = []
  virtualIds.forEach((id, i) => {
    const edge = edges.find((e) => e.target === id)
    const label = edge?.label ?? 'end'
    virtualNodes.push({
      id,
      type: 'default',
      position: { x: NODE_WIDTH + 120, y: maxY + 40 + i * 32 },
      data: { label: String(label), id, name: String(label), node_type: 'virtual', is_start: false, edges_out: [] },
    })
  })
  return {
    nodes: [...nodes, ...virtualNodes],
    edges,
  }
}

/** Nó com Handle de saída para conexões (apenas nós reais, não virtual). */
function FlowNodeWithHandle({ data }: { data: FlowNodeData }) {
  return (
    <>
      <div className="px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 shadow-sm min-w-[140px] text-center">
        {data.label}
      </div>
      <Handle type="source" position={Position.Right} className="!w-2 !h-2 !bg-accent-500" />
    </>
  )
}

const nodeTypes = { flowNode: FlowNodeWithHandle }

export const FLOW_DROP_TYPE = 'application/x-flow-node-type'
export const FLOW_DROP_START = 'application/x-flow-node-start'

interface FlowCanvasProps {
  nodes: FlowCanvasNode[]
  onNodeClick?: (nodeId: string) => void
  onNodeDragStop?: (nodeId: string, position: { x: number; y: number }) => void
  onConnect?: (params: { source: string; target: string }) => void
  onDrop?: (position: { x: number; y: number }, nodeType: 'message' | 'list' | 'buttons' | 'image' | 'file', isStart: boolean) => void
  /** Altura do canvas em px (default 400). */
  height?: number
  className?: string
}

export default function FlowCanvas({ nodes, onNodeClick, onNodeDragStop, onConnect, onDrop, height = 400, className = '' }: FlowCanvasProps) {
  const reactFlowRef = useRef<{ screenToFlowPosition: (p: { x: number; y: number }) => { x: number; y: number } } | null>(null)
  const positions = useMemo(() => getPositions(nodes), [nodes])
  const initialNodes = useMemo(() => flowNodesToReactFlow(nodes, positions), [nodes, positions])
  const initialEdges = useMemo(() => flowEdgesToReactFlow(nodes), [nodes])
  const { nodes: withVirtual, edges } = useMemo(
    () => addVirtualTargetNodes(initialNodes, initialEdges, positions),
    [initialNodes, initialEdges, positions]
  )

  const [rfNodes, setRfNodes, onNodesChange] = useNodesState(withVirtual)
  const [rfEdges, setRfEdges, onEdgesChange] = useEdgesState(edges)

  const nodesSignature = useMemo(
    () =>
      `${nodes.length}-${nodes.map((n) => n.id).sort().join(',')}-${nodes.reduce((acc, n) => acc + (n.edges_out?.length ?? 0), 0)}-${nodes.map((n) => `${n.id}:${n.position_x ?? ''},${n.position_y ?? ''}`).join('|')}`,
    [nodes]
  )

  useEffect(() => {
    const pos = getPositions(nodes)
    const initNodes = flowNodesToReactFlow(nodes, pos)
    const initEdges = flowEdgesToReactFlow(nodes)
    const { nodes: nextNodes, edges: nextEdges } = addVirtualTargetNodes(initNodes, initEdges, pos)
    setRfNodes(nextNodes)
    setRfEdges(nextEdges)
    // Sync only when nodes/edges content change (nodesSignature), not on every parent re-render
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodesSignature])

  const handleNodeClick: OnNodeClick = useCallback(
    (_, node) => {
      if (!node.id.startsWith('virtual-') && onNodeClick) onNodeClick(node.id)
    },
    [onNodeClick]
  )

  const handleNodeDragStop: NodeDragHandler = useCallback(
    (_, node) => {
      if (node.id.startsWith('virtual-')) return
      onNodeDragStop?.(node.id, node.position)
    },
    [onNodeDragStop]
  )

  const handleConnect: OnConnect = useCallback(
    (connection) => {
      if (!connection?.source || !connection?.target) return
      if (connection.target.startsWith('virtual-')) return
      if (connection.source === connection.target) return // evita self-loop acidental
      onConnect?.({ source: connection.source, target: connection.target })
    },
    [onConnect]
  )

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'copy'
  }, [])

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      const nodeType = e.dataTransfer.getData(FLOW_DROP_TYPE) as 'message' | 'list' | 'buttons' | 'image' | 'file' | ''
      const isStart = e.dataTransfer.getData(FLOW_DROP_START) === '1'
      if (!nodeType || !['message', 'list', 'buttons', 'image', 'file'].includes(nodeType)) return
      // ref pode ser null com canvas vazio no primeiro frame; fallback (0,0) abre o modal e o usuário pode ajustar
      const position = reactFlowRef.current?.screenToFlowPosition({ x: e.clientX, y: e.clientY }) ?? { x: 0, y: 0 }
      onDrop?.(position, nodeType, isStart)
    },
    [onDrop]
  )

  return (
    <div
      className={`rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 min-h-[300px] overflow-hidden relative ${className}`}
      style={{ height }}
      onDragOver={onDrop ? handleDragOver : undefined}
      onDrop={onDrop ? handleDrop : undefined}
    >
      <ReactFlow
        ref={reactFlowRef as any}
        nodes={rfNodes}
        edges={rfEdges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={handleNodeClick}
        onNodeDragStop={handleNodeDragStop}
        onConnect={handleConnect}
        nodesDraggable={true}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.2}
        maxZoom={1.5}
        defaultEdgeOptions={{ type: 'smoothstep', deletable: false }}
        nodeOrigin={[0.5, 0.5]}
      >
        <Controls />
        <Background gap={12} size={1} />
      </ReactFlow>
      {nodes.length === 0 && (
        <div className="absolute inset-0 flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-gray-200 dark:border-gray-700 bg-gray-50/80 dark:bg-gray-900/50 pointer-events-none">
          <div className="w-12 h-12 rounded-full bg-gray-200 dark:bg-gray-700 flex items-center justify-center mb-3">
            <span className="text-lg text-gray-400 dark:text-gray-500">◇</span>
          </div>
          <p className="text-sm font-medium text-gray-600 dark:text-gray-400">Nenhuma etapa ainda</p>
          <p className="text-xs text-gray-500 dark:text-gray-500 mt-0.5">Arraste uma etapa da barra lateral para o canvas para começar.</p>
        </div>
      )}
    </div>
  )
}
