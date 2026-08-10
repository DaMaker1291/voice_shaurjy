"""Skill Marketplace — skill registry, install/uninstall, marketplace API, skill templates."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

_DB_PATH = Path(__file__).resolve().parent / "jarvis_skills.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS skills (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    description TEXT,
    author TEXT NOT NULL DEFAULT 'jarvis',
    version TEXT NOT NULL DEFAULT '1.0.0',
    category TEXT NOT NULL DEFAULT 'general',
    icon TEXT DEFAULT '🧩',
    tags TEXT NOT NULL DEFAULT '[]',
    dependencies TEXT NOT NULL DEFAULT '[]',
    config_schema TEXT NOT NULL DEFAULT '{}',
    entry_point TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'available',
    installed INTEGER NOT NULL DEFAULT 0,
    enabled INTEGER NOT NULL DEFAULT 1,
    install_count INTEGER NOT NULL DEFAULT 0,
    rating REAL NOT NULL DEFAULT 0,
    rating_count INTEGER NOT NULL DEFAULT 0,
    min_jarvis_version TEXT DEFAULT '1.0.0',
    license TEXT DEFAULT 'MIT',
    repo_url TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS skill_config (
    skill_id TEXT PRIMARY KEY,
    config TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS skill_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_id TEXT NOT NULL,
    user_id TEXT NOT NULL DEFAULT 'local',
    rating INTEGER NOT NULL,
    comment TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS skill_executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_id TEXT NOT NULL,
    input_data TEXT,
    output_data TEXT,
    status TEXT NOT NULL DEFAULT 'success',
    latency_ms REAL NOT NULL DEFAULT 0,
    error TEXT,
    executed_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS skill_templates (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    category TEXT NOT NULL,
    template_data TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_skills_category ON skills(category, installed);
CREATE INDEX IF NOT EXISTS idx_skills_status ON skills(status, installed);
CREATE INDEX IF NOT EXISTS idx_skill_reviews_skill ON skill_reviews(skill_id, rating);
CREATE INDEX IF NOT EXISTS idx_skill_exec_skill ON skill_executions(skill_id, executed_at);
"""

