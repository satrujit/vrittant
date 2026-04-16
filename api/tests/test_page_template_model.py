from app.models.page_template import PageTemplate


def test_page_template_create(db):
    tpl = PageTemplate(
        name="Front Page Lead",
        paper_size="broadsheet",
        width_mm=380.0,
        height_mm=560.0,
        zones=[
            {
                "id": "zone-1",
                "type": "headline",
                "x_mm": 20, "y_mm": 40,
                "width_mm": 170, "height_mm": 30,
                "columns": 1, "column_gap_mm": 4,
                "font_size_pt": 28, "font_family": "serif",
                "label": "Main Headline",
            }
        ],
        created_by="reviewer-1",
    )
    db.add(tpl)
    db.commit()
    db.refresh(tpl)

    assert tpl.id is not None
    assert tpl.name == "Front Page Lead"
    assert tpl.paper_size == "broadsheet"
    assert len(tpl.zones) == 1
    assert tpl.zones[0]["type"] == "headline"
    assert tpl.width_mm == 380.0


def test_page_template_defaults(db):
    tpl = PageTemplate(
        name="Minimal",
        width_mm=280.0,
        height_mm=430.0,
        zones=[],
    )
    db.add(tpl)
    db.commit()
    db.refresh(tpl)

    assert tpl.paper_size == "broadsheet"
    assert tpl.created_at is not None
