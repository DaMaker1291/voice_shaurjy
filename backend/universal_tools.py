"""Universal Tools — interact with ANY external system via API, DB, web, or code."""

import os
import sys
import io
import re
import json
import base64
import asyncio
import logging
import sqlite3
import subprocess
import urllib.parse
from typing import Optional, Any
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class UniversalTools:
    """A universal tool layer that can interact with any external system."""

    def __init__(self):
        self._session = None
        self._last_response = None

    # ── HTTP / REST API ─────────────────────────────────────────────────
    async def http_request(self, method: str = "GET", url: str = "",
                           headers: dict = None, body: Any = None,
                           params: dict = None) -> dict:
        """Make any HTTP request to any API. Returns {'status', 'headers', 'body', 'json'}."""
        try:
            import aiohttp
            headers = headers or {}
            params = params or {}

            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.request(method, url, params=params, json=body,
                                           timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    content_type = resp.headers.get("Content-Type", "")
                    text = await resp.text()
                    result = {
                        "status": resp.status,
                        "headers": dict(resp.headers),
                        "body": text[:50000],
                    }
                    if "application/json" in content_type:
                        try:
                            result["json"] = json.loads(text[:100000])
                        except json.JSONDecodeError:
                            pass
                    self._last_response = result
                    return result
        except ImportError:
            import urllib.request
            req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                         headers=headers, method=method)
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    text = resp.read().decode("utf-8", errors="replace")
                    result = {"status": resp.status, "headers": dict(resp.headers), "body": text[:50000]}
                    if "application/json" in resp.headers.get("Content-Type", ""):
                        try:
                            result["json"] = json.loads(text[:100000])
                        except json.JSONDecodeError:
                            pass
                    return result
            except Exception as e:
                return {"status": 0, "error": str(e)}
        except Exception as e:
            return {"status": 0, "error": str(e)}

    async def http_get(self, url: str, headers: dict = None, params: dict = None) -> dict:
        return await self.http_request("GET", url, headers, params=params)

    async def http_post(self, url: str, data: Any = None, headers: dict = None) -> dict:
        return await self.http_request("POST", url, headers, body=data)

    async def http_put(self, url: str, data: Any = None, headers: dict = None) -> dict:
        return await self.http_request("PUT", url, headers, body=data)

    async def http_delete(self, url: str, headers: dict = None) -> dict:
        return await self.http_request("DELETE", url, headers)

    # ── Web Scraper ─────────────────────────────────────────────────────
    async def web_scrape(self, url: str, selector: str = "body") -> dict:
        """Scrape readable content from a URL. Strips scripts/styles, returns clean text."""
        result = await self.http_get(url)
        if result.get("status") != 200:
            return {"success": False, "error": f"HTTP {result.get('status')}", "content": ""}

        html = result.get("body", "")
        content = html

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup(["script", "style", "noscript", "iframe", "svg", "head", "form", "nav", "footer"]):
                tag.decompose()
            title = soup.title.get_text(" ", strip=True) if soup.title else ""
            body = soup.body if soup.body else soup
            text = re.sub(r'\s+', ' ', body.get_text("\n", strip=True)).strip()
            content = soup.prettify()[:10000]
        except Exception:
            # Fallback: strip <style>/<script> blocks with regex before removing tags
            html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
            html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<[^>]+>', ' ', html)
            text = re.sub(r'\s+', ' ', text).strip()[:10000]
            title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
            title = re.sub(r'\s+', ' ', title_match.group(1)).strip() if title_match else ""

        return {
            "success": True,
            "url": url,
            "title": title,
            "content": content[:10000],
            "text": text[:5000],
            "word_count": len(text.split()),
        }

    # ── Database Query ──────────────────────────────────────────────────
    def query_sqlite(self, db_path: str, query: str, params: list = None) -> dict:
        """Query any SQLite database."""
        try:
            expanded = os.path.expandvars(os.path.expanduser(db_path))
            if not os.path.exists(expanded):
                return {"success": False, "error": f"Database not found: {expanded}"}
            conn = sqlite3.connect(expanded)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params or [])
            if query.strip().upper().startswith("SELECT"):
                rows = [dict(row) for row in cursor.fetchall()]
                result = {"success": True, "rows": rows, "count": len(rows)}
            else:
                conn.commit()
                result = {"success": True, "affected": cursor.rowcount}
            conn.close()
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    def query_postgres(self, conn_string: str, query: str, params: list = None) -> dict:
        """Query a PostgreSQL database."""
        try:
            import psycopg2
            conn = psycopg2.connect(conn_string)
            cursor = conn.cursor()
            cursor.execute(query, params or [])
            if query.strip().upper().startswith("SELECT"):
                columns = [desc[0] for desc in cursor.description]
                rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
                result = {"success": True, "rows": rows, "count": len(rows)}
            else:
                conn.commit()
                result = {"success": True, "affected": cursor.rowcount}
            conn.close()
            return result
        except ImportError:
            return {"success": False, "error": "psycopg2 not installed"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def query_database(self, connection: str, query: str, params: list = None) -> dict:
        """Query any database (auto-detects SQLite vs PostgreSQL)."""
        if connection.endswith(".db") or connection.endswith(".sqlite"):
            return self.query_sqlite(connection, query, params)
        return self.query_postgres(connection, query, params)

    # ── Code Execution ──────────────────────────────────────────────────
    def run_python(self, code: str, timeout: int = 30) -> dict:
        """Run Python code in ExecutionVault sandbox and return stdout/stderr."""
        from execution_vault import vaulted_python
        vr = vaulted_python(code, timeout=timeout)
        if vr.blocked:
            return {"success": False, "error": f"BLOCKED: {vr.block_reason}", "stdout": "", "stderr": vr.block_reason, "returncode": -1}
        if vr.timed_out:
            return {"success": False, "error": "Timed out", "stdout": "", "stderr": ""}
        return {
            "success": vr.exit_code == 0,
            "stdout": vr.stdout[:5000],
            "stderr": vr.stderr[:2000],
            "returncode": vr.exit_code,
        }

    def run_javascript(self, code: str, timeout: int = 15) -> dict:
        """Run JavaScript code via Node.js and return stdout/stderr."""
        try:
            result = subprocess.run(
                ["node", "-e", code],
                capture_output=True, text=True, timeout=timeout
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout[:5000],
                "stderr": result.stderr[:2000],
                "returncode": result.returncode,
            }
        except FileNotFoundError:
            return {"success": False, "error": "Node.js not found"}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def run_shell(self, command: str, timeout: int = 30) -> dict:
        """Run a shell command in ExecutionVault sandbox; returns structured result."""
        from execution_vault import vaulted_run
        vr = vaulted_run(command, timeout=timeout)
        if vr.blocked:
            return {"success": False, "error": f"BLOCKED: {vr.block_reason}", "stdout": "", "stderr": vr.block_reason, "returncode": -1}
        if vr.timed_out:
            return {"success": False, "error": "Timed out", "stdout": "", "stderr": "", "returncode": -1}
        return {
            "success": vr.exit_code == 0,
            "stdout": vr.stdout[:10000],
            "stderr": vr.stderr[:2000],
            "returncode": vr.exit_code,
        }

    # ── File Format Conversion ──────────────────────────────────────────
    def read_pdf(self, path: str) -> dict:
        """Extract text from a PDF file."""
        try:
            import PyPDF2
            expanded = os.path.expandvars(os.path.expanduser(path))
            if not os.path.exists(expanded):
                return {"success": False, "error": f"File not found: {expanded}"}
            text = []
            with open(expanded, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text.append(page.extract_text() or "")
            return {"success": True, "text": "\n".join(text)[:20000], "pages": len(reader.pages)}
        except ImportError:
            try:
                import pdfminer
                return {"success": False, "error": "Use PyPDF2 for PDF reading"}
            except ImportError:
                return {"success": False, "error": "No PDF library. Install: pip install PyPDF2"}

    def read_image(self, path: str) -> dict:
        """Analyze an image file — extract metadata and run OCR."""
        try:
            from PIL import Image
            expanded = os.path.expandvars(os.path.expanduser(path))
            if not os.path.exists(expanded):
                return {"success": False, "error": f"File not found: {expanded}"}
            img = Image.open(expanded)
            info = {
                "format": img.format,
                "size": img.size,
                "mode": img.mode,
                "width": img.width,
                "height": img.height,
            }
            # OCR if available
            try:
                import pytesseract
                text = pytesseract.image_to_string(img)
                info["ocr_text"] = text[:5000]
            except Exception:
                info["ocr_text"] = ""
            # Base64 for AI analysis
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            info["base64"] = base64.b64encode(buffer.getvalue()).decode()
            return {"success": True, **info}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Email ───────────────────────────────────────────────────────────
    def send_email_smtp(self, to: str, subject: str, body: str,
                        smtp_server: str = "", smtp_user: str = "",
                        smtp_pass: str = "", from_addr: str = "") -> dict:
        """Send an email via SMTP."""
        try:
            import smtplib
            from email.message import EmailMessage
            smtp_server = smtp_server or os.getenv("SMTP_SERVER", "smtp.gmail.com")
            smtp_user = smtp_user or os.getenv("SMTP_USER", "")
            smtp_pass = smtp_pass or os.getenv("SMTP_PASS", "")
            from_addr = from_addr or smtp_user or "jarvis@local"

            if not smtp_user or not smtp_pass:
                return {"success": False, "error": "SMTP not configured. Set SMTP_USER and SMTP_PASS env vars."}

            msg = EmailMessage()
            msg.set_content(body)
            msg["Subject"] = subject
            msg["From"] = from_addr
            msg["To"] = to

            with smtplib.SMTP_SSL(smtp_server) as s:
                s.login(smtp_user, smtp_pass)
                s.send_message(msg)
            return {"success": True, "to": to, "subject": subject}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Speech / Audio ──────────────────────────────────────────────────
    def speak_text(self, text: str) -> dict:
        """Speak text using TTS."""
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
            return {"success": True, "spoken": text[:100]}
        except ImportError:
            try:
                # Fallback: PowerShell TTS on Windows
                escaped = text.replace("'", "''")
                subprocess.run(["powershell", "-Command",
                    f"Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('{escaped}')"],
                    capture_output=True, timeout=30)
                return {"success": True, "spoken": text[:100]}
            except Exception as e:
                return {"success": False, "error": str(e)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── QR / Barcode ────────────────────────────────────────────────────
    def read_qr(self, path: str) -> dict:
        """Read a QR code from an image file."""
        try:
            from pyzbar.pyzbar import decode
            from PIL import Image
            expanded = os.path.expandvars(os.path.expanduser(path))
            if not os.path.exists(expanded):
                return {"success": False, "error": f"File not found: {expanded}"}
            img = Image.open(expanded)
            codes = decode(img)
            if codes:
                return {"success": True, "data": codes[0].data.decode(), "type": str(codes[0].type)}
            return {"success": False, "error": "No QR code found"}
        except ImportError:
            return {"success": False, "error": "pyzbar not installed"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Utility ──────────────────────────────────────────────────────────
    def encode_base64(self, data: str) -> str:
        return base64.b64encode(data.encode()).decode()

    def decode_base64(self, data: str) -> str:
        return base64.b64decode(data).decode()

    def generate_uuid(self) -> str:
        import uuid
        return str(uuid.uuid4())

    def timestamp(self) -> str:
        return datetime.now().isoformat()


_tools: Optional[UniversalTools] = None


def get_tools() -> UniversalTools:
    global _tools
    if _tools is None:
        _tools = UniversalTools()
    return _tools
