"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import Link from "next/link";
import { BASE, safeJson } from "@/lib/api";

interface GraphNode {
  id: string;
  name: string;
  node_type: string;
  importance: number;
  similarity?: number;
}

interface GraphEdge {
  source: string;
  target: string;
  edge_type: string;
  weight: number;
}

interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

const TYPE_COLORS: Record<string, string> = {
  person: "#00FF66",
  habit: "#FFB300",
  preference: "#00B4D8",
  emotion: "#FF66B2",
  goal: "#A855F7",
  learning: "#00B4D8",
  relationship: "#FF3333",
  system: "#71717a",
  entity: "#e4e4e7",
  concept: "#FFD700",
  skill: "#00FF66",
  unknown: "#52525b",
};

export default function GraphPage() {
  const [graph, setGraph] = useState<GraphData>({ nodes: [], edges: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [semanticResults, setSemanticResults] = useState<GraphNode[]>([]);
  const [semanticQuery, setSemanticQuery] = useState("");
  const [embedRunning, setEmbedRunning] = useState(false);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [stats, setStats] = useState<any>(null);
  const [embedStatus, setEmbedStatus] = useState<any>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [hoveredNode, setHoveredNode] = useState<GraphNode | null>(null);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });
  const nodePositions = useRef<Map<string, { x: number; y: number }>>(new Map());

  const fetchGraph = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [graphRes, statsRes, embedRes] = await Promise.allSettled([
        safeJson(await fetch(`${BASE}/api/graph/visualization`)),
        safeJson(await fetch(`${BASE}/api/graph/stats`)),
        safeJson(await fetch(`${BASE}/api/graph/embeddings/status`)),
      ]);
      if (graphRes.status === "fulfilled") setGraph(graphRes.value);
      if (statsRes.status === "fulfilled") setStats(statsRes.value);
      if (embedRes.status === "fulfilled") setEmbedStatus(embedRes.value);
    } catch (e: any) {
      setError(e.message);
    }
    setLoading(false);
  }, []);

  useEffect(() => { fetchGraph(); }, [fetchGraph]);

  const semanticSearch = useCallback(async () => {
    if (!semanticQuery.trim()) return;
    try {
      const res = await safeJson(await fetch(`${BASE}/api/graph/semantic_search?q=${encodeURIComponent(semanticQuery)}&limit=10`));
      setSemanticResults(res.results || []);
    } catch {}
  }, [semanticQuery]);

  const generateEmbeddings = useCallback(async () => {
    setEmbedRunning(true);
    try {
      await fetch(`${BASE}/api/graph/embeddings/generate`, { method: "POST" });
      await fetchGraph();
    } catch {}
    setEmbedRunning(false);
  }, [fetchGraph]);

  // Layout nodes in a force-directed-ish layout
  useEffect(() => {
    if (!graph.nodes.length) return;
    const w = dimensions.width || 800;
    const h = dimensions.height || 600;
    const positions = new Map<string, { x: number; y: number }>();

    // Group nodes by type
    const groups = new Map<string, GraphNode[]>();
    graph.nodes.forEach(n => {
      const key = n.node_type || "unknown";
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key)!.push(n);
    });

    let angle = 0;
    const groupKeys = Array.from(groups.keys());
    groupKeys.forEach((type, gi) => {
      const groupAngle = (gi / groupKeys.length) * Math.PI * 2;
      const groupRadius = Math.min(w, h) * 0.3;
      const groupCenter = {
        x: w / 2 + Math.cos(groupAngle) * groupRadius,
        y: h / 2 + Math.sin(groupAngle) * groupRadius,
      };

      groups.get(type)!.forEach((node, ni) => {
        const subAngle = (ni / groups.get(type)!.length) * Math.PI * 2;
        const subRadius = 30 + (groups.get(type)!.length * 5);
        positions.set(node.id, {
          x: groupCenter.x + Math.cos(subAngle) * subRadius,
          y: groupCenter.y + Math.sin(subAngle) * subRadius,
        });
      });
    });

    nodePositions.current = positions;
  }, [graph.nodes, dimensions]);

  // Draw the graph on canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const rect = canvas.parentElement?.getBoundingClientRect();
    if (rect) {
      canvas.width = rect.width;
      canvas.height = rect.height;
      setDimensions({ width: rect.width, height: rect.height });
    }

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw edges
    ctx.strokeStyle = "rgba(255,255,255,0.06)";
    ctx.lineWidth = 1;
    graph.edges.forEach(edge => {
      const from = nodePositions.current.get(edge.source);
      const to = nodePositions.current.get(edge.target);
      if (from && to) {
        ctx.beginPath();
        ctx.moveTo(from.x, from.y);
        ctx.lineTo(to.x, to.y);
        ctx.stroke();
      }
    });

    // Draw nodes
    graph.nodes.forEach(node => {
      const pos = nodePositions.current.get(node.id);
      if (!pos) return;

      const color = TYPE_COLORS[node.node_type] || TYPE_COLORS.unknown;
      const radius = 3 + node.importance * 4;
      const isHovered = hoveredNode?.id === node.id;
      const isSelected = selectedNode?.id === node.id;

      ctx.beginPath();
      ctx.arc(pos.x, pos.y, isHovered || isSelected ? radius + 2 : radius, 0, Math.PI * 2);
      ctx.fillStyle = isSelected ? "#fff" : color;
      ctx.globalAlpha = isHovered || isSelected ? 1 : 0.7;
      ctx.fill();
      ctx.globalAlpha = 1;

      if (isHovered || isSelected) {
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      // Label for hovered or important nodes
      if (isHovered || node.importance > 0.7) {
        ctx.fillStyle = "#e4e4e7";
        ctx.font = "9px monospace";
        ctx.fillText(node.name.substring(0, 20), pos.x + radius + 4, pos.y + 3);
      }
    });
  }, [graph, hoveredNode, selectedNode, dimensions]);

  // Handle canvas mouse move
  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    let found: GraphNode | null = null;
    for (const node of graph.nodes) {
      const pos = nodePositions.current.get(node.id);
      if (pos) {
        const dist = Math.sqrt((pos.x - x) ** 2 + (pos.y - y) ** 2);
        if (dist < 10) { found = node; break; }
      }
    }
    setHoveredNode(found);
  }, [graph.nodes]);

  const filteredNodes = graph.nodes.filter(n =>
    !search || n.name.toLowerCase().includes(search.toLowerCase()) || n.node_type.toLowerCase().includes(search.toLowerCase())
  );

  const typeCounts = new Map<string, number>();
  graph.nodes.forEach(n => {
    typeCounts.set(n.node_type || "unknown", (typeCounts.get(n.node_type || "unknown") || 0) + 1);
  });

  return (
    <div style={{ minHeight: "100vh", background: "#09090b", color: "#e4e4e7", fontFamily: "var(--font-sans, system-ui, sans-serif)", padding: "20px", maxWidth: 1400, margin: "0 auto" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <div>
          <Link href="/" style={{ fontSize: 12, color: "#52525b", textDecoration: "none" }}>← Back to JARVIS</Link>
          <h1 style={{ fontSize: 24, fontWeight: 700, margin: "4px 0 0", color: "#fff" }}>Knowledge Graph</h1>
          <p style={{ fontSize: 13, color: "#71717a", margin: "2px 0 0" }}>Local SQLite hybrid memory — sub-10ms context recall</p>
        </div>
        <button onClick={fetchGraph} style={{ padding: "6px 14px", borderRadius: 6, background: "rgba(255,255,255,0.05)", color: "#a1a1aa", border: "1px solid rgba(255,255,255,0.1)", cursor: "pointer", fontSize: 12 }}>↻ Refresh</button>
      </div>

      {/* Stats */}
      <div style={{ display: "flex", gap: 12, marginBottom: 20, flexWrap: "wrap" }}>
        <StatBox label="Nodes" value={`${graph.nodes.length}`} color="#00FF66" />
        <StatBox label="Edges" value={`${graph.edges.length}`} color="#00B4D8" />
        <StatBox label="Types" value={`${typeCounts.size}`} color="#FFB300" />
        <StatBox label="Embedded" value={`${embedStatus?.embedded || 0}/${embedStatus?.total_nodes || 0}`} color="#A855F7" />
      </div>

      {loading && <div style={{ color: "#71717a", fontSize: 13, padding: 40, textAlign: "center" }}>Loading graph...</div>}
      {error && <div style={{ color: "#FF3333", fontSize: 13, padding: 12, background: "rgba(255,51,51,0.1)", borderRadius: 8 }}>{error}</div>}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 300px", gap: 16, minHeight: 500 }}>
        {/* Graph Canvas */}
        <div style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 12, position: "relative", overflow: "hidden" }}>
          <canvas ref={canvasRef} onMouseMove={handleMouseMove} onClick={() => setSelectedNode(hoveredNode)} style={{ width: "100%", height: "100%", cursor: hoveredNode ? "pointer" : "default" }} />
          {graph.nodes.length === 0 && !loading && (
            <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", color: "#52525b", fontSize: 13 }}>
              No graph data yet. Start chatting to build your knowledge graph.
            </div>
          )}
          {/* Legend */}
          <div style={{ position: "absolute", bottom: 12, left: 12, display: "flex", flexWrap: "wrap", gap: 8 }}>
            {Array.from(typeCounts.entries()).map(([type, count]) => (
              <div key={type} style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 9, color: "#71717a" }}>
                <div style={{ width: 6, height: 6, borderRadius: "50%", background: TYPE_COLORS[type] || "#52525b" }} />
                {type} ({count})
              </div>
            ))}
          </div>
        </div>

        {/* Sidebar */}
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {/* Search */}
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Filter nodes..."
            style={{ padding: "8px 12px", borderRadius: 6, background: "rgba(255,255,255,0.05)", color: "#e4e4e7", border: "1px solid rgba(255,255,255,0.1)", fontSize: 12 }} />

          {/* Semantic Search */}
          <div style={{ display: "flex", gap: 6 }}>
            <input value={semanticQuery} onChange={e => setSemanticQuery(e.target.value)}
              placeholder="Semantic search..."
              onKeyDown={e => e.key === "Enter" && semanticSearch()}
              style={{ flex: 1, padding: "8px 12px", borderRadius: 6, background: "rgba(0,180,216,0.08)", color: "#e4e4e7", border: "1px solid rgba(0,180,216,0.2)", fontSize: 12 }} />
            <button onClick={semanticSearch} style={{ padding: "8px 10px", borderRadius: 6, background: "rgba(0,180,216,0.15)", color: "#00B4D8", border: "1px solid rgba(0,180,216,0.3)", cursor: "pointer", fontSize: 11 }}>🔍</button>
          </div>

          {/* Embed All Button */}
          <button onClick={generateEmbeddings} disabled={embedRunning}
            style={{ padding: "6px 12px", borderRadius: 6, background: embedRunning ? "rgba(168,85,247,0.05)" : "rgba(168,85,247,0.12)", color: "#A855F7", border: "1px solid rgba(168,85,247,0.2)", cursor: embedRunning ? "wait" : "pointer", fontSize: 11 }}>
            {embedRunning ? "Embedding..." : `Generate Embeddings (${embedStatus?.pending || 0} pending)`}
          </button>

          {/* Semantic Results */}
          {semanticResults.length > 0 && (
            <div style={{ background: "rgba(0,180,216,0.04)", border: "1px solid rgba(0,180,216,0.1)", borderRadius: 8, padding: 10, maxHeight: 180, overflowY: "auto" }}>
              <div style={{ fontSize: 10, color: "#00B4D8", marginBottom: 6, fontWeight: 600 }}>SEMANTIC RESULTS ({semanticResults.length})</div>
              {semanticResults.map(node => (
                <div key={node.id} onClick={() => setSelectedNode(node)} style={{ padding: "4px 6px", borderRadius: 4, cursor: "pointer", fontSize: 10, display: "flex", alignItems: "center", gap: 6 }}>
                  <div style={{ width: 4, height: 4, borderRadius: "50%", background: TYPE_COLORS[node.node_type] || "#52525b" }} />
                  <span style={{ color: "#a1a1aa" }}>{node.name}</span>
                  <span style={{ fontSize: 8, color: "#00B4D8", marginLeft: "auto" }}>{node.similarity}</span>
                </div>
              ))}
            </div>
          )}

          {/* Selected Node */}
          {selectedNode && (
            <div style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 10, padding: 16 }}>
              <div style={{ fontSize: 11, color: "#71717a", marginBottom: 4 }}>SELECTED NODE</div>
              <div style={{ fontSize: 16, fontWeight: 600, color: TYPE_COLORS[selectedNode.node_type] || "#e4e4e7" }}>{selectedNode.name}</div>
              <div style={{ fontSize: 11, color: "#71717a", marginTop: 4 }}>Type: {selectedNode.node_type}</div>
              <div style={{ fontSize: 11, color: "#71717a" }}>Importance: {selectedNode.importance.toFixed(2)}</div>
              <div style={{ fontSize: 11, color: "#71717a" }}>ID: {selectedNode.id.substring(0, 16)}...</div>
              {/* Connected nodes */}
              <div style={{ marginTop: 12, fontSize: 11, color: "#71717a", fontWeight: 600 }}>Connections:</div>
              {graph.edges.filter(e => e.source === selectedNode.id || e.target === selectedNode.id).slice(0, 5).map((edge, i) => {
                const otherId = edge.source === selectedNode.id ? edge.target : edge.source;
                const other = graph.nodes.find(n => n.id === otherId);
                return (
                  <div key={i} style={{ fontSize: 10, color: "#a1a1aa", marginTop: 4 }}>
                    → {other?.name || otherId.substring(0, 12)} <span style={{ color: "#52525b" }}>({edge.edge_type})</span>
                  </div>
                );
              })}
            </div>
          )}

          {/* Node List */}
          <div style={{ flex: 1, overflowY: "auto", maxHeight: 300 }}>
            <div style={{ fontSize: 11, color: "#71717a", marginBottom: 6, fontWeight: 600 }}>NODES ({filteredNodes.length})</div>
            {filteredNodes.slice(0, 50).map(node => (
              <div key={node.id} onClick={() => setSelectedNode(node)}
                style={{ padding: "6px 8px", borderRadius: 4, cursor: "pointer", fontSize: 11, display: "flex", alignItems: "center", gap: 6, background: selectedNode?.id === node.id ? "rgba(0,180,216,0.1)" : "transparent" }}
                onMouseEnter={() => setHoveredNode(node)}
                onMouseLeave={() => setHoveredNode(null)}>
                <div style={{ width: 5, height: 5, borderRadius: "50%", background: TYPE_COLORS[node.node_type] || "#52525b", flexShrink: 0 }} />
                <span style={{ color: "#a1a1aa", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{node.name}</span>
                <span style={{ fontSize: 8, color: "#52525b", marginLeft: "auto" }}>{node.node_type}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function StatBox({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 10, padding: "14px 16px", minWidth: 120 }}>
      <div style={{ fontSize: 10, color: "#71717a", marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.05em" }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color }}>{value}</div>
    </div>
  );
}
