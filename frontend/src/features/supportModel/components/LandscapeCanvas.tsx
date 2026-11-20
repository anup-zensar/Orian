import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Background,
  BaseEdge,
  Controls,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  getStraightPath,
  useInternalNode,
  type Connection,
  type Edge,
  type ReactFlowInstance,
  type EdgeProps,
  type InternalNode,
  type Node,
  type NodeChange,
  type NodeProps,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { makeStyles, mergeClasses, tokens } from '@fluentui/react-components';
import type { Landscape } from '../api';
import { APP_NODE_ID, directionOf, radialLayout, targetNameOf, type Pos } from '../graph';

const useStyles = makeStyles({
  frame: {
    height: '520px',
    width: '100%',
    minWidth: 0,
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    borderRadius: tokens.borderRadiusMedium,
    backgroundColor: tokens.colorNeutralBackground2,
  },
  node: {
    boxSizing: 'border-box',
    padding: '6px 10px',
    borderRadius: tokens.borderRadiusMedium,
    border: `1px solid ${tokens.colorNeutralStroke1}`,
    backgroundColor: tokens.colorNeutralBackground1,
    color: tokens.colorNeutralForeground1,
    textAlign: 'center',
    fontSize: tokens.fontSizeBase200,
    lineHeight: tokens.lineHeightBase200,
    overflow: 'hidden',
  },
  nodeSelected: {
    border: `2px solid ${tokens.colorNeutralForeground1}`,
    backgroundColor: tokens.colorBrandBackground2,
  },
  center: {
    backgroundColor: tokens.colorBrandBackground,
    color: tokens.colorNeutralForegroundOnBrand,
    fontSize: tokens.fontSizeBase300,
    fontWeight: tokens.fontWeightSemibold,
  },
  type: { color: tokens.colorNeutralForeground3, fontSize: tokens.fontSizeBase100 },
  hidden: { opacity: 0, pointerEvents: 'none' },
});

const SIZE = { app: { w: 180, h: 60 }, comp: { w: 160, h: 58 } };

interface NodeData extends Record<string, unknown> {
  label: string;
  type?: string;
  center?: boolean;
  selected?: boolean;
}

function LandscapeNode({ data }: NodeProps<Node<NodeData>>) {
  const s = useStyles();
  const size = data.center ? SIZE.app : SIZE.comp;
  return (
    <div
      className={mergeClasses(s.node, data.center && s.center, data.selected && s.nodeSelected)}
      style={{ width: size.w, height: size.h }}
    >
      {/* Handles sit at the centre; the floating edge computes the visible border anchor. */}
      <Handle
        type="target"
        position={Position.Top}
        className={s.hidden}
        style={{ top: '50%', left: '50%' }}
      />
      <Handle
        type="source"
        position={Position.Top}
        className={s.hidden}
        style={{ top: '50%', left: '50%' }}
      />
      <div>{data.label}</div>
      {data.type && <div className={s.type}>{data.type}</div>}
    </div>
  );
}

function center(n: InternalNode) {
  const w = n.measured.width ?? SIZE.comp.w;
  const h = n.measured.height ?? SIZE.comp.h;
  const p = n.internals.positionAbsolute;
  return { x: p.x + w / 2, y: p.y + h / 2, w, h };
}

/** Point where the line from node a's centre to node b's centre leaves a's box. */
function borderPoint(a: ReturnType<typeof center>, b: ReturnType<typeof center>) {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  if (dx === 0 && dy === 0) return { x: a.x, y: a.y };
  const scale = Math.min(
    dx === 0 ? Infinity : a.w / 2 / Math.abs(dx),
    dy === 0 ? Infinity : a.h / 2 / Math.abs(dy),
  );
  return { x: a.x + dx * scale, y: a.y + dy * scale };
}

function FloatingEdge({ id, source, target, markerStart, markerEnd, style, label }: EdgeProps) {
  const src = useInternalNode(source);
  const tgt = useInternalNode(target);
  if (!src || !tgt) return null;
  const a = center(src);
  const b = center(tgt);
  const p1 = borderPoint(a, b);
  const p2 = borderPoint(b, a);
  const [path, lx, ly] = getStraightPath({
    sourceX: p1.x,
    sourceY: p1.y,
    targetX: p2.x,
    targetY: p2.y,
  });
  return (
    <BaseEdge
      id={id}
      path={path}
      markerStart={markerStart}
      markerEnd={markerEnd}
      style={style}
      label={label}
      labelX={lx}
      labelY={ly}
      labelStyle={{ fontSize: 10 }}
    />
  );
}

const nodeTypes = { landscape: LandscapeNode };
const edgeTypes = { floating: FloatingEdge };

export type CanvasSelection = { kind: 'node'; id: string } | { kind: 'edge'; id: string } | null;

/** React Flow canvas: central app in the middle, components radial, edges with direction from
 * each component's relation (A-65 style: layout computed client-side). */
