"""JARVIS Universal Action Fabric — Composable Primitives.

This is the fundamental architecture that makes arbitrary tasks achievable.

Instead of hard-coded tasks, JARVIS has a small set of extremely reliable
PRIMITIVES from which it can construct almost any workflow.

    find → identify → authorize → transfer → verify → report

Every primitive has:
  - PRECONDITIONS (what must be true before)
  - ACTION (what to do)
  - POSTCONDITIONS (what must be true after)

The model generates the plan.
The executor executes it.
Verification confirms it happened.

That separation is the key to reliability.

ARCHITECTURE:

    USER
      │
      ▼
    NATURAL LANGUAGE
      │
      ▼
    INTENT RESOLVER
      │
      ▼
    OBJECT RESOLVER
      │
      ▼
    MISSION PLANNER
      │
      ▼
    EXECUTION GRAPH (primitives)
      │
      ▼
    CAPABILITY FABRIC
      │
      ▼
    OBSERVE → VERIFY → RESULT/RECOVER
"""

import os
import sys
import json
import time
import hashlib
import logging
import shutil
import mimetypes
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from abc import ABC, abstractmethod

log = logging.getLogger("action_fabric")


# ══════════════════════════════════════════════════════════════
#  PRIMITIVE CATEGORIES
# ══════════════════════════════════════════════════════════════

class PrimitiveCategory(Enum):
    COMPUTER = "computer"
    FILESYSTEM = "filesystem"
    BROWSER = "browser"
    WORKSPACE = "workspace"
    APPLICATION = "application"
    MISSION = "mission"
    TRANSFER = "transfer"


# ══════════════════════════════════════════════════════════════
#  OBJECT MODEL — Identity for Everything
# ══════════════════════════════════════════════════════════════

class ObjectType(Enum):
    FILE = "file"
    DIRECTORY = "directory"
    WINDOW = "window"
    APPLICATION = "application"
    BROWSER_TAB = "browser_tab"
    WEB_PAGE = "web_page"
    WORKSPACE = "workspace"
    MISSION = "mission"
    EMAIL = "email"
    IMAGE = "image"
    VIDEO = "video"
    SPREADSHEET = "spreadsheet"
    DOCUMENT = "document"
    PROCESS = "process"
    DEVICE = "device"
    CLIPBOARD = "clipboard"
    UNKNOWN = "unknown"


@dataclass
class JarvObject:
    """Universal object identity.

    Every object JARVIS can perceive or manipulate gets an identity.
    This enables reasoning about relationships and references.
    """
    id: str
    type: ObjectType
    name: str
    uri: str  # jarvis:// URI
    location: str = ""
    mime_type: str = ""
    size_bytes: int = 0
    created_at: float = 0
    modified_at: float = 0
    hash: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    parent_id: str = ""
    children_ids: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    accessible: bool = True
    verified: bool = False

    def to_dict(self) -> dict:
        d = asdict(self)
        d["type"] = self.type.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "JarvObject":
        d["type"] = ObjectType(d.get("type", "unknown"))
        return cls(**d)


def create_object(object_type: ObjectType, name: str, uri: str,
                 **kwargs) -> JarvObject:
    """Create a new object with auto-generated ID."""
    obj_id = f"obj_{object_type.value}_{int(time.time() * 1000)}"
    return JarvObject(
        id=obj_id,
        type=object_type,
        name=name,
        uri=uri,
        **kwargs,
    )


# ══════════════════════════════════════════════════════════════
#  UNIVERSAL LOCATOR — jarvis:// Namespace
# ══════════════════════════════════════════════════════════════

class UniversalLocator:
    """Universal URI system for all resources.

    Every resource gets a jarvis:// URI that works regardless of
    the underlying OS or environment.

    Examples:
        jarvis://user/desktop/report.docx
        jarvis://user/documents/
        jarvis://workspace/mission-123/project/
        jarvis://workspace/mission-123/downloads/image.png
        jarvis://browser/tab/active
        jarvis://browser/tab/12345
        jarvis://application/blender
        jarvis://process/chrome
        jarvis://clipboard/current
    """

    SCHEMES = {
        "user",      # User's computer files
        "workspace", # Mission workspace files
        "browser",   # Browser tabs/pages
        "application", # Applications
        "process",   # Running processes
        "clipboard", # Clipboard content
        "device",    # Connected devices
    }

    @staticmethod
    def resolve(uri: str) -> str:
        """Resolve a jarvis:// URI to an actual filesystem path or handle.

        Translates:
            jarvis://user/desktop/report.docx → C:\Users\User\Desktop\report.docx
            jarvis://workspace/mission-123/report.docx → ~/.jarvis/mission_worlds/mission-123/files/report.docx
        """
        if not uri.startswith("jarvis://"):
            return uri  # Already a real path

        parts = uri.replace("jarvis://", "").split("/", 1)
        scheme = parts[0] if parts else ""
        path = parts[1] if len(parts) > 1 else ""

        if scheme == "user":
            return UniversalLocator._resolve_user_path(path)
        elif scheme == "workspace":
            return UniversalLocator._resolve_workspace_path(path)
        elif scheme in ("browser", "application", "process", "clipboard", "device"):
            return uri  # These are handles, not filesystem paths
        else:
            return uri

    @staticmethod
    def _resolve_user_path(path: str) -> str:
        """Resolve user:// paths to actual OS paths."""
        home = os.path.expanduser("~")
        path_map = {
            "desktop": os.path.join(home, "Desktop"),
            "documents": os.path.join(home, "Documents"),
            "downloads": os.path.join(home, "Downloads"),
            "pictures": os.path.join(home, "Pictures"),
            "videos": os.path.join(home, "Videos"),
            "music": os.path.join(home, "Music"),
            "home": home,
        }
        parts = path.split("/", 1)
        base = path_map.get(parts[0].lower(), home)
        remainder = parts[1] if len(parts) > 1 else ""
        return os.path.join(base, remainder) if remainder else base

    @staticmethod
    def _resolve_workspace_path(path: str) -> str:
        """Resolve workspace:// paths to actual workspace directories."""
        worlds_dir = os.path.expanduser("~/.jarvis/mission_worlds")
        parts = path.split("/", 1)
        world_id = parts[0] if parts else ""
        remainder = parts[1] if len(parts) > 1 else "files"
        return os.path.join(worlds_dir, world_id, remainder)

    @staticmethod
    def create_uri(scheme: str, *parts) -> str:
        """Create a jarvis:// URI."""
        path = "/".join(str(p) for p in parts if p)
        return f"jarvis://{scheme}/{path}"

    @staticmethod
    def detect_scheme(path: str) -> str:
        """Detect the scheme for a given path."""
        if path.startswith("jarvis://"):
            return path.split("://")[1].split("/")[0]
        home = os.path.expanduser("~")
        if path.startswith(home):
            return "user"
        worlds_dir = os.path.expanduser("~/.jarvis/mission_worlds")
        if path.startswith(worlds_dir):
            return "workspace"
        return "user"


