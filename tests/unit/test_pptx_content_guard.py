from src.deliverables.pptx.content_guard import is_placeholder, sanitize_slides, strip_leaks


def test_placeholder_detection():
    for t in ("TBD", "No steps extracted", "0 workflow steps", "N/A", "[TBC]", "Lorem ipsum"):
        assert is_placeholder(t)
    for t in ("14 workflow steps", "Finance Controller", "Invoice matching"):
        assert not is_placeholder(t)


def test_strip_internal_heading_from_title():
    assert strip_leaks("## ObjectiveNow Close acceleration") == "Close acceleration"
    slides, report = sanitize_slides([{"slide_type": "title", "title": "ObjectiveNow P2P transformation"}])
    assert slides[0]["title"] == "P2P transformation"
    assert report


def test_drops_empty_content_slide_keeps_title():
    slides, _ = sanitize_slides([
        {"slide_type": "title", "title": "Deck"},
        {"slide_type": "bullets", "title": "Empty", "bullets": ["TBD", "N/A"]},
        {"slide_type": "bullets", "title": "Real", "bullets": ["Invoices wait 12 days", "TBD"]},
    ])
    assert [s["title"] for s in slides] == ["Deck", "Real"]
    assert slides[1]["bullets"] == ["Invoices wait 12 days"]


def test_table_columns_stay_aligned():
    slides, _ = sanitize_slides([{
        "slide_type": "table", "title": "Owners",
        "table": {"headers": ["Step", "Owner", "Output"], "rows": [["Match", "TBD", "Paid"], ["TBD", "TBD", "TBD"]]},
    }])
    assert slides[0]["table"]["rows"] == [["Match", "", "Paid"]]


def test_ids_preserved():
    slides, _ = sanitize_slides([{
        "slide_type": "stat_cards", "title": "Scale", "slide_id": "slide_02",
        "stat_cards": [{"stat": "14", "label": "steps", "fill": "dark"}],
    }])
    assert slides[0]["slide_id"] == "slide_02"
    assert slides[0]["stat_cards"][0]["stat"] == "14"
