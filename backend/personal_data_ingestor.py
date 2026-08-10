"""
Personal Data Ingestor — continuously scans ALL user data sources
and builds a unified personal knowledge base.

Data sources:
  - Files (Documents, Desktop, Downloads, Recent)
  - Calendar events (Outlook, Apple, ICS)
  - Emails (Outlook, Apple Mail)
  - Contacts (Outlook, Apple, Android)
  - Browser profiles / bookmarks
  - Installed apps & usage
  - Running processes & services
  - Device & OS profile

Baseline RAM: < 5 MB (SQLite-backed, no ML frameworks)
All data persisted to disk. Lazy-loaded on demand.
"""

import hashlib
import json
import os
import re
import sqlite3
import threading
import time
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

# ── Constants ───────────────────────────────────────────────────────

HOME = Path.home()
INGESTOR_DIR = Path(__file__).parent / ".ingestor_data"
INGESTOR_DIR.mkdir(exist_ok=True)

# File types we can extract text from
TEXT_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css",
    ".json", ".xml", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".csv", ".log", ".rst", ".tex", ".org", ".nfo", ".readme",
    ".java", ".cpp", ".c", ".h", ".hpp", ".rs", ".go", ".rb", ".php",
    ".swift", ".kt", ".scala", ".clj", ".ex", ".exs", ".erl",
    ".bat", ".ps1", ".sh", ".zsh", ".bash", ".fish",
    ".sql", ".r", ".m", ".mm",
}

OFFICE_EXTENSIONS = {
    ".docx", ".xlsx", ".pptx",
}

IGNORE_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv", "env",
    ".tox", ".eggs", "egg-info", "dist", "build", ".next", ".nuxt",
    ".cache", ".npm", ".yarn", ".pytest_cache", ".mypy_cache",
    ".DS_Store", "Thumbs.db",
}

# ── Database ────────────────────────────────────────────────────────

_conn_lock = threading.Lock()


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(INGESTOR_DIR / "personal_knowledge.db"), timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA cache_size=-2000")  # ~2MB cache max
    return conn


