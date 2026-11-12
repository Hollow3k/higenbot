"""
main.py
-------
FastAPI application entry point.

Start the server:
    uvicorn main:app --reload
"""

import asyncio
import json
import traceback
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select

from core.config import settings
from api.projects import router as projects_router
from agents.graph import graph
from agents.files import parse_file_blocks, sanitize_files
from agents.limits import MAX_PROMPT_CHARS
from db.database import get_sessionmaker
from db.models import GeneratedFile, GenerationRun, Project

app = FastAPI(
    title="HigenBot API",
    description="AI-powered game studio simulator backend",
    version="0.1.0",
)

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
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


# ── WebSocket: stream agent graph events ─────────────────────────────────────

def _ts() -> str:
    """ISO timestamp for event messages."""
    return datetime.now(timezone.utc).isoformat()


async def _send(ws: WebSocket, msg: dict):
    """Send a JSON message over the WebSocket."""
    await ws.send_text(json.dumps(msg, default=str))


@app.websocket("/ws/run/{run_id}")
async def websocket_run(websocket: WebSocket, run_id: str):
    """
    WebSocket endpoint that streams LangGraph agent events in real time.

    Client connects, sends a JSON payload with the user prompt:
        { "prompt": "make a snake game" }

    Server streams typed events back:
        { "type": "agent_start",  "agent": "...", "timestamp": "..." }
        { "type": "agent_done",   "agent": "...", "output": {...}, "timestamp": "..." }
        { "type": "file_written", "path": "...", "content": "...", "timestamp": "..." }
        { "type": "run_complete", "qa_passed": true, "files": {...}, "timestamp": "..." }
        { "type": "run_error",    "message": "...", "timestamp": "..." }
    """
    await websocket.accept()

    try:
        # Wait for the client to send the prompt
        data = await websocket.receive_text()
        payload = json.loads(data)
        prompt = payload.get("prompt", "")

        if not prompt:
            await _send(websocket, {
                "type": "run_error",
                "message": "No prompt provided",
                "timestamp": _ts(),
            })
            await websocket.close()
            return

        if not isinstance(prompt, str) or len(prompt) > MAX_PROMPT_CHARS:
            await _send(websocket, {
                "type": "run_error",
                "message": f"Prompt is too long. Keep it under {MAX_PROMPT_CHARS} characters.",
                "timestamp": _ts(),
            })
            await websocket.close()
            return

        # Initial state for the graph
        initial_state = {
            "user_prompt": prompt,
            "creative_vision": None,
            "design_doc": None,
            "files": {},
            "qa_report": None,
            "retry_count": 0,
            "errors": [],
        }

        # Track which agent is currently running to emit start/done events
        current_agent: str | None = None
        files_sent: set[str] = set()
        files_sent_content: dict[str, str] = {}  # path → content for DB persistence
        qa_passed = False  # set from the last QA report, never assumed

        async for event in graph.astream_events(initial_state, version="v2"):
            kind = event.get("event")
            name = event.get("name", "")

            # ── Node starts ──────────────────────────────────────────
            if kind == "on_chain_start" and name in (
                "creative_director",
                "game_designer",
                "gameplay_programmer",
                "qa_tester",
            ):
                current_agent = name
                await _send(websocket, {
                    "type": "agent_start",
                    "agent": name,
                    "timestamp": _ts(),
                })

            # ── Node ends ────────────────────────────────────────────
            elif kind == "on_chain_end" and name in (
                "creative_director",
                "game_designer",
                "gameplay_programmer",
                "qa_tester",
            ):
                output = event.get("data", {}).get("output", {})

                # Serialize Pydantic models in output
                serialized_output = {}
                for key, val in output.items():
                    if hasattr(val, "model_dump"):
                        serialized_output[key] = val.model_dump()
                    else:
                        serialized_output[key] = val

                if name == "qa_tester" and output.get("qa_report") is not None:
                    qa_passed = bool(output["qa_report"].passed)

                # Emit file_written events for new files from programmer
                if name == "gameplay_programmer" and "files" in output:
                    for path, content in output["files"].items():
                        # Resend when a QA retry changed the file, otherwise the
                        # UI and database would keep the first (broken) version.
                        if files_sent_content.get(path) != content:
                            files_sent.add(path)
                            files_sent_content[path] = content
                            await _send(websocket, {
                                "type": "file_written",
                                "path": path,
                                "content": content,
                                "timestamp": _ts(),
                            })

                await _send(websocket, {
                    "type": "agent_done",
                    "agent": name,
                    "output": serialized_output,
                    "timestamp": _ts(),
                })
                current_agent = None

        # ── Run complete ─────────────────────────────────────────────
        if not files_sent_content:
            # Surfaces as run_error (and marks the run as failed) instead of a fake success.
            raise RuntimeError(
                "The programmer did not produce a playable game (no files were returned). "
                "Check the backend log for the [llm] lines, then try again."
            )

        # Save generated files to database if we have a valid run_id
        try:
            run_uuid = uuid.UUID(run_id)
            sessionmaker = get_sessionmaker()
            async with sessionmaker() as db:
                # Check if this run exists in DB
                run_result = await db.execute(
                    select(GenerationRun).where(GenerationRun.id == run_uuid)
                )
                run = run_result.scalar_one_or_none()

                if run:
                    # Update run status
                    run.status = "done"
                    run.completed_at = datetime.now(timezone.utc)

                    # Save generated files
                    for path, content in files_sent_content.items():
                        db.add(GeneratedFile(
                            id=uuid.uuid4(),
                            run_id=run.id,
                            path=path,
                            content=content,
                            version=1,
                        ))

                    # Update project status
                    project_result = await db.execute(
                        select(Project).where(Project.id == run.project_id)
                    )
                    project = project_result.scalar_one_or_none()
                    if project:
                        project.status = "done"

                    await db.commit()
        except (ValueError, Exception):
            # run_id might not be a valid UUID (e.g. test runs) — skip DB save
            pass

        await _send(websocket, {
            "type": "run_complete",
            "qa_passed": qa_passed,
            "timestamp": _ts(),
        })

    except WebSocketDisconnect:
        pass  # Client disconnected, nothing to do

    except Exception as e:
        # Try to mark run as errored in DB
        try:
            run_uuid = uuid.UUID(run_id)
            sessionmaker = get_sessionmaker()
            async with sessionmaker() as db:
                run_result = await db.execute(
                    select(GenerationRun).where(GenerationRun.id == run_uuid)
                )
                run = run_result.scalar_one_or_none()
                if run:
                    run.status = "error"
                    run.completed_at = datetime.now(timezone.utc)
                    project_result = await db.execute(
                        select(Project).where(Project.id == run.project_id)
                    )
                    project = project_result.scalar_one_or_none()
                    if project:
                        project.status = "error"
                    await db.commit()
        except Exception:
            pass

        try:
            await _send(websocket, {
                "type": "run_error",
                "message": str(e),
                "timestamp": _ts(),
            })
        except Exception:
            pass  # WebSocket might already be closed
        traceback.print_exc()

    finally:
        try:
            await websocket.close()
        except Exception:
            pass


