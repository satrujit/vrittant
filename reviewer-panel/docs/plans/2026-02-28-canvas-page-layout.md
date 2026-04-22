# Canvas Page Layout Preview — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a "Page Layout" tab in ReviewPage that renders the story onto a canvas-based newspaper page template, with config controls for zone layout and reusable template save/load.

**Architecture:** New `page_templates` table + CRUD API for templates. Frontend adds a tab system to ReviewPage's editor column. The canvas renderer (`useCanvasRenderer` hook) draws zones and flows story text using `measureText()`. Config panel alongside the canvas lets editors tweak zones and save templates.

**Tech Stack:** SQLAlchemy (model), FastAPI (API), React (components), HTML Canvas API (rendering), CSS Modules (styling)

---

### Task 1: PageTemplate Database Model

**Files:**
- Create: `newsflow-api/app/models/page_template.py`
- Modify: `newsflow-api/app/main.py:6` (add import)
- Test: `newsflow-api/tests/test_page_template_model.py`

**Step 1: Write the failing test**

```python
# tests/test_page_template_model.py
import json
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
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/admin/Desktop/newsflow-api && source venv/bin/activate && python -m pytest tests/test_page_template_model.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.models.page_template'`

**Step 3: Write the model**

```python
# app/models/page_template.py
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, JSON, String, ForeignKey
from sqlalchemy.orm import relationship

from ..database import Base


class PageTemplate(Base):
    __tablename__ = "page_templates"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    paper_size = Column(String, default="broadsheet")
    width_mm = Column(Float, nullable=False)
    height_mm = Column(Float, nullable=False)
    zones = Column(JSON, nullable=False, default=list)
    created_by = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    creator = relationship("User")
```

Then in `app/main.py`, add import after the StoryRevision import:

```python
from .models.page_template import PageTemplate  # noqa: F401
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/admin/Desktop/newsflow-api && source venv/bin/activate && python -m pytest tests/test_page_template_model.py -v`
Expected: 2 passed

**Step 5: Commit**

```bash
git add app/models/page_template.py app/main.py tests/test_page_template_model.py
git commit -m "feat: add PageTemplate model with JSON zones column"
```

---

### Task 2: layout_config Column on StoryRevision

**Files:**
- Modify: `newsflow-api/app/models/story_revision.py:17` (add column)
- Test: `newsflow-api/tests/test_story_revision_model.py` (add test)

**Step 1: Write the failing test**

Add to `tests/test_story_revision_model.py`:

```python
def test_revision_layout_config(db, sample_story, reviewer):
    from app.models.story_revision import StoryRevision

    rev = StoryRevision(
        story_id=sample_story.id,
        editor_id=reviewer.id,
        headline="Test",
        paragraphs=[],
        layout_config={
            "template_id": "tpl-1",
            "zones": [{"id": "z1", "type": "headline", "font_size_pt": 32}],
        },
    )
    db.add(rev)
    db.commit()
    db.refresh(rev)

    assert rev.layout_config is not None
    assert rev.layout_config["template_id"] == "tpl-1"


def test_revision_layout_config_defaults_to_none(db, sample_story, reviewer):
    from app.models.story_revision import StoryRevision

    rev = StoryRevision(
        story_id=sample_story.id,
        editor_id=reviewer.id,
        headline="Test",
        paragraphs=[],
    )
    db.add(rev)
    db.commit()
    db.refresh(rev)

    assert rev.layout_config is None
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/admin/Desktop/newsflow-api && source venv/bin/activate && python -m pytest tests/test_story_revision_model.py::test_revision_layout_config -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'layout_config'`

**Step 3: Add the column**

In `app/models/story_revision.py`, add after the `paragraphs` column (line ~17):

```python
    layout_config = Column(JSON, nullable=True, default=None)
```

**Step 4: Run all revision tests to verify**

Run: `cd /Users/admin/Desktop/newsflow-api && source venv/bin/activate && python -m pytest tests/test_story_revision_model.py -v`
Expected: All pass (existing + 2 new)

**Step 5: Commit**

```bash
git add app/models/story_revision.py tests/test_story_revision_model.py
git commit -m "feat: add layout_config JSON column to story_revisions"
```

---

### Task 3: Template CRUD API Endpoints

**Files:**
- Create: `newsflow-api/app/routers/templates.py`
- Modify: `newsflow-api/app/main.py:7,32` (import + register router)
- Test: `newsflow-api/tests/test_template_endpoints.py`

**Step 1: Write failing tests**