# ══════════════════════════════════════════════════════════════
#  OBJECT RESOLVER — Natural Language to Object
# ══════════════════════════════════════════════════════════════

class ObjectResolver:
    """Resolves natural-language references to concrete objects.

    "the Word document I made earlier" → BusinessPlan.docx
    "that Chrome tab with hotel prices" → browser tab
    "the Blender project from yesterday" → project file
    """

    def __init__(self):
        self._object_index: Dict[str, JarvObject] = {}

    def index_object(self, obj: JarvObject):
        """Add an object to the searchable index."""
        self._object_index[obj.id] = obj
        # Index by name variants
        self._object_index[obj.name.lower()] = obj
        # Index by type
        type_key = f"type:{obj.type.value}"
        if type_key not in self._object_index:
            self._object_index[type_key] = []
        if isinstance(self._object_index[type_key], list):
            self._object_index[type_key].append(obj)

    def resolve(self, reference: str, context: Dict[str, Any] = None) -> List[JarvObject]:
        """Resolve a natural-language reference to candidate objects.

        Returns ranked list of candidates. If only one, it's unambiguous.
        """
        ref_lower = reference.lower().strip()
        candidates = []

        # Direct name match
        for key, obj in self._object_index.items():
            if isinstance(obj, JarvObject) and ref_lower in obj.name.lower():
                candidates.append(obj)

        # Type-based matching
        type_hints = {
            "word document": ObjectType.DOCUMENT,
            "docx": ObjectType.DOCUMENT,
            "doc": ObjectType.DOCUMENT,
            "spreadsheet": ObjectType.SPREADSHEET,
            "xlsx": ObjectType.SPREADSHEET,
            "excel": ObjectType.SPREADSHEET,
            "image": ObjectType.IMAGE,
            "png": ObjectType.IMAGE,
            "jpg": ObjectType.IMAGE,
            "jpeg": ObjectType.IMAGE,
            "video": ObjectType.VIDEO,
            "mp4": ObjectType.VIDEO,
            "presentation": ObjectType.DOCUMENT,
            "powerpoint": ObjectType.DOCUMENT,
            "pptx": ObjectType.DOCUMENT,
        }
        for hint, obj_type in type_hints.items():
            if hint in ref_lower:
                type_key = f"type:{obj_type.value}"
                if type_key in self._object_index:
                    type_objects = self._object_index[type_key]
                    if isinstance(type_objects, list):
                        candidates.extend(type_objects)

        # Context-based filtering
        if context:
            if "workspace_id" in context:
                ws_id = context["workspace_id"]
                candidates = [c for c in candidates
                            if ws_id in c.uri or "workspace" in c.uri]
            if "recent" in context:
                candidates.sort(key=lambda c: c.modified_at, reverse=True)

        # Deduplicate
        seen = set()
        unique = []
        for c in candidates:
            if c.id not in seen:
                seen.add(c.id)
                unique.append(c)

        return unique[:10]  # Top 10 candidates

    def resolve_single(self, reference: str, context: Dict[str, Any] = None) -> Optional[JarvObject]:
        """Resolve to a single object. Returns None if ambiguous."""
        candidates = self.resolve(reference, context)
        if len(candidates) == 1:
            return candidates[0]
        return None

    def index_workspace(self, workspace_dir: str):
        """Index all files in a workspace."""
        workspace_path = Path(workspace_dir)
        if not workspace_path.exists():
            return

        for f in workspace_path.rglob("*"):
            if f.is_file():
                mime = mimetypes.guess_type(str(f))[0] or ""
                obj_type = self._mime_to_type(mime, f.suffix)
                uri = UniversalLocator.create_uri(
                    "workspace",
                    f.parent.name,
                    str(f.relative_to(workspace_path.parent))
                )
                stat = f.stat()
                obj = JarvObject(
                    id=f"obj_file_{hashlib.md5(str(f).encode()).hexdigest()[:8]}",
                    type=obj_type,
                    name=f.name,
                    uri=uri,
                    location=str(f),
                    mime_type=mime,
                    size_bytes=stat.st_size,
                    modified_at=stat.st_mtime,
                )
                self.index_object(obj)

    def index_user_directory(self, directory: str):
        """Index files in a user directory."""
        dir_path = Path(directory)
        if not dir_path.exists():
            return

        for f in dir_path.iterdir():
            if f.is_file():
                mime = mimetypes.guess_type(str(f))[0] or ""
                obj_type = self._mime_to_type(mime, f.suffix)
                uri = UniversalLocator.create_uri(
                    "user",
                    dir_path.name,
                    f.name
                )
                stat = f.stat()
                obj = JarvObject(
                    id=f"obj_file_{hashlib.md5(str(f).encode()).hexdigest()[:8]}",
                    type=obj_type,
                    name=f.name,
                    uri=uri,
                    location=str(f),
                    mime_type=mime,
                    size_bytes=stat.st_size,
                    modified_at=stat.st_mtime,
                )
                self.index_object(obj)

    def _mime_to_type(self, mime: str, ext: str) -> ObjectType:
        """Map MIME type or extension to ObjectType."""
        if "image" in mime:
            return ObjectType.IMAGE
        if "video" in mime:
            return ObjectType.VIDEO
        if "spreadsheet" in mime or ext in (".xlsx", ".xls", ".csv"):
            return ObjectType.SPREADSHEET
        if "pdf" in mime or ext == ".pdf":
            return ObjectType.DOCUMENT
        if ext in (".docx", ".doc", ".odt", ".rtf"):
            return ObjectType.DOCUMENT
        if ext in (".pptx", ".ppt", ".odp"):
            return ObjectType.DOCUMENT
        if mime.startswith("text/"):
            return ObjectType.FILE
        return ObjectType.FILE