# ── WebSocket: edit game via chat ─────────────────────────────────────────────

def _edit_call(messages: list) -> tuple[dict[str, str], bool, str]:
    """
    One blocking LLM call for an edit. Runs in a worker thread.
    Returns (clean_files, was_truncated, raw_text).
    """
    from agents.nodes import _finish_reason, _get_content, programmer_llm, wait_for_programmer_request_slot

    wait_for_programmer_request_slot()
    response = programmer_llm.invoke(messages)
    text = _get_content(response)
    files, _ = sanitize_files(parse_file_blocks(text))
    files.pop("tsconfig.json", None)  # managed by the server
    return files, _finish_reason(response) == "length", text


@app.websocket("/ws/edit/{run_id}")
async def websocket_edit(websocket: WebSocket, run_id: str):
    """
    WebSocket endpoint for iterative game editing via chat.

    Client sends messages with the current files and a change request:
        { "message": "make the player faster", "files": { "src/main.ts": "..." } }

    Server responds with updated files:
        { "type": "edit_start", "timestamp": "..." }
        { "type": "file_written", "path": "...", "content": "...", "timestamp": "..." }
        { "type": "edit_done", "timestamp": "..." }
        { "type": "edit_error", "message": "...", "timestamp": "..." }

    The connection stays open for multiple back-and-forth messages.

    Size policy (see agents/limits.py): the request message is capped, the
    current files are always sent fresh (never repeated in history), history
    holds only short summaries, and the whole input must fit MAX_INPUT_TOKENS.
    """
    await websocket.accept()

    # Lazy import to avoid circular deps
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
    from agents.nodes import EDIT_SYSTEM, run_qa_check
    from agents.limits import (
        MAX_EDIT_MESSAGE_CHARS, MAX_INPUT_TOKENS, BudgetExceeded,
        estimate_tokens, messages_tokens, render_files, trim_history,
    )

    system = SystemMessage(content=EDIT_SYSTEM)
    HISTORY_TOKENS = 4_000

    # Short summaries of earlier turns, not file contents.
    history: list = []

    async def fail(message: str) -> None:
        await _send(websocket, {"type": "edit_error", "message": message, "timestamp": _ts()})

    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                await fail("Invalid message.")
                continue

            message = payload.get("message", "") if isinstance(payload, dict) else ""
            raw_files = payload.get("files", {}) if isinstance(payload, dict) else {}

            if not isinstance(message, str) or not message.strip():
                await fail("No message provided")
                continue
            message = message.strip()
            if len(message) > MAX_EDIT_MESSAGE_CHARS:
                await fail(f"Message is too long. Keep it under {MAX_EDIT_MESSAGE_CHARS} characters.")
                continue
            if not isinstance(raw_files, dict) or not all(
                isinstance(k, str) and isinstance(v, str) for k, v in raw_files.items()
            ):
                await fail("Files must be a map of path to text.")
                continue

            files, _ = sanitize_files(raw_files)
            context_files = {p: c for p, c in files.items() if p != "tsconfig.json"}
            if not context_files:
                await fail("No game files were provided.")
                continue

            await _send(websocket, {"type": "edit_start", "timestamp": _ts()})

            try:
                history = trim_history(history, HISTORY_TOKENS)
                file_budget = (
                    MAX_INPUT_TOKENS
                    - estimate_tokens(EDIT_SYSTEM)
                    - messages_tokens(history)
                    - estimate_tokens(message)
                    - 1_000
                )
                user_msg = (
                    f"CURRENT FILES\n{render_files(context_files, file_budget)}\n\n"
                    f"REQUESTED CHANGE: {message}"
                )
                messages = [system, *history, HumanMessage(content=user_msg)]

                updated, truncated, text = await asyncio.to_thread(_edit_call, messages)

                if truncated or not updated:
                    # One retry that says what went wrong.
                    print(f"[edit] unusable reply (truncated={truncated}); first 1500 chars:\n{text[:1500]}")
                    why = (
                        "was cut off by the output limit. Make the code more compact and finish every file"
                        if truncated else
                        "could not be parsed"
                    )
                    retry = messages + [HumanMessage(content=(
                        f"Your reply {why}. Reply again with ONLY the changed files, each formatted exactly as:\n"
                        "--- path/to/file.ts ---\n<complete file content>\n--- end ---\n"
                        "No explanations and no markdown fences."
                    ))]
                    updated, truncated, text = await asyncio.to_thread(_edit_call, retry)

                if truncated or not updated:
                    await fail(
                        "The model's reply was cut off. Try a smaller change."
                        if truncated else
                        "Could not parse file changes from response"
                    )
                    continue

                merged = {**context_files, **updated}
                qa_report = await asyncio.to_thread(run_qa_check, merged)
                final = updated

                if not qa_report.passed:
                    # Retry once with the errors fed back.
                    error_text = "\n".join(e[:300] for e in qa_report.errors[:10])
                    fix_budget = (
                        MAX_INPUT_TOKENS - estimate_tokens(EDIT_SYSTEM)
                        - estimate_tokens(message) - estimate_tokens(error_text) - 1_000
                    )
                    fix_msg = (
                        f"The change produced these errors:\n{error_text}\n\n"
                        f"CURRENT FILES\n{render_files(merged, fix_budget)}\n\n"
                        f"REQUESTED CHANGE: {message}\n\n"
                        "Fix the errors. Return only the changed files in the required format."
                    )
                    fixed, fixed_trunc, fixed_text = await asyncio.to_thread(
                        _edit_call, [system, HumanMessage(content=fix_msg)]
                    )
                    if fixed and not fixed_trunc:
                        final = {**updated, **fixed}

                for path, content in final.items():
                    await _send(websocket, {
                        "type": "file_written",
                        "path": path,
                        "content": content,
                        "timestamp": _ts(),
                    })
                await _send(websocket, {"type": "edit_done", "timestamp": _ts()})

                history.append(HumanMessage(content=message))
                history.append(AIMessage(content=f"Applied the change. Files changed: {', '.join(final)}."))

            except BudgetExceeded as e:
                await fail(str(e))
            except Exception as e:
                await fail(str(e))

    except WebSocketDisconnect:
        pass

    except Exception as e:
        try:
            await fail(str(e))
        except Exception:
            pass

    finally:
        try:
            await websocket.close()
        except Exception:
            pass
