"""Leading Practice source ingestion: turn an uploaded practice source into a publishable release.

The admin console's library pipeline runs these stages on every upload:

1. Extract & chunk: PDF (page markers, OCR fallback), DOCX (heading styles, page breaks) or Markdown/text is read
   into blocks, then cut into passages that respect headings and keep a page and section locator each.
2. Index & validate: a keyword index over the candidate's passages, a duplicate scan against published practices,
   permission metadata, locator integrity and citation completeness, plus a sample retrieval check.
3. Quality gates: the four publication gates derived from those results.
4. Release: the approved practice body is written as Markdown to ``<workspace>/leading_practices/published``,
   which the Leading Practice index (``lp_index``) serves to users. Each release is also kept, immutable, under
   ``<workspace>/leading_practices/releases/<practice>/<version>.md``.

Nothing here touches the database; the API layer stores the results on the ingestion job.
"""

from __future__ import annotations

import hashlib
import io
import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from src.core.config import settings
from src.core.security.zip_safety import validate_zip_for_read

SUPPORTED_EXTENSIONS = (".pdf", ".docx", ".md", ".txt")
MAX_SOURCE_BYTES = 25 * 1024 * 1024
MAX_DOCX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024

TARGET_TOKENS = 400  # passage length the chunker aims for
OVERLAP_TOKENS = 48  # tokens repeated at the start of a passage that continues the same section
_CHARS_PER_TOKEN = 4

_PAGE_MARKER_RE = re.compile(r"^\[Page (\d+)\]$")
_MD_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*$")
_NUMBERED_HEADING_RE = re.compile(r"^(\d+(?:\.\d+){0,3})\.?\s+([A-Z][^.!?]{2,80})$")
_CITATION_RE = re.compile(r"\[(\d{1,3}(?:\s*[,–-]\s*\d{1,3})*)\]")
_REFERENCE_HEADING_RE = re.compile(r"^(?:\d+(?:\.\d+)*\.?\s+)?(references|sources|bibliography|citations|notes)$", re.I)
_REFERENCE_ENTRY_RE = re.compile(r"^\s*\[?(\d{1,3})[\].)]\s*(.*)$")
_ATTRIBUTION_RE = re.compile(r"https?://|\b(?:19|20)\d{2}\b")
_UNATTRIBUTED_RE = re.compile(r"\b(?:unattributed|unknown|tbd|source needed|citation needed)\b", re.I)
_OCR_PLACEHOLDER_RE = re.compile(r"^\[(?:No text content|Unable to extract|PDF rejected)")


class SourceRejected(ValueError):
    """The upload cannot enter the pipeline (type, size or an unsafe archive)."""


# --- storage -------------------------------------------------------------------------------------------------------


def library_root() -> Path:
    return Path(settings.workspace_root) / "leading_practices"


def published_dir() -> Path:
    """Released practice bodies served to users through the Leading Practice index."""
    return library_root() / "published"


def store_upload(job_id: str, filename: str, content: bytes) -> Path:
    """Keep the original source for provenance; corrections arrive as new jobs, so nothing is overwritten."""
    target = library_root() / "uploads" / job_id / Path(filename).name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return target


# --- 1. extract & chunk --------------------------------------------------------------------------------------------


def check_source(filename: str, content: bytes) -> str:
    """Return the lower-cased extension, or raise SourceRejected."""
    ext = Path(filename or "").suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise SourceRejected(f"{filename}: only PDF, DOCX, Markdown or text sources are accepted")
    if not content:
        raise SourceRejected(f"{filename} is empty")
    if len(content) > MAX_SOURCE_BYTES:
        raise SourceRejected(f"{filename} exceeds the 25 MB file limit")
    if ext == ".docx":
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                validate_zip_for_read(archive, max_uncompressed_bytes=MAX_DOCX_UNCOMPRESSED_BYTES)
        except zipfile.BadZipFile as exc:
            raise SourceRejected(f"{filename} is not a valid DOCX file") from exc
        except ValueError as exc:
            raise SourceRejected(f"{filename}: {exc}") from exc
    return ext


def _block(kind: str, text: str, page: int | None, level: int = 0) -> dict[str, Any]:
    return {"kind": kind, "text": text.strip(), "page": page, "level": level}