```python
# tests/test_template_endpoints.py

SAMPLE_TEMPLATE = {
    "name": "Front Page",
    "paper_size": "broadsheet",
    "width_mm": 380.0,
    "height_mm": 560.0,
    "zones": [
        {
            "id": "z1",
            "type": "headline",
            "x_mm": 20, "y_mm": 40,
            "width_mm": 170, "height_mm": 30,
            "columns": 1, "column_gap_mm": 4,
            "font_size_pt": 28, "font_family": "serif",
            "label": "Main Headline",
        },
        {
            "id": "z2",
            "type": "body",
            "x_mm": 20, "y_mm": 80,
            "width_mm": 340, "height_mm": 400,
            "columns": 3, "column_gap_mm": 4,
            "font_size_pt": 10, "font_family": "serif",
            "label": "Body Text",
        },
    ],
}


def test_create_template(client, auth_header):
    resp = client.post("/admin/templates", json=SAMPLE_TEMPLATE, headers=auth_header)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Front Page"
    assert len(data["zones"]) == 2
    assert data["id"] is not None


def test_list_templates(client, auth_header):
    client.post("/admin/templates", json=SAMPLE_TEMPLATE, headers=auth_header)
    resp = client.get("/admin/templates", headers=auth_header)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["name"] == "Front Page"


def test_get_template(client, auth_header):
    create_resp = client.post("/admin/templates", json=SAMPLE_TEMPLATE, headers=auth_header)
    tpl_id = create_resp.json()["id"]
    resp = client.get(f"/admin/templates/{tpl_id}", headers=auth_header)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Front Page"


def test_update_template(client, auth_header):
    create_resp = client.post("/admin/templates", json=SAMPLE_TEMPLATE, headers=auth_header)
    tpl_id = create_resp.json()["id"]
    resp = client.put(
        f"/admin/templates/{tpl_id}",
        json={"name": "Updated Name"},
        headers=auth_header,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Name"
    assert len(resp.json()["zones"]) == 2  # zones unchanged


def test_delete_template(client, auth_header):
    create_resp = client.post("/admin/templates", json=SAMPLE_TEMPLATE, headers=auth_header)
    tpl_id = create_resp.json()["id"]
    resp = client.delete(f"/admin/templates/{tpl_id}", headers=auth_header)
    assert resp.status_code == 204
    get_resp = client.get(f"/admin/templates/{tpl_id}", headers=auth_header)
    assert get_resp.status_code == 404
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/admin/Desktop/newsflow-api && source venv/bin/activate && python -m pytest tests/test_template_endpoints.py -v`
Expected: FAIL — 404 on `/admin/templates`

**Step 3: Write the router**

```python
# app/routers/templates.py
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models.page_template import PageTemplate
from ..models.user import User

router = APIRouter(prefix="/admin/templates", tags=["templates"])


class TemplateCreate(BaseModel):
    name: str
    paper_size: str = "broadsheet"
    width_mm: float
    height_mm: float
    zones: list[dict]


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    paper_size: Optional[str] = None
    width_mm: Optional[float] = None
    height_mm: Optional[float] = None
    zones: Optional[list[dict]] = None


class TemplateResponse(BaseModel):
    id: str
    name: str
    paper_size: str
    width_mm: float
    height_mm: float
    zones: list[dict]
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


@router.post("", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
def create_template(
    body: TemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tpl = PageTemplate(
        name=body.name,
        paper_size=body.paper_size,
        width_mm=body.width_mm,
        height_mm=body.height_mm,
        zones=body.zones,
        created_by=current_user.id,
    )
    db.add(tpl)
    db.commit()
    db.refresh(tpl)
    return tpl


@router.get("", response_model=list[TemplateResponse])
def list_templates(db: Session = Depends(get_db)):
    return db.query(PageTemplate).order_by(PageTemplate.updated_at.desc()).all()


@router.get("/{template_id}", response_model=TemplateResponse)
def get_template(template_id: str, db: Session = Depends(get_db)):
    tpl = db.query(PageTemplate).filter(PageTemplate.id == template_id).first()
    if not tpl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return tpl


@router.put("/{template_id}", response_model=TemplateResponse)
def update_template(
    template_id: str,
    body: TemplateUpdate,
    db: Session = Depends(get_db),
):
    tpl = db.query(PageTemplate).filter(PageTemplate.id == template_id).first()
    if not tpl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    if body.name is not None:
        tpl.name = body.name
    if body.paper_size is not None:
        tpl.paper_size = body.paper_size
    if body.width_mm is not None:
        tpl.width_mm = body.width_mm
    if body.height_mm is not None:
        tpl.height_mm = body.height_mm
    if body.zones is not None:
        tpl.zones = body.zones

    tpl.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(tpl)
    return tpl


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(template_id: str, db: Session = Depends(get_db)):
    tpl = db.query(PageTemplate).filter(PageTemplate.id == template_id).first()
    if not tpl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    db.delete(tpl)
    db.commit()
```

Then in `app/main.py`:
- Add import: `from .routers import admin, auth, editions, files, sarvam, stories, templates`
- Add registration: `app.include_router(templates.router)`

**Step 4: Run tests to verify they pass**

Run: `cd /Users/admin/Desktop/newsflow-api && source venv/bin/activate && python -m pytest tests/test_template_endpoints.py -v`
Expected: 5 passed

**Step 5: Run full test suite**

Run: `cd /Users/admin/Desktop/newsflow-api && source venv/bin/activate && python -m pytest tests/ -v`
Expected: All pass (existing 11 + 2 model + 5 endpoint = 18)

**Step 6: Commit**

```bash
git add app/routers/templates.py app/main.py tests/test_template_endpoints.py
git commit -m "feat: add template CRUD API endpoints"
```

---

