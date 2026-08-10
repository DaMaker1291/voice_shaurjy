"""
JARVIS System Daemon — Always-on background service.
WebSocket command listener + persistent SQLite + agent orchestration.
"""
import asyncio
import json
import os
import sys
import time
import logging
import sqlite3
import threading
from pathlib import Path

logger = logging.getLogger("daemon")

try:
    import websockets
except ImportError:
    logger.error("pip install websockets")
    sys.exit(1)

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "jarvis.db"
PID_PATH = DATA_DIR / "daemon.pid"


class JarvisDB:
    def __init__(self, db_path=None):
        self.db_path = db_path or str(DB_PATH)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT, updated_at REAL);
                CREATE TABLE IF NOT EXISTS devices (id TEXT PRIMARY KEY, name TEXT, type TEXT, ip TEXT, port INTEGER, capabilities TEXT, last_seen REAL);
                CREATE TABLE IF NOT EXISTS execution_log (id INTEGER PRIMARY KEY AUTOINCREMENT, goal TEXT, success INTEGER, steps_total INTEGER, steps_done INTEGER, duration_s REAL, timestamp REAL, details TEXT);
                CREATE TABLE IF NOT EXISTS chat_history (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT, timestamp REAL);
            """)

    def set_pref(self, key, value):
        with sqlite3.connect(self.db_path) as c:
            c.execute("INSERT OR REPLACE INTO preferences VALUES (?,?,?)", (key, value, time.time()))

    def get_pref(self, key, default=""):
        with sqlite3.connect(self.db_path) as c:
            r = c.execute("SELECT value FROM preferences WHERE key=?", (key,)).fetchone()
            return r[0] if r else default

    def register_device(self, device_id, name, dtype, ip, port, caps=None):
        with sqlite3.connect(self.db_path) as c:
            c.execute("INSERT OR REPLACE INTO devices VALUES (?,?,?,?,?,?,?)",
                      (device_id, name, dtype, ip, port, json.dumps(caps or []), time.time()))

    def get_devices(self):
        with sqlite3.connect(self.db_path) as c:
            return [{"id": r[0], "name": r[1], "type": r[2], "ip": r[3], "port": r[4],
                     "capabilities": json.loads(r[5] or "[]"), "last_seen": r[6]}
                    for r in c.execute("SELECT * FROM devices").fetchall()]

    def log_execution(self, goal, success, steps_total, steps_done, duration_s, details=None):
        with sqlite3.connect(self.db_path) as c:
            c.execute("INSERT INTO execution_log (goal,success,steps_total,steps_done,duration_s,timestamp,details) VALUES (?,?,?,?,?,?,?)",
                      (goal, int(success), steps_total, steps_done, duration_s, time.time(), json.dumps(details or {}, default=str)))

    def get_executions(self, limit=20):
        with sqlite3.connect(self.db_path) as c:
            return [{"goal": r[1], "success": bool(r[2]), "steps_total": r[3], "steps_done": r[4],
                     "duration_s": r[5], "timestamp": r[6]} for r in
                    c.execute("SELECT * FROM execution_log ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()]

    def add_chat(self, role, content):
        with sqlite3.connect(self.db_path) as c:
            c.execute("INSERT INTO chat_history (role,content,timestamp) VALUES (?,?,?)", (role, content, time.time()))

    def get_chat(self, limit=50):
        with sqlite3.connect(self.db_path) as c:
            rows = c.execute("SELECT role,content,timestamp FROM chat_history ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
            return [{"role": r[0], "content": r[1], "timestamp": r[2]} for r in reversed(rows)]


class JarvisDaemon:
    def __init__(self):
        self.db = JarvisDB()
        self.agent = None

    def _ensure_agent(self):
        if self.agent is None:
            from computer_use import ComputerUseAgent
            self.agent = ComputerUseAgent()

    async def handle(self, ws, path=None):
        logger.info(f"Client connected: {ws.remote_address}")
        try:
            async for msg in ws:
                try:
                    cmd = json.loads(msg)
                    resp = await self.dispatch(cmd)
                    await ws.send(json.dumps(resp, default=str))
                except json.JSONDecodeError:
                    await ws.send(json.dumps({"success": False, "error": "Invalid JSON"}))
                except Exception as e:
                    await ws.send(json.dumps({"success": False, "error": str(e)}))
        except websockets.exceptions.ConnectionClosed:
            pass
        logger.info(f"Client disconnected")

    async def dispatch(self, cmd):
        action = cmd.get("type", cmd.get("action", ""))

        if action in ("execute", "goal"):
            goal = cmd.get("goal", cmd.get("text", ""))
            if not goal:
                return {"success": False, "error": "No goal"}
            self._ensure_agent()
            try:
                from stream_server import broadcast_log
                broadcast_log(f"Goal: {goal}", "log-info")
            except Exception:
                pass
            result = await self.agent.execute(goal)
            if isinstance(result, dict):
                self.db.log_execution(goal, result.get("success", False),
                                      result.get("steps_total", 0), result.get("steps_done", 0),
                                      result.get("duration_seconds", 0), result)
            return result

        elif action == "chat":
            content = cmd.get("content", cmd.get("text", ""))
            if not content:
                return {"success": False, "error": "No message"}
            self.db.add_chat("user", content)
            try:
                from groq_agent import call as groq_call
                msgs = [{"role": "system", "content": "You are JARVIS, a helpful AI assistant."}]
                for h in self.db.get_chat(20)[:-1]:
                    msgs.append({"role": h["role"], "content": h["content"]})
                msgs.append({"role": "user", "content": content})
                resp = groq_call(msgs, max_tokens=500, temperature=0.7)
                self.db.add_chat("assistant", resp or "Error")
                return {"success": True, "response": resp}
            except Exception as e:
                return {"success": False, "error": str(e)}

        elif action == "devices":
            return {"success": True, "devices": self.db.get_devices()}

        elif action == "history":
            return {"success": True, "history": self.db.get_executions(cmd.get("limit", 20))}

        elif action == "status":
            return {"success": True, "status": "running", "uptime": time.time(),
                    "devices": len(self.db.get_devices()),
                    "executions": len(self.db.get_executions(1000))}

        elif action == "ping":
            return {"success": True, "pong": True}

        return {"success": False, "error": f"Unknown: {action}"}


def run_daemon(host="127.0.0.1", port=8766):
    daemon = JarvisDaemon()
    PID_PATH.write_text(str(os.getpid()))
    logger.info(f"JARVIS daemon on ws://{host}:{port}")

    async def main():
        async with websockets.serve(daemon.handle, host, port):
            logger.info("Daemon running. Ctrl+C to stop.")
            await asyncio.Future()

    asyncio.run(main())


def run_background(host="127.0.0.1", port=8766):
    """Start daemon in a background thread."""
    t = threading.Thread(target=run_daemon, args=(host, port), daemon=True)
    t.start()
    return t


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[DAEMON] %(message)s")
    run_daemon()
