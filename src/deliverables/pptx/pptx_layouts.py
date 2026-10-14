"""Map slide types to real PowerPoint layouts (not Blank).

Using Title Slide / Title Only / Section Header layouts means Outline view
shows titles, Reset Slide restores placeholders, and screen readers get a
proper reading order for the title. Content shapes are still freeform on top.
"""

from __future__ import annotations

from typing import Any

# python-pptx default presentation layout indices
_LAYOUT_TITLE = 0
_LAYOUT_TITLE_CONTENT = 1
_LAYOUT_SECTION = 2
_LAYOUT_TITLE_ONLY = 5
_LAYOUT_BLANK = 6

_SLIDE_TYPE_LAYOUT: dict[str, int] = {
    "title": _LAYOUT_TITLE,
    "section_divider": _LAYOUT_SECTION,
    "bullets": _LAYOUT_TITLE_CONTENT,
    "stat_cards": _LAYOUT_TITLE_ONLY,
    "column_cards": _LAYOUT_TITLE_ONLY,
    "table": _LAYOUT_TITLE_ONLY,
    "chart": _LAYOUT_TITLE_ONLY,
    "big_number": _LAYOUT_TITLE_ONLY,
    "process_flow": _LAYOUT_TITLE_ONLY,
    "stack_layers": _LAYOUT_TITLE_ONLY,
    "split_panel": _LAYOUT_TITLE_ONLY,
    "lanes": _LAYOUT_TITLE_ONLY,
    "workstream_cards": _LAYOUT_TITLE_ONLY,
    "tower_cards": _LAYOUT_TITLE_ONLY,
    "roadmap_matrix": _LAYOUT_TITLE_ONLY,
    "swimlane_timeline": _LAYOUT_TITLE_ONLY,
    "flagship_cards": _LAYOUT_TITLE_ONLY,
}


def layout_index_for(slide_type: str, prs: Any) -> int:
    """Return a safe layout index for ``slide_type`` given the presentation's masters."""
    preferred = _SLIDE_TYPE_LAYOUT.get((slide_type or "").strip().lower(), _LAYOUT_TITLE_ONLY)
    n = len(prs.slide_layouts)
    if n <= 0:
        return 0
    if preferred < n:
        return preferred
    # Fall back: Title Only if present, else last layout (often Blank).
    if _LAYOUT_TITLE_ONLY < n:
        return _LAYOUT_TITLE_ONLY
    return n - 1


def add_slide_with_layout(prs: Any, slide_type: str, title: str = "") -> Any:
    """Add a slide from a named layout and seed the title placeholder when present."""
    idx = layout_index_for(slide_type, prs)
    slide = prs.slides.add_slide(prs.slide_layouts[idx])
    text = (title or "").strip()
    if text:
        try:
            if slide.shapes.title is not None:
                slide.shapes.title.text = text[:200]
        except Exception:  # noqa: BLE001,S110 — placeholder may be absent
            pass
    return slide


def _norm(text: str) -> str:
    return " ".join((text or "").split()).lower()


def _pin_textbox_look(tx_body: Any) -> None:
    """Keep a text box's look once it lives in a title placeholder.

    Text boxes default to left aligned and top anchored; a title placeholder inherits
    centred (or bottom-anchored) text from the layout. Write the text box defaults out
    explicitly wherever the copied text relied on them.
    """
    from pptx.oxml.ns import qn

    body_pr = tx_body.find(qn("a:bodyPr"))
    if body_pr is not None and body_pr.get("anchor") is None:
        body_pr.set("anchor", "t")
    for para in tx_body.findall(qn("a:p")):
        p_pr = para.find(qn("a:pPr"))
        if p_pr is None:
            p_pr = para.makeelement(qn("a:pPr"), {})
            para.insert(0, p_pr)
        if p_pr.get("algn") is None:
            p_pr.set("algn", "l")


def tidy_slide_placeholders(slide: Any) -> None:
    """Leave one title on the slide and no empty placeholders.

    The composers draw their own styled title text box, while the layout's title
    placeholder was also filled in (in the template's large default font), so every
    title appeared twice, overlapping. The styled text box's geometry and formatting are
    moved into the title placeholder, which keeps the title in Outline view and for
    screen readers, and the duplicate box is dropped. Placeholders nothing was written
    to (subtitle, body) are removed so they do not show "Click to add text".
    """
    import copy

    title = slide.shapes.title
    if title is not None and title.has_text_frame and title.text_frame.text.strip():
        wanted = _norm(title.text_frame.text)
        for shape in slide.shapes:
            if shape.is_placeholder or not shape.has_text_frame:
                continue
            text = _norm(shape.text_frame.text)
            if text and (text == wanted or text.startswith(wanted) or wanted.startswith(text)):
                title.left, title.top, title.width, title.height = shape.left, shape.top, shape.width, shape.height
                title_body = title._element.txBody
                styled = copy.deepcopy(shape._element.txBody)
                _pin_textbox_look(styled)
                title_body.getparent().replace(title_body, styled)
                shape._element.getparent().remove(shape._element)
                break
    for shape in list(slide.placeholders):
        if title is not None and shape.shape_id == title.shape_id:
            continue
        if not (shape.has_text_frame and shape.text_frame.text.strip()):
            shape._element.getparent().remove(shape._element)


def tidy_presentation(prs: Any) -> None:
    """Apply ``tidy_slide_placeholders`` to every slide; one bad slide must not stop the rest."""
    import logging

    for index, slide in enumerate(prs.slides):
        try:
            tidy_slide_placeholders(slide)
        except Exception as exc:  # noqa: BLE001 — leave that slide as rendered
            logging.getLogger(__name__).warning("placeholder clean-up skipped on slide %d: %s", index + 1, exc)


def set_slide_notes(slide: Any, text: str) -> None:
    """Write speaker notes from ``notes`` / ``speaker_notes`` content."""
    body = (text or "").strip()
    if not body:
        return
    try:
        notes = slide.notes_slide
        tf = notes.notes_text_frame
        tf.clear()
        # Keep notes readable: soft-wrap long blobs into paragraphs.
        chunks = [body[i : i + 900] for i in range(0, len(body), 900)] or [body]
        for i, chunk in enumerate(chunks):
            para = tf.paragraphs[0] if i == 0 and tf.paragraphs else tf.add_paragraph()
            if i > 0:
                para = tf.add_paragraph()
            para.text = chunk
    except Exception:  # noqa: BLE001,S110 — notes are best-effort
        pass