# ══════════════════════════════════════════════════════════════
#  PRECONDITION / POSTCONDITION CONTRACTS
# ══════════════════════════════════════════════════════════════

@dataclass
class Contract:
    """Precondition + Postcondition contract for a primitive action."""
    preconditions: List[str] = field(default_factory=list)
    postconditions: List[str] = field(default_factory=list)
    invariants: List[str] = field(default_factory=list)  # Must always be true

    def to_dict(self) -> dict:
        return asdict(self)


# ══════════════════════════════════════════════════════════════
#  VERIFICATION ENGINE
# ══════════════════════════════════════════════════════════════

@dataclass
class VerificationResult:
    """Result of a verification check."""
    passed: bool
    condition: str
    expected: str = ""
    actual: str = ""
    method: str = ""
    confidence: float = 1.0
    details: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class VerificationEngine:
    """Universal verification engine.

    Every meaningful action produces:
        ACTION → OBSERVATION → VERIFICATION

    Example:
        COPY report.docx → Check destination → File exists? Size matches? Hash matches?
    """

    def verify_file_exists(self, path: str) -> VerificationResult:
        """Verify a file exists at the given path."""
        exists = os.path.exists(path)
        return VerificationResult(
            passed=exists,
            condition="file_exists",
            expected=path,
            actual="exists" if exists else "not found",
            method="os.path.exists",
        )

    def verify_file_size(self, path: str, expected_size: int) -> VerificationResult:
        """Verify a file has the expected size."""
        if not os.path.exists(path):
            return VerificationResult(
                passed=False, condition="file_size",
                expected=str(expected_size), actual="file not found",
            )
        actual_size = os.path.getsize(path)
        passed = actual_size == expected_size
        return VerificationResult(
            passed=passed,
            condition="file_size",
            expected=str(expected_size),
            actual=str(actual_size),
            method="os.path.getsize",
        )

    def verify_file_hash(self, path: str, expected_hash: str) -> VerificationResult:
        """Verify a file has the expected hash."""
        if not os.path.exists(path):
            return VerificationResult(
                passed=False, condition="file_hash",
                expected=expected_hash, actual="file not found",
            )
        with open(path, "rb") as f:
            actual_hash = hashlib.md5(f.read()).hexdigest()
        passed = actual_hash == expected_hash
        return VerificationResult(
            passed=passed,
            condition="file_hash",
            expected=expected_hash,
            actual=actual_hash,
            method="md5",
        )

    def verify_directory_exists(self, path: str) -> VerificationResult:
        """Verify a directory exists."""
        exists = os.path.isdir(path)
        return VerificationResult(
            passed=exists,
            condition="directory_exists",
            expected=path,
            actual="exists" if exists else "not found",
            method="os.path.isdir",
        )

    def verify_process_running(self, name: str) -> VerificationResult:
        """Verify a process is running."""
        try:
            import subprocess
            if sys.platform == "win32":
                result = subprocess.run(
                    ["tasklist", "/FI", f"IMAGENAME eq {name}.exe"],
                    capture_output=True, text=True, timeout=5
                )
                running = name.lower() in result.stdout.lower()
            else:
                result = subprocess.run(
                    ["pgrep", "-f", name],
                    capture_output=True, text=True, timeout=5
                )
                running = result.returncode == 0
            return VerificationResult(
                passed=running,
                condition="process_running",
                expected=name,
                actual="running" if running else "not running",
                method="tasklist/pgrep",
            )
        except Exception as e:
            return VerificationResult(
                passed=False, condition="process_running",
                expected=name, actual=f"check failed: {e}",
            )

    def verify_window_exists(self, title_substring: str) -> VerificationResult:
        """Verify a window with the given title exists."""
        try:
            from capability_fabric import get_capability_fabric
            fabric = get_capability_fabric()
            result = fabric.computer.list_windows()
            if result.ok:
                for w in result.data:
                    if title_substring.lower() in w.title.lower():
                        return VerificationResult(
                            passed=True, condition="window_exists",
                            expected=title_substring, actual=f"found: {w.title}",
                        )
            return VerificationResult(
                passed=False, condition="window_exists",
                expected=title_substring, actual="not found",
            )
        except Exception as e:
            return VerificationResult(
                passed=False, condition="window_exists",
                expected=title_substring, actual=f"check failed: {e}",
            )

    def verify_url_accessible(self, url: str) -> VerificationResult:
        """Verify a URL is accessible."""
        try:
            import urllib.request
            req = urllib.request.Request(url, method="HEAD")
            urllib.request.urlopen(req, timeout=10)
            return VerificationResult(
                passed=True, condition="url_accessible",
                expected=url, actual="accessible",
            )
        except Exception as e:
            return VerificationResult(
                passed=False, condition="url_accessible",
                expected=url, actual=f"not accessible: {e}",
            )

    def verify_text_content(self, path: str, expected_text: str) -> VerificationResult:
        """Verify a file contains expected text."""
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            found = expected_text in content
            return VerificationResult(
                passed=found, condition="text_content",
                expected=expected_text[:100],
                actual="found" if found else "not found",
            )
        except Exception as e:
            return VerificationResult(
                passed=False, condition="text_content",
                expected=expected_text[:100], actual=f"read failed: {e}",
            )

    def verify(self, condition: str, **kwargs) -> VerificationResult:
        """Generic verification dispatcher."""
        verifiers = {
            "file_exists": lambda: self.verify_file_exists(kwargs.get("path", "")),
            "file_size": lambda: self.verify_file_size(kwargs.get("path", ""), kwargs.get("size", 0)),
            "file_hash": lambda: self.verify_file_hash(kwargs.get("path", ""), kwargs.get("hash", "")),
            "directory_exists": lambda: self.verify_directory_exists(kwargs.get("path", "")),
            "process_running": lambda: self.verify_process_running(kwargs.get("name", "")),
            "window_exists": lambda: self.verify_window_exists(kwargs.get("title", "")),
            "url_accessible": lambda: self.verify_url_accessible(kwargs.get("url", "")),
            "text_content": lambda: self.verify_text_content(kwargs.get("path", ""), kwargs.get("text", "")),
        }
        verifier = verifiers.get(condition)
        if verifier:
            return verifier()
        return VerificationResult(
            passed=False, condition=condition,
            actual=f"unknown condition: {condition}",
        )