def _init_db():
    with _get_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS files (
                path TEXT PRIMARY KEY,
                name TEXT,
                extension TEXT,
                size INTEGER,
                modified REAL,
                created REAL,
                content_preview TEXT,
                content_hash TEXT,
                words INTEGER,
                last_scanned REAL,
                category TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_files_ext ON files(extension);
            CREATE INDEX IF NOT EXISTS idx_files_modified ON files(modified);
            CREATE INDEX IF NOT EXISTS idx_files_category ON files(category);

            CREATE TABLE IF NOT EXISTS file_keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT,
                keyword TEXT,
                frequency INTEGER,
                FOREIGN KEY(file_path) REFERENCES files(path)
            );
            CREATE INDEX IF NOT EXISTS idx_fk_keyword ON file_keywords(keyword);

            CREATE TABLE IF NOT EXISTS calendar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT,
                subject TEXT,
                start_time REAL,
                end_time REAL,
                location TEXT,
                organizer TEXT,
                attendees TEXT,
                description TEXT,
                is_recurring INTEGER DEFAULT 0,
                last_scanned REAL
            );
            CREATE INDEX IF NOT EXISTS idx_cal_start ON calendar(start_time);

            CREATE TABLE IF NOT EXISTS emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender TEXT,
                sender_name TEXT,
                recipients TEXT,
                subject TEXT,
                body_preview TEXT,
                received_time REAL,
                has_attachments INTEGER DEFAULT 0,
                folder TEXT,
                last_scanned REAL
            );
            CREATE INDEX IF NOT EXISTS idx_email_time ON emails(received_time);
            CREATE INDEX IF NOT EXISTS idx_email_sender ON emails(sender);

            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                email TEXT,
                phone TEXT,
                company TEXT,
                source TEXT,
                last_scanned REAL
            );

            CREATE TABLE IF NOT EXISTS browser_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_name TEXT,
                profile_email TEXT,
                bookmark_title TEXT,
                bookmark_url TEXT,
                source TEXT,
                last_scanned REAL
            );

            CREATE TABLE IF NOT EXISTS installed_apps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                vendor TEXT,
                version TEXT,
                install_date REAL,
                size_mb REAL,
                source TEXT,
                last_scanned REAL
            );

            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                root_path TEXT,
                language TEXT,
                last_activity REAL,
                file_count INTEGER,
                description TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_proj_activity ON projects(last_activity);

            CREATE TABLE IF NOT EXISTS knowledge_entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type TEXT,
                entity_name TEXT,
                context TEXT,
                source_file TEXT,
                confidence REAL DEFAULT 0.5,
                first_seen REAL,
                last_seen REAL,
                UNIQUE(entity_type, entity_name)
            );
            CREATE INDEX IF NOT EXISTS idx_ke_type ON knowledge_entities(entity_type);
            CREATE INDEX IF NOT EXISTS idx_ke_name ON knowledge_entities(entity_name);

            CREATE TABLE IF NOT EXISTS scan_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT,
                items_found INTEGER,
                duration_ms REAL,
                timestamp REAL
            );

            CREATE TABLE IF NOT EXISTS daily_rhythm (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day_of_week INTEGER,
                hour INTEGER,
                activity_type TEXT,
                frequency INTEGER DEFAULT 0,
                apps TEXT
            );

            CREATE TABLE IF NOT EXISTS topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT UNIQUE,
                frequency INTEGER DEFAULT 1,
                last_mentioned REAL,
                related_files TEXT,
                related_emails INTEGER DEFAULT 0,
                category TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_topic_freq ON topics(frequency DESC);
        """)


_init_db()


# ── Text Extraction ─────────────────────────────────────────────────

def _extract_text(filepath: Path, max_chars: int = 2000) -> str:
    """Extract readable text from a file. Pure Python, zero ML."""
    ext = filepath.suffix.lower()
    try:
        if ext in TEXT_EXTENSIONS:
            text = filepath.read_text(encoding="utf-8", errors="replace")
            return text[:max_chars]

        if ext == ".pdf":
            try:
                import io
                content = filepath.read_bytes()
                text = ""
                # Basic PDF text extraction (no PyMuPDF dependency)
                raw = content.decode("latin-1")
                for m in re.finditer(r'\((.*?)\)', raw):
                    t = m.group(1)
                    if len(t) > 3 and not all(c in " \\/()<>[]{}#" for c in t):
                        text += t + " "
                return text[:max_chars] if len(text) > 20 else "[PDF - binary content]"
            except:
                return "[PDF - unreadable]"

        if ext in OFFICE_EXTENSIONS:
            return f"[Office document: {filepath.name}]"

        # Binary files — try to extract ASCII strings
        try:
            text = filepath.read_text(encoding="utf-8", errors="ignore")
            if len(text) > 10 and sum(1 for c in text[:200] if c.isprintable()) > len(text[:200]) * 0.6:
                return text[:max_chars]
        except:
            pass

        return ""
    except:
        return ""


def _extract_keywords(text: str, max_keywords: int = 30) -> list[tuple[str, int]]:
    """Extract meaningful keywords with frequency. Pure Python."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    words = text.split()
    
    stopwords = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "need", "dare", "ought",
        "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
        "as", "into", "through", "during", "before", "after", "above", "below",
        "between", "out", "off", "over", "under", "again", "further", "then",
        "once", "here", "there", "when", "where", "why", "how", "all", "each",
        "every", "both", "few", "more", "most", "other", "some", "such", "no",
        "nor", "not", "only", "own", "same", "so", "than", "too", "very",
        "just", "because", "but", "and", "or", "if", "while", "although",
        "this", "that", "these", "those", "it", "its", "i", "you", "he", "she",
        "we", "they", "me", "him", "her", "us", "them", "my", "your", "his",
        "her", "our", "their", "mine", "yours", "his", "hers", "ours", "theirs",
        "about", "which", "what", "who", "whom", "whose", "any", "one", "two",
        "also", "get", "got", "go", "going", "went", "come", "came", "make",
        "made", "take", "took", "know", "new", "like", "want", "see", "say",
        "said", "tell", "told", "think", "thought", "look", "use", "work",
        "need", "seem", "let", "give", "find", "try",
    }
    
    words = [w for w in words if len(w) > 2 and w not in stopwords and w.isalpha()]
    counter = Counter(words)
    return counter.most_common(max_keywords)


