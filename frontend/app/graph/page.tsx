"use client";

import React, { useState, useEffect, useCallback } from "react";

interface GraphNode {
  id: string;
  type: string;
  label: string;
  metadata: Record<string, any>;
  created_at: string;
}

interface GraphEdge {
  source: string;
  target: string;
  relation: string;
  weight: number;
}

interface WorktreeBranch {
  id: string;
  root_concept: string;
  branch_name: string;
  parent_id: string | null;
  mastery: number;
  next_review: string;
  repetition: number;
  ease_factor: number;
  interval_days: number;
}

interface SearchResult {
  node_id: string;
  type: string;
  label: string;
  relevance: number;
  content: string;
  metadata: Record<string, any>;
}

export default function KnowledgeWorktreePage() {
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [worktree, setWorktree] = useState<WorktreeBranch[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [stats, setStats] = useState<Record<string, any>>({});
  const [activeTab, setActiveTab] = useState<"graph" | "worktree" | "search">("graph");
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [nodeEdges, setNodeEdges] = useState<GraphEdge[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // New branch form
  const [newRoot, setNewRoot] = useState("");
  const [newBranch, setNewBranch] = useState("");

  const fetchStats = useCallback(async () => {
    try {
      const res = await fetch("/api/graph/stats");
      const data = await res.json();
      setStats(data);
    } catch (e) {
      console.error("Stats fetch error:", e);
    }
  }, []);

  const fetchNodes = useCallback(async (type?: string) => {
    setLoading(true);
    try {
      const url = type ? `/api/graph/nodes?type=${type}&limit=100` : "/api/graph/nodes?limit=100";
      const res = await fetch(url);
      const data = await res.json();
      setNodes(data.nodes || []);
    } catch (e) {
      setError("Failed to load graph nodes");
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchWorktree = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/graph/worktree");
      const data = await res.json();
      setWorktree(data.due || data.tree || []);
    } catch (e) {
      setError("Failed to load worktree");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStats();
    fetchNodes();
  }, [fetchStats, fetchNodes]);

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    setLoading(true);
    try {
      const res = await fetch(`/api/graph/search?query=${encodeURIComponent(searchQuery)}&limit=20`);
      const data = await res.json();
      setSearchResults(data.results || []);
    } catch (e) {
      setError("Search failed");
    } finally {
      setLoading(false);
    }
  };

  const handleNodeSelect = async (node: GraphNode) => {
    setSelectedNode(node);
    try {
      const res = await fetch(`/api/graph/edges?node_id=${node.id}&direction=both`);
      const data = await res.json();
      setNodeEdges(data.edges || []);
    } catch (e) {
      console.error("Edge fetch error:", e);
    }
  };

  const handleCreateBranch = async () => {
    if (!newRoot.trim() || !newBranch.trim()) return;
    try {
      const res = await fetch("/api/graph/worktree/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ root_concept: newRoot, branch_name: newBranch }),
      });
      if (res.ok) {
        setNewRoot("");
        setNewBranch("");
        fetchWorktree();
      }
    } catch (e) {
      setError("Failed to create branch");
    }
  };

  const handleReview = async (branchId: string, quality: number) => {
    try {
      await fetch("/api/graph/worktree/review", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ branch_id: branchId, quality }),
      });
      fetchWorktree();
    } catch (e) {
      console.error("Review error:", e);
    }
  };

  const getMasteryColor = (mastery: number) => {
    if (mastery >= 90) return "text-emerald-400";
    if (mastery >= 70) return "text-blue-400";
    if (mastery >= 50) return "text-yellow-400";
    if (mastery >= 30) return "text-orange-400";
    return "text-red-400";
  };

  const getMasteryBg = (mastery: number) => {
    if (mastery >= 90) return "bg-emerald-500/20 border-emerald-500/30";
    if (mastery >= 70) return "bg-blue-500/20 border-blue-500/30";
    if (mastery >= 50) return "bg-yellow-500/20 border-yellow-500/30";
    if (mastery >= 30) return "bg-orange-500/20 border-orange-500/30";
    return "bg-red-500/20 border-red-500/30";
  };

  const nodeTypeIcon = (type: string) => {
    const icons: Record<string, string> = {
      concept: "●",
      person: "◉",
      organization: "◆",
      location: "▲",
      skill: "★",
      emotion: "♡",
      habit: "↻",
      project: "■",
      tool: "⚙",
    };
    return icons[type] || "○";
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-200">
      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-2 h-2 rounded-full bg-purple-400 animate-pulse" />
            <h1 className="text-2xl font-light tracking-tight text-white">
              Knowledge Worktree
            </h1>
          </div>
          <p className="text-sm text-zinc-500 ml-5">
            Hybrid graph memory — concepts, relationships, mastery tracking
          </p>
        </div>

        {/* Stats Bar */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
          {[
            { label: "Total Nodes", value: stats.total_nodes || 0, color: "text-purple-400" },
            { label: "Total Edges", value: stats.total_edges || 0, color: "text-blue-400" },
            { label: "Worktree Nodes", value: stats.worktree_nodes || 0, color: "text-emerald-400" },
            { label: "Due for Review", value: stats.due_for_review || 0, color: "text-yellow-400" },
          ].map((stat) => (
            <div
              key={stat.label}
              className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4"
            >
              <div className={`text-2xl font-light ${stat.color}`}>
                {stat.value}
              </div>
              <div className="text-xs text-zinc-500 mt-1">{stat.label}</div>
            </div>
          ))}
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mb-6 bg-zinc-900/50 p-1 rounded-lg border border-zinc-800 w-fit">
          {(["graph", "worktree", "search"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
                activeTab === tab
                  ? "bg-zinc-800 text-white"
                  : "text-zinc-500 hover:text-zinc-300"
              }`}
            >
              {tab === "graph" && "Graph Explorer"}
              {tab === "worktree" && "Worktree"}
              {tab === "search" && "Search"}
            </button>
          ))}
        </div>

        {/* Graph Tab */}
        {activeTab === "graph" && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Node List */}
            <div className="lg:col-span-1">
              <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4">
                <h3 className="text-sm font-medium text-zinc-400 mb-3">
                  Nodes ({nodes.length})
                </h3>
                <div className="space-y-2 max-h-[600px] overflow-y-auto">
                  {nodes.map((node) => (
                    <button
                      key={node.id}
                      onClick={() => handleNodeSelect(node)}
                      className={`w-full text-left p-3 rounded-lg border transition-all ${
                        selectedNode?.id === node.id
                          ? "bg-purple-500/10 border-purple-500/30"
                          : "bg-zinc-800/50 border-zinc-700/50 hover:border-zinc-600"
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-purple-400">
                          {nodeTypeIcon(node.type)}
                        </span>
                        <span className="text-sm font-medium text-zinc-200 truncate">
                          {node.label}
                        </span>
                      </div>
                      <div className="text-xs text-zinc-500 mt-1 ml-5">
                        {node.type} • {new Date(node.created_at).toLocaleDateString()}
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Node Detail */}
            <div className="lg:col-span-2">
              {selectedNode ? (
                <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-6">
                  <div className="flex items-center gap-3 mb-4">
                    <span className="text-2xl text-purple-400">
                      {nodeTypeIcon(selectedNode.type)}
                    </span>
                    <div>
                      <h2 className="text-xl font-medium text-white">
                        {selectedNode.label}
                      </h2>
                      <p className="text-sm text-zinc-500">{selectedNode.type}</p>
                    </div>
                  </div>

                  {/* Metadata */}
                  {Object.keys(selectedNode.metadata).length > 0 && (
                    <div className="mb-6">
                      <h4 className="text-xs font-medium text-zinc-500 mb-2">
                        Metadata
                      </h4>
                      <div className="bg-zinc-800/50 rounded-lg p-3">
                        <pre className="text-xs text-zinc-400 overflow-x-auto">
                          {JSON.stringify(selectedNode.metadata, null, 2)}
                        </pre>
                      </div>
                    </div>
                  )}

                  {/* Connected Edges */}
                  <div>
                    <h4 className="text-xs font-medium text-zinc-500 mb-2">
                      Connections ({nodeEdges.length})
                    </h4>
                    <div className="space-y-2">
                      {nodeEdges.map((edge, i) => {
                        const otherId =
                          edge.source === selectedNode.id
                            ? edge.target
                            : edge.source;
                        const direction =
                          edge.source === selectedNode.id ? "→" : "←";
                        return (
                          <div
                            key={i}
                            className="flex items-center gap-3 p-2 bg-zinc-800/50 rounded-lg"
                          >
                            <span className="text-zinc-600">{direction}</span>
                            <span className="text-sm text-zinc-300">
                              {otherId}
                            </span>
                            <span className="text-xs text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded">
                              {edge.relation}
                            </span>
                            <span className="text-xs text-zinc-500 ml-auto">
                              w: {edge.weight}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-12 flex items-center justify-center">
                  <p className="text-zinc-600 text-sm">
                    Select a node to view details
                  </p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Worktree Tab */}
        {activeTab === "worktree" && (
          <div className="space-y-6">
            {/* Create Branch */}
            <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4">
              <h3 className="text-sm font-medium text-zinc-400 mb-3">
                Create Knowledge Branch
              </h3>
              <div className="flex gap-3">
                <input
                  type="text"
                  placeholder="Root concept (e.g., Machine Learning)"
                  value={newRoot}
                  onChange={(e) => setNewRoot(e.target.value)}
                  className="flex-1 bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-purple-500"
                />
                <input
                  type="text"
                  placeholder="Branch name (e.g., Neural Networks)"
                  value={newBranch}
                  onChange={(e) => setNewBranch(e.target.value)}
                  className="flex-1 bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-purple-500"
                />
                <button
                  onClick={handleCreateBranch}
                  className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-sm font-medium rounded-lg transition-colors"
                >
                  Create
                </button>
              </div>
            </div>

            {/* Branches */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {worktree.map((branch) => (
                <div
                  key={branch.id}
                  className={`border rounded-lg p-4 ${getMasteryBg(branch.mastery)}`}
                >
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <div className="text-sm font-medium text-zinc-200">
                        {branch.branch_name}
                      </div>
                      <div className="text-xs text-zinc-500">
                        {branch.root_concept}
                      </div>
                    </div>
                    <div className={`text-lg font-light ${getMasteryColor(branch.mastery)}`}>
                      {branch.mastery}%
                    </div>
                  </div>

                  {/* Mastery Bar */}
                  <div className="w-full h-1.5 bg-zinc-800 rounded-full mb-3 overflow-hidden">
                    <div
                      className="h-full bg-purple-500 rounded-full transition-all duration-500"
                      style={{ width: `${branch.mastery}%` }}
                    />
                  </div>

                  {/* Stats */}
                  <div className="flex items-center gap-4 text-xs text-zinc-500 mb-3">
                    <span>Rep: {branch.repetition}</span>
                    <span>EF: {branch.ease_factor}</span>
                    <span>Int: {branch.interval_days}d</span>
                  </div>

                  {/* Next Review */}
                  <div className="text-xs text-zinc-400 mb-3">
                    Next review:{" "}
                    {branch.next_review
                      ? new Date(branch.next_review).toLocaleDateString()
                      : "Now"}
                  </div>

                  {/* Review Buttons */}
                  <div className="flex gap-2">
                    {[
                      { q: 1, label: "Again", color: "bg-red-600 hover:bg-red-500" },
                      { q: 3, label: "Hard", color: "bg-orange-600 hover:bg-orange-500" },
                      { q: 4, label: "Good", color: "bg-blue-600 hover:bg-blue-500" },
                      { q: 5, label: "Easy", color: "bg-emerald-600 hover:bg-emerald-500" },
                    ].map((btn) => (
                      <button
                        key={btn.q}
                        onClick={() => handleReview(branch.id, btn.q)}
                        className={`flex-1 px-2 py-1 text-xs font-medium text-white rounded transition-colors ${btn.color}`}
                      >
                        {btn.label}
                      </button>
                    ))}
                  </div>
                </div>
              ))}

              {worktree.length === 0 && (
                <div className="col-span-full text-center py-12 text-zinc-600 text-sm">
                  No knowledge branches yet. Create one above.
                </div>
              )}
            </div>
          </div>
        )}

        {/* Search Tab */}
        {activeTab === "search" && (
          <div className="space-y-6">
            {/* Search Bar */}
            <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4">
              <div className="flex gap-3">
                <input
                  type="text"
                  placeholder="Search knowledge graph..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                  className="flex-1 bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-purple-500"
                />
                <button
                  onClick={handleSearch}
                  className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-sm font-medium rounded-lg transition-colors"
                >
                  Search
                </button>
              </div>
            </div>

            {/* Results */}
            <div className="space-y-3">
              {searchResults.map((result, i) => (
                <div
                  key={i}
                  className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-4 hover:border-zinc-700 transition-colors"
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-purple-400">
                        {nodeTypeIcon(result.type)}
                      </span>
                      <span className="text-sm font-medium text-zinc-200">
                        {result.label}
                      </span>
                      <span className="text-xs text-zinc-500 bg-zinc-800 px-2 py-0.5 rounded">
                        {result.type}
                      </span>
                    </div>
                    <span className="text-xs text-purple-400">
                      {(result.relevance * 100).toFixed(0)}% match
                    </span>
                  </div>
                  <p className="text-sm text-zinc-400 line-clamp-2">
                    {result.content}
                  </p>
                  {Object.keys(result.metadata).length > 0 && (
                    <div className="mt-2 flex gap-2 flex-wrap">
                      {Object.entries(result.metadata).slice(0, 3).map(([k, v]) => (
                        <span
                          key={k}
                          className="text-xs text-zinc-500 bg-zinc-800/50 px-2 py-0.5 rounded"
                        >
                          {k}: {String(v).slice(0, 30)}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}

              {searchResults.length === 0 && searchQuery && !loading && (
                <div className="text-center py-12 text-zinc-600 text-sm">
                  No results found for "{searchQuery}"
                </div>
              )}
            </div>
          </div>
        )}

        {/* Error Toast */}
        {error && (
          <div className="fixed bottom-6 right-6 bg-red-900/80 border border-red-700 text-red-200 px-4 py-3 rounded-lg text-sm backdrop-blur-sm">
            {error}
            <button
              onClick={() => setError(null)}
              className="ml-3 text-red-400 hover:text-red-200"
            >
              ×
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
