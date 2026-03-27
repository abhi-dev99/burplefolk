import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ReactFlow,
  Controls,
  Background,
  BackgroundVariant,
  MarkerType,
  Handle,
  Position,
  BaseEdge,
  EdgeLabelRenderer,
  type EdgeProps,
  useStore,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import dagre from 'dagre';
import clsx from 'clsx';
import { Key } from 'lucide-react';

const normalizeTableName = (value: string) => {
  const raw = String(value || '').trim().toLowerCase();
  if (!raw) return '';
  const dotParts = raw.split('.');
  const base = dotParts[dotParts.length - 1] || raw;
  return base.replace(/[^a-z0-9_]/g, '');
};

const TableNode = ({ data }: any) => {
  return (
    <div className="relative bg-white/90 dark:bg-[#0b1220]/90 backdrop-blur-md rounded-xl border-2 border-slate-200 dark:border-slate-700 shadow-xl overflow-hidden min-w-[240px]">
      <Handle id="l" type="target" position={Position.Left} className="!w-2 !h-2 !bg-blue-500 !border-0 !opacity-80" />
      <Handle id="r" type="source" position={Position.Right} className="!w-2 !h-2 !bg-blue-500 !border-0 !opacity-80" />
      <Handle id="t" type="target" position={Position.Top} className="!w-2 !h-2 !bg-blue-500 !border-0 !opacity-80" />
      <Handle id="b" type="source" position={Position.Bottom} className="!w-2 !h-2 !bg-blue-500 !border-0 !opacity-80" />

      <div className="bg-gradient-to-r from-blue-600 to-blue-500 px-4 py-3 border-b border-blue-700/50">
        <h3 className="font-bold text-white tracking-wide text-sm">{data.label}</h3>
      </div>
      <div className="flex flex-col text-sm py-1">
        {data.columns.map((col: any, i: number) => {
          const isPK = String(col.role).includes('PK') || String(col.semantic_role).includes('primary');
          const isFK = String(col.semantic_role || '').toLowerCase().includes('foreign') || (String(col.column || '').endsWith('_id') && !isPK);
          return (
            <div key={i} className="flex items-center justify-between px-4 py-1.5 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors border-b border-slate-100 dark:border-slate-800 last:border-0">
              <div className="flex items-center gap-2">
                {isPK && <Key className="w-3 h-3 text-amber-500" />}
                <span className={clsx('font-medium', isPK ? 'text-amber-600 dark:text-amber-400' : isFK ? 'text-rose-500' : 'text-slate-700 dark:text-slate-300')}>
                  {String(col.column || '-')}
                </span>
              </div>
              <span className="text-[10px] font-mono text-slate-400 dark:text-slate-500 uppercase">{String(col.dtype || col.sample_dtype || 'VARCHAR')}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

const nodeTypes = {
  tableNode: TableNode,
};

const bezierPoint = (
  t: number,
  p0: { x: number; y: number },
  p1: { x: number; y: number },
  p2: { x: number; y: number },
  p3: { x: number; y: number }
) => {
  const omt = 1 - t;
  const x = (omt ** 3) * p0.x + 3 * (omt ** 2) * t * p1.x + 3 * omt * (t ** 2) * p2.x + (t ** 3) * p3.x;
  const y = (omt ** 3) * p0.y + 3 * (omt ** 2) * t * p1.y + 3 * omt * (t ** 2) * p2.y + (t ** 3) * p3.y;
  return { x, y };
};

const DraggableCurvedEdge = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  markerEnd,
  label,
  style,
  data,
}: EdgeProps) => {
  const zoom = useStore((s) => s.transform[2] || 1);
  const dragRef = useRef<{
    pointerX: number;
    pointerY: number;
    startOffsetX: number;
    startOffsetY: number;
  } | null>(null);

  const offset = (data?.offset as { x: number; y: number } | undefined) || { x: 0, y: 0 };
  const onOffsetChange = data?.onOffsetChange as ((edgeId: string, next: { x: number; y: number }) => void) | undefined;

  const dx = targetX - sourceX;

  const c1 = {
    x: sourceX + dx * 0.33 + offset.x,
    y: sourceY + offset.y,
  };
  const c2 = {
    x: sourceX + dx * 0.66 + offset.x,
    y: targetY + offset.y,
  };

  const edgePath = `M ${sourceX},${sourceY} C ${c1.x},${c1.y} ${c2.x},${c2.y} ${targetX},${targetY}`;
  const labelPoint = bezierPoint(
    0.5,
    { x: sourceX, y: sourceY },
    c1,
    c2,
    { x: targetX, y: targetY }
  );

  const onMouseDownPath = useCallback(
    (event: any) => {
      if (!onOffsetChange) return;
      event.stopPropagation();
      event.preventDefault();

      const start = {
        pointerX: event.clientX,
        pointerY: event.clientY,
        startOffsetX: offset.x,
        startOffsetY: offset.y,
      };
      dragRef.current = start;

      const handleMove = (moveEvent: MouseEvent) => {
        const active = dragRef.current;
        if (!active) return;

        const deltaX = (moveEvent.clientX - active.pointerX) / Math.max(zoom, 0.1);
        const deltaY = (moveEvent.clientY - active.pointerY) / Math.max(zoom, 0.1);
        onOffsetChange(id, {
          x: active.startOffsetX + deltaX,
          y: active.startOffsetY + deltaY,
        });
      };

      const handleUp = () => {
        dragRef.current = null;
        window.removeEventListener('mousemove', handleMove);
        window.removeEventListener('mouseup', handleUp);
      };

      window.addEventListener('mousemove', handleMove);
      window.addEventListener('mouseup', handleUp);
    },
    [id, offset.x, offset.y, onOffsetChange, zoom]
  );

  return (
    <>
      <path
        d={edgePath}
        fill="none"
        stroke="transparent"
        strokeWidth={16}
        style={{ cursor: 'grab', pointerEvents: 'stroke' }}
        onMouseDown={onMouseDownPath}
      />
      <BaseEdge id={id} path={edgePath} markerEnd={markerEnd} style={style} />
      {label ? (
        <EdgeLabelRenderer>
          <div
            className="nodrag nopan absolute pointer-events-none"
            style={{
              transform: `translate(-50%, -50%) translate(${labelPoint.x}px, ${labelPoint.y}px)`,
              zIndex: 1000,
            }}
          >
            <span className="rounded-md px-2 py-1 text-[10px] font-semibold tracking-wide bg-white/95 dark:bg-slate-950/90 text-slate-800 dark:text-slate-100 border border-slate-300/70 dark:border-slate-700/80 shadow-sm">
              {String(label)}
            </span>
          </div>
        </EdgeLabelRenderer>
      ) : null}
    </>
  );
};

const edgeTypes = {
  draggableCurved: DraggableCurvedEdge,
};

const getLayoutedElements = (nodes: any[], edges: any[], direction = 'LR') => {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));

  const isHorizontal = direction === 'LR';
  const nodeCount = nodes.length;
  const dynamicNodeSep = nodeCount > 10 ? 130 : 90;
  const dynamicRankSep = nodeCount > 10 ? 280 : 210;
  dagreGraph.setGraph({
    rankdir: direction,
    nodesep: dynamicNodeSep,
    ranksep: dynamicRankSep,
    ranker: 'network-simplex',
    acyclicer: 'greedy',
  });

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: 260, height: 50 + (node.data.columns.length * 35) });
  });

  edges.forEach((edge) => {
    if (dagreGraph.hasNode(edge.source) && dagreGraph.hasNode(edge.target)) {
      dagreGraph.setEdge(edge.source, edge.target);
    }
  });

  dagre.layout(dagreGraph);

  const updatedNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    if (!nodeWithPosition) return node;

    return {
      ...node,
      zIndex: 50,
      targetPosition: isHorizontal ? 'left' : 'top',
      sourcePosition: isHorizontal ? 'right' : 'bottom',
      position: {
        x: nodeWithPosition.x - nodeWithPosition.width / 2,
        y: nodeWithPosition.y - nodeWithPosition.height / 2,
      },
    };
  });

  return { nodes: updatedNodes, edges };
};

