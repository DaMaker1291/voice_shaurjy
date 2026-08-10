"""
Log Parser — Parse application logs, extract errors, stack traces, and patterns.

Supports: plain text logs, JSON logs, Python tracebacks, Node.js errors,
nginx/apache access logs, Docker container logs.
"""

import re
import json
import time
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path
from collections import Counter, defaultdict

log = logging.getLogger("jarvis-logparser")


@dataclass
class LogEntry:
    timestamp: str = ""
    level: str = ""
    source: str = ""
    message: str = ""
    stack_trace: str = ""
    file: str = ""
    line: int = 0
    raw: str = ""

    def to_dict(self):
        return asdict(self)


@dataclass
class LogAnalysis:
    total_lines: int = 0
    errors: List[LogEntry] = field(default_factory=list)
    warnings: List[LogEntry] = field(default_factory=list)
    stack_traces: List[str] = field(default_factory=list)
    error_patterns: Dict[str, int] = field(default_factory=dict)
    timeline: List[Dict] = field(default_factory=list)
    affected_files: List[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self):
        d = asdict(self)
        d["errors"] = [e.to_dict() if hasattr(e, 'to_dict') else e for e in self.errors]
        d["warnings"] = [w.to_dict() if hasattr(w, 'to_dict') else w for w in self.warnings]
        return d


# ── Pattern definitions ──────────────────────────────────────────────────────

_ERROR_PATTERNS = [
    # Python traceback
    (r'Traceback \(most recent call last\):', "python_traceback"),
    (r'File "([^"]+)", line (\d+)', "python_file_error"),
    # Node.js errors
    (r'(?:Error|TypeError|ReferenceError|SyntaxError|RangeError):\s*(.+)', "nodejs_error"),
    (r'at\s+(.+?)\s+\((.+?):(\d+):\d+\)', "nodejs_stack"),
    # Java exceptions
    (r'(?:Exception|Error)\s*(?:\(.+?\))?:\s*(.+)', "java_exception"),
    # Generic error patterns
    (r'\b(?:ERROR|FATAL|CRITICAL|PANIC)\b[:\s]+(.+)', "generic_error"),
    (r'\b(?:WARN|WARNING)\b[:\s]+(.+)', "generic_warning"),
    # HTTP errors
    (r'(?:GET|POST|PUT|DELETE|PATCH)\s+\S+\s+(\d{3})', "http_status"),
    # Database errors
    (r'(?:SQL|Query|query)\s+(?:Error|error|Failed|failed)[:\s]*(.+)', "db_error"),
    # Memory/resource
    (r'(?:OutOfMemory|OOM|MemoryError|MemoryError)[:\s]*(.+)', "memory_error"),
    (r'(?:timeout|Timeout|TIMEOUT)(?:\s+(?:after|exceeded)\s+(\d+)s?)?', "timeout"),
    # Security
    (r'(?:CVE|vulnerability|exploit|breach|unauthorized|forbidden)', "security"),
]

_STACK_START = re.compile(r'^Traceback \(most recent call last\):')
_STACK_FRAME = re.compile(r'^\s+File "(.+?)", line (\d+), in (.+)')
_STACK_ERROR = re.compile(r'^(\w+(?:\.\w+)*(?:Error|Exception|Warning)):\s*(.*)')
_HTTP_STATUS = re.compile(r'(?:GET|POST|PUT|DELETE|PATCH)\s+\S+\s+(\d{3})')