export function LandscapeCanvas(props: {
  landscape: Landscape;
  editable: boolean;
  selection: CanvasSelection;
  onSelect: (s: CanvasSelection) => void;
  /** Drag from component A to node B: A now connects to B. */
  onConnect: (componentId: string, targetNodeId: string) => void;
}) {
  const { landscape, selection } = props;
  const s = useStyles();
  const [dragged, setDragged] = useState<Record<string, Pos>>({});
  const frameRef = useRef<HTMLDivElement>(null);
  const flowRef = useRef<ReactFlowInstance<Node<NodeData>, Edge> | null>(null);
  // Keep the whole landscape in view when the content width changes (Orion panel, nav, window).
  useEffect(() => {
    const el = frameRef.current;
    if (!el || typeof ResizeObserver === 'undefined') return;
    let raf = 0;
    const ro = new ResizeObserver(() => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => void flowRef.current?.fitView({ padding: 0.1 }));
    });
    ro.observe(el);
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, []);
  const layout = useMemo(() => radialLayout(landscape), [landscape]);

  const nodes = useMemo<Node<NodeData>[]>(() => {
    const list: Node<NodeData>[] = [
      {
        id: APP_NODE_ID,
        type: 'landscape',
        position: dragged[APP_NODE_ID] ?? layout[APP_NODE_ID] ?? { x: 0, y: 0 },
        data: {
          label: landscape.central_app,
          center: true,
          selected: selection?.kind === 'node' && selection.id === APP_NODE_ID,
        },
        // Centre the node on the origin.
        origin: [0.5, 0.5],
        ariaLabel: `${landscape.central_app}, central application`,
        deletable: false,
      },
    ];
    for (const c of landscape.components) {
      list.push({
        id: c.id,
        type: 'landscape',
        position: dragged[c.id] ?? layout[c.id] ?? { x: 0, y: 0 },
        origin: [0.5, 0.5],
        ariaLabel: `${c.name}, ${c.type}`,
        data: {
          label: c.name,
          type: c.type,
          selected: selection?.kind === 'node' && selection.id === c.id,
        },
        deletable: false,
      });
    }
    return list;
  }, [landscape, layout, dragged, selection]);

  const edges = useMemo<Edge[]>(() => {
    const idByName = new Map(landscape.components.map((c) => [c.name, c.id]));
    const out: Edge[] = [];
    for (const c of landscape.components) {
      const tName = targetNameOf(c, landscape.central_app);
      const tId = tName === landscape.central_app ? APP_NODE_ID : idByName.get(tName);
      if (!tId || tId === c.id) continue;
      const dir = directionOf(c);
      const isSel = selection?.kind === 'edge' && selection.id === c.id;
      const color = isSel ? tokens.colorNeutralForeground1 : tokens.colorNeutralForeground3;
      const marker = { type: MarkerType.ArrowClosed, color };
      const base: Edge = {
        id: c.id,
        type: 'floating',
        source: c.id,
        target: tId,
        style: { stroke: color, strokeWidth: isSel ? 2.5 : 1.5 },
        interactionWidth: 24,
      };
      if (dir === 'bidirectional') out.push({ ...base, markerStart: marker, markerEnd: marker });
      else if (dir === 'inbound') out.push({ ...base, markerEnd: marker });
      else if (dir === 'outbound')
        out.push({ ...base, source: tId, target: c.id, id: c.id, markerEnd: marker });
      else
        out.push({
          ...base,
          label: 'child of',
          style: { ...base.style, strokeDasharray: '5 4' },
        });
    }
    return out;
  }, [landscape, selection]);

  const onNodesChange = (changes: NodeChange<Node<NodeData>>[]) => {
    for (const ch of changes) {
      if (ch.type === 'position' && ch.position) {
        const pos = ch.position;
        setDragged((d) => ({ ...d, [ch.id]: pos }));
      }
    }
  };

  const onConnect = (c: Connection) => {
    if (!props.editable || !c.source || !c.target || c.source === c.target) return;
    // The central app has no outgoing relation of its own: connect the component side.
    if (c.source === APP_NODE_ID) props.onConnect(c.target, APP_NODE_ID);
    else props.onConnect(c.source, c.target);
  };

  return (
    <div
      ref={frameRef}
      className={s.frame}
      data-testid="landscape-canvas"
      // Keyboard: Enter/Space on a focused node or edge selects it (React Flow only fires its
      // click handlers for the mouse).
      onKeyDown={(e) => {
        if (e.key !== 'Enter' && e.key !== ' ') return;
        const el = (e.target as HTMLElement).closest<HTMLElement>(
          '.react-flow__node, .react-flow__edge',
        );
        const id = el?.dataset.id ?? el?.getAttribute('data-id');
        if (!el || !id) return;
        e.preventDefault();
        props.onSelect({ kind: el.classList.contains('react-flow__edge') ? 'edge' : 'node', id });
      }}
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodesChange={onNodesChange}
        onNodeClick={(_, n) => props.onSelect({ kind: 'node', id: n.id })}
        onEdgeClick={(_, e) => props.onSelect({ kind: 'edge', id: e.id })}
        onPaneClick={() => props.onSelect(null)}
        onConnect={onConnect}
        nodesConnectable={props.editable}
        elementsSelectable
        fitView
        onInit={(i) => {
          flowRef.current = i;
        }}
        fitViewOptions={{ padding: 0.1 }}
        minZoom={0.3}
        proOptions={{ hideAttribution: true }}
      >
        <Background />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
