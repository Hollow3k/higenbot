"""
main.py
-------
FastAPI application entry point.

Start the server:
    uvicorn main:app --reload

Fixes in this version:
  M1 — file_written emitted whenever content is new OR changed (not first-seen only).
       DB persists the LATEST content per path.
  M2 — qa_passed reflects the real QA outcome; qa_errors and spec_violations
       are included in run_complete (extra fields only).
  M3 — narrow exception handling; real DB errors are logged, not swallowed.
  M4 — /ws/edit uses asyncio.to_thread for all blocking calls (LLM + QA).
  M5 — /ws/edit uses write_file tool-calling (shared with programmer node),
       robust retry, never sends broken files, conversation history capped by chars.
"""

import asyncio
import json
import logging
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
from agents.scaffold import SCAFFOLD_PATHS, load_api_summary
from db.database import get_sessionmaker
from db.models import GeneratedFile, GenerationRun, Project

logger = logging.getLogger(__name__)

app = FastAPI(
    title="HigenBot API",
    description="AI-powered game studio simulator backend",
    version="0.2.0",
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


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _send(ws: WebSocket, msg: dict):
    await ws.send_text(json.dumps(msg, default=str))


# ── WebSocket: stream agent graph events ─────────────────────────────────────

@app.websocket("/ws/run/{run_id}")
async def websocket_run(websocket: WebSocket, run_id: str):
    """
    Stream LangGraph agent events in real time.

    Client sends: { "prompt": "make a snake game" }

    Server streams:
        { "type": "agent_start",  "agent": "...", "timestamp": "..." }
        { "type": "agent_done",   "agent": "...", "output": {...}, "timestamp": "..." }
        { "type": "file_written", "path": "...", "content": "...", "timestamp": "..." }
        { "type": "run_complete", "qa_passed": bool, "qa_errors": [...],
          "spec_violations": [...], "timestamp": "..." }
        { "type": "run_error",    "message": "...", "timestamp": "..." }
    """
    await websocket.accept()

    try:
        data    = await websocket.receive_text()
        payload = json.loads(data)
        prompt  = payload.get("prompt", "")

        if not prompt:
            await _send(websocket, {
                "type": "run_error",
                "message": "No prompt provided",
                "timestamp": _ts(),
            })
            await websocket.close()
            return

        initial_state = {
            "user_prompt": prompt,
            "creative_vision": None,
            "design_doc": None,
            "files": {},
            "qa_report": None,
            "retry_count": 0,
            "errors": [],
            "spec_violations": [],
            "design_markdown": "",
        }

        # M1 fix: track LAST sent content per path (not first-seen).
        # A path is re-emitted and re-stored whenever content changes.
        files_last_content: dict[str, str] = {}   # path → last emitted content

        # For the final QA result
        last_qa_report = None

        async for event in graph.astream_events(initial_state, version="v2"):
            kind = event.get("event")
            name = event.get("name", "")

            # ── Node starts ──────────────────────────────────────────
            if kind == "on_chain_start" and name in (
                "creative_director", "game_designer",
                "gameplay_programmer", "qa_tester",
            ):
                await _send(websocket, {
                    "type": "agent_start",
                    "agent": name,
                    "timestamp": _ts(),
                })

            # ── Node ends ────────────────────────────────────────────
            elif kind == "on_chain_end" and name in (
                "creative_director", "game_designer",
                "gameplay_programmer", "qa_tester",
            ):
                output = event.get("data", {}).get("output", {})

                # Serialize Pydantic models
                serialized_output: dict = {}
                for key, val in output.items():
                    if hasattr(val, "model_dump"):
                        serialized_output[key] = val.model_dump()
                    elif key not in ("files",):
                        # Skip large file dicts from the serialized agent_done payload
                        serialized_output[key] = val

                # Capture QA report for run_complete
                if name == "qa_tester":
                    qa_report_raw = output.get("qa_report")
                    if qa_report_raw is not None:
                        last_qa_report = qa_report_raw

                # M1 fix: emit file_written for NEW or CHANGED files
                if name == "gameplay_programmer" and "files" in output:
                    for path, content in output["files"].items():
                        if files_last_content.get(path) != content:
                            files_last_content[path] = content
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

        # ── Run complete ─────────────────────────────────────────────
        # M2 fix: compute real qa_passed from the last QA report
        qa_passed = False
        qa_errors: list[str] = []
        spec_violations: list[str] = []

        if last_qa_report is not None:
            if hasattr(last_qa_report, "passed"):
                qa_passed       = last_qa_report.passed
                qa_errors       = list(last_qa_report.errors or [])
                spec_violations = list(last_qa_report.spec_violations or [])
            elif isinstance(last_qa_report, dict):
                qa_passed       = last_qa_report.get("passed", False)
                qa_errors       = list(last_qa_report.get("errors", []))
                spec_violations = list(last_qa_report.get("spec_violations", []))

        # Persist to DB
        try:
            run_uuid = uuid.UUID(run_id)  # raises ValueError for non-UUID run_ids
            sessionmaker = get_sessionmaker()
            async with sessionmaker() as db:
                run_result = await db.execute(
                    select(GenerationRun).where(GenerationRun.id == run_uuid)
                )
                run = run_result.scalar_one_or_none()

                if run:
                    run.status       = "done"
                    run.completed_at = datetime.now(timezone.utc)

                    # M1 fix: persist LATEST content (files_last_content = final state)
                    for path, content in files_last_content.items():
                        db.add(GeneratedFile(
                            id=uuid.uuid4(),
                            run_id=run.id,
                            path=path,
                            content=content,
                            version=1,
                        ))

                    project_result = await db.execute(
                        select(Project).where(Project.id == run.project_id)
                    )
                    project = project_result.scalar_one_or_none()
                    if project:
                        project.status = "done"

                    await db.commit()

        except ValueError:
            # Non-UUID run_id (e.g. test run) — skip DB save, not an error
            pass
        except Exception as db_exc:
            # M3 fix: log real DB errors instead of silently swallowing them
            logger.error("DB save failed for run %s: %s", run_id, db_exc, exc_info=True)

        # M2 fix: include qa_errors and spec_violations in run_complete
        await _send(websocket, {
            "type": "run_complete",
            "qa_passed": qa_passed,
            "qa_errors": qa_errors,
            "spec_violations": spec_violations,
            "timestamp": _ts(),
        })

    except WebSocketDisconnect:
        pass

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
                    run.status       = "error"
                    run.completed_at = datetime.now(timezone.utc)
                    project_result   = await db.execute(
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
            pass

        traceback.print_exc()

    finally:
        try:
            await websocket.close()
        except Exception:
            pass


# ── WebSocket: edit game via chat ─────────────────────────────────────────────

# Max size of the entire files payload accepted from the client (bytes)
_MAX_FILES_PAYLOAD = 2 * 1024 * 1024   # 2 MB
# Max chars stored per conversation history entry
_MAX_HISTORY_CHARS = 8_000
# Max history entries kept
_MAX_HISTORY_ENTRIES = 10


@app.websocket("/ws/edit/{run_id}")
async def websocket_edit(websocket: WebSocket, run_id: str):
    """
    Iterative game editing via chat.

    Client sends: { "message": "make the player faster", "files": { "src/main.ts": "..." } }

    Server streams:
        { "type": "edit_start",   "timestamp": "..." }
        { "type": "file_written", "path": "...", "content": "...", "timestamp": "..." }
        { "type": "edit_done",    "timestamp": "..." }
        { "type": "edit_error",   "message": "...", "timestamp": "..." }
    """
    await websocket.accept()

    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
    from langchain_core.tools import tool as lc_tool
    from agents.nodes import get_programmer_llm, run_qa_check, _get_text, SCAFFOLD_PATHS
    from agents.prompts import edit_chat_system

    # Conversation history: list of (user_summary, assistant_summary) tuples
    # We store summaries, NOT full file dumps
    history: list[dict] = []   # [{"role": "user"|"assistant", "content": str}]

    @lc_tool
    def write_file(path: str, content: str) -> str:
        """Write a file to the project."""
        return json.dumps({"written": path, "size": len(content)})

    try:
        while True:
            raw  = await websocket.receive_text()
            payload = json.loads(raw)

            message: str = payload.get("message", "")
            files: dict[str, str] = payload.get("files", {})

            if not message:
                await _send(websocket, {
                    "type": "edit_error",
                    "message": "No message provided",
                    "timestamp": _ts(),
                })
                continue

            # Sanity-check payload size
            total_size = sum(len(v) for v in files.values())
            if total_size > _MAX_FILES_PAYLOAD:
                await _send(websocket, {
                    "type": "edit_error",
                    "message": "Files payload too large",
                    "timestamp": _ts(),
                })
                continue

            await _send(websocket, {"type": "edit_start", "timestamp": _ts()})

            # Separate current game files from scaffold (read-only context only)
            game_files = {
                path: content
                for path, content in files.items()
                if path not in SCAFFOLD_PATHS
            }
            design_md    = game_files.get("DESIGN.md", "")
            api_summary  = load_api_summary()

            # Build the context message for the LLM
            files_context = ""
            for path, content in game_files.items():
                files_context += f"\n=== {path} ===\n{content}\n"

            user_content = (
                f"Current files:\n{files_context}\n"
                f"Change request: {message}"
            )

            system = edit_chat_system(api_summary)

            # Build message list with capped history
            messages: list = [SystemMessage(content=system)]
            for h in history[-_MAX_HISTORY_ENTRIES:]:
                if h["role"] == "user":
                    messages.append(HumanMessage(content=h["content"]))
                else:
                    messages.append(AIMessage(content=h["content"]))
            messages.append(HumanMessage(content=user_content))

            # M4 fix: run blocking LLM call off the event loop
            llm = get_programmer_llm()
            llm_with_tools = llm.bind_tools([write_file])

            async def _run_edit_llm() -> dict[str, str]:
                """Run the tool-calling loop in a thread. Returns updated_files."""
                updated: dict[str, str] = {}
                loop_msgs = list(messages)
                max_iter  = 15

                for _ in range(max_iter):
                    resp = await asyncio.to_thread(llm_with_tools.invoke, loop_msgs)
                    loop_msgs.append(resp)

                    resp_text = _get_text(resp)

                    # Truncation detection
                    finish_reason = ""
                    if hasattr(resp, "response_metadata"):
                        meta = resp.response_metadata or {}
                        finish_reason = str(
                            meta.get("finish_reason", "") or
                            meta.get("stop_reason", "") or ""
                        ).lower()

                    if finish_reason in ("length", "max_tokens"):
                        loop_msgs.append(HumanMessage(
                            content="Your response was cut off. Continue from where you stopped."
                        ))
                        continue

                    if not resp.tool_calls:
                        break

                    for tc in resp.tool_calls:
                        if tc["name"] != "write_file":
                            continue
                        path    = tc["args"].get("path", "")
                        content = tc["args"].get("content", "")

                        # Reject scaffold overwrites
                        if path in SCAFFOLD_PATHS:
                            loop_msgs.append(ToolMessage(
                                content=json.dumps({"ignored": path, "reason": "scaffold — read-only"}),
                                tool_call_id=tc["id"],
                            ))
                            continue

                        updated[path] = content
                        loop_msgs.append(ToolMessage(
                            content=json.dumps({"written": path, "size": len(content)}),
                            tool_call_id=tc["id"],
                        ))

                return updated

            try:
                updated_files = await _run_edit_llm()
            except Exception as llm_exc:
                await _send(websocket, {
                    "type": "edit_error",
                    "message": f"LLM error: {llm_exc}",
                    "timestamp": _ts(),
                })
                continue

            if not updated_files:
                await _send(websocket, {
                    "type": "edit_error",
                    "message": "No files were returned by the model",
                    "timestamp": _ts(),
                })
                continue

            # M5 fix: run QA on merged files
            merged = {**game_files, **updated_files}

            # M4 fix: run QA in a thread
            qa_report = await asyncio.to_thread(
                run_qa_check,
                merged,
                design_md,
                False,   # no LLM review in edit chat (too slow)
            )

            if qa_report.passed:
                for path, content in updated_files.items():
                    await _send(websocket, {
                        "type": "file_written",
                        "path": path,
                        "content": content,
                        "timestamp": _ts(),
                    })
                await _send(websocket, {"type": "edit_done", "timestamp": _ts()})

                # Update history with summaries (NOT full file dumps)
                history.append({"role": "user", "content": message[:_MAX_HISTORY_CHARS]})
                changed_paths = ", ".join(updated_files.keys())
                history.append({
                    "role": "assistant",
                    "content": f"Updated: {changed_paths}",
                })

            else:
                # Retry up to 2 times
                all_errors   = qa_report.errors + qa_report.spec_violations
                error_block  = "\n".join(all_errors[:20])
                retry_success = False

                for _attempt in range(2):
                    retry_context = (
                        f"The changes produced errors:\n{error_block}\n\n"
                        "Fix all errors. Current merged files:\n"
                    )
                    for p, c in merged.items():
                        retry_context += f"\n=== {p} ===\n{c}\n"

                    retry_msgs: list = [SystemMessage(content=system)]
                    retry_msgs.append(HumanMessage(content=retry_context))

                    try:
                        retry_llm_with_tools = get_programmer_llm().bind_tools([write_file])

                        async def _run_retry_llm(msgs=retry_msgs) -> dict[str, str]:
                            retry_updated: dict[str, str] = {}
                            loop_msgs = list(msgs)
                            for _ in range(10):
                                resp = await asyncio.to_thread(retry_llm_with_tools.invoke, loop_msgs)
                                loop_msgs.append(resp)
                                if not resp.tool_calls:
                                    break
                                for tc in resp.tool_calls:
                                    if tc["name"] != "write_file":
                                        continue
                                    p = tc["args"].get("path", "")
                                    c = tc["args"].get("content", "")
                                    if p not in SCAFFOLD_PATHS:
                                        retry_updated[p] = c
                                    loop_msgs.append(ToolMessage(
                                        content=json.dumps({"written": p}),
                                        tool_call_id=tc["id"],
                                    ))
                            return retry_updated

                        retry_files = await _run_retry_llm()
                        if retry_files:
                            retry_merged = {**game_files, **retry_files}
                            retry_qa = await asyncio.to_thread(
                                run_qa_check, retry_merged, design_md, False
                            )
                            if retry_qa.passed:
                                for path, content in retry_files.items():
                                    await _send(websocket, {
                                        "type": "file_written",
                                        "path": path,
                                        "content": content,
                                        "timestamp": _ts(),
                                    })
                                await _send(websocket, {"type": "edit_done", "timestamp": _ts()})
                                history.append({"role": "user", "content": message[:_MAX_HISTORY_CHARS]})
                                history.append({"role": "assistant", "content": f"Updated (after retry): {', '.join(retry_files.keys())}"})
                                retry_success = True
                                break
                            # Update error context for next retry
                            all_errors  = retry_qa.errors + retry_qa.spec_violations
                            error_block = "\n".join(all_errors[:20])
                            merged = retry_merged  # continue from latest attempt
                    except Exception as retry_exc:
                        logger.warning("Edit retry %d failed: %s", _attempt + 1, retry_exc)
                        break

                if not retry_success:
                    # M5 fix: NEVER send broken files — tell the user it failed
                    summary = "; ".join(all_errors[:5])
                    await _send(websocket, {
                        "type": "edit_error",
                        "message": f"QA failed after retries — changes not applied. Errors: {summary}",
                        "timestamp": _ts(),
                    })

            # Cap history length by character count
            while len(history) > _MAX_HISTORY_ENTRIES * 2:
                history.pop(0)

    except WebSocketDisconnect:
        pass

    except Exception as e:
        try:
            await _send(websocket, {
                "type": "edit_error",
                "message": str(e),
                "timestamp": _ts(),
            })
        except Exception:
            pass

    finally:
        try:
            await websocket.close()
        except Exception:
            pass
