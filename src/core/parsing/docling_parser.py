"""Docling (2.x) document parsing: text per page, tables and pictures."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc import DoclingDocument

from src.core.config import settings

logger = logging.getLogger(__name__)

_PLAIN_TEXT_SUFFIXES = {".txt", ".json", ".log", ".text"}


def _page_of(item: Any) -> int | None:
    prov = getattr(item, "prov", None) or []
    return prov[0].page_no if prov else None


class DoclingParserService:
    def __init__(self, ocr_enabled: bool = False):
        pdf_options = PdfPipelineOptions(do_ocr=ocr_enabled, do_table_structure=True)
        self.converter = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options)}
        )

    @staticmethod
    def to_result(doc: DoclingDocument, filename: str) -> dict[str, Any]:
        page_numbers = sorted(doc.pages.keys())
        # Tables stay in the page text so the section-aware chunker keeps them with their heading.
        if page_numbers:
            pages = [{"page_number": n, "text": doc.export_to_markdown(page_no=n)} for n in page_numbers]
        else:  # formats without pagination (docx, md, html, ...)
            pages = [{"page_number": None, "text": doc.export_to_markdown()}]

        tables = [
            {"page_number": _page_of(t), "table_index": i, "markdown": t.export_to_markdown(doc)}
            for i, t in enumerate(doc.tables, 1)
        ]
        images = [
            {"page_number": _page_of(p), "image_index": i, "description": None}
            for i, p in enumerate(doc.pictures, 1)
        ]
        return {
            "filename": filename,
            "full_text": doc.export_to_markdown(),
            "pages": pages,
            "tables": tables,
            "images": images,
            "page_count": len(page_numbers),
            "table_count": len(tables),
            "image_count": len(images),
        }

    @staticmethod
    def plain_text_result(text: str, filename: str) -> dict[str, Any]:
        return {
            "filename": filename,
            "full_text": text,
            "pages": [{"page_number": None, "text": text}],
            "tables": [],
            "images": [],
            "page_count": 0,
            "table_count": 0,
            "image_count": 0,
        }

    def parse_document(self, file_bytes: bytes, filename: str) -> dict[str, Any]:
        logger.info("[PARSE] Docling parse: %s (%d bytes)", filename, len(file_bytes))
        suffix = Path(filename).suffix.lower()
        if suffix in _PLAIN_TEXT_SUFFIXES:  # formats Docling has no reader for
            return self.plain_text_result(file_bytes.decode("utf-8", errors="replace"), filename)
        with tempfile.TemporaryDirectory(prefix="aw_docling_") as tmp:
            path = Path(tmp) / f"document{suffix}"
            path.write_bytes(file_bytes)
            doc = self.converter.convert(path).document
        result = self.to_result(doc, filename)
        logger.info(
            "[PARSE] Done: %s (%d pages, %d tables, %d pictures, %d chars)",
            filename, result["page_count"], result["table_count"], result["image_count"], len(result["full_text"]),
        )
        return result


_parser_service: DoclingParserService | None = None


def get_docling_parser() -> DoclingParserService:
    global _parser_service
    if _parser_service is None:
        _parser_service = DoclingParserService(ocr_enabled=settings.docling_ocr_enabled)
    return _parser_service