### Task 4: Frontend API Service — Template Functions

**Files:**
- Modify: `reviewer-panel/src/services/api.js` (add template API functions at bottom)

**Step 1: Add template API functions**

Add before the `// ── Auth API ──` section in `api.js`:

```javascript
// ── Templates API ──

export async function fetchTemplates() {
  return apiFetch('/admin/templates');
}

export async function fetchTemplate(id) {
  return apiFetch(`/admin/templates/${id}`);
}

export async function createTemplate(data) {
  return apiFetch('/admin/templates', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateTemplate(id, data) {
  return apiFetch(`/admin/templates/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function deleteTemplate(id) {
  return apiFetch(`/admin/templates/${id}`, { method: 'DELETE' });
}
```

**Step 2: Verify build**

Run: `cd /Users/admin/Desktop/newsflow/reviewer-panel && npx vite build`
Expected: Build succeeds

**Step 3: Commit**

```bash
git add src/services/api.js
git commit -m "feat: add template CRUD functions to API service"
```

---

### Task 5: Canvas Renderer Hook — `useCanvasRenderer`

**Files:**
- Create: `reviewer-panel/src/components/PageLayoutPreview/useCanvasRenderer.js`

This is the core rendering engine. It takes a canvas ref, template config, and story content, then draws the newspaper page.

**Step 1: Create the hook**

```javascript
// src/components/PageLayoutPreview/useCanvasRenderer.js
import { useCallback, useEffect } from 'react';

const MM_TO_PX = 2.0; // scale factor: 1mm = 2px on canvas
const PT_TO_PX = 1.33; // approximate pt to px

/**
 * Wraps text into lines that fit within maxWidth.
 * Returns array of line strings.
 */
function wrapText(ctx, text, maxWidth) {
  const words = text.split(/\s+/).filter(Boolean);
  if (words.length === 0) return [];
  const lines = [];
  let currentLine = words[0];

  for (let i = 1; i < words.length; i++) {
    const testLine = currentLine + ' ' + words[i];
    const metrics = ctx.measureText(testLine);
    if (metrics.width > maxWidth) {
      lines.push(currentLine);
      currentLine = words[i];
    } else {
      currentLine = testLine;
    }
  }
  lines.push(currentLine);
  return lines;
}

/**
 * Draws text into a multi-column zone.
 * Returns number of lines that overflowed (didn't fit).
 */
function drawColumnText(ctx, text, zone, scale) {
  const x = zone.x_mm * scale;
  const y = zone.y_mm * scale;
  const w = zone.width_mm * scale;
  const h = zone.height_mm * scale;
  const cols = zone.columns || 1;
  const gap = (zone.column_gap_mm || 4) * scale;
  const fontSize = (zone.font_size_pt || 10) * PT_TO_PX;
  const lineHeight = fontSize * 1.4;
  const fontFamily = zone.font_family === 'serif'
    ? "'Noto Serif', 'Times New Roman', serif"
    : "'Noto Sans', 'Plus Jakarta Sans', sans-serif";

  ctx.font = `${fontSize}px ${fontFamily}`;
  ctx.fillStyle = '#1C1917';
  ctx.textBaseline = 'top';

  const colWidth = (w - gap * (cols - 1)) / cols;
  const lines = wrapText(ctx, text, colWidth);

  const maxLinesPerCol = Math.floor(h / lineHeight);
  let lineIdx = 0;

  for (let col = 0; col < cols && lineIdx < lines.length; col++) {
    const colX = x + col * (colWidth + gap);
    let currentY = y;

    for (let row = 0; row < maxLinesPerCol && lineIdx < lines.length; row++) {
      ctx.fillText(lines[lineIdx], colX, currentY);
      currentY += lineHeight;
      lineIdx++;
    }
  }

  return Math.max(0, lines.length - lineIdx);
}

/**
 * Draws a headline zone — single large text, bold.
 */
function drawHeadline(ctx, text, zone, scale) {
  const x = zone.x_mm * scale;
  const y = zone.y_mm * scale;
  const w = zone.width_mm * scale;
  const fontSize = (zone.font_size_pt || 28) * PT_TO_PX;
  const fontFamily = zone.font_family === 'serif'
    ? "'Noto Serif', 'Times New Roman', serif"
    : "'Noto Sans', 'Plus Jakarta Sans', sans-serif";

  ctx.font = `bold ${fontSize}px ${fontFamily}`;
  ctx.fillStyle = '#1C1917';
  ctx.textBaseline = 'top';

  const lines = wrapText(ctx, text, w);
  const lineHeight = fontSize * 1.2;
  lines.forEach((line, i) => {
    ctx.fillText(line, x, y + i * lineHeight);
  });
}

/**
 * Draws an image zone — placeholder rectangle with label.
 */
function drawImageZone(ctx, zone, scale, imageUrl) {
  const x = zone.x_mm * scale;
  const y = zone.y_mm * scale;
  const w = zone.width_mm * scale;
  const h = zone.height_mm * scale;

  ctx.fillStyle = '#F5F5F4';
  ctx.fillRect(x, y, w, h);
  ctx.strokeStyle = '#D6D3D1';
  ctx.lineWidth = 1;
  ctx.strokeRect(x, y, w, h);

  // Label
  ctx.font = '11px sans-serif';
  ctx.fillStyle = '#A8A29E';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(zone.label || 'Image', x + w / 2, y + h / 2);
  ctx.textAlign = 'start';
}