def _docx_blocks(content: bytes) -> tuple[list[dict[str, Any]], int]:
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    document = Document(io.BytesIO(content))
    blocks: list[dict[str, Any]] = []
    page = 1
    for element in document.element.body.iterchildren():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag == "p":
            paragraph = Paragraph(element, document)
            xml = element.xml
            # Word records where it broke pages when it last saved; explicit breaks count too.
            if blocks and ("w:lastRenderedPageBreak" in xml or 'w:type="page"' in xml):
                page += 1
            text = paragraph.text.strip()
            if not text:
                continue
            style = (paragraph.style.name if paragraph.style is not None else "") or ""
            match = re.match(r"Heading\s*(\d*)", style)
            if style.startswith("Title"):
                blocks.append(_block("title", text, page))
            elif match:
                blocks.append(_block("heading", text, page, int(match.group(1) or 1)))
            else:
                blocks.append(_block("para", text, page))
        elif tag == "tbl":
            for row in Table(element, document).rows:
                cells = [cell.text.strip() for cell in row.cells]
                line = " | ".join(dict.fromkeys(c for c in cells if c))
                if line:
                    blocks.append(_block("para", line, page))
    return blocks, page


def _looks_like_heading(line: str) -> int:
    """Heading level for a line of PDF or plain text, or 0. Numbered headings nest by their dots."""
    md = _MD_HEADING_RE.match(line)
    if md:
        return len(md.group(1))
    numbered = _NUMBERED_HEADING_RE.match(line)
    if numbered:
        return numbered.group(1).count(".") + 1
    if _REFERENCE_HEADING_RE.match(line):
        return 1
    return 0


def _text_blocks(text: str) -> tuple[list[dict[str, Any]], int]:
    """Blocks from extracted PDF text (``[Page N]`` markers) or Markdown / plain text."""
    blocks: list[dict[str, Any]] = []
    page: int | None = None
    pages = 0
    paragraph: list[str] = []

    def flush() -> None:
        if paragraph:
            blocks.append(_block("para", " ".join(paragraph), page))
            paragraph.clear()

    for raw in text.splitlines():
        line = raw.strip()
        marker = _PAGE_MARKER_RE.match(line)
        if marker:
            flush()
            page = int(marker.group(1))
            pages = max(pages, page)
            continue
        if not line:
            flush()
            continue
        level = _looks_like_heading(line) if len(line) <= 90 else 0
        if level:
            flush()
            md = _MD_HEADING_RE.match(line)
            kind = "title" if md and level == 1 and not blocks else "heading"
            blocks.append(_block(kind, md.group(2) if md else line, page, level))
            continue
        # Reference entries and list items stand on their own so citations can be resolved line by line.
        if _REFERENCE_ENTRY_RE.match(line) or re.match(r"^[-*•]\s+", line):
            flush()
            blocks.append(_block("para", line, page))
            continue
        paragraph.append(line)
    flush()
    return blocks, pages or 1


def blocks_from_markdown(markdown: str) -> dict[str, Any]:
    """Blocks from parser Markdown (the ingestion pipeline's Docling output, ``[Page N]`` markers allowed)."""
    blocks, pages = _text_blocks(markdown)
    readable = any(b["kind"] == "para" for b in blocks)
    return {
        "blocks": blocks,
        "pages": pages,
        "parseMode": "docling",
        "readable": readable,
        "reason": "" if readable else "No readable text was found in the source",
    }


def extract_blocks(filename: str, content: bytes) -> dict[str, Any]:
    """Read a source into ordered heading / paragraph blocks with page numbers.

    Returns ``{"blocks", "pages", "parseMode", "readable"}``; ``readable`` is False when no text could be read
    (typically a scanned PDF without OCR), and such sources cannot enter retrieval.
    """
    ext = check_source(filename, content)
    if ext == ".docx":
        blocks, pages = _docx_blocks(content)
        mode = "docx"
    elif ext == ".pdf":
        from src.memory.documents.pdf_extract import extract_pdf_text

        text, mode = extract_pdf_text(
            content,
            filename=filename,
            max_pages=int(getattr(settings, "pdf_max_pages", 200)),
            ocr_enabled=bool(getattr(settings, "pdf_ocr_enabled", True)),
            ocr_min_chars=int(getattr(settings, "pdf_ocr_min_chars_per_page", 50)),
        )
        if _OCR_PLACEHOLDER_RE.match(text.strip()):
            return {"blocks": [], "pages": 0, "parseMode": mode, "readable": False, "reason": text.strip("[] ")}
        blocks, pages = _text_blocks(text)
    else:
        blocks, pages = _text_blocks(content.decode("utf-8", errors="ignore"))
        mode = "markdown" if ext == ".md" else "text"
    readable = any(b["kind"] == "para" for b in blocks)
    return {
        "blocks": blocks,
        "pages": pages,
        "parseMode": mode,
        "readable": readable,
        "reason": "" if readable else "No readable text was found in the source",
    }