# ══════════════════════════════════════════════════════════════
#  UNIVERSAL ACTION PRIMITIVES
# ══════════════════════════════════════════════════════════════

@dataclass
class PrimitiveResult:
    """Result of executing a primitive action."""
    ok: bool
    data: Any = None
    error: str = ""
    verification: Optional[VerificationResult] = None
    duration_ms: float = 0

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "data": self.data,
            "error": self.error,
            "verification": self.verification.to_dict() if self.verification else None,
            "duration_ms": self.duration_ms,
        }


class ActionPrimitive(ABC):
    """Base class for all action primitives."""

    name: str = "base"
    category: PrimitiveCategory = PrimitiveCategory.COMPUTER
    contract: Contract = Contract()

    @abstractmethod
    def execute(self, **kwargs) -> PrimitiveResult:
        """Execute the primitive action."""
        ...

    def verify_postconditions(self, **kwargs) -> VerificationResult:
        """Verify postconditions after execution."""
        return VerificationResult(passed=True, condition="default")


# ── FILESYSTEM PRIMITIVES ──

class FindPrimitive(ActionPrimitive):
    """FIND — Locate objects by reference."""
    name = "find"
    category = PrimitiveCategory.TRANSFER

    def execute(self, reference: str = "", pattern: str = "",
               path: str = "", **kwargs) -> PrimitiveResult:
        import time as _time
        start = _time.time()

        if pattern:
            # Glob search
            matches = list(Path(path or ".").glob(pattern))
            objects = []
            for m in matches:
                mime = mimetypes.guess_type(str(m))[0] or ""
                objects.append({
                    "name": m.name,
                    "path": str(m),
                    "is_dir": m.is_dir(),
                    "size": m.stat().st_size if m.is_file() else 0,
                    "mime": mime,
                })
            return PrimitiveResult(
                ok=True, data=objects,
                duration_ms=(_time.time() - start) * 1000,
            )

        elif reference:
            # Object resolver
            resolver = ObjectResolver()
            candidates = resolver.resolve(reference)
            if candidates:
                return PrimitiveResult(
                    ok=True,
                    data=[c.to_dict() for c in candidates],
                    duration_ms=(_time.time() - start) * 1000,
                )

        return PrimitiveResult(ok=False, error="No reference or pattern provided")