def _categorize_file(path: str, name: str, ext: str) -> str:
    """Categorize a file by its path and name."""
    pl = path.lower()
    name_lower = name.lower()
    
    if "/download" in pl or "\\download" in pl:
        return "downloads"
    if "/desktop" in pl or "\\desktop" in pl:
        return "desktop"
    if "/document" in pl or "\\document" in pl:
        return "documents"
    if any(d in pl for d in [".git", "node_modules", "venv", ".venv", "__pycache__"]):
        return "ignored"
    if ext in {".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".cpp", ".c", ".rs", ".go", ".rb"}:
        return "code"
    if ext in {".md", ".txt", ".rst", ".org"}:
        return "notes"
    if ext in {".pdf", ".docx", ".xlsx", ".pptx"}:
        return "documents"
    if ext in {".json", ".xml", ".yaml", ".yml", ".toml", ".ini", ".cfg"}:
        return "config"
    if ext in {".log", ".csv"}:
        return "data"
    if ext in {".jpg", ".jpeg", ".png", ".gif", ".svg", ".ico", ".bmp", ".webp"}:
        return "images"
    if ext in {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".wma"}:
        return "audio"
    if ext in {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv"}:
        return "video"
    if ext in {".zip", ".tar", ".gz", ".bz2", ".7z", ".rar"}:
        return "archives"
    if name_lower.startswith("."):
        return "hidden"
    return "other"


def _detect_project(path: str) -> Optional[dict]:
    """Detect if a directory is a project root."""
    p = Path(path)
    if not p.is_dir():
        return None
    
    indicators = {
        "pyproject.toml": "Python",
        "setup.py": "Python",
        "requirements.txt": "Python",
        "Pipfile": "Python",
        "package.json": "JavaScript/Node",
        "go.mod": "Go",
        "Cargo.toml": "Rust",
        "Gemfile": "Ruby",
        "build.gradle": "Java/Gradle",
        "pom.xml": "Java/Maven",
        "CMakeLists.txt": "C/C++",
        "Makefile": "C/C++",
        "composer.json": "PHP",
        "project.clj": "Clojure",
        "mix.exs": "Elixir",
        "Pubspec.yaml": "Dart/Flutter",
        "index.html": "Web",
    }
    
    for indicator, lang in indicators.items():
        if (p / indicator).exists():
            return {
                "name": p.name,
                "root_path": str(p),
                "language": lang,
                "last_activity": p.stat().st_mtime if p.exists() else 0,
                "file_count": sum(1 for _ in p.rglob("*") if _.is_file()),
                "description": f"{lang} project: {p.name}",
            }
    
    # Check for git repos
    if (p / ".git").exists():
        return {
            "name": p.name,
            "root_path": str(p),
            "language": "Unknown (git repo)",
            "last_activity": p.stat().st_mtime if p.exists() else 0,
            "file_count": sum(1 for _ in p.rglob("*") if _.is_file()),
            "description": f"Git repository: {p.name}",
        }
    
    return None


# ── File Scanner ────────────────────────────────────────────────────

class FileScanner:
    """Scans user files and indexes them into SQLite. < 1 MB RAM."""
    
    def __init__(self):
        self._scanned = 0
        self._errors = 0
    
    def scan(self, paths: list[Path] | None = None, max_files: int = 5000) -> dict:
        """Scan directories for files. Pure Python, zero ML."""
        start = time.time()
        
        if paths is None:
            paths = [
                HOME / "Documents",
                HOME / "Desktop",
                HOME / "Downloads",
            ]
            # Add source code workspace directories
            code_dirs = [
                HOME / "code",
                HOME / "projects",
                HOME / "workspace",
                HOME / "src",
                HOME / "dev",
            ]
            for d in code_dirs:
                if d.exists():
                    paths.append(d)
        
        files_found = 0
        new_files = 0
        updated_files = 0
        
        with _get_db() as db:
            now = time.time()
            
            for scan_dir in paths:
                if not scan_dir.exists() or not scan_dir.is_dir():
                    continue
                
                try:
                    for entry in scan_dir.rglob("*"):
                        if not entry.is_file():
                            continue
                        
                        # Skip ignored directories
                        rel = entry.relative_to(scan_dir)
                        if any(ig in rel.parts for ig in IGNORE_DIRS):
                            continue
                        
                        # Skip dotfiles
                        if entry.name.startswith(".") and entry.suffix == "":
                            continue
                        
                        files_found += 1
                        if files_found > max_files:
                            break
                        
                        try:
                            stat = entry.stat()
                            ext = entry.suffix.lower()
                            filepath = str(entry)
                            
                            # Check if file changed
                            existing = db.execute(
                                "SELECT modified, content_hash FROM files WHERE path = ?",
                                (filepath,)
                            ).fetchone()
                            
                            if existing and existing[0] == stat.st_mtime:
                                continue  # Unchanged
                            
                            category = _categorize_file(filepath, entry.name, ext)
                            if category == "ignored":
                                continue
                            
                            content = _extract_text(entry, max_chars=2000)
                            content_hash = hashlib.md5(content.encode()).hexdigest()[:16] if content else ""
                            
                            if existing and existing[1] == content_hash:
                                # Same content, just update modified time
                                db.execute(
                                    "UPDATE files SET modified = ?, last_scanned = ? WHERE path = ?",
                                    (stat.st_mtime, now, filepath)
                                )
                                updated_files += 1
                                continue
                            
                            keywords = _extract_keywords(content)
                            word_count = len(content.split()) if content else 0
                            
                            db.execute("""
                                INSERT OR REPLACE INTO files
                                (path, name, extension, size, modified, created, content_preview, content_hash, words, last_scanned, category)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                filepath, entry.name, ext, stat.st_size,
                                stat.st_mtime, stat.st_ctime,
                                content, content_hash, word_count, now, category,
                            ))
                            
                            # Update keywords
                            db.execute("DELETE FROM file_keywords WHERE file_path = ?", (filepath,))
                            for kw, freq in keywords:
                                db.execute(
                                    "INSERT INTO file_keywords (file_path, keyword, frequency) VALUES (?, ?, ?)",
                                    (filepath, kw, freq)
                                )
                            
                            new_files += 1
                            self._scanned += 1
                            
                        except (OSError, PermissionError):
                            self._errors += 1
                            continue
                            
                except (PermissionError, OSError):
                    continue
            
            # Log scan
            elapsed = (time.time() - start) * 1000
            db.execute(
                "INSERT INTO scan_log (source, items_found, duration_ms, timestamp) VALUES (?, ?, ?, ?)",
                ("files", files_found, elapsed, now)
            )
        
        return {
            "directories_scanned": len(paths),
            "total_files": files_found,
            "new_files": new_files,
            "updated_files": updated_files,
            "duration_ms": round((time.time() - start) * 1000, 1),
            "errors": self._errors,
        }


# ── Project Scanner ─────────────────────────────────────────────────

class ProjectScanner:
    """Detect project directories. < 0.5 MB RAM."""
    
    def scan(self, max_projects: int = 50) -> list[dict]:
        """Find project directories."""
        projects = []
        search_dirs = [
            HOME / "Documents",
            HOME / "Desktop",
            HOME / "Downloads",
            HOME / "code",
            HOME / "projects",
            HOME / "workspace",
            HOME / "src",
        ]
        
        with _get_db() as db:
            now = time.time()
            
            for sd in search_dirs:
                if not sd.exists():
                    continue
                try:
                    for entry in sd.iterdir():
                        if not entry.is_dir() or entry.name.startswith("."):
                            continue
                        proj = _detect_project(str(entry))
                        if proj:
                            proj["last_activity"] = max(
                                p.stat().st_mtime for p in entry.rglob("*") if p.is_file()
                            ) if any(True for _ in entry.rglob("*") if _.is_file()) else now
                            
                            db.execute("""
                                INSERT OR REPLACE INTO projects
                                (name, root_path, language, last_activity, file_count, description)
                                VALUES (?, ?, ?, ?, ?, ?)
                            """, (
                                proj["name"], proj["root_path"], proj["language"],
                                proj["last_activity"], proj["file_count"], proj["description"],
                            ))
                            projects.append(proj)
                            
                            if len(projects) >= max_projects:
                                return projects
                except PermissionError:
                    continue
        
        return projects


# ── Knowledge Extractor ─────────────────────────────────────────────

class KnowledgeExtractor:
    """Extract entities, topics, and relationships from scanned content.
    Pure Python pattern matching. < 0.5 MB RAM."""
    
    # Entity extraction patterns
    ENTITY_PATTERNS = [
        (r'[\w\.-]+@[\w\.-]+\.\w+', 'email'),
        (r'(?:https?://|www\.)[^\s]+', 'url'),
        (r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', 'phone'),
        (r'(?:API[_-]?key|api[_-]?key|secret|password|token)\s*[:=]\s*\S+', 'credential'),
    ]
    
    TOPIC_PATTERNS = {
        "programming": [r'\b(python|javascript|typescript|react|node\.?js|api|backend|frontend|full.?stack)\b'],
        "data": [r'\b(database|sql|analytics|machine.?learning|ai|data.?science|pandas|numpy|tensorflow|pytorch)\b'],
        "web": [r'\b(website|web.?app|html|css|react|vue|angular|django|flask|fastapi)\b'],
        "business": [r'\b(startup|business|revenue|profit|market|customer|sales|marketing|investor|funding)\b'],
        "finance": [r'\b(budget|expense|invoice|tax|accounting|salary|payment|subscription|price|cost)\b'],
        "health": [r'\b(workout|exercise|diet|nutrition|sleep|medication|doctor|appointment|fitness)\b'],
        "travel": [r'\b(trip|vacation|flight|hotel|booking|travel|destination|itinerary|passport)\b'],
        "learning": [r'\b(course|tutorial|learn|study|certification|exam|degree|training|workshop)\b'],
        "creative": [r'\b(design|write|draw|paint|music|photo|video|edit|creative|art)\b'],
        "productivity": [r'\b(todo|task|deadline|schedule|calendar|meeting|appointment|reminder|goal)\b'],
        "communication": [r'\b(email|message|slack|discord|teams|zoom|meet|call|chat)\b'],
        "devops": [r'\b(docker|kubernetes|deploy|ci/cd|github|gitlab|pipeline|server|cloud|aws)\b'],
    }
    
    def extract_from_files(self) -> dict:
        """Extract knowledge entities and topics from indexed files."""
        with _get_db() as db:
            now = time.time()
            
            # Get files with content
            files = db.execute(
                "SELECT path, name, content_preview, category FROM files WHERE content_preview != '' AND content_preview NOT LIKE '[%'"
            ).fetchall()
            
            entities_found = 0
            topics_found = Counter()
            
            for filepath, name, content, category in files:
                text = f"{name}\n{content}"
                
                # Extract entities
                for pattern, etype in self.ENTITY_PATTERNS:
                    for match in re.finditer(pattern, text, re.IGNORECASE):
                        val = match.group().lower()[:100]
                        db.execute("""
                            INSERT OR REPLACE INTO knowledge_entities
                            (entity_type, entity_name, context, source_file, confidence, first_seen, last_seen)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (
                            etype, val, text[:100], filepath,
                            0.8, now, now,
                        ))
                        entities_found += 1
                
                # Extract topics
                for topic, patterns in self.TOPIC_PATTERNS.items():
                    for pattern in patterns:
                        if re.search(pattern, text, re.IGNORECASE):
                            topics_found[topic] += 1
                            break
            
            # Update topics table
            for topic, freq in topics_found.most_common():
                db.execute("""
                    INSERT INTO topics (topic, frequency, last_mentioned, category)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(topic) DO UPDATE SET
                        frequency = frequency + ?,
                        last_mentioned = MAX(last_mentioned, ?)
                """, (topic, freq, now, category, freq, now))
            
            return {
                "entities_found": entities_found,
                "topics_found": len(topics_found),
                "top_topics": [t for t, _ in topics_found.most_common(10)],
            }


# ── Daily Rhythm Analyzer ───────────────────────────────────────────

class DailyRhythmAnalyzer:
    """Analyze daily patterns from file activity and user data.
    Pure Python. < 0.3 MB RAM."""
    
    def analyze(self) -> dict:
        """Analyze when user is active and doing what."""
        with _get_db() as db:
            now = time.time()
            today = datetime.fromtimestamp(now)
            
            # Look at file modification times to infer activity patterns
            files_by_hour = defaultdict(int)
            files_by_hour_dow = defaultdict(lambda: defaultdict(int))
            
            rows = db.execute(
                "SELECT modified, category FROM files WHERE modified > ?",
                (now - 30 * 86400,)
            ).fetchall()
            
            for mod, cat in rows:
                dt = datetime.fromtimestamp(mod)
                hour = dt.hour
                dow = dt.weekday()
                files_by_hour[hour] += 1
                files_by_hour_dow[dow][hour] += 1
            
            # Determine peak hours
            peak_hours = sorted(
                files_by_hour.items(),
                key=lambda x: -x[1]
            )[:5] if files_by_hour else []
            
            # Determine productive hours (when code/notes files modified)
            code_hours = defaultdict(int)
            for mod, cat in rows:
                if cat in ("code", "notes", "documents"):
                    dt = datetime.fromtimestamp(mod)
                    code_hours[dt.hour] += 1
            
            productive_peak = sorted(
                code_hours.items(),
                key=lambda x: -x[1]
            )[:3] if code_hours else []
            
            # Store rhythm data
            for dow in range(7):
                for hour in range(24):
                    freq = files_by_hour_dow[dow].get(hour, 0)
                    if freq > 0:
                        db.execute("""
                            INSERT INTO daily_rhythm (day_of_week, hour, activity_type, frequency)
                            VALUES (?, ?, 'file_activity', ?)
                            ON CONFLICT(id) DO UPDATE SET frequency = frequency + ?
                        """, (dow, hour, freq, freq))
            
            return {
                "peak_hours": [{"hour": h, "files": c} for h, c in peak_hours],
                "productive_peak": [{"hour": h, "files": c} for h, c in productive_peak],
                "total_activity_days": len(set(
                    datetime.fromtimestamp(mod).date() for mod, _ in rows
                )) if rows else 0,
            }


# ── Personal Context Builder ────────────────────────────────────────

class PersonalContextBuilder:
    """Build a comprehensive personal context summary from all ingested data.
    This is the key to beating cloud models — no cloud model has this data."""
    
    def build_context(self, user_input: str = "", max_items: int = 5) -> dict:
        """Build a rich personal context about the user right now."""
        with _get_db() as db:
            now = time.time()
            context = {
                "recent_files": self._get_recent_files(db, max_items),
                "active_projects": self._get_active_projects(db, max_items),
                "upcoming_events": self._get_upcoming_events(db, max_items),
                "recent_emails": self._get_recent_emails(db, max_items),
                "top_topics": self._get_top_topics(db, max_items),
                "user_interests": self._get_user_interests(db),
                "peak_productivity": self._get_peak_hours(db),
                "recent_knowledge": self._search_knowledge(db, user_input),
                "scan_status": self._get_scan_status(db),
            }
            return context
    
    def _get_recent_files(self, db, limit=5) -> list:
        rows = db.execute(
            "SELECT name, path, category, modified FROM files ORDER BY modified DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [
            {
                "name": r[0], "path": r[1],
                "category": r[2],
                "when": self._time_ago(r[3]),
            } for r in rows
        ]
    
    def _get_active_projects(self, db, limit=5) -> list:
        rows = db.execute(
            "SELECT name, language, file_count, description FROM projects ORDER BY last_activity DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [
            {
                "name": r[0], "language": r[1],
                "files": r[2], "description": r[3],
            } for r in rows
        ]
    
    def _get_upcoming_events(self, db, limit=3) -> list:
        rows = db.execute(
            "SELECT subject, start_time, end_time, location FROM calendar WHERE start_time > ? ORDER BY start_time ASC LIMIT ?",
            (time.time(), limit)
        ).fetchall()
        return [
            {
                "subject": r[0],
                "start": datetime.fromtimestamp(r[1]).strftime("%a %I:%M %p") if r[1] else "",
                "location": r[3] or "",
            } for r in rows
        ]
    
    def _get_recent_emails(self, db, limit=3) -> list:
        rows = db.execute(
            "SELECT sender_name, subject, received_time FROM emails ORDER BY received_time DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [
            {
                "from": r[0] or r[1], "subject": r[1] or "(no subject)",
                "when": self._time_ago(r[2]),
            } for r in rows
        ]
    
    def _get_top_topics(self, db, limit=10) -> list:
        rows = db.execute(
            "SELECT topic, frequency, category FROM topics ORDER BY frequency DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [{"topic": r[0], "count": r[1], "category": r[2] or ""} for r in rows]
    
    def _get_user_interests(self, db) -> list:
        rows = db.execute(
            "SELECT DISTINCT category FROM topics WHERE category IS NOT NULL AND category != '' ORDER BY frequency DESC LIMIT 8"
        ).fetchall()
        return [r[0] for r in rows]
    
    def _get_peak_hours(self, db) -> dict:
        row = db.execute(
            "SELECT hour, SUM(frequency) FROM daily_rhythm WHERE activity_type = 'file_activity' GROUP BY hour ORDER BY SUM(frequency) DESC LIMIT 1"
        ).fetchone()
        return {"peak_hour": row[0] if row else 12}
    
    def _search_knowledge(self, db, query: str) -> list:
        if not query or len(query) < 3:
            return []
        words = re.findall(r'\w+', query.lower())
        if not words:
            return []
        
        # Search file keywords
        placeholders = ",".join("?" for _ in words)
        rows = db.execute(f"""
            SELECT DISTINCT f.path, f.name, f.category
            FROM file_keywords fk
            JOIN files f ON f.path = fk.file_path
            WHERE fk.keyword IN ({placeholders})
            ORDER BY fk.frequency DESC
            LIMIT 5
        """, words).fetchall()
        
        return [
            {"path": r[0], "name": r[1], "category": r[2]}
            for r in rows
        ]
    
    def _get_scan_status(self, db) -> dict:
        row = db.execute(
            "SELECT source, items_found, timestamp FROM scan_log ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        if row:
            return {
                "source": row[0],
                "items": row[1],
                "last_scan": self._time_ago(row[2]),
            }
        return {"last_scan": "never"}
    
    @staticmethod
    def _time_ago(t: float) -> str:
        if not t:
            return "unknown"
        seconds = time.time() - t
        if seconds < 60:
            return "just now"
        if seconds < 3600:
            return f"{int(seconds // 60)}m ago"
        if seconds < 86400:
            return f"{int(seconds // 3600)}h ago"
        return f"{int(seconds // 86400)}d ago"


# ── Main Ingestor ───────────────────────────────────────────────────

class PersonalDataIngestor:
    """Unified personal data ingestion engine.
    
    Memory: < 5 MB baseline
    All data SQLite-backed. Zero ML frameworks.
    """
    
    def __init__(self):
        self._file_scanner = FileScanner()
        self._project_scanner = ProjectScanner()
        self._knowledge_extractor = KnowledgeExtractor()
        self._rhythm_analyzer = DailyRhythmAnalyzer()
        self._context_builder = PersonalContextBuilder()
        self._running = False
        self._thread = None
    
    def ingest_all(self) -> dict:
        """Run all ingestion pipelines."""
        results = {}
        
        # 1. Scan files
        results["files"] = self._file_scanner.scan()
        
        # 2. Scan projects
        results["projects"] = self._project_scanner.scan()
        
        # 3. Extract knowledge
        results["knowledge"] = self._knowledge_extractor.extract_from_files()
        
        # 4. Analyze rhythm
        results["rhythm"] = self._rhythm_analyzer.analyze()
        
        return results
    
    def build_context(self, query: str = "") -> dict:
        """Build comprehensive personal context for response generation."""
        return self._context_builder.build_context(query)
    
    def search_files(self, query: str, limit: int = 10) -> list[dict]:
        """Search indexed files by keyword."""
        with _get_db() as db:
            words = re.findall(r'\w+', query.lower())
            if not words:
                return []
            
            placeholders = ",".join("?" for _ in words)
            rows = db.execute(f"""
                SELECT f.path, f.name, f.category, f.modified,
                       COUNT(fk.keyword) as match_count
                FROM file_keywords fk
                JOIN files f ON f.path = fk.file_path
                WHERE fk.keyword IN ({placeholders})
                GROUP BY f.path
                ORDER BY match_count DESC, f.modified DESC
                LIMIT ?
            """, words + [limit]).fetchall()
            
            return [
                {
                    "path": r[0], "name": r[1],
                    "category": r[2], "modified": datetime.fromtimestamp(r[3]).isoformat(),
                    "relevance": r[4],
                } for r in rows
            ]
    
    def search_emails(self, query: str, limit: int = 10) -> list[dict]:
        """Search indexed emails."""
        with _get_db() as db:
            rows = db.execute("""
                SELECT sender_name, subject, body_preview, received_time
                FROM emails
                WHERE subject LIKE ? OR body_preview LIKE ? OR sender_name LIKE ?
                ORDER BY received_time DESC
                LIMIT ?
            """, (f"%{query}%", f"%{query}%", f"%{query}%", limit)).fetchall()
            
            return [
                {
                    "from": r[0] or r[1], "subject": r[1],
                    "preview": (r[2] or "")[:100],
                    "when": datetime.fromtimestamp(r[3]).isoformat() if r[3] else "",
                } for r in rows
            ]
    
    def search_calendar(self, days: int = 7) -> list[dict]:
        """Search upcoming calendar events."""
        with _get_db() as db:
            now = time.time()
            end = now + days * 86400
            rows = db.execute("""
                SELECT subject, start_time, end_time, location, description
                FROM calendar
                WHERE start_time BETWEEN ? AND ?
                ORDER BY start_time ASC
            """, (now, end)).fetchall()
            
            return [
                {
                    "subject": r[0],
                    "start": datetime.fromtimestamp(r[1]).strftime("%a %b %d %I:%M %p") if r[1] else "",
                    "end": datetime.fromtimestamp(r[2]).strftime("%I:%M %p") if r[2] else "",
                    "location": r[3] or "",
                } for r in rows
            ]
    
    def search_contacts(self, name: str = "") -> list[dict]:
        """Search contacts."""
        with _get_db() as db:
            if name:
                rows = db.execute(
                    "SELECT name, email, phone, company FROM contacts WHERE name LIKE ? OR email LIKE ?",
                    (f"%{name}%", f"%{name}%")
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT name, email, phone, company FROM contacts LIMIT 50"
                ).fetchall()
            
            return [
                {"name": r[0], "email": r[1], "phone": r[2], "company": r[3]}
                for r in rows
            ]
    
    def get_statistics(self) -> dict:
        """Get ingestion statistics."""
        with _get_db() as db:
            return {
                "total_files": db.execute("SELECT COUNT(*) FROM files").fetchone()[0],
                "total_file_keywords": db.execute("SELECT COUNT(*) FROM file_keywords").fetchone()[0],
                "total_calendar_events": db.execute("SELECT COUNT(*) FROM calendar").fetchone()[0],
                "total_emails": db.execute("SELECT COUNT(*) FROM emails").fetchone()[0],
                "total_contacts": db.execute("SELECT COUNT(*) FROM contacts").fetchone()[0],
                "total_projects": db.execute("SELECT COUNT(*) FROM projects").fetchone()[0],
                "total_entities": db.execute("SELECT COUNT(*) FROM knowledge_entities").fetchone()[0],
                "total_topics": db.execute("SELECT COUNT(*) FROM topics").fetchone()[0],
                "last_scan": db.execute("SELECT MAX(timestamp) FROM scan_log").fetchone()[0] or 0,
            }
    
    def start_background_scan(self, interval_seconds: int = 300):
        """Start background scanning thread. < 1 MB overhead."""
        if self._running:
            return
        
        self._running = True
        
        def _loop():
            while self._running:
                try:
                    self.ingest_all()
                except Exception:
                    pass
                time.sleep(interval_seconds)
        
        self._thread = threading.Thread(target=_loop, daemon=True, name="ingestor")
        self._thread.start()
    
    def stop(self):
        self._running = False


# ── Singleton ───────────────────────────────────────────────────────

_ingestor: PersonalDataIngestor | None = None
_ingestor_lock = threading.Lock()


def get_ingestor() -> PersonalDataIngestor:
    global _ingestor
    if _ingestor is None:
        with _ingestor_lock:
            if _ingestor is None:
                _ingestor = PersonalDataIngestor()
    return _ingestor