class LogParser:
    """Parse and analyze log files."""

    def parse_file(self, filepath: str, max_lines: int = 100000) -> LogAnalysis:
        """Parse a log file and return structured analysis."""
        path = Path(filepath)
        if not path.exists():
            return LogAnalysis(summary=f"File not found: {filepath}")

        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines(max_lines)
            return self.parse_lines(lines, source=str(path))
        except Exception as e:
            return LogAnalysis(summary=f"Error reading {filepath}: {e}")

    def parse_text(self, text: str, source: str = "") -> LogAnalysis:
        """Parse a block of log text."""
        lines = text.splitlines(keepends=True)
        return self.parse_lines(lines, source=source)

    def parse_lines(self, lines: List[str], source: str = "") -> LogAnalysis:
        """Parse log lines into structured analysis."""
        analysis = LogAnalysis(total_lines=len(lines))
        current_entry = None
        in_traceback = False
        traceback_lines = []
        errors_by_type = Counter()

        for i, line in enumerate(lines):
            line = line.rstrip("\n\r")

            # Check for traceback start
            if _STACK_START.match(line):
                in_traceback = True
                traceback_lines = [line]
                continue

            if in_traceback:
                traceback_lines.append(line)
                if _STACK_ERROR.match(line) and not line.startswith(" "):
                    # End of traceback
                    trace = "\n".join(traceback_lines)
                    analysis.stack_traces.append(trace)
                    in_traceback = False
                    traceback_lines = []
                continue

            if traceback_lines:
                analysis.stack_traces.append("\n".join(traceback_lines))
                traceback_lines = []
                in_traceback = False

            # Try to parse as structured log line
            entry = self._parse_line(line, i + 1, source)
            if entry:
                if entry.level in ("ERROR", "FATAL", "CRITICAL", "CRIT"):
                    analysis.errors.append(entry)
                    # Classify error type
                    err_type = self._classify_error(entry.message)
                    errors_by_type[err_type] += 1
                elif entry.level in ("WARNING", "WARN"):
                    analysis.warnings.append(entry)

                # Check for file references
                if entry.file and entry.file not in analysis.affected_files:
                    analysis.affected_files.append(entry.file)

        if traceback_lines:
            analysis.stack_traces.append("\n".join(traceback_lines))

        analysis.error_patterns = dict(errors_by_type.most_common(20))
        analysis.timeline = self._build_timeline(analysis)
        analysis.summary = self._build_summary(analysis)
        return analysis

    def _parse_line(self, line: str, line_num: int, source: str) -> Optional[LogEntry]:
        """Try to parse a single log line into a LogEntry."""
        if not line.strip():
            return None

        entry = LogEntry(raw=line, line=line_num, source=source)

        # Pattern: TIMESTAMP LEVEL [source] message
        m = re.match(r'(\d{4}[-/]\d{2}[-/]\d{2}[T ]\d{2}:\d{2}:\d{2}[.\d]*\s*(?:Z|[+-]\d{2}:?\d{2})?)\s+(\w+)\s+(?:\[([^\]]+)\]\s+)?(.+)', line)
        if m:
            entry.timestamp = m.group(1)
            entry.level = m.group(2).upper()
            entry.source = m.group(3) or ""
            entry.message = m.group(4)
            return entry

        # Pattern: LEVEL: message
        m = re.match(r'(\w+):\s+(.+)', line)
        if m and m.group(1).upper() in ("ERROR", "WARNING", "WARN", "INFO", "DEBUG", "FATAL", "CRITICAL"):
            entry.level = m.group(1).upper()
            entry.message = m.group(2)
            return entry

        # Pattern: [LEVEL] message
        m = re.match(r'\[(\w+)\]\s+(.+)', line)
        if m and m.group(1).upper() in ("ERROR", "WARNING", "WARN", "INFO", "DEBUG"):
            entry.level = m.group(1).upper()
            entry.message = m.group(2)
            return entry

        # Generic: just store as message
        entry.message = line
        return entry

    def _classify_error(self, message: str) -> str:
        """Classify an error message into a type."""
        for pattern, err_type in _ERROR_PATTERNS:
            if re.search(pattern, message, re.IGNORECASE):
                return err_type
        # Default classification
        if "timeout" in message.lower():
            return "timeout"
        if "connection" in message.lower():
            return "connection_error"
        if "permission" in message.lower() or "denied" in message.lower():
            return "permission_error"
        if "not found" in message.lower() or "404" in message:
            return "not_found"
        if "500" in message or "internal" in message.lower():
            return "internal_error"
        return "other_error"

    def _build_timeline(self, analysis: LogAnalysis) -> List[Dict]:
        """Build a timeline of error events."""
        timeline = []
        for err in analysis.errors:
            timeline.append({
                "timestamp": err.timestamp,
                "level": err.level,
                "message": err.message[:200],
                "file": err.file,
                "line": err.line,
            })
        return sorted(timeline, key=lambda x: x.get("timestamp", ""))

    def _build_summary(self, analysis: LogAnalysis) -> str:
        """Generate a human-readable summary."""
        parts = [f"Analyzed {analysis.total_lines} lines."]
        if analysis.errors:
            parts.append(f"Found {len(analysis.errors)} errors.")
        if analysis.warnings:
            parts.append(f"Found {len(analysis.warnings)} warnings.")
        if analysis.stack_traces:
            parts.append(f"Found {len(analysis.stack_traces)} stack traces.")
        if analysis.error_patterns:
            top = list(analysis.error_patterns.items())[:3]
            parts.append("Top error types: " + ", ".join(f"{k} ({v})" for k, v in top))
        if analysis.affected_files:
            parts.append(f"Affected files: {', '.join(analysis.affected_files[:5])}")
        return " ".join(parts)


def scan_error_patterns(text: str) -> List[Dict]:
    """Quick scan for error patterns in text. Returns list of {type, match, position}."""
    results = []
    for pattern, err_type in _ERROR_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            results.append({
                "type": err_type,
                "match": m.group(0)[:200],
                "position": m.start(),
            })
    return results


_parser = None

def get_parser() -> LogParser:
    global _parser
    if _parser is None:
        _parser = LogParser()
    return _parser