class CopyPrimitive(ActionPrimitive):
    """COPY — Copy a file or directory."""
    name = "copy"
    category = PrimitiveCategory.FILESYSTEM
    contract = Contract(
        preconditions=["source exists", "source is readable", "destination permitted"],
        postconditions=["destination exists", "destination size == source size"],
    )

    def execute(self, source: str = "", destination: str = "",
               overwrite: bool = True, **kwargs) -> PrimitiveResult:
        import time as _time
        start = _time.time()
        verifier = VerificationEngine()

        # Resolve URIs
        source = UniversalLocator.resolve(source)
        destination = UniversalLocator.resolve(destination)

        # Preconditions
        if not os.path.exists(source):
            return PrimitiveResult(ok=False, error=f"Source not found: {source}")

        try:
            if os.path.isdir(source):
                shutil.copytree(source, destination, dirs_exist_ok=overwrite)
            else:
                os.makedirs(os.path.dirname(destination), exist_ok=True)
                shutil.copy2(source, destination)

            # Verify
            verification = verifier.verify_file_exists(destination)
            if verification.passed and os.path.isfile(source):
                size_v = verifier.verify_file_size(destination, os.path.getsize(source))
                verification = size_v

            return PrimitiveResult(
                ok=True, data={"source": source, "destination": destination},
                verification=verification,
                duration_ms=(_time.time() - start) * 1000,
            )
        except Exception as e:
            return PrimitiveResult(ok=False, error=str(e))


class MovePrimitive(ActionPrimitive):
    """MOVE — Move a file or directory."""
    name = "move"
    category = PrimitiveCategory.FILESYSTEM
    contract = Contract(
        preconditions=["source exists", "destination permitted"],
        postconditions=["source gone", "destination exists"],
    )

    def execute(self, source: str = "", destination: str = "",
               **kwargs) -> PrimitiveResult:
        import time as _time
        start = _time.time()
        verifier = VerificationEngine()

        source = UniversalLocator.resolve(source)
        destination = UniversalLocator.resolve(destination)

        if not os.path.exists(source):
            return PrimitiveResult(ok=False, error=f"Source not found: {source}")

        try:
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            shutil.move(source, destination)

            verification = verifier.verify_file_exists(destination)
            return PrimitiveResult(
                ok=True, data={"source": source, "destination": destination},
                verification=verification,
                duration_ms=(_time.time() - start) * 1000,
            )
        except Exception as e:
            return PrimitiveResult(ok=False, error=str(e))


class DeletePrimitive(ActionPrimitive):
    """DELETE — Remove a file or directory."""
    name = "delete"
    category = PrimitiveCategory.FILESYSTEM
    contract = Contract(
        preconditions=["target exists"],
        postconditions=["target gone"],
    )

    def execute(self, path: str = "", **kwargs) -> PrimitiveResult:
        import time as _time
        start = _time.time()

        path = UniversalLocator.resolve(path)

        if not os.path.exists(path):
            return PrimitiveResult(ok=False, error=f"Not found: {path}")

        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)

            verification = VerificationEngine().verify_file_exists(path)
            # For delete, we expect it to NOT exist
            verification.passed = not verification.passed
            verification.actual = "deleted" if verification.passed else "still exists"

            return PrimitiveResult(
                ok=True, data={"deleted": path},
                verification=verification,
                duration_ms=(_time.time() - start) * 1000,
            )
        except Exception as e:
            return PrimitiveResult(ok=False, error=str(e))


class ReadFilePrimitive(ActionPrimitive):
    """READ — Read file contents."""
    name = "read_file"
    category = PrimitiveCategory.FILESYSTEM

    def execute(self, path: str = "", **kwargs) -> PrimitiveResult:
        import time as _time
        start = _time.time()

        path = UniversalLocator.resolve(path)

        if not os.path.exists(path):
            return PrimitiveResult(ok=False, error=f"Not found: {path}")

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            return PrimitiveResult(
                ok=True, data=content,
                duration_ms=(_time.time() - start) * 1000,
            )
        except Exception as e:
            return PrimitiveResult(ok=False, error=str(e))


class WriteFilePrimitive(ActionPrimitive):
    """WRITE — Write file contents."""
    name = "write_file"
    category = PrimitiveCategory.FILESYSTEM
    contract = Contract(
        preconditions=["destination directory permitted"],
        postconditions=["file exists", "content matches"],
    )

    def execute(self, path: str = "", content: str = "",
               create_dirs: bool = True, **kwargs) -> PrimitiveResult:
        import time as _time
        start = _time.time()

        path = UniversalLocator.resolve(path)

        try:
            if create_dirs:
                os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

            verification = VerificationEngine().verify_file_exists(path)
            return PrimitiveResult(
                ok=True, data={"path": path, "bytes_written": len(content.encode())},
                verification=verification,
                duration_ms=(_time.time() - start) * 1000,
            )
        except Exception as e:
            return PrimitiveResult(ok=False, error=str(e))


class SearchFilesPrimitive(ActionPrimitive):
    """SEARCH — Search for files matching criteria."""
    name = "search_files"
    category = PrimitiveCategory.FILESYSTEM

    def execute(self, path: str = "", pattern: str = "",
               contains_text: str = "", max_results: int = 50,
               **kwargs) -> PrimitiveResult:
        import time as _time
        start = _time.time()

        path = UniversalLocator.resolve(path or ".")
        results = []

        try:
            search_path = Path(path)
            for f in search_path.rglob(pattern or "*"):
                if f.is_file() and len(results) < max_results:
                    if contains_text:
                        try:
                            with open(f, "r", encoding="utf-8", errors="replace") as fh:
                                if contains_text in fh.read():
                                    results.append(str(f))
                        except Exception:
                            pass
                    else:
                        results.append(str(f))

            return PrimitiveResult(
                ok=True, data=results,
                duration_ms=(_time.time() - start) * 1000,
            )
        except Exception as e:
            return PrimitiveResult(ok=False, error=str(e))


