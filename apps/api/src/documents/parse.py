"""Document text extraction (FR-3.1) — TXT, PDF, DOCX; Mistral OCR for scanned PDFs."""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from typing import TYPE_CHECKING
from xml.etree import ElementTree

if TYPE_CHECKING:
    from src.ai.mistral import MistralProvider


class DocumentParseError(ValueError):
    """Raised when extraction yields no usable text (FR-3.4 — never silent drop)."""


@dataclass(frozen=True)
class ParsedDocument:
    text: str
    method: str


def _ext(filename: str) -> str:
    name = filename.rsplit("/", 1)[-1].lower()
    if "." not in name:
        return ""
    return name.rsplit(".", 1)[-1]


def _parse_txt(data: bytes) -> str:
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _parse_docx(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        try:
            xml_bytes = zf.read("word/document.xml")
        except KeyError as exc:
            raise DocumentParseError("DOCX missing word/document.xml") from exc
    root = ElementTree.fromstring(xml_bytes)  # noqa: S314
    texts: list[str] = []
    for node in root.iter():
        if node.tag.endswith("}t") and node.text:
            texts.append(node.text)
    return "\n".join(texts)


def _parse_pdf_native(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise DocumentParseError(
            "PDF support requires pypdf; install API deps or upload TXT/DOCX"
        ) from exc
    reader = PdfReader(io.BytesIO(data))
    parts: list[str] = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n".join(parts).strip()


def _clean(text: str) -> str:
    return re.sub(r"[ \t]+\n", "\n", text).strip()


def _require_nonempty(text: str, method: str) -> ParsedDocument:
    cleaned = _clean(text)
    if not cleaned:
        raise DocumentParseError("Extracted text is empty")
    return ParsedDocument(text=cleaned, method=method)


def extract_text(filename: str, data: bytes) -> ParsedDocument:
    """Sync extract — native text only (no OCR). Empty scanned PDFs raise."""
    if not data:
        raise DocumentParseError("Empty file")
    ext = _ext(filename)
    if ext in ("txt", "md", "csv", "log"):
        return _require_nonempty(_parse_txt(data), "txt")
    if ext == "docx":
        return _require_nonempty(_parse_docx(data), "docx")
    if ext == "pdf" or data[:4] == b"%PDF":
        text = _parse_pdf_native(data)
        if not text:
            raise DocumentParseError(
                "PDF has no extractable text; use async extract with Mistral OCR"
            )
        return _require_nonempty(text, "pdf")
    if ext in ("png", "jpg", "jpeg", "webp", "gif"):
        raise DocumentParseError("Image uploads require Mistral OCR (async path)")
    if ext in ("doc", "rtf", "odt"):
        raise DocumentParseError(f"Unsupported format .{ext}; use PDF, DOCX, or TXT")
    if data[:2] == b"PK":
        return _require_nonempty(_parse_docx(data), "docx-sniff")
    return _require_nonempty(_parse_txt(data), "txt-fallback")


async def extract_text_async(
    filename: str,
    data: bytes,
    *,
    ocr_provider: MistralProvider | None = None,
) -> ParsedDocument:
    """Extract text; fall back to Mistral OCR for scanned PDFs / images (FR-3.1)."""
    if not data:
        raise DocumentParseError("Empty file")
    ext = _ext(filename)

    if ext in ("txt", "md", "csv", "log"):
        return _require_nonempty(_parse_txt(data), "txt")
    if ext == "docx":
        return _require_nonempty(_parse_docx(data), "docx")
    if data[:2] == b"PK" and ext not in ("png", "jpg", "jpeg", "webp", "gif"):
        try:
            return _require_nonempty(_parse_docx(data), "docx")
        except DocumentParseError:
            pass

    needs_ocr = False
    method = "mistral-ocr"
    if ext in ("png", "jpg", "jpeg", "webp", "gif"):
        needs_ocr = True
        method = "mistral-ocr-image"
    elif ext == "pdf" or data[:4] == b"%PDF":
        native = _parse_pdf_native(data)
        if native:
            return _require_nonempty(native, "pdf")
        needs_ocr = True
        method = "mistral-ocr"
    elif ext in ("doc", "rtf", "odt"):
        raise DocumentParseError(f"Unsupported format .{ext}; use PDF, DOCX, or TXT")
    else:
        try:
            return _require_nonempty(_parse_txt(data), "txt-fallback")
        except DocumentParseError:
            needs_ocr = True
            method = "mistral-ocr"

    if not needs_ocr:
        raise DocumentParseError("Extracted text is empty")
    if ocr_provider is None:
        raise DocumentParseError(
            "Scanned/image document requires Mistral OCR but no provider was configured"
        )
    try:
        text = await ocr_provider.ocr_document(data, filename=filename)
    except Exception as exc:
        raise DocumentParseError(f"Mistral OCR failed: {exc}") from exc
    return _require_nonempty(text, method)


def chunks_from_text(text: str, *, max_chars: int = 4000) -> list[tuple[str, int, int]]:
    """Return (chunk_text, span_start, span_end) preserving character offsets (FR-3.2)."""  # noqa: E501
    if len(text) <= max_chars:
        return [(text, 0, len(text))]
    out: list[tuple[str, int, int]] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        if end < len(text):
            split = text.rfind("\n", start, end)
            if split > start + max_chars // 2:
                end = split + 1
        out.append((text[start:end], start, end))
        start = end
    return out
