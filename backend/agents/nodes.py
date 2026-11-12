"""
agents/nodes.py
---------------
The four agent nodes that comprise the game-generation pipeline.

Each node receives the shared GraphState and returns a partial dict
with only the keys it wants to update.
"""

import json
import re
import subprocess
import tempfile
import os
import threading
import time
from collections import deque
from pathlib import Path

from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from dotenv import load_dotenv

from agents.briefs import compact_json, design_brief, vision_brief
from agents.files import finalize_project, parse_file_blocks, sanitize_files
from agents.limits import (
    CREATIVE_MAX_OUTPUT,
    DESIGNER_MAX_OUTPUT,
    MAX_INPUT_TOKENS,
    MAX_PROMPT_CHARS,
    PLANNER_REASONING_EFFORT,
    PROGRAMMER_MAX_OUTPUT,
    PROGRAMMER_REASONING_EFFORT,
    BudgetExceeded,
    estimate_tokens,
    render_files,
)
from agents.schemas import CreativeVision, DesignDoc, QAReport, schema_hint
from agents.state import GraphState

load_dotenv()

# ── LLM instances ───────────────────────────────────────────────────────────
# All nodes run on OpenRouter (OpenAI-compatible API) with the same model.
_OPENROUTER_MODEL   = os.environ.get("OPENROUTER_MODEL", "nvidia/nemotron-3-ultra-550b-a55b:free")
_OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
_OPENROUTER_URL     = "https://openrouter.ai/api/v1"

def _make_llm(max_tokens: int, temperature: float, effort: str, timeout: int = 240) -> ChatOpenAI:
    """
    One OpenRouter client. max_tokens includes reasoning tokens, so each caller
    gets a budget from agents.limits that leaves room for both the thinking and
    the answer. Context and output sizes are documented in agents/limits.py.
    """
    return ChatOpenAI(
        model=_OPENROUTER_MODEL,
        api_key=_OPENROUTER_API_KEY,    # type: ignore[arg-type]
        base_url=_OPENROUTER_URL,
        max_tokens=max_tokens,
        temperature=temperature,
        # A stalled free-tier request must fail fast. Worst case per call is
        # timeout * (1 + max_retries); measured healthy calls take 15-210s.
        timeout=timeout,
        max_retries=1,
        extra_body={"reasoning": {"effort": effort}},
    )


# Creative Director: imaginative, so a higher temperature.
creative_llm = _make_llm(CREATIVE_MAX_OUTPUT, 0.8, PLANNER_REASONING_EFFORT)
# Game Designer: must produce consistent numbers, so a lower temperature.
designer_llm = _make_llm(DESIGNER_MAX_OUTPUT, 0.5, PLANNER_REASONING_EFFORT)
# Gameplay Programmer and the /ws/edit endpoint.
programmer_llm = _make_llm(PROGRAMMER_MAX_OUTPUT, 0.2, PROGRAMMER_REASONING_EFFORT, timeout=420)

_PROGRAMMER_REQUEST_LIMIT = 5
_PROGRAMMER_REQUEST_WINDOW = 60.0
_programmer_request_times: deque[float] = deque()
_programmer_request_lock = threading.Lock()


def wait_for_programmer_request_slot() -> None:
    """Throttle programmer requests to five starts per rolling minute."""
    while True:
        with _programmer_request_lock:
            now = time.monotonic()
            while (
                _programmer_request_times
                and now - _programmer_request_times[0] >= _PROGRAMMER_REQUEST_WINDOW
            ):
                _programmer_request_times.popleft()

            if len(_programmer_request_times) < _PROGRAMMER_REQUEST_LIMIT:
                _programmer_request_times.append(now)
                return

            wait_seconds = _PROGRAMMER_REQUEST_WINDOW - (
                now - _programmer_request_times[0]
            )

        time.sleep(max(wait_seconds, 0.01))


def _get_content(response) -> str:
    """
    Extract the text content from a chat model response robustly.

    Reasoning models (deepseek-v4.1-flash, kimi-k3, etc.) sometimes return:
    - response.content as a list of dicts with {"type": "text", "text": "..."}
    - response.content as empty string with the real text in additional_kwargs
    - response.content as a plain string (normal case)
    """
    content = response.content

    # Case 1: list of content parts (multimodal / reasoning model format)
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict):
                parts.append(part.get("text", "") or part.get("content", ""))
            else:
                parts.append(str(part))
        content = "".join(parts)

    content = str(content).strip()

    # Case 2: empty content — look in additional_kwargs
    if not content:
        kwargs = getattr(response, "additional_kwargs", {})
        # Check for reasoning_content / content fields
        content = (
            kwargs.get("content", "")
            or kwargs.get("reasoning_content", "")
            or ""
        )
        # Also check response_metadata
        meta = getattr(response, "response_metadata", {}) or {}
        if not content:
            content = meta.get("content", "") or ""

    return str(content).strip()


