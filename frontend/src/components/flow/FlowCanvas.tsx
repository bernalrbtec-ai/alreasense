/**
 * Canvas de fluxo com React Flow: exibe nós e arestas; clique no nó para editar.
 */
import { useCallback, useMemo, useEffect } from 'react'
import {
  ReactFlow,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type OnNodeClick,
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

function flowNodesToReactFlow(
  nodes: FlowCanvasNode[],
  positions: Map<string, { x: number; y: number }>
): Node<FlowNodeData>[] {
  return nodes.map((n) => {
    const pos = positions.get(n.id) ?? { x: 0, y: 0 }
    return {
      id: n.id,
      type: 'default',
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

interface FlowCanvasProps {
  nodes: FlowCanvasNode[]
  onNodeClick?: (nodeId: string) => void
  className?: string
}

export default function FlowCanvas({ nodes, onNodeClick, className = '' }: FlowCanvasProps) {
  const positions = useMemo(() => buildLayout(nodes), [nodes])
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
      `${nodes.length}-${nodes.map((n) => n.id).sort().join(',')}-${nodes.reduce((acc, n) => acc + (n.edges_out?.length ?? 0), 0)}`,
    [nodes]
  )

  useEffect(() => {
    const pos = buildLayout(nodes)
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

  if (nodes.length === 0) {
    return (
      <div className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-gray-200 dark:border-gray-700 bg-gray-50/80 dark:bg-gray-900/50 min-h-[300px] ${className}`}>
        <div className="w-12 h-12 rounded-full bg-gray-200 dark:bg-gray-700 flex items-center justify-center mb-3">
          <span className="text-lg text-gray-400 dark:text-gray-500">◇</span>
        </div>
        <p className="text-sm font-medium text-gray-600 dark:text-gray-400">Nenhum nó ainda</p>
        <p className="text-xs text-gray-500 dark:text-gray-500 mt-0.5">Adicione um nó abaixo para ver o fluxo aqui.</p>
      </div>
    )
  }

  return (
    <div className={`rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 min-h-[300px] overflow-hidden ${className}`} style={{ height: 400 }}>
      <ReactFlow
        nodes={rfNodes}
        edges={rfEdges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={handleNodeClick}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.2}
        maxZoom={1.5}
        defaultEdgeOptions={{ type: 'smoothstep' }}
        nodeOrigin={[0.5, 0.5]}
      >
        <Controls />
        <Background gap={12} size={1} />
      </ReactFlow>
    </div>
  )
}
