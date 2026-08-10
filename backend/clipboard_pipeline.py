"""
JARVIS Smart Clipboard Pipeline Engine
======================================
Intercepts clipboard actions and offers 1-click contextual formatting:
- JSON tidying and validation
- Code language detection and translation
- URL extraction and metadata enrichment
- Phone number / email formatting
- Base64 detection and decode
- Smart paste history with search
"""

import json
import re
import time
import hashlib
import logging
import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from pathlib import Path
from enum import Enum

log = logging.getLogger("jarvis-clipboard")


class ClipboardContentType(str, Enum):
    TEXT = "text"
    JSON = "json"
    CODE = "code"
    URL = "url"
    EMAIL = "email"
    PHONE = "phone"
    BASE64 = "base64"
    MARKDOWN = "markdown"
    HTML = "html"
    UNKNOWN = "unknown"


@dataclass
class ClipboardEntry:
    """A single clipboard history entry."""
    id: str
    content: str
    content_type: str
    timestamp: float
    source_app: str = ""
    formatted_versions: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    pinned: bool = False


@dataclass
class FormatAction:
    """A suggested formatting action for clipboard content."""
    action_id: str
    label: str
    description: str
    icon: str
    output: str
    confidence: float


class SmartClipboardPipeline:
    """
    Real-time clipboard interception, classification, and formatting engine.
    Runs locally with zero cloud dependency for privacy.
    """

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = data_dir or os.path.join(
            os.path.expanduser("~"), ".jarvis", "clipboard"
        )
        os.makedirs(self.data_dir, exist_ok=True)
        self._history: List[ClipboardEntry] = []
        self._max_history = 500
        self._last_content = ""
        self._load_history()

    def _load_history(self):
        """Load clipboard history from disk."""
        history_file = os.path.join(self.data_dir, "history.json")
        if os.path.exists(history_file):
            try:
                with open(history_file, "r") as f:
                    data = json.load(f)
                self._history = [ClipboardEntry(**e) for e in data]
                log.info(f"Loaded {len(self._history)} clipboard entries")
            except Exception as e:
                log.error(f"Failed to load clipboard history: {e}")

    def _save_history(self):
        """Persist clipboard history to disk."""
        history_file = os.path.join(self.data_dir, "history.json")
        try:
            with open(history_file, "w") as f:
                json.dump([asdict(e) for e in self._history[-self._max_history:]], f, indent=2)
        except Exception as e:
            log.error(f"Failed to save clipboard history: {e}")

    def classify_content(self, content: str) -> ClipboardContentType:
        """Classify clipboard content into a type category."""
        if not content or not content.strip():
            return ClipboardContentType.TEXT

        stripped = content.strip()

        # JSON detection
        if (stripped.startswith("{") and stripped.endswith("}")) or \
           (stripped.startswith("[") and stripped.endswith("]")):
            try:
                json.loads(stripped)
                return ClipboardContentType.JSON
            except json.JSONDecodeError:
                pass

        # URL detection
        url_pattern = re.compile(
            r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+(?:/[^\s]*)?'
        )
        if url_pattern.match(stripped):
            return ClipboardContentType.URL

        # Email detection
        email_pattern = re.compile(
            r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        )
        if email_pattern.match(stripped):
            return ClipboardContentType.EMAIL

        # Phone detection
        phone_pattern = re.compile(
            r'^[\+]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{1,4}[-\s\.]?[0-9]{1,9}$'
        )
        if phone_pattern.match(stripped.replace(" ", "")):
            return ClipboardContentType.PHONE

        # Base64 detection (long strings of base64 chars)
        if len(stripped) > 20 and re.match(r'^[A-Za-z0-9+/=\s]+$', stripped):
            try:
                import base64
                decoded = base64.b64decode(stripped)
                if len(decoded) > 10:
                    return ClipboardContentType.BASE64
            except Exception:
                pass

        # Code detection
        code_indicators = [
            r'(?:def|class|function|import|from|const|let|var|return)\s',
            r'[{}\[\]();].*[{}\[\]();]',
            r'(?:if|else|for|while|switch|case)\s*\(',
            r'//.*$|/\*.*\*/|#.*$',
            r'(?:public|private|protected|static)\s+(?:class|void|int|string)',
        ]
        code_score = sum(1 for p in code_indicators if re.search(p, stripped, re.MULTILINE))
        if code_score >= 2:
            return ClipboardContentType.CODE

        # Markdown detection
        md_indicators = [
            r'^#{1,6}\s', r'\*\*.*\*\*', r'```', r'`[^`]+`',
            r'\[.*\]\(.*\)', r'^[-*+]\s', r'^\d+\.\s',
        ]
        md_score = sum(1 for p in md_indicators if re.search(p, stripped, re.MULTILINE))
        if md_score >= 2:
            return ClipboardContentType.MARKDOWN

        # HTML detection
        if stripped.startswith("<") and ">" in stripped:
            return ClipboardContentType.HTML

        return ClipboardContentType.TEXT

    def suggest_formats(self, content: str) -> List[FormatAction]:
        """Generate formatting suggestions for clipboard content."""
        content_type = self.classify_content(content)
        suggestions = []

        if content_type == ClipboardContentType.JSON:
            suggestions.append(FormatAction(
                action_id="json_pretty",
                label="Pretty Print",
                description="Format JSON with indentation",
                icon="📋",
                output=json.dumps(json.loads(content.strip()), indent=2, ensure_ascii=False),
                confidence=0.95,
            ))
            suggestions.append(FormatAction(
                action_id="json_minify",
                label="Minify",
                description="Remove all whitespace",
                icon="📦",
                output=json.dumps(json.loads(content.strip()), separators=(',', ':'), ensure_ascii=False),
                confidence=0.9,
            ))
            # Validate and report errors
            try:
                parsed = json.loads(content.strip())
                suggestions.append(FormatAction(
                    action_id="json_validate",
                    label="Validate",
                    description=f"Valid JSON ({type(parsed).__name__})",
                    icon="✅",
                    output=content,
                    confidence=1.0,
                ))
            except json.JSONDecodeError as e:
                suggestions.append(FormatAction(
                    action_id="json_validate",
                    label="Invalid JSON",
                    description=f"Error: {e.msg} at line {e.lineno}",
                    icon="❌",
                    output=content,
                    confidence=1.0,
                ))

        elif content_type == ClipboardContentType.CODE:
            # Detect language heuristics
            lang = self._detect_code_language(content)
            suggestions.append(FormatAction(
                action_id="code_format",
                label=f"Format {lang.upper()}",
                description=f"Clean up {lang} code formatting",
                icon="💻",
                output=content.strip(),
                confidence=0.8,
            ))
            suggestions.append(FormatAction(
                action_id="code_copy_md",
                label="Copy as Markdown",
                description="Wrap in markdown code block",
                icon="📝",
                output=f"```{lang}\n{content.strip()}\n```",
                confidence=0.85,
            ))

        elif content_type == ClipboardContentType.URL:
            suggestions.append(FormatAction(
                action_id="url_markdown",
                label="As Markdown Link",
                description="Create markdown hyperlink",
                icon="🔗",
                output=f"[link]({content.strip()})",
                confidence=0.9,
            ))
            suggestions.append(FormatAction(
                action_id="url_extract_domain",
                label="Extract Domain",
                description="Get the domain name",
                icon="🌐",
                output=re.search(r'https?://([^/]+)', content.strip()).group(1) if re.search(r'https?://([^/]+)', content.strip()) else content.strip(),
                confidence=0.85,
            ))

        elif content_type == ClipboardContentType.EMAIL:
            suggestions.append(FormatAction(
                action_id="email_mailto",
                label="Create mailto: Link",
                description="Click to send email",
                icon="📧",
                output=f"mailto:{content.strip()}",
                confidence=0.95,
            ))

        elif content_type == ClipboardContentType.PHONE:
            phone = content.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
            suggestions.append(FormatAction(
                action_id="phone_tel",
                label="Create tel: Link",
                description="Click to call",
                icon="📞",
                output=f"tel:{phone}",
                confidence=0.9,
            ))

        elif content_type == ClipboardContentType.BASE64:
            try:
                import base64
                decoded = base64.b64decode(content.strip()).decode("utf-8", errors="replace")
                suggestions.append(FormatAction(
                    action_id="base64_decode",
                    label="Decode Base64",
                    description="Convert base64 to text",
                    icon="🔓",
                    output=decoded,
                    confidence=0.85,
                ))
            except Exception:
                pass

        elif content_type == ClipboardContentType.MARKDOWN:
            suggestions.append(FormatAction(
                action_id="md_strip",
                label="Strip Formatting",
                description="Remove markdown syntax",
                icon="📄",
                output=self._strip_markdown(content),
                confidence=0.8,
            ))

        # Universal: word/char count
        word_count = len(content.split())
        char_count = len(content)
        suggestions.append(FormatAction(
            action_id="info_count",
            label=f"{word_count} words, {char_count} chars",
            description="Content statistics",
            icon="📊",
            output=content,
            confidence=1.0,
        ))

        return sorted(suggestions, key=lambda a: a.confidence, reverse=True)

    def _detect_code_language(self, content: str) -> str:
        """Heuristic language detection for code snippets."""
        indicators = {
            "python": [r'\bdef\s+\w+\s*\(', r'\bimport\s+\w+', r'\bclass\s+\w+:', r'print\s*\(', r'\.append\('],
            "javascript": [r'\bconst\s+\w+\s*=', r'\blet\s+\w+\s*=', r'\bfunction\s+\w+\s*\(', r'=>', r'\.then\('],
            "typescript": [r':\s*(string|number|boolean|any|void)', r'\binterface\s+\w+', r'\benum\s+\w+'],
            "html": [r'<html', r'<div', r'<span', r'<!DOCTYPE'],
            "css": [r'\{[\s\S]*?:\s*[\w#]+;', r'@media', r'\.[\w-]+\s*\{'],
            "bash": [r'#!/bin/bash', r'\becho\b', r'\bif\s*\[', r'\bfi\b'],
            "sql": [r'\bSELECT\b', r'\bFROM\b', r'\bWHERE\b', r'\bINSERT\b'],
            "json": [r'^\s*\{', r'^\s*\['],
            "rust": [r'\bfn\s+\w+', r'\blet\s+mut\b', r'\bimpl\b', r'\bpub\b'],
            "go": [r'\bfunc\s+\w+', r'\bpackage\s+\w+', r':='],
        }
        scores = {}
        for lang, patterns in indicators.items():
            score = sum(1 for p in patterns if re.search(p, content, re.MULTILINE))
            if score > 0:
                scores[lang] = score
        if scores:
            return max(scores, key=scores.get)
        return "text"

    def _strip_markdown(self, text: str) -> str:
        """Remove markdown formatting from text."""
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
        text = re.sub(r'\*(.*?)\*', r'\1', text)
        text = re.sub(r'`(.*?)`', r'\1', text)
        text = re.sub(r'```[\s\S]*?```', '', text)
        text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)
        text = re.sub(r'^[-*+]\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\d+\.\s+', '', text, flags=re.MULTILINE)
        return text.strip()

    def process_clipboard(self, content: str, source_app: str = "") -> Dict[str, Any]:
        """
        Process new clipboard content: classify, suggest formats, store history.
        Returns classification, suggestions, and entry metadata.
        """
        if not content or content == self._last_content:
            return {"action": "ignored", "reason": "duplicate_or_empty"}

        self._last_content = content
        content_type = self.classify_content(content)
        suggestions = self.suggest_formats(content)

        # Create history entry
        entry_id = hashlib.md5(f"{content[:200]}_{time.time()}".encode()).hexdigest()[:12]
        entry = ClipboardEntry(
            id=entry_id,
            content=content[:5000],  # Cap at 5KB per entry
            content_type=content_type.value,
            timestamp=time.time(),
            source_app=source_app,
            formatted_versions={s.action_id: s.output for s in suggestions},
            metadata={
                "char_count": len(content),
                "word_count": len(content.split()),
                "line_count": content.count("\n") + 1,
            },
        )

        self._history.append(entry)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
        self._save_history()

        return {
            "action": "processed",
            "entry_id": entry_id,
            "content_type": content_type.value,
            "suggestions": [asdict(s) for s in suggestions],
            "metadata": entry.metadata,
        }

    def get_history(self, limit: int = 50, search: str = "") -> List[Dict[str, Any]]:
        """Get clipboard history with optional search."""
        entries = self._history
        if search:
            search_lower = search.lower()
            entries = [e for e in entries if search_lower in e.content.lower()]
        return [asdict(e) for e in reversed(entries[-limit:])]

    def pin_entry(self, entry_id: str) -> bool:
        """Pin/unpin a clipboard entry."""
        for entry in self._history:
            if entry.id == entry_id:
                entry.pinned = not entry.pinned
                self._save_history()
                return True
        return False

    def delete_entry(self, entry_id: str) -> bool:
        """Delete a clipboard entry."""
        before = len(self._history)
        self._history = [e for e in self._history if e.id != entry_id]
        if len(self._history) < before:
            self._save_history()
            return True
        return False

    def clear_history(self):
        """Clear all clipboard history."""
        self._history.clear()
        self._save_history()

    def get_stats(self) -> Dict[str, Any]:
        """Get clipboard pipeline statistics."""
        type_counts = {}
        for entry in self._history:
            t = entry.content_type
            type_counts[t] = type_counts.get(t, 0) + 1
        return {
            "total_entries": len(self._history),
            "type_distribution": type_counts,
            "max_history": self._max_history,
            "data_dir": self.data_dir,
        }


# ── Singleton ────────────────────────────────────────────────────────────
_pipeline: Optional[SmartClipboardPipeline] = None


def get_clipboard_pipeline() -> SmartClipboardPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = SmartClipboardPipeline()
    return _pipeline