def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response, handling markdown code blocks and thinking tags."""
    # Remove <think>...</think> blocks (reasoning tokens)
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # Try to find JSON in code blocks first
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        text = match.group(1)
    text = text.strip()
    if not text:
        raise ValueError("LLM returned empty content after stripping think blocks")
    # Remove trailing commas before } or ] (common LLM mistake)
    text = re.sub(r",\s*([}\]])", r"\1", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            return json.loads(text[start:end + 1])
        raise


# ─────────────────────────────────────────────────────────────────────────────
# Shared helper: ask for JSON, validate against a Pydantic model, retry on error
# ─────────────────────────────────────────────────────────────────────────────

_MAX_PLANNER_ATTEMPTS = 3


def _finish_reason(response) -> str:
    meta = getattr(response, "response_metadata", {}) or {}
    return str(meta.get("finish_reason", "") or "")


def log_call(label: str, response, started: float) -> None:
    """One diagnostic line per LLM call: time, finish reason, token usage, reply size."""
    usage = getattr(response, "usage_metadata", None) or {}
    details = usage.get("output_token_details") or {}
    print(
        f"[llm] {label}: {time.monotonic() - started:.0f}s "
        f"finish={_finish_reason(response) or '?'} "
        f"in={usage.get('input_tokens', '?')} out={usage.get('output_tokens', '?')} "
        f"reasoning={details.get('reasoning', '?')} reply_chars={len(_get_content(response))}",
        flush=True,
    )


def _structured_call(model, messages: list, model_class):
    """
    Invoke `model`, parse the reply as JSON, validate it with `model_class`.
    On failure the validation error is sent back so the model can correct it.
    """
    if estimate_tokens("".join(str(m.content) for m in messages)) > MAX_INPUT_TOKENS:
        raise BudgetExceeded("Planner input is larger than the input budget.")

    last_exc: Exception | None = None
    for _ in range(_MAX_PLANNER_ATTEMPTS):
        wait_for_programmer_request_slot()
        started = time.monotonic()
        response = model.invoke(messages)
        log_call(model_class.__name__, response, started)
        text = _get_content(response)
        try:
            if _finish_reason(response) == "length":
                raise ValueError(
                    "The reply was cut off by the output limit. "
                    "Make every field shorter and use fewer list items."
                )
            return model_class(**_extract_json(text))
        except Exception as exc:
            last_exc = exc
            messages = messages + [
                AIMessage(content=text[:8000]),
                HumanMessage(content=(
                    f"That reply was rejected:\n{str(exc)[:1500]}\n\n"
                    "Return the complete corrected JSON object only, matching the format exactly."
                )),
            ]
    assert last_exc is not None
    raise last_exc


# ─────────────────────────────────────────────────────────────────────────────
# Node 1: Creative Director
# ─────────────────────────────────────────────────────────────────────────────

_CREATIVE_SYSTEM = (
    "You are the Creative Director of a small browser-game studio. Turn the player's idea into a "
    "creative vision that makes the finished game look and feel polished.\n\n"
    "RULES\n"
    "- Stay faithful to the idea. Keep everything the player names (characters, teams, mechanics, "
    "setting, camera, controls). Add detail; never replace their idea with a different game.\n"
    "- The game is drawn entirely with Canvas 2D: shapes, gradients, glow, particles, text. "
    "No images, no downloaded fonts, no libraries. Sound comes from WebAudio oscillators.\n"
    "- Choose a restrained palette: one dark or muted background, one hero color for the player, "
    "one danger color, one accent. Hex codes only. HUD text must contrast strongly with the background.\n"
    "- Prefer a distinctive, specific look over generic neon unless the idea calls for it.\n"
    "- Be concrete. Every field must change what gets built; no filler adjectives.\n\n"
    "Respond with ONLY one JSON object in exactly this shape (comments show limits):\n"
)


def creative_director_node(state: GraphState) -> dict:
    """Interpret the user request and produce a structured CreativeVision."""
    prompt = state["user_prompt"].strip()[:MAX_PROMPT_CHARS]
    messages = [
        SystemMessage(content=_CREATIVE_SYSTEM + schema_hint(CreativeVision)),
        HumanMessage(content=f"GAME IDEA:\n{prompt}"),
    ]
    return {"creative_vision": _structured_call(creative_llm, messages, CreativeVision)}


# ─────────────────────────────────────────────────────────────────────────────
# Node 2: Game Designer
# ─────────────────────────────────────────────────────────────────────────────

_DESIGNER_SYSTEM = (
    "You are the Game Designer. Turn the creative vision into a specification that a programmer can "
    "implement in ONE TypeScript file of 500-900 lines without making any design decisions.\n\n"
    "RULES\n"
    "- The player's original request is binding. If it states controls or mechanics (for example "
    "'shoot where I click'), the design must implement them exactly. The vision only adds style.\n"
    "- Scope tightly: one core mechanic done well beats many half-built ones. Use 3-6 entity types "
    "and 2-5 mechanics for a typical game. Everything you list WILL be implemented.\n"
    "- Numbers, not adjectives: speeds in px/s, durations in seconds, sizes in px, counts. "
    "Put every balance number in `tunables` (at least 6) and keep entity values consistent with them.\n"
    "- Canvas coordinates: origin top-left, y grows downward. Everything must fit inside the canvas size you choose.\n"
    "- The game is playable on the first frame with no menu. Describe what happens in the first 10 seconds.\n"
    "- Fair and finishable: the first 20 seconds are easy, difficulty ramps gradually, the player can "
    "always see what killed them, and there is a restart control (R key or click).\n"
    "- Game feel: every hit, pickup, score and loss gets particles, shake or flash, plus a WebAudio sound.\n"
    "- Exactly one entity has role 'player': the thing the player controls (for a mouse-aimed game this "
    "may be the shooter or the crosshair).\n\n"
    "Respond with ONLY one JSON object in exactly this shape (comments show limits):\n"
)


def game_designer_node(state: GraphState) -> dict:
    """Translate the creative vision into a concrete game-design document."""
    vision = state["creative_vision"]
    prompt = state["user_prompt"].strip()[:MAX_PROMPT_CHARS]
    messages = [
        SystemMessage(content=_DESIGNER_SYSTEM + schema_hint(DesignDoc)),
        HumanMessage(content=(
            f"ORIGINAL REQUEST FROM THE PLAYER:\n{prompt}\n\n"
            f"CREATIVE VISION:\n{vision_brief(vision)}"
        )),
    ]
    return {"design_doc": _structured_call(designer_llm, messages, DesignDoc)}


# ─────────────────────────────────────────────────────────────────────────────
# Node 3: Gameplay Programmer
# ─────────────────────────────────────────────────────────────────────────────

PROGRAMMER_SYSTEM = (
    "You are a senior TypeScript game programmer. Implement the design brief as a complete, polished, "
    "bug-free browser game on an HTML5 Canvas.\n\n"
    "OUTPUT FORMAT (strict). Reply with ONLY these two blocks, with no explanation and no markdown fences:\n"
    "--- index.html ---\n"
    "<complete file>\n"
    "--- end ---\n"
    "--- src/main.ts ---\n"
    "<complete file>\n"
    "--- end ---\n\n"
    "HARD REQUIREMENTS\n"
    "1. Exactly these two files. tsconfig.json is added automatically. No import or export statements, "
    "no other files, no CDN scripts, no images, no web fonts (use 'monospace' or 'sans-serif').\n"
    "2. index.html: a minimal page with <canvas id=\"game\" width=\"W\" height=\"H\"> using the brief's "
    "canvas size, body background set to the palette background, the canvas centered and scaled to fit "
    "(CSS: width:min(100vw, calc(100vh * W / H)); height:auto), and <script src=\"dist/main.js\"></script> "
    "as the last element of body.\n"
    "3. src/main.ts: wrap ALL code in an IIFE `(() => { ... })();` so names never clash with browser "
    "globals. Strict TypeScript: type every function parameter and return value and avoid implicit any. "
    "Get the canvas and context with EXACTLY these two lines (a null check would not carry into your functions):\n"
    "   const canvas = document.getElementById('game') as HTMLCanvasElement;\n"
    "   const ctx = canvas.getContext('2d') as CanvasRenderingContext2D;\n"
    "4. Copy the CONSTANTS from the brief verbatim at the top of the IIFE and use them everywhere. "
    "Do not scatter other magic numbers for balance.\n"
    "5. Loop: requestAnimationFrame, dt in seconds clamped to 0.05. Every movement is speed * dt, never per frame.\n"
    "6. The game is already playing on the first frame (no title screen). On win or loss show an overlay "
    "with the result, the score and 'Press R or click to restart'. Restart must reset all state completely.\n"
    "7. Input: keep pressed keys in a Set via window keydown/keyup; preventDefault for arrow keys and Space; "
    "clear the Set on window blur. Use pointer events. Convert pointer positions to canvas coordinates with "
    "x = (e.clientX - rect.left) * canvas.width / rect.width (same for y), because the canvas is scaled by CSS.\n"
    "8. Audio: create the AudioContext lazily on the first keydown or pointerdown (browsers block it earlier), "
    "wrap it in try/catch, play short OscillatorNode + GainNode envelopes, master volume at most 0.25.\n"
    "9. Correctness: clamp the player inside the canvas, never spawn entities on top of the player, remove "
    "entities that leave the screen or die, cap particles at 300, and avoid division by zero when normalizing vectors.\n"
    "10. Visuals: use ONLY the palette colors (and lighter or darker tints of them). Draw a gradient background "
    "plus one subtle moving or textured layer, entities as shapes with the described details, glow via "
    "shadowBlur (reset it to 0 after drawing each glowing object), particles, screen shake via ctx.translate, "
    "and a readable HUD in bold monospace with a text shadow.\n"
    "11. Implement EVERY mechanic, entity, spawn rule, scoring rule, difficulty step, feedback effect and edge "
    "case in the brief. Never replace the core mechanic with something simpler.\n"
    "12. Length: 500 to 900 lines, compact and readable, no dead code. Never exceed 1000 lines. "
    "Always finish every block; an unfinished file is a failure.\n\n"
    "Suggested order inside the IIFE: constants, types, state, helpers, input, audio, reset/spawn, "
    "update, collisions, particles, render, loop.\n"
    "Before answering, mentally play the first 10 seconds and the restart path, and fix any bug you find."
)

EDIT_SYSTEM = (
    "You are a senior TypeScript game programmer editing an existing HTML5 Canvas game. "
    "You receive the current files and one change request.\n\n"
    "OUTPUT FORMAT (strict). Reply with ONLY the files you changed, each as:\n"
    "--- path/to/file ---\n"
    "<complete new file content>\n"
    "--- end ---\n"
    "No explanation, no markdown fences, no diffs. Every file you return must be complete.\n\n"
    "RULES\n"
    "- Only index.html and src/*.ts files exist. src/main.ts must stay one plain script wrapped in an IIFE, "
    "with no import or export. tsconfig.json is managed automatically; never return it.\n"
    "- Make the smallest change that fully delivers the request, and keep every other behavior working.\n"
    "- Stay strictly typed (no implicit any). Reuse the existing constants and helpers instead of adding duplicates.\n"
    "- If the request is about input (clicking, aiming, keys), make sure it works on the scaled canvas by "
    "converting pointer positions with x = (e.clientX - rect.left) * canvas.width / rect.width.\n"
    "- Keep the file compact. Never exceed 1000 lines. Finish every block; an unfinished file is a failure.\n"
    "- Before answering, trace the new behavior through update and render once and fix any bug you find."
)

_REQUIRED_FILES = ("index.html", "src/main.ts")
_MAX_PROGRAMMER_ATTEMPTS = 2


def _error_lines(errors: list[str]) -> str:
    seen: list[str] = []
    for e in errors:
        e = e.strip()[:300]
        if e and e not in seen:
            seen.append(e)
        if len(seen) >= 15:
            break
    return "\n".join(f"- {e}" for e in seen)


def _programmer_user_message(state: GraphState) -> str:
    """First pass: the brief. Retry pass: the previous code plus the errors to fix."""
    brief = (
        "CREATIVE BRIEF\n" + vision_brief(state["creative_vision"])
        + "\n\nDESIGN BRIEF\n" + design_brief(state["design_doc"])
    )
    previous = {
        p: c for p, c in (state.get("files") or {}).items() if p != "tsconfig.json"
    }
    errors = state.get("errors") or []
    if not (previous and errors):
        return brief + "\n\nWrite the game now."

    budget = MAX_INPUT_TOKENS - estimate_tokens(PROGRAMMER_SYSTEM) - 2_000
    code = render_files(previous, budget - estimate_tokens(brief))
    return (
        "Your previous version failed these checks:\n"
        f"{_error_lines(errors)}\n\n"
        "CURRENT CODE\n"
        f"{code}\n\n"
        f"{brief}\n\n"
        "Fix every error and keep everything else working. Reply with the COMPLETE corrected "
        "index.html and src/main.ts (full files, not a diff)."
    )


def gameplay_programmer_node(state: GraphState) -> dict:
    """Generate (or repair) the game source files."""
    user_msg = _programmer_user_message(state)
    if estimate_tokens(PROGRAMMER_SYSTEM + user_msg) > MAX_INPUT_TOKENS:
        raise BudgetExceeded("Programmer input is larger than the input budget.")

    messages = [SystemMessage(content=PROGRAMMER_SYSTEM), HumanMessage(content=user_msg)]
    files: dict[str, str] = {}

    for attempt in range(_MAX_PROGRAMMER_ATTEMPTS):
        wait_for_programmer_request_slot()
        started = time.monotonic()
        response = programmer_llm.invoke(messages)
        log_call(f"programmer attempt {attempt + 1}", response, started)
        text = _get_content(response)
        truncated = _finish_reason(response) == "length"

        files, problems = sanitize_files(parse_file_blocks(text))
        missing = [p for p in _REQUIRED_FILES if p not in files]
        if truncated:
            problems.append(
                "The reply hit the output limit and was cut off. Write more compact code "
                "(under 700 lines) and finish every block."
            )
        if missing:
            problems.append(f"Missing required file(s): {', '.join(missing)}.")

        if problems:
            print(f"[programmer] attempt {attempt + 1} problems: {problems}", flush=True)
            if not files:
                print(f"[programmer] reply start: {text[:600]!r}", flush=True)

        if not problems or attempt == _MAX_PROGRAMMER_ATTEMPTS - 1:
            break

        # Retry once, telling the model what was wrong. The rejected reply is not
        # re-sent (it can be very large); the original request is enough.
        messages = [
            SystemMessage(content=PROGRAMMER_SYSTEM),
            HumanMessage(content=(
                user_msg
                + "\n\nYOUR PREVIOUS REPLY WAS REJECTED:\n"
                + "\n".join(f"- {p}" for p in problems)
                + "\nReply again in the exact required format."
            )),
        ]

    if not files:
        return {"files": {}, "errors": []}
    return {"files": finalize_project(files), "errors": []}


# ─────────────────────────────────────────────────────────────────────────────
# Structural checks (cheap, deterministic, run before/alongside tsc)
# ─────────────────────────────────────────────────────────────────────────────

def structural_errors(files: dict[str, str]) -> list[str]:
    """Catch problems tsc cannot: a game that compiles but would not run in the preview."""
    errs: list[str] = []
    html = files.get("index.html", "")
    ts = files.get("src/main.ts", "")

    if not html:
        errs.append("index.html is missing.")
    elif "<canvas" not in html.lower():
        errs.append("index.html has no <canvas> element.")

    if not ts:
        errs.append("src/main.ts is missing.")
        return errs

    if re.search(r"^\s*(import|export)\b", ts, re.MULTILINE):
        errs.append("src/main.ts must not use import or export; the preview runs it as a plain script.")
    if "getContext" not in ts:
        errs.append("src/main.ts never calls getContext('2d'), so nothing can be drawn.")
    if "requestAnimationFrame" not in ts:
        errs.append("src/main.ts has no requestAnimationFrame game loop.")
    if not re.search(r"addEventListener\(\s*['\"](key|pointer|mouse|touch|click)", ts):
        errs.append("src/main.ts registers no keyboard, mouse, pointer or touch input handler.")
    if ts.count("\n") > 1200:
        errs.append("src/main.ts is over 1200 lines; make it more compact.")
    return errs

# ─────────────────────────────────────────────────────────────────────────────
# Node 4: QA Tester
# ─────────────────────────────────────────────────────────────────────────────

def qa_tester_node(state: GraphState) -> dict:
    """Run tsc --noEmit on the generated files and produce a QA report."""

    files = state["files"]

    if not files:
        return {
            "qa_report": QAReport(
                passed=False,
                errors=["No files were generated by the programmer node."],
                suggestions=["Ensure the programmer generates at least index.html and src/main.ts"],
            ),
            "retry_count": state.get("retry_count", 0) + 1,
            "errors": ["No files were generated."],
        }

    # Write files to a temp directory and run tsc
    with tempfile.TemporaryDirectory() as tmpdir:
        for rel_path, content in files.items():
            full_path = Path(tmpdir) / rel_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")

        # Check if tsconfig.json exists; if not, create a basic one
        tsconfig_path = Path(tmpdir) / "tsconfig.json"
        if not tsconfig_path.exists():
            tsconfig_path.write_text(json.dumps({
                "compilerOptions": {
                    "target": "ES2020",
                    "module": "ES2020",
                    "lib": ["ES2020", "DOM"],
                    "strict": True,
                    "noEmit": True,
                    "esModuleInterop": True,
                    "skipLibCheck": True,
                    "forceConsistentCasingInFileNames": True,
                },
                "include": ["src/**/*.ts"],
            }, indent=2), encoding="utf-8")

        # Run tsc --noEmit
        try:
            result = subprocess.run(
                ["npx", "tsc", "--noEmit"],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=60,
                shell=True,
            )
            tsc_output = result.stdout + result.stderr
            tsc_errors = [
                line.strip()
                for line in tsc_output.splitlines()
                if line.strip() and "error TS" in line
            ]
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            tsc_errors = [f"Failed to run tsc: {str(e)}"]

    tsc_errors = structural_errors(files) + tsc_errors
    passed = len(tsc_errors) == 0

    # Generate suggestions via LLM if there are errors
    suggestions = []
    if not passed:
        suggestions = [
            "Fix the TypeScript compilation errors listed above",
            "Ensure all variables are properly typed",
            "Check for missing return types and undefined references",
        ]

    report = QAReport(passed=passed, errors=tsc_errors, suggestions=suggestions)

    return {
        "qa_report": report,
        "retry_count": state.get("retry_count", 0) + 1,
        "errors": tsc_errors if not passed else [],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Standalone QA check (reusable outside the graph)
# ─────────────────────────────────────────────────────────────────────────────

def run_qa_check(files: dict[str, str]) -> QAReport:
    """Run tsc --noEmit on a set of files and return a QAReport. Usable outside the graph."""
    if not files:
        return QAReport(passed=False, errors=["No files provided"], suggestions=[])

    with tempfile.TemporaryDirectory() as tmpdir:
        for rel_path, content in files.items():
            full_path = Path(tmpdir) / rel_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")

        tsconfig_path = Path(tmpdir) / "tsconfig.json"
        if not tsconfig_path.exists():
            tsconfig_path.write_text(json.dumps({
                "compilerOptions": {
                    "target": "ES2020",
                    "module": "ES2020",
                    "lib": ["ES2020", "DOM"],
                    "strict": True,
                    "noEmit": True,
                    "esModuleInterop": True,
                    "skipLibCheck": True,
                    "forceConsistentCasingInFileNames": True,
                },
                "include": ["src/**/*.ts"],
            }, indent=2), encoding="utf-8")

        try:
            result = subprocess.run(
                ["npx", "tsc", "--noEmit"],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=60,
                shell=True,
            )
            tsc_output = result.stdout + result.stderr
            tsc_errors = [
                line.strip()
                for line in tsc_output.splitlines()
                if line.strip() and "error TS" in line
            ]
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            tsc_errors = [f"Failed to run tsc: {str(e)}"]

    tsc_errors = structural_errors(files) + tsc_errors
    passed = len(tsc_errors) == 0
    suggestions = []
    if not passed:
        suggestions = ["Fix the TypeScript errors and try again"]

    return QAReport(passed=passed, errors=tsc_errors, suggestions=suggestions)


# ─────────────────────────────────────────────────────────────────────────────
# Conditional router for QA → END or QA → programmer
# ─────────────────────────────────────────────────────────────────────────────

def qa_router(state: GraphState) -> str:
    """Route based on QA results: pass → END, fail → retry (up to 3 times)."""

    qa_report = state.get("qa_report")
    retry_count = state.get("retry_count", 0)

    if qa_report and qa_report.passed:
        return "end"

    if retry_count >= 3:
        # Give up after 3 retries
        return "end"

    return "retry"
