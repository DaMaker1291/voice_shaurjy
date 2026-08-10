"""JARVIS Work Graph — Digital memory and operational context.

Maintains a graph of:
- Projects (with tasks, files, applications, people)
- Skills (learned procedures with success/failure history)
- Workflows (reusable patterns)
- Preferences (user-specific patterns)
- Automations (scheduled tasks)

This is NOT chat history — it's structured operational memory.
"""

import os
import json
import time
import logging
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum

log = logging.getLogger("memory")

MEMORY_FILE = Path.home() / ".jarvis" / "memory.json"


class NodeType(Enum):
    PROJECT = "project"
    TASK = "task"
    FILE = "file"
    APPLICATION = "application"
    PERSON = "person"
    SKILL = "skill"
    WORKFLOW = "workflow"
    PREFERENCE = "preference"
    AUTOMATION = "automation"


class EdgeType(Enum):
    HAS_TASK = "has_task"
    HAS_FILE = "has_file"
    USES_APP = "uses_app"
    INVOLVES = "involves"
    DEPENDS_ON = "depends_on"
    LEARNED_FROM = "learned_from"
    PREFERS = "prefers"


@dataclass
class GraphNode:
    id: str
    type: str
    name: str
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: float = 0
    updated_at: float = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "type": self.type, "name": self.name,
            "properties": self.properties, "created_at": self.created_at,
            "updated_at": self.updated_at, "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GraphNode":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class GraphEdge:
    id: str
    source: str
    target: str
    type: str
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at: float = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id, "source": self.source, "target": self.target,
            "type": self.type, "properties": self.properties,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GraphEdge":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ProceduralMemory:
    """A reusable procedure learned from successful execution."""
    id: str
    name: str
    description: str
    category: str
    steps: List[Dict[str, Any]] = field(default_factory=list)
    requirements: List[str] = field(default_factory=list)
    successful_runs: int = 0
    failed_runs: int = 0
    success_rate: float = 0.0
    last_used: float = 0
    created_at: float = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "description": self.description,
            "category": self.category, "steps": self.steps,
            "requirements": self.requirements, "successful_runs": self.successful_runs,
            "failed_runs": self.failed_runs, "success_rate": self.success_rate,
            "last_used": self.last_used, "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ProceduralMemory":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class WorkGraph:
    """Maintains the operational memory graph."""

    def __init__(self):
        self._nodes: Dict[str, GraphNode] = {}
        self._edges: Dict[str, GraphEdge] = {}
        self._procedures: Dict[str, ProceduralMemory] = {}
        self._preferences: Dict[str, Any] = {}
        self._load()

    def _load(self):
        """Load memory from disk."""
        if MEMORY_FILE.exists():
            try:
                data = json.loads(MEMORY_FILE.read_text())
                for item in data.get("nodes", []):
                    node = GraphNode.from_dict(item)
                    self._nodes[node.id] = node
                for item in data.get("edges", []):
                    edge = GraphEdge.from_dict(item)
                    self._edges[edge.id] = edge
                for item in data.get("procedures", []):
                    proc = ProceduralMemory.from_dict(item)
                    self._procedures[proc.id] = proc
                self._preferences = data.get("preferences", {})
                log.info(f"[MEMORY] Loaded {len(self._nodes)} nodes, {len(self._edges)} edges, {len(self._procedures)} procedures")
            except Exception as e:
                log.error(f"[MEMORY] Load failed: {e}")

    def _save(self):
        """Save memory to disk."""
        MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "nodes": [n.to_dict() for n in self._nodes.values()],
            "edges": [e.to_dict() for e in self._edges.values()],
            "procedures": [p.to_dict() for p in self._procedures.values()],
            "preferences": self._preferences,
        }
        MEMORY_FILE.write_text(json.dumps(data, indent=2))

    def add_node(self, node_type: str, name: str, properties: Dict[str, Any] = None) -> GraphNode:
        """Add a node to the graph."""
        import uuid
        node = GraphNode(
            id=str(uuid.uuid4())[:8],
            type=node_type,
            name=name,
            properties=properties or {},
            created_at=time.time(),
            updated_at=time.time(),
        )
        self._nodes[node.id] = node
        self._save()
        return node

    def add_edge(self, source_id: str, target_id: str, edge_type: str, properties: Dict[str, Any] = None) -> GraphEdge:
        """Add an edge between two nodes."""
        import uuid
        edge = GraphEdge(
            id=str(uuid.uuid4())[:8],
            source=source_id,
            target=target_id,
            type=edge_type,
            properties=properties or {},
            created_at=time.time(),
        )
        self._edges[edge.id] = edge
        self._save()
        return edge

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        """Get a node by ID."""
        return self._nodes.get(node_id)

    def get_nodes_by_type(self, node_type: str) -> List[GraphNode]:
        """Get all nodes of a specific type."""
        return [n for n in self._nodes.values() if n.type == node_type]

    def get_edges_from(self, node_id: str) -> List[GraphEdge]:
        """Get all edges originating from a node."""
        return [e for e in self._edges.values() if e.source == node_id]

    def get_edges_to(self, node_id: str) -> List[GraphEdge]:
        """Get all edges pointing to a node."""
        return [e for e in self._edges.values() if e.target == node_id]

    def search(self, query: str, node_type: str = None) -> List[GraphNode]:
        """Search nodes by name or properties."""
        results = []
        query_lower = query.lower()
        for node in self._nodes.values():
            if node_type and node.type != node_type:
                continue
            if query_lower in node.name.lower():
                results.append(node)
                continue
            for val in node.properties.values():
                if isinstance(val, str) and query_lower in val.lower():
                    results.append(node)
                    break
        return results

    def learn_procedure(self, name: str, description: str, category: str,
                       steps: List[Dict], requirements: List[str] = None) -> ProceduralMemory:
        """Learn a reusable procedure from successful execution."""
        proc = ProceduralMemory(
            id=str(hash(f"{name}_{category}"))[:8],
            name=name,
            description=description,
            category=category,
            steps=steps,
            requirements=requirements or [],
            successful_runs=1,
            success_rate=100.0,
            created_at=time.time(),
            last_used=time.time(),
        )
        self._procedures[proc.id] = proc
        self._save()
        return proc

    def use_procedure(self, procedure_id: str, success: bool = True) -> Optional[ProceduralMemory]:
        """Record usage of a procedure."""
        proc = self._procedures.get(procedure_id)
        if not proc:
            return None

        if success:
            proc.successful_runs += 1
        else:
            proc.failed_runs += 1

        total = proc.successful_runs + proc.failed_runs
        proc.success_rate = (proc.successful_runs / total) * 100 if total > 0 else 0
        proc.last_used = time.time()
        self._save()
        return proc

    def find_procedure(self, name: str = None, category: str = None, min_success_rate: float = 0) -> List[ProceduralMemory]:
        """Find procedures matching criteria."""
        results = []
        for proc in self._procedures.values():
            if name and name.lower() not in proc.name.lower():
                continue
            if category and proc.category != category:
                continue
            if proc.success_rate < min_success_rate:
                continue
            results.append(proc)
        return sorted(results, key=lambda p: p.success_rate, reverse=True)

    def set_preference(self, key: str, value: Any):
        """Set a user preference."""
        self._preferences[key] = value
        self._save()

    def get_preference(self, key: str, default: Any = None) -> Any:
        """Get a user preference."""
        return self._preferences.get(key, default)

    def get_all_preferences(self) -> Dict[str, Any]:
        """Get all preferences."""
        return dict(self._preferences)

    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        return {
            "total_nodes": len(self._nodes),
            "total_edges": len(self._edges),
            "total_procedures": len(self._procedures),
            "procedures_by_category": self._count_by_field(self._procedures.values(), "category"),
            "nodes_by_type": self._count_by_field(self._nodes.values(), "type"),
            "total_preferences": len(self._preferences),
        }

    def _count_by_field(self, items, field: str) -> Dict[str, int]:
        """Count items by a field value."""
        counts = {}
        for item in items:
            val = getattr(item, field, "unknown")
            counts[val] = counts.get(val, 0) + 1
        return counts

    def export_graph(self) -> Dict[str, Any]:
        """Export the full graph for visualization."""
        return {
            "nodes": [{"id": n.id, "type": n.type, "name": n.name, "properties": n.properties} for n in self._nodes.values()],
            "edges": [{"source": e.source, "target": e.target, "type": e.type} for e in self._edges.values()],
        }

    def get_related(self, node_id: str, max_depth: int = 2) -> Dict[str, Any]:
        """Get all nodes related to a given node (within depth limit)."""
        visited = set()
        related = {"nodes": [], "edges": []}

        def _traverse(current_id: str, depth: int):
            if depth > max_depth or current_id in visited:
                return
            visited.add(current_id)

            node = self._nodes.get(current_id)
            if node:
                related["nodes"].append(node.to_dict())

            for edge in self._edges.values():
                if edge.source == current_id and edge.target not in visited:
                    related["edges"].append(edge.to_dict())
                    _traverse(edge.target, depth + 1)
                elif edge.target == current_id and edge.source not in visited:
                    related["edges"].append(edge.to_dict())
                    _traverse(edge.source, depth + 1)

        _traverse(node_id, 0)
        return related


# Global instance
_graph = None


def get_work_graph() -> WorkGraph:
    global _graph
    if _graph is None:
        _graph = WorkGraph()
    return _graph
