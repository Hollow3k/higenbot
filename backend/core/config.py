"""
core/config.py
--------------
Single source of truth for every env-var the app needs.

pydantic-settings reads fields from the .env file (and from real env vars,
which take priority).  Any file that needs a value just does:

    from core.config import settings
    print(settings.GROQ_API_KEY)

No raw os.getenv() calls anywhere else.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Database ────────────────────────────────────────────────────────────
    # Supabase "Transaction mode" connection string (port 6543) for async use.
    # Example: postgresql+asyncpg://postgres:[password]@db.[ref].supabase.co:6543/postgres
    DATABASE_URL: str = ""

    # ── AI / LLM ────────────────────────────────────────────────────────────
    GROQ_API_KEY: str = ""

    # ── Supabase Auth ───────────────────────────────────────────────────────
    # Project URL — shown on the Supabase dashboard under Settings → API.
    # Example: https://xyzcompany.supabase.co
    SUPABASE_URL: str = ""

    # Public anon key — Settings → API → Project API keys.
    # Used for Supabase Auth verification requests.
    SUPABASE_ANON_KEY: str = ""

    # JWT Secret — Settings → API → JWT Settings → "JWT Secret".
    # The backend uses this to *verify* tokens that Supabase issued; it never
    # creates tokens itself.
    SUPABASE_JWT_SECRET: str = ""

    # ── CORS ────────────────────────────────────────────────────────────────
    # Comma-separated list of allowed origins for CORS.
    # In development this is overridden by the explicit list in main.py; you
    # can also set it here for production (e.g. "https://higenbot.vercel.app").
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:4173"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    # ── App metadata ────────────────────────────────────────────────────────
    APP_ENV: str = "development"  # "development" | "production"

    # Tell pydantic-settings to load from a .env file sitting next to this
    # project.  env_file is resolved relative to the *working directory* when
    # uvicorn is started (i.e., the backend/ folder).
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # Allow extra fields in .env without raising validation errors
        extra="ignore",
    )


# Module-level singleton — import this everywhere.
settings = Settings()