const assignHandlesByGeometry = (nodes: any[], edges: any[]) => {
  const nodeMap = new Map<string, any>();
  nodes.forEach((n) => nodeMap.set(String(n.id), n));

  return edges.map((edge) => {
    const source = nodeMap.get(String(edge.source));
    const target = nodeMap.get(String(edge.target));
    if (!source || !target) return edge;

    const sourceCenter = {
      x: source.position.x + 130,
      y: source.position.y + ((source.data?.columns?.length || 1) * 35 + 50) / 2,
    };
    const targetCenter = {
      x: target.position.x + 130,
      y: target.position.y + ((target.data?.columns?.length || 1) * 35 + 50) / 2,
    };

    const dx = targetCenter.x - sourceCenter.x;
    const dy = targetCenter.y - sourceCenter.y;

    let sourceHandle = 'r';
    let targetHandle = 'l';
    if (Math.abs(dy) > Math.abs(dx)) {
      sourceHandle = dy > 0 ? 'b' : 't';
      targetHandle = dy > 0 ? 't' : 'b';
    } else {
      sourceHandle = dx > 0 ? 'r' : 'l';
      targetHandle = dx > 0 ? 'l' : 'r';
    }

    return { ...edge, sourceHandle, targetHandle };
  });
};

type ERDiagramProps = {
  analysisData: any;
  showEdgeLabels?: boolean;
};