def estimate_tokens(text: str) -> int:
    return max(1, round(len(text) / _CHARS_PER_TOKEN))


def _overlap_tail(text: str) -> str:
    tail = text[-OVERLAP_TOKENS * _CHARS_PER_TOKEN :]
    space = tail.find(" ")
    return tail[space + 1 :] if 0 <= space < len(tail) - 1 else tail


def _section_labels(blocks: list[dict[str, Any]]) -> list[str]:
    """The section each block sits in, numbered §1, §2 … by top-level heading."""
    labels: list[str] = []
    top = 0
    current = "Introduction"
    for block in blocks:
        if block["kind"] == "heading":
            numbered = re.match(r"^(\d+(?:\.\d+)*)\.?\s+(.*)$", block["text"])
            if numbered:
                current = f"§{numbered.group(1)} {numbered.group(2)[:80]}"
                top = max(top, int(numbered.group(1).split(".")[0]))
            else:
                if block["level"] <= 1 or current == "Introduction":
                    top += 1
                current = f"§{top} {block['text'][:80]}"
        labels.append(current)
    return labels


def chunk_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Heading-aware passages: a heading always starts a passage; a long section is split with a short overlap."""
    target_chars = TARGET_TOKENS * _CHARS_PER_TOKEN
    labels = _section_labels(blocks)
    chunks: list[dict[str, Any]] = []
    carry = ""  # overlap from the previous passage of the same section
    parts: list[str] = []
    pages: list[int] = []
    section = "Introduction"

    def emit(*, keep_overlap: bool) -> None:
        nonlocal carry
        body = "\n\n".join(([carry] if carry else []) + parts).strip()
        if parts and any(c.isalnum() for c in "".join(parts)):
            chunks.append({"text": body, "section": section, "page": pages[0] if pages else None,
                           "pageEnd": pages[-1] if pages else None})
        carry = _overlap_tail(body) if keep_overlap and parts else ""
        parts.clear()
        pages.clear()

    for block, label in zip(blocks, labels, strict=True):
        if block["kind"] in ("heading", "title"):
            emit(keep_overlap=False)
            section = label
            continue
        if block["page"] is not None:
            pages.append(block["page"])
        parts.append(block["text"])
        if sum(len(p) for p in parts) >= target_chars:
            emit(keep_overlap=True)
    emit(keep_overlap=False)

    for index, chunk in enumerate(chunks, start=1):
        chunk["id"] = f"ch-{index:03d}"
        chunk["code"] = f"CH-{index:03d}"
        chunk["tokens"] = estimate_tokens(chunk["text"])
        chunk["sha256"] = hashlib.sha256(_normalise(chunk["text"]).encode()).hexdigest()
        in_references = bool(_REFERENCE_HEADING_RE.match(_plain_heading(chunk["section"])))
        chunk["citations"] = [] if in_references else sorted(cited_numbers(chunk["text"]))
    return chunks


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


# --- citations ------------------------------------------------------------------------------------------------------


def cited_numbers(text: str) -> set[int]:
    numbers: set[int] = set()
    for group in _CITATION_RE.findall(text):
        for part in re.split(r"\s*,\s*", group):
            bounds = re.split(r"\s*[–-]\s*", part)
            if len(bounds) == 2 and bounds[0].isdigit() and bounds[1].isdigit():
                low, high = int(bounds[0]), int(bounds[1])
                if 0 < high - low <= 20:
                    numbers.update(range(low, high + 1))
                    continue
            if bounds[0].isdigit():
                numbers.add(int(bounds[0]))
    return numbers


def analyse_citations(blocks: list[dict[str, Any]]) -> dict[str, Any]:
    """Every reference cited in the body must have an entry in the references section that names a source
    (a link or a year). Returns the cited, listed, attributed and missing reference numbers."""
    cited: set[int] = set()
    entries: dict[int, str] = {}
    in_references = False
    for block in blocks:
        if block["kind"] in ("heading", "title"):
            in_references = bool(_REFERENCE_HEADING_RE.match(block["text"]))
            continue
        if in_references:
            entry = _REFERENCE_ENTRY_RE.match(block["text"])
            if entry:
                entries[int(entry.group(1))] = entry.group(2).strip()
            continue
        cited |= cited_numbers(block["text"])
    attributed = {
        n for n, text in entries.items() if _ATTRIBUTION_RE.search(text) and not _UNATTRIBUTED_RE.search(text)
    }
    references = sorted(cited | set(entries))
    return {
        "references": references,
        "cited": sorted(cited),
        "attributed": sorted(attributed & set(references)),
        "missing": sorted(set(references) - attributed),
        "entries": {str(n): entries[n] for n in sorted(entries)},
    }


def chunk_quality(chunk: dict[str, Any], missing: list[int]) -> tuple[str, str]:
    """(label, tone) shown against each passage in the chunk inventory."""
    gaps = [n for n in chunk.get("citations", []) if n in missing]
    if gaps:
        return f"Reference {', '.join(str(n) for n in gaps)} missing", "warn"
    words = chunk["text"].split()
    letters = sum(c.isalpha() for c in chunk["text"])
    if len(words) < 12 or letters / max(1, len(chunk["text"])) < 0.5:
        return "Low text quality", "warn"
    return "Readable", "ok"


# --- 2. index & validate --------------------------------------------------------------------------------------------


def _row(row_id: str, label: str, ok: bool, result: str, detail: str) -> dict[str, Any]:
    return {"id": row_id, "label": label, "result": result, "detail": detail, "tone": "ok" if ok else "warn",
            "passed": ok}


def _plain_heading(section: str) -> str:
    return re.sub(r"^§[\d.]+\s*", "", section).strip()


def sample_retrieval(chunks: list[dict[str, Any]], *, limit: int = 3) -> list[dict[str, Any]]:
    """Query the candidate's own keyword index with section headings; each should find a passage from its section."""
    from src.memory.knowledge.lp_index import LPIndex, keyword_search
    from src.memory.retrieval import _build_bm25_index

    if not chunks:
        return []
    index = LPIndex(
        fingerprint="candidate",
        chunks=chunks,
        bm25=_build_bm25_index([f"{_plain_heading(c['section'])}\n{c['text']}" for c in chunks]),
    )
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for chunk in chunks:
        query = re.sub(r"^\d+(?:\.\d+)*\.?\s*", "", _plain_heading(chunk["section"]))
        if not query or query == "Introduction" or query.lower() in seen or _REFERENCE_HEADING_RE.match(query):
            continue
        seen.add(query.lower())
        hits = keyword_search(index, query, 1)
        top = chunks[hits[0][0]] if hits else None
        relevant = top is not None and top["section"] == chunk["section"]
        rows.append(_row(
            f"rc-{len(rows) + 1}",
            query,
            relevant,
            locator(top) if top else "No passage returned",
            "Relevant · Provenance intact" if relevant else "Top passage is from another section",
        ))
        if len(rows) >= limit:
            break
    return rows


