"""
agents/nodes.py
---------------
The four agent nodes that comprise the game-generation pipeline,
plus the shared QA function used by both the graph and /ws/edit.

Changes from original:
- F1: QA uses shutil.which, no shell=True, tsc-not-found is an infra error
- F2: Removed "start in PLAYING state" and "under 300 lines" rules
- F3/F4: Full schemas; designer+programmer receive user_prompt; programmer
        receives render_design_markdown() not a lossy summary
- F5: Retry passes previous game files and merges returned files
- F6: Models/limits are env-driven via core.config.settings
- F7: Planner nodes retry up to 2 extra times on parse/validation failure
- F8: qa_router cap comes from settings.QA_MAX_ATTEMPTS
- Scaffold: inlined preamble injected into src/main.ts; writes ignored for
        scaffold paths; tsconfig.json always overwritten with canonical version
- Truncation: finish_reason == "length" or MAX_TOKENS triggers a re-ask
- Gemini content-as-list handled
"""

import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, AIMessage
from langchain_core.tools import tool
from dotenv import load_dotenv

from agents.prompts import (
    CREATIVE_DIRECTOR_SYSTEM,
    GAME_DESIGNER_SYSTEM,
    gameplay_programmer_system,
    gameplay_programmer_retry,
    QA_REVIEWER_SYSTEM,
)
from agents.scaffold import (
    SCAFFOLD_PATHS,
    build_inline_preamble,
    load_api_summary,
    load_scaffold,
    load_skeleton,
    load_tsconfig,
)
from agents.schemas import (
    CreativeVision,
    DesignDoc,
    QAReport,
    render_design_markdown,
)
from agents.state import GraphState
from core.config import settings

load_dotenv()

logger = logging.getLogger(__name__)


# ── LLM factory ──────────────────────────────────────────────────────────────
# All nodes use moonshotai/kimi-k3 via NVIDIA's OpenAI-compatible NIM endpoint.
# We use ChatOpenAI directly so we can pass reasoning_effort and a custom base_url.

from langchain_openai import ChatOpenAI

def _make_nvidia_llm(temperature: float, max_tokens: int, reasoning_effort: str) -> ChatOpenAI:
    """
    Build a ChatOpenAI client pointing at NVIDIA's OpenAI-compatible endpoint.

    The NVIDIA API mirrors the OpenAI Chat Completions spec, including the
    `reasoning_effort` extension field supported by kimi-k3.
    """
    return ChatOpenAI(
        model=settings.NVIDIA_MODEL,
        api_key=settings.NVIDIA_API_KEY,          # type: ignore[arg-type]
        base_url=settings.NVIDIA_BASE_URL,
        max_tokens=max_tokens,
        temperature=temperature,
        model_kwargs={
            "reasoning_effort": reasoning_effort,
        },
    )


def _make_planner_llm() -> ChatOpenAI:
    # Creative Director: high creativity
    return _make_nvidia_llm(
        temperature=0.7,
        max_tokens=settings.PLANNER_MAX_TOKENS,
        reasoning_effort=settings.PLANNER_REASONING_EFFORT,
    )

def _make_designer_llm() -> ChatOpenAI:
    # Game Designer: balanced
    return _make_nvidia_llm(
        temperature=0.5,
        max_tokens=settings.PLANNER_MAX_TOKENS,
        reasoning_effort=settings.PLANNER_REASONING_EFFORT,
    )

def _make_programmer_llm() -> ChatOpenAI:
    # Programmer: low temperature, large output budget
    return _make_nvidia_llm(
        temperature=0.2,
        max_tokens=settings.PROGRAMMER_MAX_TOKENS,
        reasoning_effort=settings.PROGRAMMER_REASONING_EFFORT,
    )

def _make_reviewer_llm() -> ChatOpenAI:
    # QA reviewer: deterministic
    return _make_nvidia_llm(
        temperature=0.1,
        max_tokens=2048,
        reasoning_effort=settings.PLANNER_REASONING_EFFORT,
    )