/**
 * Draws a masthead zone — newspaper name.
 */
function drawMasthead(ctx, text, zone, scale) {
  const x = zone.x_mm * scale;
  const y = zone.y_mm * scale;
  const w = zone.width_mm * scale;
  const fontSize = (zone.font_size_pt || 36) * PT_TO_PX;

  ctx.font = `bold ${fontSize}px 'Noto Serif', serif`;
  ctx.fillStyle = '#1C1917';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'top';
  ctx.fillText(text, x + w / 2, y);
  ctx.textAlign = 'start';
}

/**
 * Main render function — draws entire page.
 */
function renderPage(ctx, canvas, template, story) {
  const scale = MM_TO_PX;
  const pageW = template.width_mm * scale;
  const pageH = template.height_mm * scale;

  canvas.width = pageW;
  canvas.height = pageH;

  // White page background
  ctx.fillStyle = '#FFFFFF';
  ctx.fillRect(0, 0, pageW, pageH);

  // Page border
  ctx.strokeStyle = '#E7E5E4';
  ctx.lineWidth = 1;
  ctx.strokeRect(0, 0, pageW, pageH);

  // Build body text from paragraphs
  const bodyText = (story.paragraphs || [])
    .map((p) => (typeof p === 'string' ? p : p.text || ''))
    .filter(Boolean)
    .join(' ');

  // Draw each zone
  const zones = template.zones || [];
  for (const zone of zones) {
    // Zone guide border (dashed)
    ctx.setLineDash([4, 3]);
    ctx.strokeStyle = '#D6D3D1';
    ctx.lineWidth = 0.5;
    ctx.strokeRect(
      zone.x_mm * scale,
      zone.y_mm * scale,
      zone.width_mm * scale,
      zone.height_mm * scale,
    );
    ctx.setLineDash([]);

    switch (zone.type) {
      case 'headline':
        drawHeadline(ctx, story.headline || '', zone, scale);
        break;
      case 'body':
        drawColumnText(ctx, bodyText, zone, scale);
        break;
      case 'image':
        drawImageZone(ctx, zone, scale);
        break;
      case 'masthead':
        drawMasthead(ctx, zone.label || 'Newspaper', zone, scale);
        break;
      default:
        break;
    }
  }
}

/**
 * Hook: manages canvas rendering lifecycle.
 * @param {RefObject} canvasRef - ref to <canvas> element
 * @param {object} template - { width_mm, height_mm, zones: [...] }
 * @param {object} story - { headline, paragraphs: [...] }
 */
export default function useCanvasRenderer(canvasRef, template, story) {
  const render = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !template) return;
    const ctx = canvas.getContext('2d');
    renderPage(ctx, canvas, template, story || { headline: '', paragraphs: [] });
  }, [canvasRef, template, story]);

  useEffect(() => {
    render();
  }, [render]);

  return { render };
}
```

**Step 2: Verify build**

Run: `cd /Users/admin/Desktop/newsflow/reviewer-panel && npx vite build`
Expected: Build succeeds (no imports of this file yet, but no syntax errors)

**Step 3: Commit**

```bash
git add src/components/PageLayoutPreview/useCanvasRenderer.js
git commit -m "feat: add canvas renderer hook with multi-column text reflow"
```

---

### Task 6: LayoutConfigPanel Component

**Files:**
- Create: `reviewer-panel/src/components/PageLayoutPreview/LayoutConfigPanel.jsx`
- Create: `reviewer-panel/src/components/PageLayoutPreview/LayoutConfigPanel.module.css`

**Step 1: Create the config panel component**

```jsx
// src/components/PageLayoutPreview/LayoutConfigPanel.jsx
import { useState, useEffect } from 'react';
import { Plus, Trash2, Save } from 'lucide-react';
import { fetchTemplates, createTemplate } from '../../services/api';
import styles from './LayoutConfigPanel.module.css';

const ZONE_TYPES = ['headline', 'body', 'image', 'masthead'];
const PAPER_PRESETS = {
  broadsheet: { width_mm: 380, height_mm: 560 },
  tabloid: { width_mm: 280, height_mm: 430 },
};

