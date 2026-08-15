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
from pathlib import Path

from langchain.chat_models import init_chat_model
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import tool
from dotenv import load_dotenv

from agents.schemas import CreativeVision, DesignDoc, QAReport
from agents.state import GraphState

load_dotenv()

# Map GEMINI_API_KEY to what langchain-google-genai expects
if os.environ.get("GEMINI_API_KEY") and not os.environ.get("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

# ── LLM instances ───────────────────────────────────────────────────────────
llm = init_chat_model(
    "openai/gpt-oss-120b",
    model_provider="groq",
    max_tokens=4096,
)

# Programmer uses Gemini (higher token limits for code generation)
programmer_llm = init_chat_model(
    "gemini-3.5-flash",
    model_provider="google_genai",
    max_tokens=8192,
)


def _schema_prompt(model_class) -> str:
    """Build a clear prompt showing the expected JSON fields, not the raw schema."""
    fields = model_class.model_fields
    lines = ["{"]
    for name, field in fields.items():
        desc = field.description or ""
        if field.annotation == list or (hasattr(field.annotation, '__origin__') and field.annotation.__origin__ is list):
            lines.append(f'  "{name}": ["..."],  // {desc}')
        else:
            lines.append(f'  "{name}": "...",  // {desc}')
    lines.append("}")
    return "\n".join(lines)


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
    # Try parsing
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Last resort: find the first { and last } to extract the JSON object
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            return json.loads(text[start:end + 1])
        raise


# ─────────────────────────────────────────────────────────────────────────────
# Node 1: Creative Director
# ─────────────────────────────────────────────────────────────────────────────

def creative_director_node(state: GraphState) -> dict:
    """Interpret the user request and produce a structured CreativeVision."""

    schema_hint = _schema_prompt(CreativeVision)

    response = llm.invoke([
        SystemMessage(content=(
            "You are a Creative Director for browser-based games. "
            "Given a user's game idea, produce a clear creative vision that will "
            "guide the rest of the development team. Be specific and imaginative. "
            "The game will be implemented as a single-page TypeScript/HTML5 Canvas game.\n\n"
            "You MUST respond with ONLY a valid JSON object matching this format:\n"
            f"{schema_hint}\n\n"
            "Fill in each field with a real value. No extra text, no markdown, just JSON."
        )),
        HumanMessage(content=state["user_prompt"]),
    ])

    data = _extract_json(response.content)
    vision = CreativeVision(**data)
    return {"creative_vision": vision}


# ─────────────────────────────────────────────────────────────────────────────
# Node 2: Game Designer
# ─────────────────────────────────────────────────────────────────────────────

def game_designer_node(state: GraphState) -> dict:
    """Translate the creative vision into a concrete game-design document."""

    schema_hint = _schema_prompt(DesignDoc)

    vision = state["creative_vision"]
    vision_text = (
        f"Title: {vision.game_title}\n"
        f"Theme: {vision.theme}\n"
        f"Visual Style: {vision.visual_style}\n"
        f"Mood: {vision.mood}\n"
        f"Target Feel: {vision.target_feel}"
    )

    response = llm.invoke([
        SystemMessage(content=(
            "You are a Game Designer specializing in browser-based HTML5 Canvas games. "
            "Given the creative vision below, produce a detailed game-design document. "
            "Be practical — the game must be implementable in a single TypeScript file "
            "with an HTML5 Canvas, no external game engine or asset loading.\n\n"
            "You MUST respond with ONLY a valid JSON object matching this format:\n"
            f"{schema_hint}\n\n"
            "Fill in each field with a real value. No extra text, no markdown, just JSON."
        )),
        HumanMessage(content=f"Creative Vision:\n{vision_text}"),
    ])

    data = _extract_json(response.content)
    design = DesignDoc(**data)
    return {"design_doc": design}


# ─────────────────────────────────────────────────────────────────────────────
# Node 3: Gameplay Programmer
# ─────────────────────────────────────────────────────────────────────────────

@tool
def write_file(path: str, content: str) -> str:
    """Write a file to the project. Path should be relative (e.g. 'src/main.ts')."""
    return json.dumps({"written": path, "size": len(content)})


def gameplay_programmer_node(state: GraphState) -> dict:
    """Generate the game source files using a tool-calling loop."""

    vision = state["creative_vision"]
    design = state["design_doc"]
    errors = state.get("errors", [])

    # Build context for the programmer
    context_parts = [
        f"Game Title: {vision.game_title}",
        f"Theme: {vision.theme}",
        f"Visual Style: {vision.visual_style}",
        f"Mood: {vision.mood}",
        f"Target Feel: {vision.target_feel}",
        "",
        f"Player Controls: {design.player_controls}",
        f"Core Loop: {design.core_loop}",
        f"Win Condition: {design.win_condition}",
        f"Lose Condition: {design.lose_condition}",
        f"Entities: {', '.join(design.entities)}",
        f"Level Structure: {design.level_structure}",
    ]

    # If retrying, include previous errors for the LLM to fix
    if errors:
        context_parts.append("")
        context_parts.append("PREVIOUS ERRORS TO FIX:")
        for err in errors:
            context_parts.append(f"  - {err}")

    system_prompt = (
        "You are a senior TypeScript gameplay programmer. "
        "Generate a complete, working browser game using HTML5 Canvas and TypeScript. "
        "Use the write_file tool to create each file. You MUST create at minimum:\n"
        "  1. index.html — the HTML shell with a <canvas> element\n"
        "  2. src/main.ts — the game entry point and loop\n"
        "  3. tsconfig.json — MUST include: {\"compilerOptions\":{\"target\":\"ES2020\",\"module\":\"ES2020\",\"lib\":[\"ES2020\",\"DOM\"],\"outDir\":\"dist\",\"strict\":true}}\n\n"
        "CRITICAL RULES:\n"
        "- The game MUST start in a PLAYING state immediately on load (no menus, no splash screens)\n"
        "- No external dependencies (no npm packages, no CDN scripts)\n"
        "- All game logic in TypeScript, rendered to a <canvas>\n"
        "- The HTML file should reference the compiled JS via <script src='dist/main.js'></script>\n"
        "- Use requestAnimationFrame for the game loop\n"
        "- The game must be interactive from the first frame\n"
        "- Keep code simple and under 300 lines total\n"
        "- If previous errors are listed, fix them in this iteration"
    )

    # Bind the tool and run a tool-calling loop
    llm_with_tools = programmer_llm.bind_tools([write_file])

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content="\n".join(context_parts)),
    ]

    files: dict[str, str] = {}

    # Tool-calling loop: keep invoking until the LLM stops calling tools
    max_iterations = 15
    for _ in range(max_iterations):
        response = llm_with_tools.invoke(messages)
        messages.append(response)

        if not response.tool_calls:
            break

        # Process each tool call
        for tool_call in response.tool_calls:
            if tool_call["name"] == "write_file":
                args = tool_call["args"]
                file_path = args["path"]
                file_content = args["content"]
                files[file_path] = file_content

                # Feed the tool result back
                from langchain_core.messages import ToolMessage
                messages.append(ToolMessage(
                    content=json.dumps({"written": file_path, "size": len(file_content)}),
                    tool_call_id=tool_call["id"],
                ))

    return {"files": files, "errors": []}


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
