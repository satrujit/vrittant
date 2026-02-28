# Security Hardening + AWS Deployment Design

**Date:** 2026-02-28
**Status:** Approved — saved for later implementation
**Target:** EC2 + RDS PostgreSQL + S3

## Architecture

```
         Route 53 DNS (newsflow.app)
                  |
         ALB / SSL Termination
                  |
        EC2 (t3.small) — Nginx
        |                    |
   React dist/        Gunicorn+Uvicorn
   (static)           FastAPI backend
                       |       |       |
                  RDS Postgres  S3    Secrets Manager
                  (db.t3.micro) (files) (API keys)
```

## Security Audit Summary

### Critical (6 issues)
1. **Hardcoded API keys** in `config.py` — OpenAI + Sarvam keys exposed in source
2. **CORS allows all origins** (`*`) with credentials — CSRF vulnerability
3. **Hardcoded OTP (`123456`)** — trivial authentication bypass
4. **15+ admin endpoints unprotected** — no `Depends(get_current_user)`
5. **No rate limiting** — brute-force/DoS trivial on all endpoints
6. **Weak JWT secret** — predictable dev string

### High (9 issues)
7. No file upload validation (any type, no size limit)
8. SQLite in production (no concurrency)
9. Entitlements table never enforced server-side
10. No file type/MIME validation
11. WebSocket JWT in query params (logged in proxy/browser)
12. No database migrations (uses create_all())
13. No deployment infrastructure (Dockerfile, nginx, systemd)
14. No .env.example
15. 30-day JWT expiry too long

### Medium (36 issues)
- No security headers, no CSRF protection, no structured logging
- No audit trail, no token refresh, no logout mechanism
- JSON columns without validation, status enums not enforced
- No database backups, no monitoring, no health checks

## Implementation Plan

### Phase 1: Security Hardening
1. Remove hardcoded keys — use `.env` + `pydantic-settings`
2. Fix CORS — env-configurable origin whitelist
3. Replace hardcoded OTP with Firebase Auth (separate task)
4. Protect admin endpoints — `Depends(get_current_user)` + role check
5. Add rate limiting — `slowapi` (5/min OTP, 30/min API)
6. Add file upload validation — whitelist extensions, 10MB max
7. Add security headers middleware
8. Strengthen JWT — 256-bit random secret, 7-day expiry

### Phase 2: Database Migration
1. Add Alembic for migrations
2. Switch to PostgreSQL via `DATABASE_URL` env var
3. Configure connection pooling
4. Add enum constraints for status/user_type

### Phase 3: File Storage
1. Add `boto3` for S3 uploads
2. Replace local `/uploads` with S3 bucket
3. Presigned URLs for file access

### Phase 4: Deployment Infrastructure
1. Dockerfile for FastAPI backend
2. nginx.conf for reverse proxy + React static hosting
3. docker-compose.yml for local dev (API + Postgres + nginx)
4. systemd service for EC2 production
5. Gunicorn with Uvicorn workers
6. `.env.example` with all required variables

### Phase 5: Frontend Config
1. Replace hardcoded `API_BASE = '192.168.1.7:8000'` with `VITE_API_BASE` env var
2. Same for Flutter app `ApiConfig.baseUrl`

## AWS Resources (estimated ~$50-80/mo)
- EC2 t3.small: ~$15/mo
- RDS db.t3.micro PostgreSQL: ~$15/mo
- S3 bucket: ~$1-5/mo
- ALB (optional): ~$20/mo
- Route 53: ~$0.50/mo
- Secrets Manager: ~$1/mo