def locator(chunk: dict[str, Any]) -> str:
    parts = [chunk["code"]]
    if chunk.get("page"):
        parts.append(f"p.{chunk['page']}")
    if chunk.get("section"):
        parts.append(chunk["section"].split(" ", 1)[0])
    return " · ".join(parts)


def validate(
    chunks: list[dict[str, Any]],
    citations: dict[str, Any],
    *,
    owner: str,
    classification: str,
    rights: str,
    published_hashes: dict[str, str],
) -> dict[str, Any]:
    """Index & validate checks. ``published_hashes`` maps passage hashes of published practices to their id."""
    total = len(chunks)
    indexed = sum(1 for c in chunks if c["text"].strip())
    # Reference lists legitimately repeat across practices that cite the same sources; only guidance counts.
    hashes = [c["sha256"] for c in chunks if not _REFERENCE_HEADING_RE.match(_plain_heading(c.get("section", "")))]
    internal_dupes = len(hashes) - len(set(hashes))
    external = sorted({published_hashes[h] for h in hashes if h in published_hashes})
    located = sum(1 for c in chunks if c.get("page") or c.get("section"))
    references = citations["references"]
    attributed = citations["attributed"]
    retrieval = sample_retrieval(chunks)
    checks = [
        _row("iv-1", "Index coverage", indexed == total and total > 0, "Passed" if indexed == total and total else "Attention",
             f"{indexed} / {total} passages indexed"),
        _row("iv-2", "Duplicate scan", not internal_dupes and not external, "Passed" if not internal_dupes and not external else "Attention",
             f"{internal_dupes} exact duplicates" + (f" · overlaps {', '.join(p.upper() for p in external)}" if external else "")),
        _row("iv-3", "Permission metadata", bool(owner and classification and rights),
             "Passed" if owner and classification and rights else "Attention",
             "Owner & classification retained" if owner and classification and rights else "Owner, classification or rights missing"),
        _row("iv-4", "Locator integrity", located == total and total > 0, "Passed" if located == total and total else "Attention",
             f"{located} / {total} passages carry a page or section locator"),
        _row("iv-5", "Citation completeness", not citations["missing"], "Passed" if not citations["missing"] else "Attention",
             f"{len(attributed)} / {len(references)} references attributed" if references else "No references cited"),
    ]
    return {
        "indexed": indexed,
        "total": total,
        "internalDuplicates": internal_dupes,
        "overlapsWith": external,
        "checks": checks,
        "retrievalChecks": retrieval,
        "validatedAt": datetime.now().isoformat(timespec="minutes"),
    }


