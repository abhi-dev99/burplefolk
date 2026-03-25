import { useMemo } from 'react';
import { ReactFlow, Controls, Background, BackgroundVariant, MarkerType, Handle, Position } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import dagre from 'dagre';
import clsx from 'clsx';
import { Key } from 'lucide-react';

const TableNode = ({ data }: any) => {
  return (
    <div className="bg-white/90 dark:bg-[#0b1220]/90 backdrop-blur-md rounded-xl border-2 border-slate-200 dark:border-slate-700 shadow-xl overflow-hidden min-w-[240px]">
      <Handle type="target" position={Position.Left} className="w-1.5 h-1.5 !bg-blue-500 rounded-full border border-white dark:border-slate-800" />
      <Handle type="source" position={Position.Right} className="w-1.5 h-1.5 !bg-blue-500 rounded-full border border-white dark:border-slate-800" />
      <div className="bg-gradient-to-r from-blue-600 to-blue-500 px-4 py-3 border-b border-blue-700/50">
        <h3 className="font-bold text-white tracking-wide text-sm">{data.label}</h3>
      </div>
      <div className="flex flex-col text-sm py-1">
        {data.columns.map((col: any, i: number) => {
          const isPK = String(col.role).includes('PK') || String(col.semantic_role).includes('primary');
          const isFK = String(col.semantic_role || '').toLowerCase().includes('foreign') || String(col.column || '').endsWith('_id') && !isPK;
          return (
            <div key={i} className="flex items-center justify-between px-4 py-1.5 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors border-b border-slate-100 dark:border-slate-800 last:border-0">
               <div className="flex items-center gap-2">
                 {isPK && <Key className="w-3 h-3 text-amber-500" />}
                 <span className={clsx("font-medium", isPK ? "text-amber-600 dark:text-amber-400" : isFK ? "text-rose-500" : "text-slate-700 dark:text-slate-300")}>{String(col.column || '-')}</span>
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

const getLayoutedElements = (nodes: any[], edges: any[], direction = 'LR') => {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  
  const isHorizontal = direction === 'LR';
  dagreGraph.setGraph({ rankdir: direction, nodesep: 60, ranksep: 200 });

  nodes.forEach((node) => {
    // approximate width and height based on columns length
    dagreGraph.setNode(node.id, { width: 260, height: 50 + (node.data.columns.length * 35) });
  });

  edges.forEach((edge) => {
    if (dagreGraph.hasNode(edge.source) && dagreGraph.hasNode(edge.target)) {
      dagreGraph.setEdge(edge.source, edge.target);
    } else {
      console.warn(`Dagre skipped edge constraint: [${edge.source}] -> [${edge.target}] due to missing nodes.`);
    }
  });

  dagre.layout(dagreGraph);

  const updatedNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id);
    if (!nodeWithPosition) return node;
    
    return {
      ...node,
      targetPosition: isHorizontal ? 'left' : 'top',
      sourcePosition: isHorizontal ? 'right' : 'bottom',
      position: {
        x: nodeWithPosition.x - nodeWithPosition.width / 2,
        y: nodeWithPosition.y - nodeWithPosition.height / 2,
      }
    };
  });

  return { nodes: updatedNodes, edges };
};

export default function ERDiagram({ analysisData }: { analysisData: any }) {
  const initialNodes = useMemo(() => {
    if (!analysisData?.analysis?.table_profiles) return [];
    return analysisData.analysis.table_profiles.map((t: any) => ({
      id: String(t.table),
      type: 'tableNode',
      data: { label: String(t.table).toUpperCase(), columns: t.column_profiles || [] },
      position: { x: 0, y: 0 }
    }));
  }, [analysisData]);

  const initialEdges = useMemo(() => {
    if (!analysisData?.analysis?.relationships) return [];
    return analysisData.analysis.relationships.map((rel: any, i: number) => ({
      id: `e${i}-${rel.parent_table}-${rel.child_table}`,
      source: String(rel.parent_table),
      target: String(rel.child_table),
      label: `${rel.parent_column} = ${rel.child_column}`,
      type: 'smoothstep',
      animated: true,
      style: { stroke: '#64748b', strokeWidth: 2 },
      labelStyle: { fill: '#64748b', fontWeight: 600, fontSize: 10 },
      labelBgStyle: { fill: 'transparent' },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: '#64748b',
      },
    }));
  }, [analysisData]);

  const { nodes: layoutedNodes, edges: layoutedEdges } = useMemo(() => 
    getLayoutedElements(initialNodes, initialEdges, 'LR'),
  [initialNodes, initialEdges]);

  return (
    <div id="react-flow-er-container" style={{ width: '100%', height: '800px', borderRadius: '2rem', overflow: 'hidden' }}>
      <ReactFlow
        nodes={layoutedNodes}
        edges={layoutedEdges}
        nodeTypes={nodeTypes}
        fitView
        className="bg-transparent"
        minZoom={0.1}
        maxZoom={1.5}
        defaultEdgeOptions={{ zIndex: 0 }}
      >
        <Background variant={BackgroundVariant.Dots} gap={24} size={2} color="#94a3b8" />
        <Controls className="fill-blue-500" />
      </ReactFlow>
    </div>
  );
}