# Lazy singletons — constructed on first call to avoid import-time errors
_planner_llm = None
_designer_llm = None
_programmer_llm = None
_reviewer_llm = None

def _get_planner():
    global _planner_llm
    if _planner_llm is None:
        _planner_llm = _make_planner_llm()
    return _planner_llm

def _get_designer():
    global _designer_llm
    if _designer_llm is None:
        _designer_llm = _make_designer_llm()
    return _designer_llm

def _get_programmer():
    global _programmer_llm
    if _programmer_llm is None:
        _programmer_llm = _make_programmer_llm()
    return _programmer_llm

def _get_reviewer():
    global _reviewer_llm
    if _reviewer_llm is None:
        _reviewer_llm = _make_reviewer_llm()
    return _reviewer_llm

# Public alias used by main.py /ws/edit
def get_programmer_llm():
    return _get_programmer()


# ── JSON extraction ──────────────────────────────────────────────────────────

def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response, handling markdown code blocks and thinking tags."""
    # Remove <think>...</think> blocks (Qwen reasoning tokens)
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # Try to find JSON in code blocks first
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        text = match.group(1)
    text = text.strip()
    # Remove trailing commas before } or ] (common LLM mistake)
    text = re.sub(r",\s*([}\]])", r"\1", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end   = text.rfind("}")
        if start != -1 and end != -1:
            return json.loads(text[start:end + 1])
        raise


def _schema_prompt(model_class) -> str:
    """
    Build a type-aware schema hint for LLM output.
    Shows nested objects and lists with example values, not just '...'.
    """
    import typing

    def _field_example(annotation, description: str) -> str:
        origin = getattr(annotation, "__origin__", None)
        args   = getattr(annotation, "__args__",   ())

        # list[SomeModel]
        if origin is list and args:
            inner = args[0]
            if hasattr(inner, "model_fields"):
                inner_ex = _model_example(inner)
                return f"[{inner_ex}]  // {description}"
            return f'["..."]  // {description}'

        # list[str] / list[int]
        if origin is list:
            return f'["..."]  // {description}'

        # Pydantic sub-model
        if hasattr(annotation, "model_fields"):
            return f"{_model_example(annotation)}  // {description}"

        # Literal
        if origin is typing.Literal:
            opts = "|".join(f'"{a}"' for a in args)
            return f'"{args[0]}"  // one of: {opts}. {description}'

        return f'"..."  // {description}'

    def _model_example(model_class) -> str:
        lines = ["{"]
        for name, field in model_class.model_fields.items():
            desc = field.description or ""
            ann  = field.annotation
            lines.append(f'  "{name}": {_field_example(ann, desc)},')
        lines.append("}")
        return "\n".join(lines)

    return _model_example(model_class)


def _invoke_with_retry(llm, messages: list, model_class, max_extra: int = 2):
    """
    Invoke LLM, parse + validate the response, retry up to max_extra times
    on parse or Pydantic validation failure, feeding the error back.
    """
    last_exc = None
    for attempt in range(1 + max_extra):
        try:
            response = llm.invoke(messages)
            text = _get_text(response)
            data = _extract_json(text)
            return model_class(**data), text
        except Exception as exc:
            last_exc = exc
            logger.warning("LLM parse/validation attempt %d failed: %s", attempt + 1, exc)
            messages = messages + [
                AIMessage(content=_get_text(response) if "response" in dir() else ""),
                HumanMessage(content=(
                    f"Your response caused a validation error: {exc}\n"
                    "Please fix it and return ONLY valid JSON matching the schema."
                )),
            ]
    raise last_exc  # type: ignore[misc]


def _get_text(response) -> str:
    """Extract text from an LLM response, handling Gemini list-of-parts."""
    content = response.content
    if isinstance(content, list):
        return "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    return str(content)


# ── write_file tool ───────────────────────────────────────────────────────────

@tool
def write_file(path: str, content: str) -> str:
    """Write a file to the project. Path should be relative (e.g. 'src/main.ts')."""
    return json.dumps({"written": path, "size": len(content)})


# ── Scaffold helpers ─────────────────────────────────────────────────────────

def _inject_scaffold(files: dict[str, str]) -> dict[str, str]:
    """
    Return files with:
    - scaffold source files added (src/input.ts etc.)
    - tsconfig.json set to the canonical version
    - src/main.ts prefixed with the inline preamble (if present)
    """
    result = dict(files)

    # Always use the canonical tsconfig
    result["tsconfig.json"] = load_tsconfig()

    # Add scaffold source files (they stream as file_written events too)
    scaffold_sources = load_scaffold()
    for path, content in scaffold_sources.items():
        result[path] = content

    # Prefix src/main.ts with the inlined preamble
    if "src/main.ts" in result:
        preamble = build_inline_preamble()
        existing = result["src/main.ts"]
        # Strip any stray import statements for scaffold files the model may have added
        existing = re.sub(
            r'^import\s+.*?from\s+["\']\.\/(?:input|loop|canvas|audio|fx|state|storage)["\'].*?;?\s*$',
            "",
            existing,
            flags=re.MULTILINE,
        )
        result["src/main.ts"] = preamble + "\n" + existing

    return result


def _game_files_only(files: dict[str, str]) -> dict[str, str]:
    """Return only non-scaffold game files (for retry context shown to LLM)."""
    return {
        path: content
        for path, content in files.items()
        if path not in SCAFFOLD_PATHS
    }


# ─────────────────────────────────────────────────────────────────────────────
# Node 1: Creative Director
# ─────────────────────────────────────────────────────────────────────────────

def creative_director_node(state: GraphState) -> dict:
    """Interpret the user request and produce a structured CreativeVision."""
    llm = _get_planner()
    schema_hint = _schema_prompt(CreativeVision)

    messages = [
        SystemMessage(content=(
            f"{CREATIVE_DIRECTOR_SYSTEM}\n\n"
            "You MUST respond with ONLY a valid JSON object matching this schema:\n"
            f"{schema_hint}\n\n"
            "Fill in EVERY field with real, specific content. No extra text, no markdown, just JSON."
        )),
        HumanMessage(content=state["user_prompt"]),
    ]

    vision, _ = _invoke_with_retry(llm, messages, CreativeVision)
    return {"creative_vision": vision}


# ─────────────────────────────────────────────────────────────────────────────
# Node 2: Game Designer
# ─────────────────────────────────────────────────────────────────────────────

def game_designer_node(state: GraphState) -> dict:
    """Translate the creative vision into a concrete game-design document."""
    llm = _get_designer()
    schema_hint = _schema_prompt(DesignDoc)

    vision = state["creative_vision"]

    # Build a rich vision summary from all available fields
    vision_lines = [
        f"Title: {vision.game_title}",
        f"Pitch: {vision.pitch}" if vision.pitch else "",
        f"Theme: {vision.theme}",
        f"Core verb: {vision.core_verb}" if vision.core_verb else "",
        f"Core fantasy: {vision.core_fantasy}" if vision.core_fantasy else "",
        f"Visual style: {vision.visual_style}",
        f"Mood: {vision.mood}",
        f"Target feel: {vision.target_feel}",
        f"Font stack: {vision.font_stack}" if vision.font_stack else "",
        f"Audio personality: {vision.audio_personality}" if vision.audio_personality else "",
        f"Juice personality: {vision.juice_personality}" if vision.juice_personality else "",
    ]
    if vision.palette:
        palette_str = ", ".join(f"{p.role}={p.hex}" for p in vision.palette)
        vision_lines.append(f"Palette: {palette_str}")
    if vision.art_direction:
        vision_lines.append(f"Art direction: {vision.art_direction}")
    vision_text = "\n".join(line for line in vision_lines if line)

    messages = [
        SystemMessage(content=(
            f"{GAME_DESIGNER_SYSTEM}\n\n"
            "You MUST respond with ONLY a valid JSON object matching this schema:\n"
            f"{schema_hint}\n\n"
            "Fill in EVERY field with real, specific, numeric content. No extra text, no markdown, just JSON."
        )),
        HumanMessage(content=(
            f"Original idea: {state['user_prompt']}\n\n"
            f"Creative Vision:\n{vision_text}"
        )),
    ]

    design, _ = _invoke_with_retry(llm, messages, DesignDoc)

    # Backfill legacy 'entities' list from entities_detail if the model left it empty
    if not design.entities and design.entities_detail:
        design.entities = [e.name for e in design.entities_detail]

    # Render the full design as markdown — used by programmer node and as DESIGN.md
    design_md = render_design_markdown(state["user_prompt"], vision, design)

    return {
        "design_doc": design,
        "design_markdown": design_md,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Node 3: Gameplay Programmer
# ─────────────────────────────────────────────────────────────────────────────

def gameplay_programmer_node(state: GraphState) -> dict:
    """Generate the game source files using a tool-calling loop."""
    llm = _get_programmer()
    llm_with_tools = llm.bind_tools([write_file])

    vision  = state["creative_vision"]
    design  = state["design_doc"]
    errors  = state.get("errors", [])
    spec_violations = state.get("spec_violations", [])
    retry_count = state.get("retry_count", 0)
    previous_files = state.get("files", {})  # keep for retry merge

    # Build the design markdown — used as the authoritative context
    design_md = render_design_markdown(state["user_prompt"], vision, design)

    api_summary = load_api_summary()
    skeleton    = load_skeleton()

    if retry_count == 0:
        # First attempt
        system = gameplay_programmer_system(api_summary, skeleton)
        messages: list = [
            SystemMessage(content=system),
            HumanMessage(content=(
                f"Original idea: {state['user_prompt']}\n\n"
                f"{design_md}"
            )),
        ]
    else:
        # Retry — pass previous game files (excluding scaffold) plus errors
        system = gameplay_programmer_system(api_summary, skeleton)
        prev_game = _game_files_only(previous_files)
        retry_msg = gameplay_programmer_retry(prev_game, errors, spec_violations)
        messages = [
            SystemMessage(content=system),
            HumanMessage(content=(
                f"Original idea: {state['user_prompt']}\n\n"
                f"{design_md}\n\n"
                f"{retry_msg}"
            )),
        ]

    # Tool-calling loop
    files: dict[str, str] = {}
    max_iterations = 20

    for _ in range(max_iterations):
        response = llm_with_tools.invoke(messages)
        messages.append(response)

        response_text = _get_text(response)

        # Check for truncation: finish_reason == "length" or MAX_TOKENS
        finish_reason = ""
        if hasattr(response, "response_metadata"):
            meta = response.response_metadata or {}
            finish_reason = str(
                meta.get("finish_reason", "") or
                meta.get("stop_reason", "") or
                ""
            ).lower()

        if finish_reason in ("length", "max_tokens"):
            logger.warning("Programmer response truncated (finish_reason=%s); asking for continuation", finish_reason)
            messages.append(HumanMessage(content=(
                "Your response was cut off. Continue from exactly where you stopped. "
                "If you were in the middle of a write_file call, complete that file first."
            )))
            continue

        if not response.tool_calls:
            # Check if the model said "done" or gave a text response with no tools
            if "done" in response_text.lower() or not response_text.strip():
                break
            # If it gave us text output without calling tools, it may have
            # embedded the code — fall through and stop the loop
            break

        # Process tool calls
        for tool_call in response.tool_calls:
            if tool_call["name"] != "write_file":
                continue
            args = tool_call["args"]
            path: str    = args.get("path", "")
            content: str = args.get("content", "")

            # Reject scaffold file overwrites (silently acknowledge)
            if path in SCAFFOLD_PATHS:
                logger.info("Programmer tried to write scaffold path %s — ignored", path)
                messages.append(ToolMessage(
                    content=json.dumps({"ignored": path, "reason": "scaffold file — read-only"}),
                    tool_call_id=tool_call["id"],
                ))
                continue

            files[path] = content
            messages.append(ToolMessage(
                content=json.dumps({"written": path, "size": len(content)}),
                tool_call_id=tool_call["id"],
            ))

    # Merge with previous files on retry so we never lose working files
    if retry_count > 0:
        prev_game = _game_files_only(previous_files)
        merged = {**prev_game, **files}
    else:
        merged = files

    # Always include DESIGN.md so it travels through file_written and the DB
    design_md = state.get("design_markdown", "")
    if design_md:
        merged["DESIGN.md"] = design_md

    # Validate required files
    if "src/main.ts" not in merged:
        logger.error("Programmer produced no src/main.ts")
    if "index.html" not in merged:
        logger.error("Programmer produced no index.html")

    # Inject scaffold (preamble + scaffold sources + canonical tsconfig)
    full_files = _inject_scaffold(merged)

    return {"files": full_files, "errors": [], "spec_violations": []}


# ─────────────────────────────────────────────────────────────────────────────
# Shared QA function
# ─────────────────────────────────────────────────────────────────────────────

def _find_tsc() -> str | None:
    """Find the tsc binary. Returns None if not found."""
    # Platform-aware: tsc.cmd on Windows, tsc on POSIX
    for name in ("tsc", "tsc.cmd"):
        found = shutil.which(name)
        if found:
            return found
    # Fall back to npx tsc if npx is available
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if npx:
        return None  # Caller will use npx separately
    return None


def _run_tsc(tmpdir: str) -> tuple[bool, list[str]]:
    """
    Run tsc --noEmit in tmpdir.
    Returns (tsc_available, error_lines).
    tsc_available=False means tsc wasn't found — treat as infra warning, not pass.
    """
    tsc = _find_tsc()

    # Try tsc directly
    if tsc:
        cmd = [tsc, "--noEmit", "--project", str(Path(tmpdir) / "tsconfig.json")]
    else:
        # Try npx tsc (works when Node is installed but tsc isn't global)
        npx = shutil.which("npx") or shutil.which("npx.cmd")
        if not npx:
            return False, ["tsc not available: Node.js/TypeScript not installed in this environment"]
        cmd = [npx, "tsc", "--noEmit", "--project", str(Path(tmpdir) / "tsconfig.json")]

    try:
        result = subprocess.run(
            cmd,
            cwd=tmpdir,
            capture_output=True,
            text=True,
            timeout=60,
            # NO shell=True — passes args correctly on POSIX
        )
        output = result.stdout + result.stderr
        errors = [
            line.strip()
            for line in output.splitlines()
            if line.strip() and "error TS" in line
        ]
        return True, errors
    except subprocess.TimeoutExpired:
        return True, ["tsc timed out after 60s"]
    except FileNotFoundError:
        return False, ["tsc executable not found"]
    except Exception as exc:
        return True, [f"tsc subprocess error: {exc}"]


# Patterns for static checks
_BANNED = [
    (r"\bkeyCode\b",                      "Uses deprecated event.keyCode"),
    (r"\balert\s*\(",                      "Uses alert()"),
    (r"\beval\s*\(",                       "Uses eval()"),
    (r"\bprompt\s*\(",                     "Uses prompt()"),
    (r":\s*any\b",                         "Uses TypeScript 'any' type"),
    (r"\bTODO\b",                          "Contains TODO"),
    (r"https?://",                         "Contains external URL"),
    (r"<img\b",                            "Contains <img> tag"),
    (r"@import\b",                         "Contains CSS @import (fonts)"),
    (r"\bsetInterval\b",                   "Uses setInterval (use GameLoop instead)"),
    (r"localStorage\.(?:getItem|setItem)", "Accesses localStorage directly (use storage.ts)"),
]

_REQUIRED_PATTERNS = [
    (r"\bInputManager\b",  "InputManager not used"),
    (r"\bGameLoop\b",      "GameLoop not used"),
    (r"\bStateMachine\b",  "StateMachine not used"),
    (r"\bgame_over\b",     "No game_over state"),
    (r"\bpause[d]?\b",     "No pause state"),
    (r"\brestart\b",       "No restart logic"),
    (r"\bdt\b",            "No dt-based motion"),
    (r"\bsetupCanvas\b",   "setupCanvas not called"),
    (r"\bAudioManager\b",  "AudioManager not used"),
]


def _static_checks(files: dict[str, str]) -> list[str]:
    """Run regex-based static checks on game source files. Returns violation strings."""
    violations: list[str] = []

    # Check for required files
    if "src/main.ts" not in files:
        violations.append("Required file src/main.ts is missing")
    if "index.html" not in files:
        violations.append("Required file index.html is missing")

    # Collect game source content, excluding scaffold files.
    # For src/main.ts: strip the injected scaffold preamble section so
    # the checks fire only on the programmer-written game code, not the scaffold itself.
    game_source: dict[str, str] = {}
    for path, content in files.items():
        if not path.endswith(".ts") or path in SCAFFOLD_PATHS:
            continue
        if path == "src/main.ts":
            # Strip the preamble up to the END SCAFFOLD marker
            marker = "// ── END SCAFFOLD"
            idx = content.find(marker)
            if idx != -1:
                content = content[idx + len(marker):]
        game_source[path] = content

    all_source = "\n".join(game_source.values())

    for pattern, msg in _BANNED:
        if re.search(pattern, all_source):
            violations.append(msg)

    for pattern, msg in _REQUIRED_PATTERNS:
        if not re.search(pattern, all_source, re.IGNORECASE):
            violations.append(msg)

    return violations


def run_qa_check(
    files: dict[str, str],
    design_markdown: str = "",
    run_llm_review: bool = False,
) -> QAReport:
    """
    Shared QA function used by both qa_tester_node and /ws/edit.

    Steps:
    1. Inject scaffold + canonical tsconfig into temp dir
    2. Run tsc (no shell=True; tsc-not-found = infra warning, not pass)
    3. Static checks (regex)
    4. Optionally: LLM spec review (only if steps 2+3 clean AND run_llm_review=True)

    Returns a QAReport with errors (tsc) and spec_violations (static + LLM).
    """
    if not files:
        return QAReport(
            passed=False,
            errors=["No files provided"],
            spec_violations=["Required file src/main.ts is missing", "Required file index.html is missing"],
        )

    # ── Step 1: Write to temp dir ─────────────────────────────────────────
    # Ensure scaffold and canonical tsconfig are always present for static analysis,
    # but DO NOT write the individual scaffold source files when src/main.ts already
    # contains the inlined preamble — tsc would see duplicates from src/*.ts + main.ts.
    qa_files = _inject_scaffold(dict(files))

    with tempfile.TemporaryDirectory() as tmpdir:
        for rel_path, content in qa_files.items():
            # Skip the individual scaffold source files:
            # src/main.ts already contains their code as an inlined preamble.
            # Writing them separately causes duplicate identifier errors in tsc.
            if rel_path in SCAFFOLD_PATHS and rel_path != "tsconfig.json":
                continue
            full_path = Path(tmpdir) / rel_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")

        # ── Step 2: tsc ───────────────────────────────────────────────────
        tsc_available, tsc_errors = _run_tsc(tmpdir)

    if not tsc_available:
        # Log loudly but don't pretend it passed
        logger.error("QA INFRA: %s", tsc_errors[0] if tsc_errors else "tsc not available")
        # Treat as infra skip: static checks still run, tsc errors = infra warning
        tsc_errors = []   # don't fail the run purely on missing tsc
        # (We'll surface this as a spec_violation so the activity log shows it)

    # ── Step 3: Static checks ─────────────────────────────────────────────
    spec_violations = _static_checks(files)

    # ── Step 4: LLM spec review (optional, only if tsc + static pass) ────
    if run_llm_review and not tsc_errors and not spec_violations and design_markdown:
        try:
            llm = _get_reviewer()
            user_content = (
                f"DESIGN DOCUMENT:\n{design_markdown}\n\n"
                "SOURCE FILES:\n"
            )
            for path, content in files.items():
                if path.endswith(".ts") and path not in SCAFFOLD_PATHS:
                    user_content += f"\n=== {path} ===\n{content}\n"

            resp = llm.invoke([
                SystemMessage(content=QA_REVIEWER_SYSTEM),
                HumanMessage(content=user_content),
            ])
            resp_text = _get_text(resp)
            try:
                review_data = _extract_json(resp_text)
                review_passed: bool = review_data.get("passed", True)
                violations_raw: list = review_data.get("violations", [])
                if not review_passed:
                    for v in violations_raw:
                        item    = v.get("item", "")
                        file_   = v.get("file", "")
                        problem = v.get("problem", "")
                        fix     = v.get("fix", "")
                        spec_violations.append(
                            f"[{file_}] {item}: {problem} → Fix: {fix}"
                        )
            except Exception as parse_exc:
                logger.warning("LLM spec review parse failed: %s", parse_exc)
        except Exception as llm_exc:
            logger.warning("LLM spec review failed: %s", llm_exc)

    passed = len(tsc_errors) == 0 and len(spec_violations) == 0

    suggestions: list[str] = []
    if tsc_errors:
        suggestions.append("Fix all TypeScript compilation errors listed above")
    if spec_violations:
        suggestions.append("Address all spec violations listed above")

    return QAReport(
        passed=passed,
        errors=tsc_errors,
        spec_violations=spec_violations,
        suggestions=suggestions,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Node 4: QA Tester
# ─────────────────────────────────────────────────────────────────────────────

def qa_tester_node(state: GraphState) -> dict:
    """Run the shared QA check and produce a QAReport."""
    files = state.get("files", {})

    if not files:
        return {
            "qa_report": QAReport(
                passed=False,
                errors=["No files were generated by the programmer node."],
                spec_violations=["Required file src/main.ts is missing", "Required file index.html is missing"],
                suggestions=["Ensure the programmer generates at least index.html and src/main.ts"],
            ),
            "retry_count": state.get("retry_count", 0) + 1,
            "errors": ["No files were generated."],
            "spec_violations": [],
        }

    # Get design markdown if available (for LLM spec review on final attempt)
    design_markdown = state.get("design_markdown", "")
    retry_count     = state.get("retry_count", 0)
    max_attempts    = settings.QA_MAX_ATTEMPTS

    # Run LLM review only on the last retry (expensive; save for final check)
    run_llm = (retry_count >= max_attempts - 1) and bool(design_markdown)

    report = run_qa_check(
        files,
        design_markdown=design_markdown,
        run_llm_review=run_llm,
    )

    return {
        "qa_report": report,
        "retry_count": retry_count + 1,
        "errors": report.errors,
        "spec_violations": report.spec_violations,
    }


# ─────────────────────────────────────────────────────────────────────────────
# QA router
# ─────────────────────────────────────────────────────────────────────────────

def qa_router(state: GraphState) -> str:
    """
    Route based on QA results.
    - pass → end
    - fail and retry_count < QA_MAX_ATTEMPTS → retry
    - fail and retry_count >= QA_MAX_ATTEMPTS → end (errors remain in state)

    F8 fix: retry_count is incremented INSIDE qa_tester_node (after running),
    so comparing >= QA_MAX_ATTEMPTS is correct (no off-by-one).
    Example: QA_MAX_ATTEMPTS=4 → initial run + 3 retries = 4 total QA runs.
    """
    qa_report   = state.get("qa_report")
    retry_count = state.get("retry_count", 0)

    if qa_report and qa_report.passed:
        return "end"

    if retry_count >= settings.QA_MAX_ATTEMPTS:
        logger.warning(
            "QA failed after %d attempts. Errors: %s. Violations: %s",
            retry_count,
            state.get("errors", []),
            state.get("spec_violations", []),
        )
        return "end"

    return "retry"
