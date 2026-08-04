"""
main.py
-------
FastAPI application entry point.

Start the server:
    uvicorn main:app --reload
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.config import settings
from api.projects import router as projects_router

app = FastAPI(
    title="HigenBot API",
    description="AI-powered game studio simulator backend",
    version="0.1.0",
)

# ── CORS ─────────────────────────────────────────────────────────────────────
# Origins are read from settings (which reads from .env).
# In development the default list in config.py covers localhost:5173 and :4173.
# In production set ALLOWED_ORIGINS in the environment to your Vercel URL.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
# No api/auth.py — Supabase handles the full auth lifecycle.
# The frontend logs in via the Supabase JS SDK; the backend only verifies the
# JWT that Supabase issues (implemented in Phase 3 → core/security.py).
app.include_router(projects_router)


# ── Error handling ───────────────────────────────────────────────────────────
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "error": "http_error"},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "error": "validation_error"},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": "internal_server_error"},
    )

# ── Health ───────────────────────────────────────────────────────────────────
@app.get("/health", tags=["meta"])
async def health():
    return {
        "status": "ok",
        "service": "higenbot-api",
        "env": settings.APP_ENV,
    }
