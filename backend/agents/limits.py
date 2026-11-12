"""
agents/limits.py
----------------
Token budgets and input guards for every LLM call.

Model: nvidia/nemotron-3-ultra-550b-a55b:free on OpenRouter
    context window : 1,000,000 tokens
    max output     :    65,536 tokens (reasoning tokens count against it)

We operate far below both limits. Quality drops and latency grows long before
the hard limits, and free endpoints can enforce lower limits than advertised.
Token counts are estimated from character counts (no tokenizer dependency);
the ratio is deliberately pessimistic so estimates err high.
"""

import json
import math
import re

# ── Hard model limits (for reference / sanity checks) ───────────────────────
MODEL_CONTEXT_WINDOW = 1_000_000
MODEL_MAX_OUTPUT = 65_536

# ── Operating budgets ───────────────────────────────────────────────────────
# Input: ~6% of the window. A full game is ~12k tokens, so this leaves room
# for the brief, the prompt, a retry copy of the code, and tool-call history.
MAX_INPUT_TOKENS = 60_000

# Output caps per call (include reasoning tokens). The programmer cap is
# ~49% of the model maximum; a 900-line game is roughly 12k tokens.
#   creative : JSON ~1k tokens   + reasoning headroom
#   designer : JSON ~4-6k tokens + reasoning headroom
#   programmer: ~800 lines is ~12k tokens + reasoning headroom
CREATIVE_MAX_OUTPUT = 8_000
DESIGNER_MAX_OUTPUT = 16_000
PROGRAMMER_MAX_OUTPUT = 32_000

# Reasoning effort sent to OpenRouter. Planning needs little; code needs more.
PLANNER_REASONING_EFFORT = "low"
PROGRAMMER_REASONING_EFFORT = "medium"

# ── Untrusted-input caps ────────────────────────────────────────────────────
MAX_PROMPT_CHARS = 2_000          # user's game idea
MAX_EDIT_MESSAGE_CHARS = 1_000    # one chat edit request
MAX_PROJECT_FILES = 12

_CHARS_PER_TOKEN = 3.0


class BudgetExceeded(ValueError):
    """Raised when an input would not fit within the operating budget."""


def estimate_tokens(text: str) -> int:
    return math.ceil(len(text) / _CHARS_PER_TOKEN)


def message_tokens(message) -> int:
    """Estimate the tokens one LangChain message adds to a request."""
    content = message.content
    text = content if isinstance(content, str) else json.dumps(content, default=str)
    calls = getattr(message, "tool_calls", None) or []
    extra = json.dumps(calls, default=str) if calls else ""
    return estimate_tokens(text) + estimate_tokens(extra) + 4


def messages_tokens(messages) -> int:
    return sum(message_tokens(m) for m in messages)


def trim_history(history: list, max_tokens: int) -> list:
    """Drop the oldest messages until the history fits in max_tokens."""
    history = list(history)
    while history and messages_tokens(history) > max_tokens:
        history.pop(0)
    return history


def render_files(files: dict[str, str], max_tokens: int) -> str:
    """
    Render files in the same `--- path --- ... --- end ---` format the model is
    asked to answer in. Raises BudgetExceeded instead of silently truncating,
    because a half-shown file would be rewritten as a half-deleted file.
    """
    if len(files) > MAX_PROJECT_FILES:
        raise BudgetExceeded(
            f"Project has {len(files)} files; the limit is {MAX_PROJECT_FILES}."
        )
    text = "\n\n".join(
        f"--- {path} ---\n{content}\n--- end ---" for path, content in files.items()
    )
    used = estimate_tokens(text)
    if used > max_tokens:
        raise BudgetExceeded(
            f"Project files are about {used:,} tokens; the limit for one request is {max_tokens:,}."
        )
    return text


def normalize_path(raw: str) -> str | None:
    """
    Return a safe relative POSIX path, or None if the path is unsafe.
    File names come from the model or the client, so they must never be able
    to escape the directory they are written into.
    """
    path = str(raw).strip().replace("\\", "/")
    path = re.sub(r"^(\./)+", "", path).lstrip("/")
    if not path or len(path) > 120:
        return None
    if not re.fullmatch(r"[\w.\- /]+", path):
        return None
    if any(part in ("", ".", "..") for part in path.split("/")):
        return None
    return path
