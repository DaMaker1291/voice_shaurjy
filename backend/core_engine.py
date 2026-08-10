"""
JARVIS Core Engine — Unified Cybernetic Architecture
SQLite Graph Memory + Virtual Workstation + Compliance Ledger + MCP Integration
"""

import os
import sys
import json
import time
import sqlite3
import subprocess
import hashlib
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional

# ==============================================================================
# 1. AIR-GAPPED CORE STORAGE & RELATIONAL HYBRID GRAPH ENGINE
# ==============================================================================
class JarvisMemoryEngine:
    """Sub-10ms SQLite graph memory engine with multi-hop recall and hash-chained audit trail."""

    def __init__(self, db_path: str = "storage/jarvis_core_matrix.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self.conn.execute("PRAGMA journal_mode = WAL;")
        self.conn.execute("PRAGMA synchronous = NORMAL;")
        self.conn.execute("PRAGMA cache_size = -64000;")  # 64MB cache
        self._lock = threading.Lock()
        self._initialize_schema()

    def _initialize_schema(self):
        with self._lock:
            with self.conn:
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS nodes (
                        id TEXT PRIMARY KEY,
                        type TEXT NOT NULL,
                        name TEXT NOT NULL,
                        properties TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS edges (
                        source_id TEXT,
                        target_id TEXT,
                        predicate TEXT NOT NULL,
                        weight REAL DEFAULT 1.0,
                        PRIMARY KEY (source_id, target_id, predicate),
                        FOREIGN KEY(source_id) REFERENCES nodes(id) ON DELETE CASCADE,
                        FOREIGN KEY(target_id) REFERENCES nodes(id) ON DELETE CASCADE
                    );
                """)
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS compliance_ledger (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        prev_hash TEXT,
                        tx_hash TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        actor_node TEXT NOT NULL,
                        action_summary TEXT NOT NULL,
                        payload_data TEXT NOT NULL
                    );
                """)
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS memory_cache (
                        query_key TEXT PRIMARY KEY,
                        result_data TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        ttl_seconds INTEGER DEFAULT 300
                    );
                """)
                self.conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(source_id);")
                self.conn.execute("CREATE INDEX IF NOT EXISTS idx_edges_tgt ON edges(target_id);")
                self.conn.execute("CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type);")
                self.conn.execute("CREATE INDEX IF NOT EXISTS idx_nodes_name ON nodes(name);")

    def upsert_node(self, node_id: str, node_type: str, name: str, properties: Optional[Dict] = None):
        with self._lock:
            with self.conn:
                self.conn.execute(
                    "INSERT OR REPLACE INTO nodes (id, type, name, properties) VALUES (?, ?, ?, ?)",
                    (node_id, node_type, name, json.dumps(properties or {}))
                )

    def upsert_edge(self, source_id: str, target_id: str, predicate: str, weight: float = 1.0):
        with self._lock:
            with self.conn:
                self.conn.execute(
                    "INSERT OR REPLACE INTO edges (source_id, target_id, predicate, weight) VALUES (?, ?, ?, ?)",
                    (source_id, target_id, predicate, weight)
                )

    def multi_hop_recall(self, start_name: str, max_hops: int = 2) -> List[Dict[str, Any]]:
        cache_key = f"recall:{start_name}:{max_hops}"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        query = """
        WITH RECURSIVE GraphTraversal(id, type, name, depth, path) AS (
            SELECT n.id, n.type, n.name, 0, n.name
            FROM nodes n WHERE n.name = ?
            UNION ALL
            SELECT target.id, target.type, target.name, gt.depth + 1, gt.path || ' -> ' || target.name
            FROM edges e
            JOIN GraphTraversal gt ON e.source_id = gt.id
            JOIN nodes target ON e.target_id = target.id
            WHERE gt.depth < ?
        )
        SELECT DISTINCT name, type, path FROM GraphTraversal WHERE depth > 0;
        """
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute(query, (start_name, max_hops))
            results = [{"entity": r[0], "type": r[1], "path": r[2]} for r in cursor.fetchall()]

        self._set_cached(cache_key, results, ttl=60)
        return results

    def query_nodes(self, node_type: Optional[str] = None, limit: int = 50) -> List[Dict]:
        with self._lock:
            cursor = self.conn.cursor()
            if node_type:
                cursor.execute("SELECT id, type, name, properties FROM nodes WHERE type = ? LIMIT ?", (node_type, limit))
            else:
                cursor.execute("SELECT id, type, name, properties FROM nodes LIMIT ?", (limit,))
            return [{"id": r[0], "type": r[1], "name": r[2], "properties": json.loads(r[3] or "{}")} for r in cursor.fetchall()]

    def get_context_for_entity(self, entity_name: str) -> Dict[str, Any]:
        nodes = self.query_nodes()
        edges_query = "SELECT source_id, target_id, predicate, weight FROM edges"
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute(edges_query)
            edges = [{"source": r[0], "target": r[1], "predicate": r[2], "weight": r[3]} for r in cursor.fetchall()]

        connected = self.multi_hop_recall(entity_name, max_hops=2)
        return {
            "entity": entity_name,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "connections": connected,
            "subgraph_size": len(connected),
        }

    def _get_cached(self, key: str) -> Optional[Any]:
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT result_data, created_at, ttl_seconds FROM memory_cache WHERE query_key = ?",
                (key,)
            )
            row = cursor.fetchone()
            if row:
                created = datetime.fromisoformat(row[1])
                if (datetime.utcnow() - created).total_seconds() < row[2]:
                    return json.loads(row[0])
                else:
                    self.conn.execute("DELETE FROM memory_cache WHERE query_key = ?", (key,))
                    self.conn.commit()
        return None

    def _set_cached(self, key: str, data: Any, ttl: int = 300):
        with self._lock:
            with self.conn:
                self.conn.execute(
                    "INSERT OR REPLACE INTO memory_cache (query_key, result_data, ttl_seconds) VALUES (?, ?, ?)",
                    (key, json.dumps(data), ttl)
                )

    def append_audit_trail(self, actor: str, action: str, payload: dict):
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT tx_hash FROM compliance_ledger ORDER BY id DESC LIMIT 1;")
            last_row = cursor.fetchone()
            prev_hash = last_row[0] if last_row else "00000000000000000000000000000000"

            timestamp = datetime.utcnow().isoformat()
            payload_str = json.dumps(payload, default=str)
            raw_block = f"{prev_hash}|{timestamp}|{actor}|{action}|{payload_str}"
            tx_hash = hashlib.sha256(raw_block.encode('utf-8')).hexdigest()

            with self.conn:
                self.conn.execute("""
                    INSERT INTO compliance_ledger (prev_hash, tx_hash, timestamp, actor_node, action_summary, payload_data)
                    VALUES (?, ?, ?, ?, ?, ?);
                """, (prev_hash, tx_hash, timestamp, actor, action, payload_str))

    def get_audit_trail(self, limit: int = 50) -> List[Dict]:
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT id, prev_hash, tx_hash, timestamp, actor_node, action_summary FROM compliance_ledger ORDER BY id DESC LIMIT ?",
                (limit,)
            )
            return [
                {"id": r[0], "prev_hash": r[1], "tx_hash": r[2], "timestamp": r[3], "actor": r[4], "action": r[5]}
                for r in cursor.fetchall()
            ]

    def verify_chain_integrity(self) -> Dict[str, Any]:
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM compliance_ledger")
            total = cursor.fetchone()[0]
            cursor.execute("SELECT id, prev_hash, tx_hash, timestamp, actor_node, action_summary, payload_data FROM compliance_ledger ORDER BY id ASC")
            rows = cursor.fetchall()

        broken = 0
        prev_hash = "00000000000000000000000000000000"
        for row in rows:
            if row[1] != prev_hash:
                broken += 1
            raw_block = f"{row[1]}|{row[3]}|{row[4]}|{row[5]}|{row[6]}"
            computed_hash = hashlib.sha256(raw_block.encode('utf-8')).hexdigest()
            if computed_hash != row[2]:
                broken += 1
            prev_hash = row[2]

        return {"total_blocks": total, "broken_links": broken, "valid": broken == 0}


# ==============================================================================
# 2. ISOLATED VIRTUAL WORKSTATION MANAGER
# ==============================================================================
class HeadlessDisplayEnvironment:
    """Virtual framebuffer workstation for isolated background processing."""

    def __init__(self, display_id: int = 1):
        self.display = f":{display_id}"
        self.process_pool: Dict[str, subprocess.Popen] = {}
        self._xvfb_process = None

    def start_display(self):
        if sys.platform.startswith("linux"):
            try:
                self._xvfb_process = subprocess.Popen(
                    ["Xvfb", self.display, "-screen", "0", "1920x1080x24", "-ac"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                os.environ["DISPLAY"] = self.display
                print(f"[VDI] Virtual display started on {self.display}")
            except FileNotFoundError:
                print("[VDI] Xvfb not available — virtual display disabled")
        elif sys.platform == "darwin":
            print("[VDI] macOS detected — using native window server")

    def execute_background_process(self, app_name: str, command: List[str]) -> Optional[int]:
        env = os.environ.copy()
        if sys.platform.startswith("linux") and self._xvfb_process:
            env["DISPLAY"] = self.display
        try:
            proc = subprocess.Popen(
                command, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                cwd=os.path.expanduser("~")
            )
            self.process_pool[app_name] = proc
            print(f"[VDI] Spawned process '{app_name}' (PID: {proc.pid})")
            return proc.pid
        except Exception as e:
            print(f"[VDI] Failed to spawn '{app_name}': {e}")
            return None

    def get_process_status(self) -> Dict[str, Dict]:
        status = {}
        for name, proc in list(self.process_pool.items()):
            poll = proc.poll()
            status[name] = {
                "pid": proc.pid,
                "running": poll is None,
                "exit_code": poll,
            }
        return status

    def kill_process(self, app_name: str) -> bool:
        proc = self.process_pool.get(app_name)
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            return True
        return False

    def execute_in_xvfb(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        """Execute a shell command inside the Xvfb virtual framebuffer (Linux)
        or via the best available headless mechanism (macOS/Windows).
        
        Returns dict with keys: stdout, stderr, exit_code, timed_out, blocked, block_reason
        """
        from execution_vault import ExecutionVault, VaultPolicy
        
        if not self._xvfb_process and sys.platform.startswith("linux"):
            self.start_display()
        
        vault = ExecutionVault()
        policy = VaultPolicy(timeout=timeout)
        
        if sys.platform.startswith("linux") and self._xvfb_process:
            # Run command with DISPLAY set to the virtual framebuffer
            env_prefix = f"export DISPLAY={self.display}; "
            full_cmd = f"{env_prefix}{command}"
            vr = vault.execute(full_cmd, policy=policy)
        else:
            # macOS / Windows / no Xvfb: run through vault directly
            # macOS uses native Window Server; Windows uses TrueDesktop isolation
            vr = vault.execute(command, policy=policy)
        
        return {
            "stdout": vr.stdout,
            "stderr": vr.stderr,
            "exit_code": vr.exit_code,
            "timed_out": vr.timed_out,
            "blocked": vr.blocked,
            "block_reason": vr.block_reason,
            "security_violations": vr.security_violations,
        }

    def stop_all(self):
        for name in list(self.process_pool.keys()):
            self.kill_process(name)
        if self._xvfb_process:
            self._xvfb_process.terminate()


# ==============================================================================
# 3. DETERMINISTIC POLICY GATEWAY & SECURITY INTERCEPTOR
# ==============================================================================
class SecurityPolicyGate:
    """Security policy engine — blocks destructive commands."""

    def __init__(self):
        self.restricted_terms = self._load_restricted_terms()
        self.intercept_log: List[Dict] = []

    def _load_restricted_terms(self) -> List[str]:
        """Load restricted security terms from security_terms.json."""
        terms_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "security_terms.json")
        try:
            with open(terms_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("restricted_terms", [])
        except FileNotFoundError:
            print("[SECURITY] security_terms.json not found — no restricted terms loaded")
            return []
        except json.JSONDecodeError as e:
            print(f"[SECURITY] Failed to parse security_terms.json: {e}")
            return []

    def evaluate_payload(self, command_payload: str) -> bool:
        lower = command_payload.lower()
        for term in self.restricted_terms:
            if term.lower() in lower:
                self.intercept_log.append({
                    "term": term,
                    "payload": command_payload[:200],
                    "timestamp": datetime.utcnow().isoformat(),
                })
                return False
        return True

    def get_intercept_log(self) -> List[Dict]:
        return self.intercept_log[-50:]


# ==============================================================================
# 4. UNIFIED CORE ENGINE FACADE
# ==============================================================================
class JarvisCoreEngine:
    """Unified facade for all JARVIS subsystems."""

    def __init__(self, db_path: str = "storage/jarvis_core_matrix.db"):
        self.memory = JarvisMemoryEngine(db_path)
        self.workstation = HeadlessDisplayEnvironment()
        self.security = SecurityPolicyGate()
        self._initialized = False

    def initialize(self):
        if self._initialized:
            return
        self.workstation.start_display()
        self._seed_initial_graph()
        self._initialized = True
        print("[CORE] JarvisCoreEngine initialized successfully")

    def _seed_initial_graph(self):
        entities, edges = self._load_seed_data()
        for nid, ntype, name, props in entities:
            self.memory.upsert_node(nid, ntype, name, props)
        for src, tgt, pred in edges:
            self.memory.upsert_edge(src, tgt, pred)

    def _load_seed_data(self) -> tuple[list, list]:
        """Load seed entities and edges from seed_entities.json."""
        seed_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seed_entities.json")
        try:
            with open(seed_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("entities", []), data.get("edges", [])
        except FileNotFoundError:
            print("[CORE] seed_entities.json not found — skipping graph seeding")
            return [], []
        except json.JSONDecodeError as e:
            print(f"[CORE] Failed to parse seed_entities.json: {e}")
            return [], []

    def process_intent(self, intent: str, user_id: str = "local") -> Dict[str, Any]:
        start = time.perf_counter()

        if not self.security.evaluate_payload(intent):
            self.memory.append_audit_trail("SECURITY_GATE", "VIOLATION_BLOCKED", {"intent": intent})
            return {"status": "BLOCKED", "reason": "Security policy violation"}

        context = self.memory.get_context_for_entity(user_id)
        latency_ms = (time.perf_counter() - start) * 1000

        self.memory.append_audit_trail("CORE_ENGINE", "INTENT_PROCESSED", {
            "intent": intent[:200],
            "latency_ms": round(latency_ms, 2),
            "context_nodes": context.get("subgraph_size", 0),
        })

        return {
            "status": "PROCESSED",
            "latency_ms": round(latency_ms, 2),
            "context": context,
            "security": "CLEAR",
        }

    def get_system_status(self) -> Dict[str, Any]:
        chain = self.memory.verify_chain_integrity()
        processes = self.workstation.get_process_status()
        return {
            "memory_nodes": len(self.memory.query_nodes()),
            "audit_blocks": chain["total_blocks"],
            "chain_valid": chain["valid"],
            "active_processes": len([p for p in processes.values() if p["running"]]),
            "processes": processes,
            "security_intercepts": len(self.security.intercept_log),
        }


# Singleton
_core_engine: Optional[JarvisCoreEngine] = None
_core_lock = threading.Lock()

def get_core_engine() -> JarvisCoreEngine:
    global _core_engine
    if _core_engine is None:
        with _core_lock:
            if _core_engine is None:
                _core_engine = JarvisCoreEngine()
                _core_engine.initialize()
    return _core_engine
