"""
Knowledge Graph — Entity relationship storage and querying.

Stores entities (people, companies, concepts) and their relationships
in a local JSON database. Supports:
- Add/update entities with typed attributes
- Add relationships between entities with metadata
- Query by entity type, relationship type, or full-text search
- Build knowledge from OSINT research results
- Export subgraphs for visualization
- Persist to ~/.jarvis/knowledge_graph.json
"""

import json
import os
import time
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict

log = logging.getLogger("jarvis-kg")

_KG_PATH = Path.home() / ".jarvis" / "knowledge_graph.json"


@dataclass
class Entity:
    id: str
    name: str
    entity_type: str  # person, company, concept, location, event, product
    attributes: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    source: str = ""  # where this entity was discovered
    confidence: float = 1.0  # 0-1, how sure we are about this data
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Relationship:
    id: str
    source_id: str  # entity id
    target_id: str  # entity id
    relation_type: str  # works_at, invested_in, founded, allies_with, competes_with, etc.
    attributes: Dict[str, Any] = field(default_factory=dict)
    weight: float = 1.0  # strength of relationship
    source: str = ""
    confidence: float = 1.0
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


class KnowledgeGraph:
    """Local knowledge graph with JSON persistence."""

    def __init__(self, path: str = None):
        self._path = Path(path) if path else _KG_PATH
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._entities: Dict[str, Entity] = {}
        self._relationships: Dict[str, Relationship] = {}
        self._adjacency: Dict[str, Set[str]] = defaultdict(set)  # entity_id -> set of rel_ids
        self._load()

    def _load(self):
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            for e in data.get("entities", []):
                ent = Entity(**e)
                self._entities[ent.id] = ent
            for r in data.get("relationships", []):
                rel = Relationship(**r)
                self._relationships[rel.id] = rel
                self._adjacency[rel.source_id].add(rel.id)
                self._adjacency[rel.target_id].add(rel.id)
            log.info(f"[KG] Loaded {len(self._entities)} entities, {len(self._relationships)} relationships")
        except Exception as e:
            log.warning(f"[KG] Failed to load: {e}")

    def _save(self):
        data = {
            "entities": [e.to_dict() for e in self._entities.values()],
            "relationships": [r.to_dict() for r in self._relationships.values()],
            "updated_at": time.time(),
        }
        self._path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    def _gen_id(self, name: str, entity_type: str) -> str:
        safe = re.sub(r'[^a-z0-9]', '_', name.lower().strip())[:40]
        return f"{entity_type}_{safe}"

    def add_entity(self, name: str, entity_type: str, attributes: dict = None,
                   tags: list = None, source: str = "", confidence: float = 1.0) -> Entity:
        eid = self._gen_id(name, entity_type)
        now = time.time()
        if eid in self._entities:
            ent = self._entities[eid]
            if attributes:
                ent.attributes.update(attributes)
            if tags:
                ent.tags = list(set(ent.tags + tags))
            if source:
                ent.source = source
            if confidence > ent.confidence:
                ent.confidence = confidence
            ent.updated_at = now
        else:
            ent = Entity(
                id=eid, name=name, entity_type=entity_type,
                attributes=attributes or {}, tags=tags or [],
                source=source, confidence=confidence,
                created_at=now, updated_at=now,
            )
            self._entities[eid] = ent
        self._save()
        return ent

    def add_relationship(self, source_name: str, target_name: str, relation_type: str,
                         source_type: str = "", target_type: str = "",
                         attributes: dict = None, weight: float = 1.0,
                         source: str = "", confidence: float = 1.0) -> Optional[Relationship]:
        src_id = self._find_entity_id(source_name, source_type)
        tgt_id = self._find_entity_id(target_name, target_type)
        if not src_id or not tgt_id:
            log.debug(f"[KG] Cannot add relationship: entity not found ({source_name}, {target_name})")
            return None

        rid = f"{src_id}__{relation_type}__{tgt_id}"
        if rid in self._relationships:
            rel = self._relationships[rid]
            if weight > rel.weight:
                rel.weight = weight
            if attributes:
                rel.attributes.update(attributes)
            rel.updated_at = time.time()
        else:
            rel = Relationship(
                id=rid, source_id=src_id, target_id=tgt_id,
                relation_type=relation_type, attributes=attributes or {},
                weight=weight, source=source, confidence=confidence,
            )
            self._relationships[rid] = rel
            self._adjacency[src_id].add(rid)
            self._adjacency[tgt_id].add(rid)
        self._save()
        return rel

    def _find_entity_id(self, name: str, entity_type: str = "") -> Optional[str]:
        if entity_type:
            eid = self._gen_id(name, entity_type)
            if eid in self._entities:
                return eid
        name_lower = name.lower().strip()
        for eid, ent in self._entities.items():
            if ent.name.lower().strip() == name_lower:
                return eid
        for eid, ent in self._entities.items():
            if name_lower in ent.name.lower():
                return eid
        return None

    def get_entity(self, name: str, entity_type: str = "") -> Optional[Entity]:
        eid = self._find_entity_id(name, entity_type)
        return self._entities.get(eid) if eid else None

    def get_entity_by_id(self, eid: str) -> Optional[Entity]:
        return self._entities.get(eid)

    def get_relationships(self, entity_name: str, relation_type: str = "") -> List[Dict]:
        eid = self._find_entity_id(entity_name)
        if not eid:
            return []
        results = []
        for rid in self._adjacency.get(eid, set()):
            rel = self._relationships.get(rid)
            if not rel:
                continue
            if relation_type and rel.relation_type != relation_type:
                continue
            other_id = rel.target_id if rel.source_id == eid else rel.source_id
            other = self._entities.get(other_id)
            results.append({
                "relation": rel.relation_type,
                "with": other.name if other else other_id,
                "with_type": other.entity_type if other else "",
                "attributes": rel.attributes,
                "weight": rel.weight,
                "direction": "outgoing" if rel.source_id == eid else "incoming",
            })
        return sorted(results, key=lambda x: x["weight"], reverse=True)

    def search(self, query: str, entity_type: str = "", limit: int = 20) -> List[Entity]:
        q = query.lower()
        results = []
        for ent in self._entities.values():
            if entity_type and ent.entity_type != entity_type:
                continue
            score = 0
            if q in ent.name.lower():
                score += 10
            if q in " ".join(ent.tags).lower():
                score += 5
            for v in ent.attributes.values():
                if isinstance(v, str) and q in v.lower():
                    score += 2
            if score > 0:
                results.append((score, ent))
        results.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in results[:limit]]

    def get_subgraph(self, entity_name: str, depth: int = 2) -> Dict:
        eid = self._find_entity_id(entity_name)
        if not eid:
            return {"entities": [], "relationships": []}

        visited_entities = set()
        visited_rels = set()
        queue = [(eid, 0)]

        while queue:
            current_id, current_depth = queue.pop(0)
            if current_id in visited_entities or current_depth > depth:
                continue
            visited_entities.add(current_id)
            for rid in self._adjacency.get(current_id, set()):
                if rid in visited_rels:
                    continue
                visited_rels.add(rid)
                rel = self._relationships.get(rid)
                if rel and current_depth < depth:
                    other_id = rel.target_id if rel.source_id == current_id else rel.source_id
                    queue.append((other_id, current_depth + 1))

        entities = [self._entities[eid].to_dict() for eid in visited_entities if eid in self._entities]
        relationships = [self._relationships[rid].to_dict() for rid in visited_rels if rid in self._relationships]
        return {"entities": entities, "relationships": relationships}

    def get_all_entities(self, entity_type: str = "") -> List[Entity]:
        if entity_type:
            return [e for e in self._entities.values() if e.entity_type == entity_type]
        return list(self._entities.values())

    def get_stats(self) -> Dict:
        types = defaultdict(int)
        for e in self._entities.values():
            types[e.entity_type] += 1
        rel_types = defaultdict(int)
        for r in self._relationships.values():
            rel_types[r.relation_type] += 1
        return {
            "total_entities": len(self._entities),
            "total_relationships": len(self._relationships),
            "entity_types": dict(types),
            "relationship_types": dict(rel_types),
        }

    def ingest_osint(self, osint_data: Dict) -> int:
        """Ingest OSINT research results into the knowledge graph.
        
        Expected format:
        {
            "target": {"name": "...", "type": "person", "attributes": {...}},
            "relations": [{"name": "...", "type": "company", "relation": "works_at", "attributes": {...}}],
            "facts": ["fact 1", "fact 2"],
            "tags": ["tag1", "tag2"]
        }
        Returns number of items ingested.
        """
        count = 0
        target = osint_data.get("target", {})
        if target.get("name"):
            self.add_entity(
                target["name"], target.get("type", "person"),
                attributes=target.get("attributes", {}),
                tags=osint_data.get("tags", []),
                source=osint_data.get("source", "osint"),
                confidence=osint_data.get("confidence", 0.8),
            )
            count += 1

        for rel in osint_data.get("relations", []):
            if rel.get("name"):
                self.add_entity(
                    rel["name"], rel.get("type", "concept"),
                    attributes=rel.get("attributes", {}),
                    source=osint_data.get("source", "osint"),
                )
                if target.get("name"):
                    self.add_relationship(
                        target["name"], rel["name"],
                        rel.get("relation", "related_to"),
                        source_type=target.get("type", "person"),
                        target_type=rel.get("type", "concept"),
                        attributes=rel.get("attributes", {}),
                        source=osint_data.get("source", "osint"),
                    )
                count += 1

        facts = osint_data.get("facts", [])
        if facts and target.get("name"):
            ent = self.get_entity(target["name"])
            if ent:
                existing_facts = ent.attributes.get("facts", [])
                ent.attributes["facts"] = existing_facts + [f for f in facts if f not in existing_facts]
                ent.updated_at = time.time()
                count += len(facts)

        self._save()
        log.info(f"[KG] Ingested {count} items from OSINT")
        return count


_graph: Optional[KnowledgeGraph] = None


def get_graph() -> KnowledgeGraph:
    global _graph
    if _graph is None:
        _graph = KnowledgeGraph()
    return _graph
