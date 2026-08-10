"""Local document chunking. PDF → text via PyPDF, then semantic 500-word chunks."""

import io
import base64
import time
from pypdf import PdfReader

CHUNK_SIZE = 500
OVERLAP = 50


def _chunks(text: str, source: str = "unknown") -> list[dict]:
    words = text.split()
    out = []
    start = 0
    while start < len(words):
        end = min(start + CHUNK_SIZE, len(words))
        out.append({
            "content": " ".join(words[start:end]),
            "metadata": {
                "source": source,
                "word_start": start,
                "word_end": end,
                "ingested_at": time.time(),
            },
        })
        start += CHUNK_SIZE - OVERLAP
    return out


def process_pdf(content_b64: str, source: str = "pdf") -> list[dict]:
    reader = PdfReader(io.BytesIO(base64.b64decode(content_b64)))
    parts = []
    for i, page in enumerate(reader.pages):
        t = (page.extract_text() or "").strip()
        if t:
            parts.append(f"[Page {i+1}] {t}")
    return _chunks("\n".join(parts), source)


def process_text(content_b64: str, source: str = "text") -> list[dict]:
    return _chunks(base64.b64decode(content_b64).decode("utf-8"), source)


def process_upload(file_name: str, file_type: str, content_b64: str) -> list[dict]:
    if file_type == "application/pdf" or file_name.endswith(".pdf"):
        return process_pdf(content_b64, source=file_name)
    if file_type == "text/plain" or file_name.endswith(".txt"):
        return process_text(content_b64, source=file_name)
    raise ValueError(f"Unsupported file type: {file_type}")