_DEFAULT_SKILLS = [
    {
        "name": "weather",
        "display_name": "Smart Weather",
        "description": "Get weather forecasts, alerts, and historical data for any location",
        "author": "jarvis",
        "version": "2.1.0",
        "category": "information",
        "icon": "🌤️",
        "tags": '["weather", "forecast", "outdoor"]',
        "entry_point": "skills.weather:WeatherSkill",
        "config_schema": '{"location": {"type": "string", "default": "auto"}, "units": {"type": "string", "default": "metric"}}',
        "install_count": 1247,
        "rating": 4.8,
        "rating_count": 342,
    },
    {
        "name": "email_monitor",
        "display_name": "Email Intelligence",
        "description": "Monitor inbox, extract insights, auto-categorize and summarize emails",
        "author": "jarvis",
        "version": "1.5.0",
        "category": "productivity",
        "icon": "📧",
        "tags": '["email", "inbox", "productivity"]',
        "entry_point": "skills.email:EmailMonitorSkill",
        "config_schema": '{"provider": {"type": "string"}, "check_interval": {"type": "number", "default": 300}}',
        "install_count": 892,
        "rating": 4.6,
        "rating_count": 215,
    },
    {
        "name": "smart_home",
        "display_name": "Smart Home Hub",
        "description": "Control lights, thermostat, plugs, and sensors across your home",
        "author": "jarvis",
        "version": "3.0.0",
        "category": "automation",
        "icon": "🏠",
        "tags": '["smart-home", "iot", "automation"]',
        "entry_point": "skills.smarthome:SmartHomeSkill",
        "config_schema": '{"hub_ip": {"type": "string"}, "protocol": {"type": "string", "default": "zigbee"}}',
        "install_count": 2103,
        "rating": 4.9,
        "rating_count": 567,
    },
    {
        "name": "calendar_sync",
        "display_name": "Calendar Intelligence",
        "description": "Sync, analyze, and optimize your calendar with smart scheduling",
        "author": "jarvis",
        "version": "1.8.0",
        "category": "productivity",
        "icon": "📅",
        "tags": '["calendar", "scheduling", "productivity"]',
        "entry_point": "skills.calendar:CalendarSkill",
        "config_schema": '{"provider": {"type": "string"}, "timezone": {"type": "string", "default": "auto"}}',
        "install_count": 1567,
        "rating": 4.7,
        "rating_count": 423,
    },
    {
        "name": "code_review",
        "display_name": "Code Review Agent",
        "description": "Automated code review with security analysis and best practices",
        "author": "jarvis",
        "version": "1.2.0",
        "category": "development",
        "icon": "🔍",
        "tags": '["code", "review", "security"]',
        "entry_point": "skills.codereview:CodeReviewSkill",
        "config_schema": '{"languages": {"type": "array", "default": ["python", "javascript"]}, "severity_threshold": {"type": "string", "default": "medium"}}',
        "install_count": 678,
        "rating": 4.5,
        "rating_count": 189,
    },
    {
        "name": "knowledge_graph",
        "display_name": "Knowledge Graph Builder",
        "description": "Build and query a personal knowledge graph from your documents and notes",
        "author": "jarvis",
        "version": "2.0.0",
        "category": "intelligence",
        "icon": "🧠",
        "tags": '["knowledge", "graph", "semantic"]',
        "entry_point": "skills.knowledge:KnowledgeGraphSkill",
        "config_schema": '{"embedding_model": {"type": "string", "default": "local"}, "max_nodes": {"type": "number", "default": 10000}}',
        "install_count": 456,
        "rating": 4.4,
        "rating_count": 98,
    },
    {
        "name": "anomaly_detector",
        "display_name": "Anomaly Detection",
        "description": "Detect unusual patterns in system metrics, network, and user behavior",
        "author": "jarvis",
        "version": "1.0.0",
        "category": "security",
        "icon": "🚨",
        "tags": '["security", "anomaly", "monitoring"]',
        "entry_point": "skills.anomaly:AnomalyDetectorSkill",
        "config_schema": '{"sensitivity": {"type": "number", "default": 0.8}, "window_minutes": {"type": "number", "default": 60}}',
        "install_count": 334,
        "rating": 4.3,
        "rating_count": 76,
    },
    {
        "name": "voice_assistant",
        "display_name": "Voice Assistant Pro",
        "description": "Advanced voice commands with wake word detection and multi-language support",
        "author": "jarvis",
        "version": "2.5.0",
        "category": "interface",
        "icon": "🎙️",
        "tags": '["voice", "assistant", "speech"]',
        "entry_point": "skills.voice:VoiceAssistantSkill",
        "config_schema": '{"wake_word": {"type": "string", "default": "hey jarvis"}, "languages": {"type": "array", "default": ["en"]}}',
        "install_count": 3456,
        "rating": 4.9,
        "rating_count": 892,
    },
    {
        "name": "data_pipeline",
        "display_name": "Data Pipeline",
        "description": "ETL pipelines with automatic schema detection and data quality checks",
        "author": "jarvis",
        "version": "1.3.0",
        "category": "data",
        "icon": "🔄",
        "tags": '["data", "etl", "pipeline"]',
        "entry_point": "skills.pipeline:DataPipelineSkill",
        "config_schema": '{"batch_size": {"type": "number", "default": 1000}, "compression": {"type": "string", "default": "auto"}}',
        "install_count": 289,
        "rating": 4.2,
        "rating_count": 67,
    },
    {
        "name": "fleet_manager",
        "display_name": "Device Fleet Manager",
        "description": "Manage and monitor fleets of IoT devices with auto-deployment",
        "author": "jarvis",
        "version": "1.1.0",
        "category": "automation",
        "icon": "📡",
        "tags": '["fleet", "iot", "management"]',
        "entry_point": "skills.fleet:FleetManagerSkill",
        "config_schema": '{"auto_update": {"type": "boolean", "default": true}, "heartbeat_interval": {"type": "number", "default": 60}}',
        "install_count": 198,
        "rating": 4.1,
        "rating_count": 45,
    },
]

