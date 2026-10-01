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
    DATABASE_URL: str = ""

    # ── AI / LLM — NVIDIA NIM (all nodes) ─────────────────────────────────
    # All four nodes (creative director, designer, programmer, reviewer) use
    # the same NVIDIA-hosted model via their OpenAI-compatible endpoint.
    NVIDIA_API_KEY: str = ""
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_MODEL: str = "moonshotai/kimi-k3"

    # Token limits per role — kimi-k3 supports up to 131072 output tokens,
    # but we cap conservatively to avoid cost spikes.
    PLANNER_MAX_TOKENS: int = 16000    # director, designer, reviewer
    PROGRAMMER_MAX_TOKENS: int = 32000  # programmer (large code output)

    # reasoning_effort: "default" | "max" — set to "max" for best quality,
    # "default" to reduce latency/cost on the planner nodes.
    PLANNER_REASONING_EFFORT: str = "max"
    PROGRAMMER_REASONING_EFFORT: str = "max"

    # Legacy keys kept so existing .env files don't break
    GROQ_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    PLANNER_PROVIDER: str = "openai"   # unused — kept for compat
    PLANNER_MODEL: str = "moonshotai/kimi-k3"  # unused — kept for compat
    PROGRAMMER_PROVIDER: str = "openai"  # unused — kept for compat
    PROGRAMMER_MODEL: str = "moonshotai/kimi-k3"  # unused — kept for compat
    GEMINI_THINKING_BUDGET: int = 0     # unused — kept for compat

    # ── QA ──────────────────────────────────────────────────────────────────
    # Total number of QA runs allowed (initial attempt + retries).
    # e.g. 4 = 1 initial + 3 retries
    QA_MAX_ATTEMPTS: int = 4

    # ── Supabase Auth ───────────────────────────────────────────────────────
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_JWT_SECRET: str = ""

    # ── CORS ────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:4173"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    # ── App metadata ────────────────────────────────────────────────────────
    APP_ENV: str = "development"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Module-level singleton — import this everywhere.
settings = Settings()
