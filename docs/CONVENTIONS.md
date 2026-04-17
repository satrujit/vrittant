# Vrittant Conventions

One canonical pattern per concern. When in doubt, follow these rules.

## 1. Backend: routers
- One router per `routers/<thing>.py`, mounted in `main.py`.
- Split into a sub-package (`routers/<thing>/__init__.py` + sub-modules) once one file would exceed ~400 LOC.
- Keep route handlers thin; push logic into `services/` or `utils/`.

## 2. Backend: scoping by org
- Always use `from app.utils.scope import get_owned_or_404`.
- Never write the manual `db.query(...).filter(org_id=...).first()` pattern by hand.
- Cross-org access returns 404, not 403.

## 3. Backend: authed endpoints
- Depend on `get_current_user` from `app.deps` for any authed route.
- For org_admin-only endpoints, depend on `get_org_admin` from `app.deps`. If absent, the first endpoint that needs it introduces it there — do not inline an `if user.role != "org_admin"` check at the route.
- Do not re-check roles inside the handler body.

## 4. Backend: external HTTP
- Use `httpx.AsyncClient` with an explicit `timeout=` argument.
- Never log response bodies (they may contain echoed credentials/OTPs/PII). Log status code, endpoint name, and the upstream request ID if the API returns one.

## 5. Backend: tests
- pytest, one test per behavior, use fixtures from `tests/conftest.py`.
- New tests must follow TDD: write the failing test first (see the TDD skill).
- Prefer behavioral assertions over implementation snapshots.

## 6. Panel: API calls
- Always go through `services/http.js` (`apiGet` / `apiPost` / `apiPut` / `apiDelete`).
- One `ApiError` shape, one 401 redirect path — do not reinvent per page.
- Page-level `try/catch { setError(...) }` produces a single error toast, not bespoke per-page UI.

## 7. Panel: forms + dialogs
- shadcn `Dialog` + `react-hook-form`. One pattern only.
- `useForm` -> `<form onSubmit={handleSubmit(onSave)}>` -> submit calls an API helper from `services/http.js`.
- No ad-hoc `useState` form scaffolding for new forms.

## 8. Panel: widgets
*Target layout — Phase 2.7 migrates existing widgets to this shape.*
- One renderer per file under `components/widgets/<Kind>.jsx`.
- The CATALOG mapping (kind -> component) lives in `components/widgets/index.js`.
- `WidgetsPage.jsx` consumes the CATALOG and renders the grid; it does not own the mapping.

## 9. Naming
- Files in `kebab-case` for routes/pages.
- `PascalCase` for React components.
- `snake_case` for Python modules, functions, and variables.

## 10. Commits
- Conventional Commits: `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`.
- One concern per commit. No mixed refactors + features.