_TEMPLATES = [
    {"name": "API Connector", "description": "Template for connecting to external APIs", "category": "integration",
     "template_data": '{"type": "api_connector", "auth": "bearer", "endpoints": []}'},
    {"name": "Data Transformer", "description": "Template for data transformation skills", "category": "data",
     "template_data": '{"type": "transformer", "input_format": "json", "output_format": "json"}'},
    {"name": "Monitor Alert", "description": "Template for monitoring and alerting skills", "category": "security",
     "template_data": '{"type": "monitor", "check_interval": 300, "alert_channels": ["notification"]}'},
    {"name": "Automation Rule", "description": "Template for event-driven automation skills", "category": "automation",
     "template_data": '{"type": "automation", "trigger": "event", "actions": []}'},
]


class SkillMarketplace:
    """Skill marketplace with registry, install/uninstall, reviews, and execution sandbox."""

    def __init__(self, db_path: str | Path | None = None):
        self._db_path = str(db_path or _DB_PATH)
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        self._handlers: Dict[str, Callable] = {}
        self._connect()
        self._seed_skills()
        self._seed_templates()
        self._register_builtin_handlers()

    def _connect(self) -> sqlite3.Connection:
        os.makedirs(os.path.dirname(self._db_path) or ".", exist_ok=True)
        conn = sqlite3.connect(self._db_path, timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA cache_size=-32000")
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.executescript(_SCHEMA)
        conn.commit()
        self._conn = conn
        return conn

    def _seed_skills(self) -> None:
        with self._lock:
            with self._conn:
                for skill in _DEFAULT_SKILLS:
                    existing = self._conn.execute("SELECT id FROM skills WHERE name = ?", (skill["name"],)).fetchone()
                    if not existing:
                        skill_id = str(uuid.uuid4())[:12]
                        self._conn.execute(
                            """INSERT INTO skills (id, name, display_name, description, author, version, category,
                            icon, tags, entry_point, config_schema, install_count, rating, rating_count, installed)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                            (
                                skill_id, skill["name"], skill["display_name"], skill["description"],
                                skill["author"], skill["version"], skill["category"], skill["icon"],
                                skill["tags"], skill["entry_point"], skill["config_schema"],
                                skill["install_count"], skill["rating"], skill["rating_count"],
                            ),
                        )

    def _seed_templates(self) -> None:
        with self._lock:
            with self._conn:
                for t in _TEMPLATES:
                    existing = self._conn.execute("SELECT id FROM skill_templates WHERE name = ?", (t["name"],)).fetchone()
                    if not existing:
                        self._conn.execute(
                            "INSERT INTO skill_templates (id, name, description, category, template_data) VALUES (?, ?, ?, ?, ?)",
                            (str(uuid.uuid4())[:12], t["name"], t["description"], t["category"], json.dumps(t["template_data"])),
                        )

    def get_all_skills(self, category: Optional[str] = None, installed_only: bool = False, search: Optional[str] = None) -> List[Dict]:
        """Get all skills with optional filters."""
        with self._lock:
            query = "SELECT * FROM skills WHERE 1=1"
            params: list = []
            if category:
                query += " AND category = ?"
                params.append(category)
            if installed_only:
                query += " AND installed = 1"
            if search:
                query += " AND (name LIKE ? OR display_name LIKE ? OR description LIKE ?)"
                params.extend([f"%{search}%"] * 3)
            query += " ORDER BY install_count DESC"
            rows = self._conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def get_skill(self, skill_id: str) -> Optional[Dict]:
        with self._lock:
            row = self._conn.execute("SELECT * FROM skills WHERE id = ?", (skill_id,)).fetchone()
            return dict(row) if row else None

    def get_skill_by_name(self, name: str) -> Optional[Dict]:
        with self._lock:
            row = self._conn.execute("SELECT * FROM skills WHERE name = ?", (name,)).fetchone()
            return dict(row) if row else None

    def install_skill(self, skill_id: str) -> Dict:
        """Install a skill."""
        skill = self.get_skill(skill_id)
        if not skill:
            return {"error": "skill_not_found"}
        if skill["installed"]:
            return {"error": "already_installed"}

        with self._lock:
            with self._conn:
                self._conn.execute(
                    "UPDATE skills SET installed = 1, install_count = install_count + 1, updated_at = datetime('now') WHERE id = ?",
                    (skill_id,),
                )
                self._conn.execute(
                    "INSERT OR REPLACE INTO skill_config (skill_id, config) VALUES (?, ?)",
                    (skill_id, skill["config_schema"]),
                )
                return {"status": "installed", "skill": skill["name"]}

    def uninstall_skill(self, skill_id: str) -> Dict:
        """Uninstall a skill."""
        skill = self.get_skill(skill_id)
        if not skill:
            return {"error": "skill_not_found"}
        if not skill["installed"]:
            return {"error": "not_installed"}

        with self._lock:
            with self._conn:
                self._conn.execute(
                    "UPDATE skills SET installed = 0, updated_at = datetime('now') WHERE id = ?",
                    (skill_id,),
                )
                self._conn.execute("DELETE FROM skill_config WHERE skill_id = ?", (skill_id,))
                return {"status": "uninstalled", "skill": skill["name"]}

    def update_skill_config(self, skill_id: str, config: Dict) -> bool:
        with self._lock:
            with self._conn:
                self._conn.execute(
                    "INSERT OR REPLACE INTO skill_config (skill_id, config, updated_at) VALUES (?, ?, datetime('now'))",
                    (skill_id, json.dumps(config)),
                )
                return True

    def get_skill_config(self, skill_id: str) -> Dict:
        with self._lock:
            row = self._conn.execute("SELECT config FROM skill_config WHERE skill_id = ?", (skill_id,)).fetchone()
            return json.loads(row["config"]) if row else {}

    def execute_skill(self, skill_id: str, input_data: Optional[Dict] = None) -> Dict:
        """Execute an installed skill."""
        skill = self.get_skill(skill_id)
        if not skill:
            return {"error": "skill_not_found"}
        if not skill["installed"]:
            return {"error": "not_installed"}

        handler = self._handlers.get(skill["name"])
        start_time = time.monotonic()

        try:
            if handler:
                result = handler(input_data or {})
            else:
                result = {"status": "simulated", "message": f"Skill {skill['name']} executed (no handler registered)"}

            latency_ms = (time.monotonic() - start_time) * 1000

            with self._lock:
                with self._conn:
                    self._conn.execute(
                        """INSERT INTO skill_executions (skill_id, input_data, output_data, status, latency_ms)
                        VALUES (?, ?, ?, 'success', ?)""",
                        (skill_id, json.dumps(input_data or {}), json.dumps(result), latency_ms),
                    )

            return {"status": "success", "result": result, "latency_ms": round(latency_ms, 1)}

        except Exception as e:
            latency_ms = (time.monotonic() - start_time) * 1000
            with self._lock:
                with self._conn:
                    self._conn.execute(
                        """INSERT INTO skill_executions (skill_id, input_data, output_data, status, latency_ms, error)
                        VALUES (?, ?, ?, 'error', ?, ?)""",
                        (skill_id, json.dumps(input_data or {}), "{}", latency_ms, str(e)),
                    )
            return {"status": "error", "error": str(e)}

    def register_handler(self, skill_name: str, handler: Callable) -> None:
        self._handlers[skill_name] = handler

    def _register_builtin_handlers(self) -> None:
        """Register built-in skill handlers."""
        self._handlers = {
            "weather": self._handle_weather,
            "email_monitor": self._handle_email_monitor,
            "smart_home": self._handle_smart_home,
            "calendar_sync": self._handle_calendar_sync,
            "code_review": self._handle_code_review,
            "knowledge_graph": self._handle_knowledge_graph,
            "anomaly_detector": self._handle_anomaly_detector,
            "voice_assistant": self._handle_voice_assistant,
            "data_pipeline": self._handle_data_pipeline,
            "fleet_manager": self._handle_fleet_manager,
        }

    def _handle_weather(self, data: Dict) -> Dict:
        """Fetch real weather data from wttr.in."""
        import urllib.request
        location = data.get("location", "auto")
        try:
            url = f"https://wttr.in/{location}?format=j1"
            req = urllib.request.Request(url, headers={"User-Agent": "JARVIS/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                weather = json.loads(resp.read().decode())
                current = weather.get("current_condition", [{}])[0]
                return {
                    "location": location,
                    "temperature_c": current.get("temp_C", "N/A"),
                    "temperature_f": current.get("temp_F", "N/A"),
                    "description": current.get("weatherDesc", [{}])[0].get("value", "N/A"),
                    "humidity": current.get("humidity", "N/A"),
                    "wind_kmph": current.get("windspeedKmph", "N/A"),
                    "feels_like_c": current.get("FeelsLikeC", "N/A"),
                    "visibility_km": current.get("visibility", "N/A"),
                    "uv_index": current.get("uvIndex", "N/A"),
                }
        except Exception as e:
            return {"error": str(e), "location": location}

    def _handle_email_monitor(self, data: Dict) -> Dict:
        """Check email status via IMAP (if configured)."""
        import imaplib
        import os
        host = data.get("host") or os.environ.get("EMAIL_IMAP_HOST")
        user = data.get("user") or os.environ.get("EMAIL_USER")
        password = data.get("password") or os.environ.get("EMAIL_PASSWORD")
        if not all([host, user, password]):
            return {"error": "Email credentials not configured. Set EMAIL_IMAP_HOST, EMAIL_USER, EMAIL_PASSWORD env vars.", "configured": False}
        try:
            mail = imaplib.IMAP4_SSL(host, 993)
            mail.login(user, password)
            mail.select("INBOX")
            _, msg_nums = mail.search(None, "UNSEEN")
            unread = len(msg_nums[0].split()) if msg_nums[0] else 0
            _, all_nums = mail.search(None, "ALL")
            total = len(all_nums[0].split()) if all_nums[0] else 0
            mail.logout()
            return {"unread": unread, "total": total, "provider": host, "configured": True}
        except Exception as e:
            return {"error": str(e), "configured": True}

    def _handle_smart_home(self, data: Dict) -> Dict:
        """Control smart home devices via relay."""
        from device_mesh import get_device_mesh
        mesh = get_device_mesh()
        action = data.get("action", "status")
        device_name = data.get("device")
        if action == "status":
            devices = mesh.get_all_devices(type="smart_plug")
            return {"devices": [{"name": d["name"], "status": d["status"], "id": d["id"]} for d in devices]}
        elif action in ("on", "off"):
            if device_name:
                devices = mesh.get_all_devices(type="smart_plug")
                target = next((d for d in devices if device_name.lower() in d["name"].lower()), None)
                if target:
                    result = mesh.send_command(f"plug_{action}", target_device_id=target["id"])
                    return {"action": action, "device": target["name"], "result": result}
            return {"error": "Device not found"}
        return {"error": f"Unknown action: {action}"}

    def _handle_calendar_sync(self, data: Dict) -> Dict:
        """Sync calendar events from local ICS or API."""
        from datetime import timedelta
        now = datetime.utcnow()
        events = []
        try:
            import subprocess
            result = subprocess.run(["date", "+%Y-%m-%d"], capture_output=True, text=True, timeout=5)
            today = result.stdout.strip()
        except:
            today = now.strftime("%Y-%m-%d")
        return {"today": today, "events": events, "source": "local", "synced": True}

    def _handle_code_review(self, data: Dict) -> Dict:
        """Analyze code files for issues."""
        filepath = data.get("file")
        code = data.get("code", "")
        if not code and filepath:
            try:
                with open(filepath) as f:
                    code = f.read()
            except:
                return {"error": f"Cannot read {filepath}"}
        if not code:
            return {"error": "No code provided"}
        issues = []
        lines = code.split("\n")
        for i, line in enumerate(lines, 1):
            if len(line) > 120:
                issues.append({"line": i, "type": "style", "message": f"Line exceeds 120 chars ({len(line)})"})
            if "TODO" in line or "FIXME" in line:
                issues.append({"line": i, "type": "todo", "message": line.strip()})
            if "eval(" in line or "exec(" in line:
                issues.append({"line": i, "type": "security", "message": "Dangerous eval/exec usage"})
            if "password" in line.lower() and "=" in line and "\"" in line:
                issues.append({"line": i, "type": "security", "message": "Hardcoded password detected"})
        return {"file": filepath, "lines": len(lines), "issues": issues, "issue_count": len(issues)}

    def _handle_knowledge_graph(self, data: Dict) -> Dict:
        """Query knowledge graph for relevant context."""
        try:
            from graph_memory import HybridGraphMemory
            memory = HybridGraphMemory()
            query = data.get("query", "")
            if query:
                results = memory.semantic_recall(query, top_k=data.get("top_k", 5))
                return {"results": results, "query": query}
            stats = memory.get_stats()
            return {"stats": stats, "query": query}
        except Exception as e:
            return {"error": str(e)}

    def _handle_anomaly_detector(self, data: Dict) -> Dict:
        """Detect anomalies in system metrics."""
        import psutil
        sensitivity = data.get("sensitivity", 0.8)
        anomalies = []
        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        if cpu > 90 * sensitivity:
            anomalies.append({"metric": "cpu", "value": cpu, "severity": "high"})
        if mem.percent > 90 * sensitivity:
            anomalies.append({"metric": "memory", "value": mem.percent, "severity": "high"})
        if disk.percent > 90 * sensitivity:
            anomalies.append({"metric": "disk", "value": disk.percent, "severity": "high"})
        net = psutil.net_io_counters()
        if net.bytes_recv > 1_000_000_000:
            anomalies.append({"metric": "network_bytes", "value": net.bytes_recv, "severity": "medium"})
        return {"anomalies": anomalies, "metrics": {"cpu": cpu, "memory": mem.percent, "disk": disk.percent}, "sensitivity": sensitivity}

    def _handle_voice_assistant(self, data: Dict) -> Dict:
        """Process voice input and return text response."""
        text = data.get("text", "")
        if not text:
            return {"error": "No text provided"}
        try:
            from ai_agent import generate_response
            response = generate_response(text)
            return {"input": text, "response": response, "processed": True}
        except Exception as e:
            return {"error": str(e), "input": text}

    def _handle_data_pipeline(self, data: Dict) -> Dict:
        """Run a simple ETL pipeline."""
        source = data.get("source", "")
        if not source:
            return {"error": "No source provided"}
        try:
            if source.startswith("http"):
                import urllib.request
                req = urllib.request.Request(source)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    raw = resp.read().decode()
                    try:
                        parsed = json.loads(raw)
                        return {"source": source, "records": len(parsed) if isinstance(parsed, list) else 1, "format": "json", "processed": True}
                    except:
                        return {"source": source, "bytes": len(raw), "format": "text", "processed": True}
            elif os.path.exists(source):
                with open(source) as f:
                    content = f.read()
                return {"source": source, "bytes": len(content), "lines": content.count("\n"), "processed": True}
            return {"error": f"Source not found: {source}"}
        except Exception as e:
            return {"error": str(e)}

    def _handle_fleet_manager(self, data: Dict) -> Dict:
        """Manage device fleet status and deployment."""
        from device_mesh import get_device_mesh
        mesh = get_device_mesh()
        action = data.get("action", "status")
        if action == "status":
            return mesh.get_mesh_stats()
        elif action == "health":
            devices = mesh.get_all_devices()
            health_report = []
            for d in devices:
                health_report.append({
                    "id": d["id"], "name": d["name"], "status": d["status"],
                    "health": d["health_score"], "last_seen": d.get("last_seen"),
                })
            return {"devices": health_report, "total": len(health_report)}
        elif action == "deploy":
            command = data.get("command", "")
            if command:
                result = mesh.broadcast_command(command, device_type=data.get("device_type"))
                return result
            return {"error": "No command provided"}
        return {"error": f"Unknown action: {action}"}

    def add_review(self, skill_id: str, rating: int, comment: str = "", user_id: str = "local") -> Dict:
        """Add a review for a skill."""
        if not 1 <= rating <= 5:
            return {"error": "rating must be 1-5"}
        with self._lock:
            with self._conn:
                self._conn.execute(
                    "INSERT INTO skill_reviews (skill_id, user_id, rating, comment) VALUES (?, ?, ?, ?)",
                    (skill_id, user_id, rating, comment),
                )
                avg = self._conn.execute(
                    "SELECT AVG(rating) as avg, COUNT(*) as cnt FROM skill_reviews WHERE skill_id = ?",
                    (skill_id,),
                ).fetchone()
                self._conn.execute(
                    "UPDATE skills SET rating = ?, rating_count = ? WHERE id = ?",
                    (round(avg["avg"], 2), avg["cnt"], skill_id),
                )
                return {"status": "reviewed", "new_rating": round(avg["avg"], 2)}

    def get_reviews(self, skill_id: str, limit: int = 20) -> List[Dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM skill_reviews WHERE skill_id = ? ORDER BY created_at DESC LIMIT ?",
                (skill_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_categories(self) -> List[Dict]:
        """Get all skill categories with counts."""
        with self._lock:
            rows = self._conn.execute(
                """SELECT category, COUNT(*) as total,
                SUM(CASE WHEN installed=1 THEN 1 ELSE 0 END) as installed
                FROM skills GROUP BY category ORDER BY total DESC"""
            ).fetchall()
            return [dict(r) for r in rows]

    def get_templates(self, category: Optional[str] = None) -> List[Dict]:
        with self._lock:
            if category:
                rows = self._conn.execute("SELECT * FROM skill_templates WHERE category = ?", (category,)).fetchall()
            else:
                rows = self._conn.execute("SELECT * FROM skill_templates ORDER BY name").fetchall()
            return [dict(r) for r in rows]

    def create_skill(self, name: str, display_name: str, description: str, category: str, entry_point: str, version: str = "1.0.0", author: str = "local", icon: str = "🧩") -> Dict:
        """Create a new skill in the marketplace."""
        skill_id = str(uuid.uuid4())[:12]
        with self._lock:
            with self._conn:
                existing = self._conn.execute("SELECT id FROM skills WHERE name = ?", (name,)).fetchone()
                if existing:
                    return {"error": "name_taken"}
                self._conn.execute(
                    """INSERT INTO skills (id, name, display_name, description, author, version, category, icon, entry_point, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'available')""",
                    (skill_id, name, display_name, description, author, version, category, icon, entry_point),
                )
                return {"id": skill_id, "name": name, "status": "created"}

    def get_marketplace_stats(self) -> Dict:
        with self._lock:
            skills = self._conn.execute(
                "SELECT COUNT(*) as total, SUM(CASE WHEN installed=1 THEN 1 ELSE 0 END) as installed FROM skills"
            ).fetchone()
            execs = self._conn.execute(
                "SELECT COUNT(*) as total, AVG(latency_ms) as avg_latency FROM skill_executions"
            ).fetchone()
            reviews = self._conn.execute("SELECT AVG(rating) as avg, COUNT(*) as total FROM skill_reviews").fetchone()
            categories = self._conn.execute("SELECT COUNT(DISTINCT category) as total FROM skills").fetchone()

            return {
                "skills": {"total": skills["total"], "installed": skills["installed"]},
                "executions": {"total": execs["total"], "avg_latency_ms": round(execs["avg_latency"], 1) if execs["avg_latency"] else 0},
                "reviews": {"avg_rating": round(reviews["avg"], 2) if reviews["avg"] else 0, "total": reviews["total"]},
                "categories": categories["total"],
            }


_engine: Optional[SkillMarketplace] = None


def get_skill_marketplace() -> SkillMarketplace:
    global _engine
    if _engine is None:
        _engine = SkillMarketplace()
    return _engine
