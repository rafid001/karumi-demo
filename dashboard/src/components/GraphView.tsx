import { useMemo } from "react";
import {
  Background,
  Controls,
  MarkerType,
  ReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { type Graph, type GraphEdge, type GraphNode } from "../api";

interface Props {
  graph: Graph | null;
}

function shortPath(url: string) {
  try {
    const parsed = new URL(url);
    return parsed.pathname === "/" ? "/" : parsed.pathname;
  } catch {
    return url;
  }
}

function pathOrder(url: string) {
  try {
    const path = new URL(url).pathname.replace(/\/$/, "") || "/";
    const order = ["/", "/projects", "/team", "/settings"];
    const idx = order.indexOf(path);
    return idx >= 0 ? idx : 100 + path.length;
  } catch {
    return 999;
  }
}

function findRoot(nodes: GraphNode[]): GraphNode {
  return [...nodes].sort((a, b) => {
    const aRoot = shortPath(a.url) === "/" ? 0 : 1;
    const bRoot = shortPath(b.url) === "/" ? 0 : 1;
    if (aRoot !== bRoot) return aRoot - bRoot;
    return pathOrder(a.url) - pathOrder(b.url);
  })[0];
}

function layoutNodes(nodes: GraphNode[]): Map<string, { x: number; y: number }> {
  const positions = new Map<string, { x: number; y: number }>();
  if (!nodes.length) return positions;

  const root = findRoot(nodes);
  const others = nodes.filter((n) => n.id !== root.id).sort((a, b) => pathOrder(a.url) - pathOrder(b.url));

  if (nodes.length > 6) {
    const byDepth: Record<number, number> = {};
    nodes.forEach((node) => {
      const depth = Number(node.metadata?.depth ?? 0);
      const index = byDepth[depth] ?? 0;
      byDepth[depth] = index + 1;
      positions.set(node.id, { x: depth * 320, y: index * 150 });
    });
    return positions;
  }

  const gapY = 220;
  const centerY = ((others.length - 1) * gapY) / 2;
  positions.set(root.id, { x: 40, y: centerY });
  others.forEach((node, index) => {
    positions.set(node.id, { x: 500, y: index * gapY });
  });

  return positions;
}

function buildEdges(root: GraphNode, nodes: GraphNode[], edges: GraphEdge[]): Edge[] {
  const arrow = {
    type: MarkerType.ArrowClosed,
    width: 14,
    height: 14,
    color: "#525252",
  };

  if (nodes.length <= 6) {
    return nodes
      .filter((n) => n.id !== root.id)
      .map((node) => ({
        id: `flow-${root.id}-${node.id}`,
        source: root.id,
        target: node.id,
        type: "default",
        markerEnd: arrow,
        style: { stroke: "#525252", strokeWidth: 1.5 },
      }));
  }

  const seen = new Set<string>();
  const result: Edge[] = [];
  for (const edge of edges) {
    const pair = [edge.from_node_id, edge.to_node_id].sort().join("|");
    if (seen.has(pair)) continue;
    seen.add(pair);

    const fromDepth =
      nodes.find((n) => n.id === edge.from_node_id)?.metadata?.depth ?? 99;
    const toDepth = nodes.find((n) => n.id === edge.to_node_id)?.metadata?.depth ?? 99;
    const forward = Number(fromDepth) <= Number(toDepth);

    result.push({
      id: edge.id,
      source: forward ? edge.from_node_id : edge.to_node_id,
      target: forward ? edge.to_node_id : edge.from_node_id,
      type: "default",
      markerEnd: arrow,
      style: { stroke: "#404040", strokeWidth: 1.5 },
    });
  }
  return result;
}

function metaStr(value: unknown): string | null {
  if (typeof value === "string" && value.trim()) return value.trim();
  return null;
}

function NodeCard({ node }: { node: GraphNode }) {
  const isKey = Boolean(node.metadata?.is_key_moment);
  const depth = node.metadata?.depth;
  const purpose = metaStr(node.metadata?.purpose);
  const action = metaStr(node.metadata?.primary_action);
  const journey = metaStr(node.metadata?.journey_moment);

  return (
    <div className={`graph-node-card ${isKey ? "graph-node-card--key" : ""}`}>
      <div className="graph-node-card-top">
        <div className="graph-node-title-row">
          {depth !== undefined && (
            <span className="graph-node-depth">L{Number(depth)}</span>
          )}
          <div className="graph-node-title">{node.title || "Untitled"}</div>
        </div>
        {isKey && <span className="graph-node-badge">key</span>}
      </div>
      <div className="graph-node-path">{shortPath(node.url)}</div>
      {purpose && <p className="graph-node-purpose">{purpose}</p>}
      {action && (
        <div className="graph-node-action">
          <span className="graph-node-action-label">CTA</span>
          <span className="graph-node-action-chip">{action}</span>
        </div>
      )}
      {journey && <div className="graph-node-journey">{journey}</div>}
    </div>
  );
}

export default function GraphView({ graph }: Props) {
  const { nodes, edges } = useMemo(() => {
    if (!graph) return { nodes: [] as Node[], edges: [] as Edge[] };

    const positions = layoutNodes(graph.nodes);
    const root = findRoot(graph.nodes);

    const flowNodes: Node[] = graph.nodes.map((node) => ({
      id: node.id,
      position: positions.get(node.id) ?? { x: 0, y: 0 },
      data: { label: <NodeCard node={node} /> },
      className: node.metadata?.is_key_moment
        ? "graph-flow-node graph-flow-node--key"
        : "graph-flow-node",
    }));

    const flowEdges = buildEdges(root, graph.nodes, graph.edges);
    return { nodes: flowNodes, edges: flowEdges };
  }, [graph]);

  if (!graph) {
    return <p className="empty">Select a product to view its knowledge graph.</p>;
  }

  if (!graph.nodes.length) {
    return <p className="empty">No nodes in graph — run a crawl first.</p>;
  }

  const keyCount = graph.nodes.filter((n) => n.metadata?.is_key_moment).length;

  return (
    <div className="graph-wrap">
      <div className="graph-summary">
        <span>{graph.nodes.length} pages</span>
        <span>{graph.edges.length} links</span>
        {keyCount > 0 && <span>{keyCount} key moments</span>}
      </div>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        fitViewOptions={{ padding: 0.4 }}
        colorMode="dark"
        proOptions={{ hideAttribution: true }}
        nodesDraggable
        nodesConnectable={false}
        minZoom={0.5}
        maxZoom={1.3}
        defaultEdgeOptions={{
          type: "default",
          markerEnd: { type: MarkerType.ArrowClosed, color: "#525252" },
        }}
      >
        <Background gap={24} size={1} color="#141414" />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