export default function ERDiagram({ analysisData, showEdgeLabels = true }: ERDiagramProps) {
  const [isDarkMode, setIsDarkMode] = useState<boolean>(() =>
    typeof document !== 'undefined' ? document.documentElement.classList.contains('dark') : false
  );
  const [edgeOffsets, setEdgeOffsets] = useState<Record<string, { x: number; y: number }>>({});

  const handleEdgeOffsetChange = useCallback((edgeId: string, next: { x: number; y: number }) => {
    setEdgeOffsets((prev) => ({
      ...prev,
      [edgeId]: next,
    }));
  }, []);

  useEffect(() => {
    if (typeof document === 'undefined') return;
    const root = document.documentElement;
    const observer = new MutationObserver(() => {
      setIsDarkMode(root.classList.contains('dark'));
    });
    observer.observe(root, { attributes: true, attributeFilter: ['class'] });
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    setEdgeOffsets({});
  }, [analysisData]);

  const initialNodes = useMemo(() => {
    if (!analysisData?.analysis?.table_profiles) return [];
    return analysisData.analysis.table_profiles.map((t: any) => ({
      id: String(t.table),
      type: 'tableNode',
      data: { label: String(t.table).toUpperCase(), columns: t.column_profiles || [] },
      position: { x: 0, y: 0 },
    }));
  }, [analysisData]);

  const nodeLookup = useMemo(() => {
    const map = new Map<string, string>();
    initialNodes.forEach((node: any) => {
      const nodeId = String(node.id || '');
      const normalized = normalizeTableName(nodeId);
      if (normalized && !map.has(normalized)) map.set(normalized, nodeId);
      if (nodeId && !map.has(nodeId.toLowerCase())) map.set(nodeId.toLowerCase(), nodeId);
    });
    return map;
  }, [initialNodes]);

  const initialEdges = useMemo(() => {
    if (!analysisData?.analysis?.relationships) return [];
    const edges = analysisData.analysis.relationships.map((rel: any, i: number) => {
      const parentRaw = String(rel.parent_table || '');
      const childRaw = String(rel.child_table || '');
      const source = nodeLookup.get(normalizeTableName(parentRaw)) || nodeLookup.get(parentRaw.toLowerCase()) || parentRaw;
      const target = nodeLookup.get(normalizeTableName(childRaw)) || nodeLookup.get(childRaw.toLowerCase()) || childRaw;
      return {
        id: `e${i}-${source}-${target}`,
        source,
        target,
        label: showEdgeLabels ? `${rel.parent_column} = ${rel.child_column}` : '',
        type: 'draggableCurved',
        animated: false,
        style: { stroke: isDarkMode ? '#60a5fa' : '#2563eb', strokeWidth: 2.4 },
        markerEnd: { type: MarkerType.ArrowClosed, color: isDarkMode ? '#60a5fa' : '#2563eb' },
        data: {
          offset: edgeOffsets[`e${i}-${source}-${target}`] || { x: 0, y: 0 },
          onOffsetChange: handleEdgeOffsetChange,
        },
      };
    });

    return edges.filter(
      (edge: any) =>
        edge.source !== edge.target &&
        nodeLookup.has(normalizeTableName(edge.source)) &&
        nodeLookup.has(normalizeTableName(edge.target))
    );
  }, [analysisData, nodeLookup, isDarkMode, showEdgeLabels, edgeOffsets, handleEdgeOffsetChange]);

  const { nodes: layoutedNodes, edges: layoutedEdges } = useMemo(() => getLayoutedElements(initialNodes, initialEdges, 'LR'), [initialNodes, initialEdges]);
  const routedEdges = useMemo(() => assignHandlesByGeometry(layoutedNodes, layoutedEdges), [layoutedNodes, layoutedEdges]);

  return (
    <div
      className={clsx(
        'w-full h-[800px] rounded-[2rem] overflow-hidden border',
        isDarkMode ? 'bg-[#070b14] border-slate-800' : 'bg-slate-100 border-slate-200'
      )}
    >
      <ReactFlow
        nodes={layoutedNodes}
        edges={routedEdges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        colorMode={isDarkMode ? 'dark' : 'light'}
        className="bg-transparent"
        minZoom={0.1}
        maxZoom={1.5}
        defaultEdgeOptions={{ zIndex: 5, interactionWidth: 18 }}
        edgesReconnectable={false}
        nodesConnectable={false}
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1.6} color={isDarkMode ? '#334155' : '#94a3b8'} />
        <Controls className="fill-blue-500 bg-white/90 dark:bg-slate-900/90 border border-slate-300 dark:border-slate-700 rounded-xl" />
      </ReactFlow>
    </div>
  );
}