# --- 3. quality gates -----------------------------------------------------------------------------------------------


def quality_gates(job: dict[str, Any]) -> list[dict[str, Any]]:
    """The four publication gates. Every gate must pass before the candidate can be submitted or published."""
    validation = job.get("validation") or {}
    citations = job.get("citations") or {}
    checks = {c["id"]: c for c in validation.get("checks", [])}
    missing = citations.get("missing", [])
    references = citations.get("references", [])
    rights_ok = bool(job.get("rights") and job.get("owner"))
    dupes_ok = checks.get("iv-2", {}).get("passed", False)
    locators_ok = checks.get("iv-4", {}).get("passed", False) and checks.get("iv-1", {}).get("passed", False)
    return [
        _row("qg-1", "Provenance & rights", rights_ok, "Passed" if rights_ok else "Attention",
             job.get("rights") or "Add source attribution and rights"),
        _row("qg-2", "Citation verification", not missing,
             f"{len(references) - len(missing)} / {len(references)} verified" if references else "Passed",
             f"Correct reference {', '.join(str(n) for n in missing)}" if missing else "All cited references attributed"),
        _row("qg-3", "Classification & duplication", dupes_ok and bool(job.get("classification")),
             "Passed" if dupes_ok and job.get("classification") else "Attention",
             checks.get("iv-2", {}).get("detail", "Duplicate scan not run")),
        _row("qg-4", "Chunk & page integrity", locators_ok, "Passed" if locators_ok else "Attention",
             f"{job.get('chunkCount', 0)} chunks / {job.get('pages', 0)} pages"),
    ]


# --- 4. release -----------------------------------------------------------------------------------------------------


def practice_detail(blocks: list[dict[str, Any]]) -> dict[str, Any]:
    """The library detail panel content: a description, when to use it, and the core guidance."""
    paragraphs = [b["text"] for b in blocks if b["kind"] == "para" and len(b["text"].split()) >= 8]

    def sentence(text: str) -> str:
        first = re.split(r"(?<=[.!?])\s+", text.strip())[0]
        return first if len(first) <= 240 else first[:237].rstrip() + "…"

    description = sentence(paragraphs[0]) if paragraphs else ""
    guidance: list[str] = []
    for position, block in enumerate(blocks):
        if block["kind"] != "heading" or _REFERENCE_HEADING_RE.match(block["text"]):
            continue
        body = next((b["text"] for b in blocks[position + 1 :] if b["kind"] == "para"), "")
        label = re.sub(r"^\d+(?:\.\d+)*\.?\s*", "", block["text"])
        guidance.append(f"{label}: {sentence(body)}" if body else label)
        if len(guidance) == 5:
            break
    return {
        "description": description,
        "recommendedWhen": sentence(paragraphs[1]) if len(paragraphs) > 1 else description,
        "coreGuidance": guidance or [sentence(p) for p in paragraphs[:3]],
    }


def render_markdown(title: str, meta: dict[str, str], blocks: list[dict[str, Any]]) -> str:
    lines = [f"# {title}", ""]
    lines += [f"- **{key}:** {value}" for key, value in meta.items() if value]
    lines.append("")
    for block in blocks:
        if block["kind"] == "title":
            continue
        if block["kind"] == "heading":
            lines += [f"{'#' * min(6, block['level'] + 1)} {block['text']}", ""]
        else:
            lines += [block["text"], ""]
    return "\n".join(lines).rstrip() + "\n"


def write_release(practice_id: str, version: str, markdown: str) -> Path:
    """Replace the served body and keep an immutable copy of this release."""
    served = published_dir() / f"{practice_id}.md"
    served.parent.mkdir(parents=True, exist_ok=True)
    served.write_text(markdown, encoding="utf-8")
    archive = library_root() / "releases" / practice_id / f"{re.sub(r'[^A-Za-z0-9._-]+', '_', version)}.md"
    archive.parent.mkdir(parents=True, exist_ok=True)
    if not archive.exists():
        archive.write_text(markdown, encoding="utf-8")
    return served
