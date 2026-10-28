"""Docling (2.x) document parsing: text per page, tables and pictures.

Text inside pictures (charts, screenshots, scanned diagrams) is read with RapidOCR and written where the picture sits
(``[Image text: ...]``), so it is chunked, embedded and searchable with its section.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc import DoclingDocument, PictureItem

from src.core.config import settings

logger = logging.getLogger(__name__)

_PLAIN_TEXT_SUFFIXES = {".txt", ".json", ".log", ".text"}
_IMAGE = "<!-- image -->"  # Docling's picture placeholder in Markdown
_MIN_OCR_SCORE = 0.5

_ocr_engine: Any = None


def _ocr() -> Any:
    """RapidOCR (bundled ONNX models), loaded once; None when it cannot run here."""
    global _ocr_engine
    if _ocr_engine is None:
        try:
            from rapidocr import RapidOCR

            _ocr_engine = RapidOCR()
        except Exception as exc:  # missing onnxruntime etc.: pictures are skipped, parsing goes on
            logger.warning("[PARSE] OCR unavailable, text inside pictures is skipped: %s", exc)
            _ocr_engine = False
    return _ocr_engine or None


def _picture_text(doc: DoclingDocument, picture: PictureItem) -> str:
    engine = _ocr()
    image = picture.get_image(doc) if engine else None
    if image is None:
        return ""
    try:
        result = engine(image.convert("RGB"))
    except Exception as exc:
        logger.warning("[PARSE] OCR failed on a picture: %s", exc)
        return ""
    lines = [t for t, score in zip(result.txts or (), result.scores or ()) if score >= _MIN_OCR_SCORE]
    return " ".join(lines).strip()


def _fill_pictures(markdown: str, texts: list[str]) -> str:
    """Replace Docling's picture placeholders, in order, with the OCR text of each picture (or nothing)."""
    parts = markdown.split(_IMAGE)
    out = [parts[0]]
    for i, rest in enumerate(parts[1:]):
        text = texts[i] if i < len(texts) else ""
        out.append((f"[Image text: {text}]" if text else "") + rest)
    return "".join(out)


def _page_of(item: Any) -> int | None:
    prov = getattr(item, "prov", None) or []
    return prov[0].page_no if prov else None


class DoclingParserService:
    def __init__(self, ocr_enabled: bool = False):
        # OCR (RapidOCR) reads bitmap areas and scanned pages; picture images are kept for the picture OCR below.
        pdf_options = PdfPipelineOptions(
            do_ocr=ocr_enabled,
            ocr_options=RapidOcrOptions(),
            do_table_structure=True,
            generate_picture_images=True,
            images_scale=2.0,
        )
        self.converter = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options)}
        )

    @staticmethod
    def to_result(doc: DoclingDocument, filename: str) -> dict[str, Any]:
        page_numbers = sorted(doc.pages.keys())
        pictures = [(_page_of(p), _picture_text(doc, p)) for p in doc.pictures]
        # Tables stay in the page text so the section-aware chunker keeps them with their heading; each picture's
        # placeholder becomes its OCR text.
        if page_numbers:
            pages = [
                {"page_number": n, "text": _fill_pictures(doc.export_to_markdown(page_no=n), [t for pg, t in pictures if pg == n])}
                for n in page_numbers
            ]
        else:  # formats without pagination (docx, md, html, ...)
            pages = [{"page_number": None, "text": _fill_pictures(doc.export_to_markdown(), [t for _, t in pictures])}]

        tables = [
            {"page_number": _page_of(t), "table_index": i, "markdown": t.export_to_markdown(doc)}
            for i, t in enumerate(doc.tables, 1)
        ]
        images = [
            {"page_number": page, "image_index": i, "description": None, "text": text}
            for i, (page, text) in enumerate(pictures, 1)
        ]
        return {
            "filename": filename,
            "full_text": "\n\n".join(p["text"] for p in pages),
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