# ── COMPUTER PRIMITIVES ──

class ClickPrimitive(ActionPrimitive):
    """CLICK — Click at coordinates or on element."""
    name = "click"
    category = PrimitiveCategory.COMPUTER

    def execute(self, x: int = 0, y: int = 0, button: str = "left",
               element: str = "", **kwargs) -> PrimitiveResult:
        import time as _time
        start = _time.time()

        try:
            from capability_fabric import get_capability_fabric
            fabric = get_capability_fabric()

            if element:
                # Try browser first
                if fabric._browser:
                    result = fabric.browser.click_text(element)
                    return PrimitiveResult(ok=result.ok, error=result.error,
                                         duration_ms=(_time.time() - start) * 1000)

            if x and y:
                result = fabric.computer.click(x, y, button)
                return PrimitiveResult(ok=result.ok, error=result.error,
                                     duration_ms=(_time.time() - start) * 1000)

            return PrimitiveResult(ok=False, error="No coordinates or element specified")
        except Exception as e:
            return PrimitiveResult(ok=False, error=str(e))


class TypePrimitive(ActionPrimitive):
    """TYPE — Type text."""
    name = "type"
    category = PrimitiveCategory.COMPUTER

    def execute(self, text: str = "", target: str = "", **kwargs) -> PrimitiveResult:
        import time as _time
        start = _time.time()

        try:
            from capability_fabric import get_capability_fabric
            fabric = get_capability_fabric()

            if target and fabric._browser:
                result = fabric.browser.type_into(target, text)
            else:
                result = fabric.computer.type_text(text)

            return PrimitiveResult(ok=result.ok, error=result.error,
                                 duration_ms=(_time.time() - start) * 1000)
        except Exception as e:
            return PrimitiveResult(ok=False, error=str(e))


class ScreenshotPrimitive(ActionPrimitive):
    """SCREENSHOT — Capture the screen."""
    name = "screenshot"
    category = PrimitiveCategory.COMPUTER

    def execute(self, save_path: str = "", **kwargs) -> PrimitiveResult:
        import time as _time
        start = _time.time()

        try:
            from capability_fabric import get_capability_fabric
            fabric = get_capability_fabric()
            result = fabric.computer.screenshot()

            if result.ok and save_path and result.data:
                save_path = UniversalLocator.resolve(save_path)
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                with open(save_path, "wb") as f:
                    f.write(result.data)

            return PrimitiveResult(
                ok=result.ok, data=result.data,
                error=result.error,
                duration_ms=(_time.time() - start) * 1000,
            )
        except Exception as e:
            return PrimitiveResult(ok=False, error=str(e))


class LaunchPrimitive(ActionPrimitive):
    """LAUNCH — Start an application."""
    name = "launch"
    category = PrimitiveCategory.APPLICATION
    contract = Contract(
        preconditions=["application available"],
        postconditions=["process running", "window exists"],
    )

    def execute(self, app: str = "", args: List[str] = None,
               url: str = "", **kwargs) -> PrimitiveResult:
        import time as _time
        start = _time.time()

        try:
            from capability_fabric import get_capability_fabric
            fabric = get_capability_fabric()

            if url:
                result = fabric.browser.navigate(url)
            elif app:
                result = fabric.app.launch(app, args)
            else:
                return PrimitiveResult(ok=False, error="No app or URL specified")

            # Verify
            verification = None
            if app:
                verification = VerificationEngine().verify_process_running(app)

            return PrimitiveResult(
                ok=result.ok, error=result.error,
                verification=verification,
                duration_ms=(_time.time() - start) * 1000,
            )
        except Exception as e:
            return PrimitiveResult(ok=False, error=str(e))


class ExecutePrimitive(ActionPrimitive):
    """EXECUTE — Run a shell command."""
    name = "execute"
    category = PrimitiveCategory.FILESYSTEM

    def execute(self, command: str = "", timeout: int = 30,
               **kwargs) -> PrimitiveResult:
        import time as _time
        start = _time.time()

        try:
            from capability_fabric import get_capability_fabric
            fabric = get_capability_fabric()
            result = fabric.computer.execute_command(command, timeout)

            return PrimitiveResult(
                ok=result.ok, data=result.data,
                error=result.error,
                duration_ms=(_time.time() - start) * 1000,
            )
        except Exception as e:
            return PrimitiveResult(ok=False, error=str(e))


class NavigatePrimitive(ActionPrimitive):
    """NAVIGATE — Open a URL in the browser."""
    name = "navigate"
    category = PrimitiveCategory.BROWSER

    def execute(self, url: str = "", **kwargs) -> PrimitiveResult:
        import time as _time
        start = _time.time()

        try:
            from capability_fabric import get_capability_fabric
            fabric = get_capability_fabric()
            result = fabric.browser.navigate(url)

            verification = VerificationEngine().verify_url_accessible(url) if url else None

            return PrimitiveResult(
                ok=result.ok, error=result.error,
                verification=verification,
                duration_ms=(_time.time() - start) * 1000,
            )
        except Exception as e:
            return PrimitiveResult(ok=False, error=str(e))