function ZoneEditor({ zone, onChange, onRemove }) {
  const update = (key, value) => onChange({ ...zone, [key]: value });

  return (
    <div className={styles.zoneCard}>
      <div className={styles.zoneHeader}>
        <input
          className={styles.zoneLabel}
          value={zone.label || ''}
          onChange={(e) => update('label', e.target.value)}
          placeholder="Zone label"
        />
        <button className={styles.removeBtn} onClick={onRemove} title="Remove zone">
          <Trash2 size={14} />
        </button>
      </div>

      <div className={styles.zoneFields}>
        <label className={styles.field}>
          <span>Type</span>
          <select value={zone.type} onChange={(e) => update('type', e.target.value)}>
            {ZONE_TYPES.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </label>

        <div className={styles.fieldRow}>
          <label className={styles.field}>
            <span>X (mm)</span>
            <input type="number" value={zone.x_mm} onChange={(e) => update('x_mm', +e.target.value)} />
          </label>
          <label className={styles.field}>
            <span>Y (mm)</span>
            <input type="number" value={zone.y_mm} onChange={(e) => update('y_mm', +e.target.value)} />
          </label>
        </div>

        <div className={styles.fieldRow}>
          <label className={styles.field}>
            <span>W (mm)</span>
            <input type="number" value={zone.width_mm} onChange={(e) => update('width_mm', +e.target.value)} />
          </label>
          <label className={styles.field}>
            <span>H (mm)</span>
            <input type="number" value={zone.height_mm} onChange={(e) => update('height_mm', +e.target.value)} />
          </label>
        </div>

        {(zone.type === 'body' || zone.type === 'headline') && (
          <div className={styles.fieldRow}>
            <label className={styles.field}>
              <span>Cols</span>
              <input type="number" min={1} max={5} value={zone.columns || 1}
                onChange={(e) => update('columns', +e.target.value)} />
            </label>
            <label className={styles.field}>
              <span>Font (pt)</span>
              <input type="number" min={6} max={72} value={zone.font_size_pt || 10}
                onChange={(e) => update('font_size_pt', +e.target.value)} />
            </label>
          </div>
        )}
      </div>
    </div>
  );
}

export default function LayoutConfigPanel({ template, onChange }) {
  const [templates, setTemplates] = useState([]);
  const [saveName, setSaveName] = useState('');
  const [showSave, setShowSave] = useState(false);

  useEffect(() => {
    fetchTemplates().then(setTemplates).catch(() => {});
  }, []);

  const handleTemplateSelect = (e) => {
    const tpl = templates.find((t) => t.id === e.target.value);
    if (tpl) {
      onChange({
        ...tpl,
        _templateId: tpl.id,
      });
    }
  };

  const handlePaperPreset = (e) => {
    const preset = PAPER_PRESETS[e.target.value];
    if (preset) {
      onChange({ ...template, ...preset, paper_size: e.target.value });
    }
  };

  const updateZone = (idx, zone) => {
    const zones = [...template.zones];
    zones[idx] = zone;
    onChange({ ...template, zones });
  };

  const removeZone = (idx) => {
    const zones = template.zones.filter((_, i) => i !== idx);
    onChange({ ...template, zones });
  };

  const addZone = () => {
    const newZone = {
      id: `zone-${Date.now()}`,
      type: 'body',
      x_mm: 20,
      y_mm: 20,
      width_mm: 100,
      height_mm: 100,
      columns: 1,
      column_gap_mm: 4,
      font_size_pt: 10,
      font_family: 'serif',
      label: `Zone ${template.zones.length + 1}`,
    };
    onChange({ ...template, zones: [...template.zones, newZone] });
  };

  const handleSaveTemplate = async () => {
    if (!saveName.trim()) return;
    try {
      const created = await createTemplate({
        name: saveName.trim(),
        paper_size: template.paper_size || 'broadsheet',
        width_mm: template.width_mm,
        height_mm: template.height_mm,
        zones: template.zones,
      });
      setTemplates((prev) => [created, ...prev]);
      setSaveName('');
      setShowSave(false);
    } catch {
      // handle error silently
    }
  };

  return (
    <div className={styles.panel}>
      {/* Template selector */}
      <div className={styles.section}>
        <label className={styles.sectionLabel}>Template</label>
        <select
          className={styles.templateSelect}
          value={template._templateId || ''}
          onChange={handleTemplateSelect}
        >
          <option value="">Custom</option>
          {templates.map((t) => (
            <option key={t.id} value={t.id}>{t.name}</option>
          ))}
        </select>
      </div>

      {/* Paper size */}
      <div className={styles.section}>
        <label className={styles.sectionLabel}>Paper Size</label>
        <select
          className={styles.templateSelect}
          value={template.paper_size || 'broadsheet'}
          onChange={handlePaperPreset}
        >
          <option value="broadsheet">Broadsheet (380×560)</option>
          <option value="tabloid">Tabloid (280×430)</option>
        </select>
      </div>

      {/* Zones */}
      <div className={styles.section}>
        <div className={styles.sectionHeader}>
          <label className={styles.sectionLabel}>Zones</label>
          <button className={styles.addBtn} onClick={addZone}>
            <Plus size={14} /> Add
          </button>
        </div>
        {template.zones.map((zone, i) => (
          <ZoneEditor
            key={zone.id || i}
            zone={zone}
            onChange={(z) => updateZone(i, z)}
            onRemove={() => removeZone(i)}
          />
        ))}
      </div>

      {/* Save as template */}
      <div className={styles.section}>
        {showSave ? (
          <div className={styles.saveRow}>
            <input
              className={styles.saveInput}
              value={saveName}
              onChange={(e) => setSaveName(e.target.value)}
              placeholder="Template name"
            />
            <button className={styles.saveConfirmBtn} onClick={handleSaveTemplate}>
              <Save size={14} />
            </button>
          </div>
        ) : (
          <button className={styles.saveAsBtn} onClick={() => setShowSave(true)}>
            <Save size={14} /> Save as Template
          </button>
        )}
      </div>
    </div>
  );
}
```

**Step 2: Create CSS module**

```css
/* src/components/PageLayoutPreview/LayoutConfigPanel.module.css */

.panel {
  display: flex;
  flex-direction: column;
  gap: var(--vr-space-base);
  padding: var(--vr-space-base);
  overflow-y: auto;
  height: 100%;
}

.section { display: flex; flex-direction: column; gap: var(--vr-space-xs); }

.sectionHeader {
  display: flex; align-items: center; justify-content: space-between;
}

.sectionLabel {
  font-size: 11px; font-weight: var(--vr-weight-semibold);
  color: var(--vr-muted); text-transform: uppercase; letter-spacing: 0.05em;
}

.templateSelect {
  width: 100%; padding: 6px 8px; border: 1px solid var(--vr-border);
  border-radius: var(--vr-radius-sm); font-size: var(--vr-text-xs);
  font-family: var(--vr-font-sans); background: var(--vr-card-bg);
}

.addBtn {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 4px 8px; border: 1px solid var(--vr-border);
  border-radius: var(--vr-radius-sm); background: none;
  font-size: 11px; font-family: var(--vr-font-sans);
  color: var(--vr-coral); cursor: pointer;
}
.addBtn:hover { background: var(--vr-coral-light); }

.zoneCard {
  border: 1px solid var(--vr-border); border-radius: var(--vr-radius-md);
  padding: var(--vr-space-sm); background: var(--vr-card-bg);
}

.zoneHeader {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: var(--vr-space-xs);
}

.zoneLabel {
  border: none; font-size: var(--vr-text-xs); font-weight: var(--vr-weight-semibold);
  color: var(--vr-heading); background: transparent; flex: 1;
  font-family: var(--vr-font-sans);
}
.zoneLabel:focus { outline: none; border-bottom: 1px solid var(--vr-coral); }

.removeBtn {
  background: none; border: none; color: var(--vr-muted); cursor: pointer;
  padding: 2px;
}
.removeBtn:hover { color: var(--vr-status-rejected); }

.zoneFields { display: flex; flex-direction: column; gap: 4px; }

.fieldRow { display: flex; gap: 6px; }

.field {
  display: flex; flex-direction: column; gap: 2px; flex: 1;
}
.field span {
  font-size: 10px; color: var(--vr-muted); font-weight: var(--vr-weight-medium);
}
.field input, .field select {
  padding: 4px 6px; border: 1px solid var(--vr-border);
  border-radius: var(--vr-radius-sm); font-size: 12px;
  font-family: var(--vr-font-sans); width: 100%;
}
.field input:focus, .field select:focus {
  outline: none; border-color: var(--vr-coral);
}

.saveAsBtn {
  display: flex; align-items: center; gap: 6px; width: 100%;
  padding: 8px; border: 1px dashed var(--vr-border);
  border-radius: var(--vr-radius-md); background: none;
  font-size: var(--vr-text-xs); font-family: var(--vr-font-sans);
  color: var(--vr-section); cursor: pointer;
}
.saveAsBtn:hover { border-color: var(--vr-coral); color: var(--vr-coral); }

.saveRow { display: flex; gap: 6px; }

.saveInput {
  flex: 1; padding: 6px 8px; border: 1px solid var(--vr-border);
  border-radius: var(--vr-radius-sm); font-size: var(--vr-text-xs);
  font-family: var(--vr-font-sans);
}

.saveConfirmBtn {
  padding: 6px 10px; border: none; border-radius: var(--vr-radius-sm);
  background: var(--vr-coral); color: white; cursor: pointer;
}
```

**Step 3: Verify build**

Run: `cd /Users/admin/Desktop/newsflow/reviewer-panel && npx vite build`
Expected: Build succeeds

**Step 4: Commit**

```bash
git add src/components/PageLayoutPreview/
git commit -m "feat: add LayoutConfigPanel component with zone editor and template save"
```

---

### Task 7: PageLayoutCanvas Component

**Files:**
- Create: `reviewer-panel/src/components/PageLayoutPreview/PageLayoutCanvas.jsx`
- Create: `reviewer-panel/src/components/PageLayoutPreview/PageLayoutCanvas.module.css`
- Create: `reviewer-panel/src/components/PageLayoutPreview/index.js`

**Step 1: Create the canvas wrapper component**

```jsx
// src/components/PageLayoutPreview/PageLayoutCanvas.jsx
import { useRef } from 'react';
import useCanvasRenderer from './useCanvasRenderer';
import styles from './PageLayoutCanvas.module.css';

export default function PageLayoutCanvas({ template, story }) {
  const canvasRef = useRef(null);
  useCanvasRenderer(canvasRef, template, story);

  return (
    <div className={styles.canvasWrap}>
      <canvas ref={canvasRef} className={styles.canvas} />
    </div>
  );
}
```

```css
/* src/components/PageLayoutPreview/PageLayoutCanvas.module.css */

.canvasWrap {
  flex: 1;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  overflow: auto;
  padding: var(--vr-space-base);
  background: var(--vr-bg);
}

.canvas {
  box-shadow: var(--vr-shadow-lg);
  border-radius: 2px;
  max-width: 100%;
  height: auto;
}
```

```javascript
// src/components/PageLayoutPreview/index.js
export { default as PageLayoutCanvas } from './PageLayoutCanvas';
export { default as LayoutConfigPanel } from './LayoutConfigPanel';
```

**Step 2: Verify build**

Run: `cd /Users/admin/Desktop/newsflow/reviewer-panel && npx vite build`
Expected: Build succeeds

**Step 3: Commit**

```bash
git add src/components/PageLayoutPreview/
git commit -m "feat: add PageLayoutCanvas wrapper and barrel export"
```

---

### Task 8: Integrate Page Layout Tab into ReviewPage

**Files:**
- Modify: `reviewer-panel/src/pages/ReviewPage.jsx` (add tab state, import components, render tab content)
- Modify: `reviewer-panel/src/pages/ReviewPage.module.css` (add tab bar + layout tab styles)

This is the integration task. Key changes:

**Step 1: Add imports to ReviewPage.jsx (top of file)**

After existing imports, add:

```javascript
import { PageLayoutCanvas, LayoutConfigPanel } from '../components/PageLayoutPreview';
```

**Step 2: Add state for tab and template config**

After existing `useState` declarations (around line 70), add:

```javascript
const [activeTab, setActiveTab] = useState('editor'); // 'editor' | 'layout'
const [layoutTemplate, setLayoutTemplate] = useState({
  paper_size: 'broadsheet',
  width_mm: 380,
  height_mm: 560,
  zones: [
    { id: 'z1', type: 'masthead', x_mm: 20, y_mm: 10, width_mm: 340, height_mm: 25, columns: 1, column_gap_mm: 4, font_size_pt: 36, font_family: 'serif', label: 'Pragativadi' },
    { id: 'z2', type: 'headline', x_mm: 20, y_mm: 45, width_mm: 340, height_mm: 35, columns: 1, column_gap_mm: 4, font_size_pt: 28, font_family: 'serif', label: 'Headline' },
    { id: 'z3', type: 'body', x_mm: 20, y_mm: 90, width_mm: 340, height_mm: 450, columns: 3, column_gap_mm: 5, font_size_pt: 10, font_family: 'serif', label: 'Body Text' },
  ],
});
```

**Step 3: Add tab bar in JSX**

In the editor column (after the chip row at line ~692, before the toolbar), add a tab bar:

```jsx
{/* Tab bar: Editor | Page Layout */}
<div className={styles.tabBar}>
  <button
    className={`${styles.tab} ${activeTab === 'editor' ? styles.tabActive : ''}`}
    onClick={() => setActiveTab('editor')}
  >
    Editor
  </button>
  <button
    className={`${styles.tab} ${activeTab === 'layout' ? styles.tabActive : ''}`}
    onClick={() => setActiveTab('layout')}
  >
    Page Layout
  </button>
</div>
```

**Step 4: Wrap editor content in conditional, add layout tab**

Wrap the toolbar + editor + word count + attachments + voice indicators + bottom bar in `{activeTab === 'editor' && ( ... )}`.

Then add the layout tab content:

```jsx
{activeTab === 'layout' && (
  <div className={styles.layoutTab}>
    <PageLayoutCanvas
      template={layoutTemplate}
      story={{
        headline: headline,
        paragraphs: story?.paragraphs || [],
      }}
    />
    <LayoutConfigPanel
      template={layoutTemplate}
      onChange={setLayoutTemplate}
    />
  </div>
)}
```

**Step 5: Add CSS for tab bar and layout tab**

Add to `ReviewPage.module.css`:

```css
/* ── Tab Bar ── */

.tabBar {
  display: flex;
  gap: 0;
  border-bottom: 1px solid var(--vr-border);
  margin-bottom: var(--vr-space-sm);
}

.tab {
  padding: var(--vr-space-sm) var(--vr-space-base);
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  font-family: var(--vr-font-sans);
  font-size: var(--vr-text-sm);
  font-weight: var(--vr-weight-medium);
  color: var(--vr-muted);
  cursor: pointer;
  transition: all var(--vr-transition-fast);
}

.tab:hover {
  color: var(--vr-heading);
}

.tabActive {
  color: var(--vr-coral);
  border-bottom-color: var(--vr-coral);
}

/* ── Layout Tab ── */

.layoutTab {
  display: flex;
  flex: 1;
  gap: var(--vr-space-base);
  overflow: hidden;
}
```

**Step 6: Verify build**

Run: `cd /Users/admin/Desktop/newsflow/reviewer-panel && npx vite build`
Expected: Build succeeds

**Step 7: Visual verification**

Start dev server, navigate to a story review page, switch to "Page Layout" tab. Verify:
- Canvas renders a page with masthead, headline, and body text in 3 columns
- Config panel shows zone list with editable fields
- Changing font size or column count re-renders the canvas

**Step 8: Commit**

```bash
git add src/pages/ReviewPage.jsx src/pages/ReviewPage.module.css
git commit -m "feat: integrate Page Layout tab with canvas preview and config panel"
```

---

### Task 9: Wire layout_config to Story Save

**Files:**
- Modify: `newsflow-api/app/routers/admin.py:112-116` (add `layout_config` to `AdminStoryUpdate`)
- Modify: `newsflow-api/app/routers/admin.py:370-392` (save `layout_config` on revision)
- Modify: `newsflow-api/app/routers/admin.py:70-78` (add `layout_config` to `AdminRevisionInfo`)
- Modify: `reviewer-panel/src/pages/ReviewPage.jsx` (include layout_config in save payload)

**Step 1: Write the failing test**

```python
# Add to tests/test_admin_revision_endpoints.py

def test_save_layout_config(client, auth_header, sample_story):
    layout = {
        "template_id": "tpl-1",
        "zones": [{"id": "z1", "type": "headline", "font_size_pt": 32}],
    }
    resp = client.put(
        f"/admin/stories/{sample_story.id}",
        json={"headline": "Test", "layout_config": layout},
        headers=auth_header,
    )
    assert resp.status_code == 200
    assert resp.json()["revision"]["layout_config"] == layout
```

**Step 2: Run test — should fail**

Run: `cd /Users/admin/Desktop/newsflow-api && source venv/bin/activate && python -m pytest tests/test_admin_revision_endpoints.py::test_save_layout_config -v`
Expected: FAIL — `layout_config` not in response

**Step 3: Update backend**

In `admin.py`:

1. Add to `AdminStoryUpdate`:
   ```python
   layout_config: Optional[dict] = None
   ```

2. Add to `AdminRevisionInfo`:
   ```python
   layout_config: Optional[dict] = None
   ```

3. In the PUT endpoint, after setting `existing_rev.paragraphs` / `new_rev` creation, add layout_config handling:
   ```python
   # In the existing_rev branch:
   if body.layout_config is not None:
       existing_rev.layout_config = body.layout_config

   # In the new_rev creation, add:
   # layout_config=body.layout_config,
   ```

**Step 4: Update frontend save**

In `ReviewPage.jsx`, find `handleSaveContent` and add `layout_config` to the payload when the layout tab has been used:

```javascript
const payload = { headline, paragraphs: /* existing */ };
if (layoutTemplate && activeTab === 'layout') {
  payload.layout_config = {
    template_id: layoutTemplate._templateId || null,
    paper_size: layoutTemplate.paper_size,
    width_mm: layoutTemplate.width_mm,
    height_mm: layoutTemplate.height_mm,
    zones: layoutTemplate.zones,
  };
}
```

**Step 5: Run tests**

Run: `cd /Users/admin/Desktop/newsflow-api && source venv/bin/activate && python -m pytest tests/ -v`
Expected: All pass

**Step 6: Commit**

```bash
# Backend
cd /Users/admin/Desktop/newsflow-api
git add app/routers/admin.py tests/test_admin_revision_endpoints.py
git commit -m "feat: persist layout_config on story revision save"

# Frontend
cd /Users/admin/Desktop/newsflow/reviewer-panel
git add src/pages/ReviewPage.jsx
git commit -m "feat: include layout_config in story save payload"
```

---

### Task 10: Load Saved Layout on Story Fetch

**Files:**
- Modify: `reviewer-panel/src/pages/ReviewPage.jsx` (load layout_config from revision on fetch)

**Step 1: Update the story fetch effect**

In the `useEffect` that loads the story (find the block that checks `rev.headline`), add after loading revision content:

```javascript
// Load saved layout config if present
if (rev.layout_config) {
  setLayoutTemplate({
    ...rev.layout_config,
    _templateId: rev.layout_config.template_id || null,
  });
}
```

**Step 2: Visual verification**

1. Open a story, switch to Page Layout tab, change a zone's font size
2. Save the story
3. Reload the page — layout config should be restored

**Step 3: Commit**

```bash
git add src/pages/ReviewPage.jsx
git commit -m "feat: restore saved layout_config when loading story revision"
```

---

### Task 11: Final Integration Test + Backend Restart

**Step 1: Run full backend test suite**

Run: `cd /Users/admin/Desktop/newsflow-api && source venv/bin/activate && python -m pytest tests/ -v`
Expected: All pass

**Step 2: Run frontend build**

Run: `cd /Users/admin/Desktop/newsflow/reviewer-panel && npx vite build`
Expected: Build succeeds with no errors

**Step 3: Restart backend**

```bash
kill $(pgrep -f 'uvicorn app.main:app') 2>/dev/null
cd /Users/admin/Desktop/newsflow-api && source venv/bin/activate
nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/newsflow-api.log 2>&1 &
```

**Step 4: End-to-end visual verification**

1. Open reviewer panel → navigate to a story
2. Editor tab works as before
3. Switch to Page Layout tab → canvas shows story in newspaper format
4. Tweak zone columns, font size → canvas re-renders
5. Save as template → template appears in dropdown
6. Save story → reload → layout restored

**Step 5: Commit any remaining fixes**