class ExtractPrimitive(ActionPrimitive):
    """EXTRACT — Extract text/data from browser page."""
    name = "extract"
    category = PrimitiveCategory.BROWSER

    def execute(self, selector: str = "", mode: str = "text",
               **kwargs) -> PrimitiveResult:
        import time as _time
        start = _time.time()

        try:
            from capability_fabric import get_capability_fabric
            fabric = get_capability_fabric()

            if mode == "links":
                result = fabric.browser.extract_links()
            elif mode == "dom":
                result = fabric.browser.get_dom()
            elif selector:
                result = fabric.browser.execute_js(
                    f"document.querySelector('{selector}')?.innerText"
                )
            else:
                result = fabric.browser.get_text()

            return PrimitiveResult(
                ok=result.ok, data=result.data,
                error=result.error,
                duration_ms=(_time.time() - start) * 1000,
            )
        except Exception as e:
            return PrimitiveResult(ok=False, error=str(e))


class InspectPrimitive(ActionPrimitive):
    """INSPECT — Get detailed information about an object."""
    name = "inspect"
    category = PrimitiveCategory.COMPUTER

    def execute(self, target: str = "", **kwargs) -> PrimitiveResult:
        import time as _time
        start = _time.time()

        result = {"target": target}

        # File inspection
        path = UniversalLocator.resolve(target) if "://" in target else target
        if os.path.exists(path):
            stat = os.stat(path)
            result.update({
                "type": "file" if os.path.isfile(path) else "directory",
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "created": stat.st_ctime,
                "readable": os.access(path, os.R_OK),
                "writable": os.access(path, os.W_OK),
            })
            mime = mimetypes.guess_type(path)[0]
            if mime:
                result["mime"] = mime

        return PrimitiveResult(
            ok=True, data=result,
            duration_ms=(_time.time() - start) * 1000,
        )


class WaitPrimitive(ActionPrimitive):
    """WAIT — Wait for a condition or duration."""
    name = "wait"
    category = PrimitiveCategory.MISSION

    def execute(self, seconds: float = 1, condition: str = "",
               timeout: float = 30, **kwargs) -> PrimitiveResult:
        import time as _time
        start = _time.time()

        if condition:
            # Wait for condition
            verifier = VerificationEngine()
            elapsed = 0
            while elapsed < timeout:
                parts = condition.split("=", 1)
                cond_name = parts[0].strip()
                cond_params = {}
                if len(parts) > 1:
                    # Parse key=value pairs
                    for kv in parts[1].split(","):
                        k, v = kv.split("=", 1) if "=" in kv else (kv, "")
                        cond_params[k.strip()] = v.strip()

                result = verifier.verify(cond_name, **cond_params)
                if result.passed:
                    return PrimitiveResult(
                        ok=True, data=f"Condition met after {elapsed:.1f}s",
                        duration_ms=(_time.time() - start) * 1000,
                    )
                _time.sleep(1)
                elapsed += 1

            return PrimitiveResult(
                ok=False, error=f"Timeout waiting for: {condition}",
                duration_ms=(_time.time() - start) * 1000,
            )
        else:
            # Simple sleep
            _time.sleep(seconds)
            return PrimitiveResult(
                ok=True, data=f"Waited {seconds}s",
                duration_ms=(_time.time() - start) * 1000,
            )


# ══════════════════════════════════════════════════════════════
#  TRANSFER PRIMITIVE (Universal)
# ══════════════════════════════════════════════════════════════

class TransferPrimitive(ActionPrimitive):
    """TRANSFER — Move any object between any locations.

    The universal primitive for moving things:
        workspace → user desktop
        user desktop → workspace
        workspace A → workspace B
        browser → file
        file → email
    """
    name = "transfer"
    category = PrimitiveCategory.TRANSFER
    contract = Contract(
        preconditions=["source exists", "source accessible", "destination permitted"],
        postconditions=["destination exists", "destination verified"],
    )

    def execute(self, source: str = "", destination: str = "",
               verify: bool = True, **kwargs) -> PrimitiveResult:
        import time as _time
        start = _time.time()
        verifier = VerificationEngine()

        # Resolve URIs
        source_path = UniversalLocator.resolve(source)
        dest_path = UniversalLocator.resolve(destination)

        # Preconditions
        if not os.path.exists(source_path):
            return PrimitiveResult(ok=False, error=f"Source not found: {source}")

        try:
            # Ensure destination directory exists
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)

            # Perform transfer
            if os.path.isdir(source_path):
                shutil.copytree(source_path, dest_path, dirs_exist_ok=True)
            else:
                shutil.copy2(source_path, dest_path)

            # Verify
            verification = None
            if verify:
                verification = verifier.verify_file_exists(dest_path)
                if verification.passed and os.path.isfile(source_path):
                    size_v = verifier.verify_file_size(dest_path, os.path.getsize(source_path))
                    verification = size_v

            return PrimitiveResult(
                ok=True,
                data={"source": source, "destination": destination,
                      "source_uri": source_path, "dest_uri": dest_path},
                verification=verification,
                duration_ms=(_time.time() - start) * 1000,
            )
        except Exception as e:
            return PrimitiveResult(ok=False, error=str(e))


# ══════════════════════════════════════════════════════════════
#  PRIMITIVE REGISTRY
# ══════════════════════════════════════════════════════════════

class PrimitiveRegistry:
    """Registry of all available primitives."""

    def __init__(self):
        self._primitives: Dict[str, ActionPrimitive] = {}
        self._register_all()

    def _register_all(self):
        """Register all built-in primitives."""
        primitives = [
            # Filesystem
            FindPrimitive(), CopyPrimitive(), MovePrimitive(), DeletePrimitive(),
            ReadFilePrimitive(), WriteFilePrimitive(), SearchFilesPrimitive(),
            # Computer
            ClickPrimitive(), TypePrimitive(), ScreenshotPrimitive(),
            # Application
            LaunchPrimitive(),
            # Browser
            NavigatePrimitive(), ExtractPrimitive(),
            # General
            ExecutePrimitive(), InspectPrimitive(), WaitPrimitive(),
            # Transfer
            TransferPrimitive(),
        ]
        for p in primitives:
            self._primitives[p.name] = p

    def get(self, name: str) -> Optional[ActionPrimitive]:
        return self._primitives.get(name)

    def list_all(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": p.name,
                "category": p.category.value,
                "contract": p.contract.to_dict(),
            }
            for p in self._primitives.values()
        ]

    def execute(self, name: str, **kwargs) -> PrimitiveResult:
        """Execute a primitive by name."""
        primitive = self.get(name)
        if not primitive:
            return PrimitiveResult(ok=False, error=f"Unknown primitive: {name}")
        return primitive.execute(**kwargs)


# ══════════════════════════════════════════════════════════════
#  EXECUTION GRAPH (Planning Language)
# ══════════════════════════════════════════════════════════════

@dataclass
class ExecutionStep:
    """A single step in an execution graph."""
    id: str
    primitive: str
    params: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    description: str = ""
    status: str = "pending"  # pending, running, completed, failed
    result: Optional[PrimitiveResult] = None
    retries: int = 0
    max_retries: int = 2

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "primitive": self.primitive,
            "params": self.params,
            "depends_on": self.depends_on,
            "description": self.description,
            "status": self.status,
            "result": self.result.to_dict() if self.result else None,
            "retries": self.retries,
        }


@dataclass
class ExecutionGraph:
    """A structured plan made of composable primitives."""
    id: str
    goal: str
    steps: List[ExecutionStep] = field(default_factory=list)
    status: str = "planning"
    created_at: float = 0
    started_at: float = 0
    completed_at: float = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "goal": self.goal,
            "steps": [s.to_dict() for s in self.steps],
            "status": self.status,
        }

    def get_ready_steps(self) -> List[ExecutionStep]:
        """Get steps whose dependencies are all completed."""
        completed_ids = {s.id for s in self.steps if s.status == "completed"}
        return [
            s for s in self.steps
            if s.status == "pending"
            and all(dep in completed_ids for dep in s.depends_on)
        ]


# ══════════════════════════════════════════════════════════════
#  COMPOSITION ENGINE
# ══════════════════════════════════════════════════════════════

class CompositionEngine:
    """Executes execution graphs by composing primitives.

    This is the engine that turns plans into reality.
    """

    def __init__(self):
        self._registry = PrimitiveRegistry()
        self._verifier = VerificationEngine()
        self._object_resolver = ObjectResolver()

    def execute_graph(self, graph: ExecutionGraph,
                     on_step_complete: Callable = None) -> ExecutionGraph:
        """Execute an entire execution graph."""
        graph.status = "running"
        graph.started_at = time.time()

        max_iterations = 100  # Safety limit
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            ready = graph.get_ready_steps()

            if not ready:
                # Check if all done
                all_done = all(s.status in ("completed", "failed") for s in graph.steps)
                if all_done:
                    failed = any(s.status == "failed" for s in graph.steps)
                    graph.status = "failed" if failed else "completed"
                    graph.completed_at = time.time()
                    break
                time.sleep(0.5)
                continue

            for step in ready:
                step.status = "running"

                # Execute the primitive
                result = self._registry.execute(step.primitive, **step.params)
                step.result = result

                if result.ok:
                    step.status = "completed"
                elif step.retries < step.max_retries:
                    step.retries += 1
                    step.status = "pending"  # Will retry
                else:
                    step.status = "failed"

                if on_step_complete:
                    on_step_complete(step)

        return graph

    def execute_plan(self, goal: str, steps: List[Dict[str, Any]]) -> ExecutionGraph:
        """Execute a plan from a list of step dictionaries."""
        graph = ExecutionGraph(
            id=f"exec_{int(time.time())}",
            goal=goal,
            created_at=time.time(),
        )

        for i, step_def in enumerate(steps):
            step = ExecutionStep(
                id=f"step_{i}",
                primitive=step_def.get("action", step_def.get("primitive", "")),
                params=step_def.get("params", {}),
                depends_on=step_def.get("depends_on", []),
                description=step_def.get("description", ""),
            )
            graph.steps.append(step)

        return self.execute_graph(graph)


# ── Singleton ──
_registry: Optional[PrimitiveRegistry] = None
_composition: Optional[CompositionEngine] = None
_verifier: Optional[VerificationEngine] = None
_resolver: Optional[ObjectResolver] = None


def get_primitive_registry() -> PrimitiveRegistry:
    global _registry
    if _registry is None:
        _registry = PrimitiveRegistry()
    return _registry


def get_composition_engine() -> CompositionEngine:
    global _composition
    if _composition is None:
        _composition = CompositionEngine()
    return _composition


def get_verification_engine() -> VerificationEngine:
    global _verifier
    if _verifier is None:
        _verifier = VerificationEngine()
    return _verifier


def get_object_resolver() -> ObjectResolver:
    global _resolver
    if _resolver is None:
        _resolver = ObjectResolver()
    return _resolver
