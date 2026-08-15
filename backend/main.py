"""
main.py
-------
FastAPI application entry point.

Start the server:
    uvicorn main:app --reload
"""

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
    allow_origins=settings.ALLOWED_ORIGINS,
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

                # Emit file_written events for new files from programmer
                if name == "gameplay_programmer" and "files" in output:
                    for path, content in output["files"].items():
                        if path not in files_sent:
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
        # Save generated files to database if we have a valid run_id
        qa_passed = True
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
    """
    await websocket.accept()

    # Lazy import to avoid circular deps
    from langchain_core.messages import SystemMessage, HumanMessage
    from agents.nodes import programmer_llm, run_qa_check

    # Conversation history for multi-turn context
    conversation: list = []

    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)

            message = payload.get("message", "")
            files = payload.get("files", {})

            if not message:
                await _send(websocket, {
                    "type": "edit_error",
                    "message": "No message provided",
                    "timestamp": _ts(),
                })
                continue

            await _send(websocket, {
                "type": "edit_start",
                "timestamp": _ts(),
            })

            # Build the prompt with current files as context
            files_context = ""
            for path, content in files.items():
                files_context += f"\n--- {path} ---\n{content}\n"

            system_prompt = (
                "You are a game developer assistant. The user has a working HTML5 Canvas + TypeScript game. "
                "They want to make changes to it. You will receive the current files and a change request.\n\n"
                "Rules:\n"
                "- Output ONLY the complete updated file contents\n"
                "- Format your response as one or more file blocks like this:\n"
                "--- path/to/file.ts ---\n"
                "file content here\n"
                "--- end ---\n\n"
                "- Only include files that changed\n"
                "- Make sure the game still works after your changes\n"
                "- Keep changes minimal and focused on what the user asked for"
            )

            user_msg = f"Current files:\n{files_context}\n\nRequested change: {message}"

            # Build messages (include conversation history for context)
            messages = [SystemMessage(content=system_prompt)]
            messages.extend(conversation)
            messages.append(HumanMessage(content=user_msg))

            try:
                response = programmer_llm.invoke(messages)
                response_text = response.content

                # Handle Gemini returning content as list of parts
                if isinstance(response_text, list):
                    response_text = "".join(
                        part.get("text", "") if isinstance(part, dict) else str(part)
                        for part in response_text
                    )

                # Parse the response into file blocks
                updated_files = _parse_file_blocks(response_text)

                if not updated_files:
                    await _send(websocket, {
                        "type": "edit_error",
                        "message": "Could not parse file changes from response",
                        "timestamp": _ts(),
                    })
                else:
                    # Merge updated files with existing files for QA
                    merged_files = {**files, **updated_files}

                    # Run QA check
                    qa_report = run_qa_check(merged_files)

                    if qa_report.passed:
                        for path, content in updated_files.items():
                            await _send(websocket, {
                                "type": "file_written",
                                "path": path,
                                "content": content,
                                "timestamp": _ts(),
                            })

                        await _send(websocket, {
                            "type": "edit_done",
                            "timestamp": _ts(),
                        })
                    else:
                        # Retry once with errors fed back
                        error_context = "\n".join(qa_report.errors[:10])
                        retry_msg = (
                            f"The changes produced TypeScript errors:\n{error_context}\n\n"
                            f"Fix these errors. Here are the files again:\n"
                        )
                        for path, content in merged_files.items():
                            retry_msg += f"\n--- {path} ---\n{content}\n"

                        retry_messages = [SystemMessage(content=system_prompt)]
                        retry_messages.extend(conversation)
                        retry_messages.append(HumanMessage(content=retry_msg))

                        retry_response = programmer_llm.invoke(retry_messages)
                        retry_text = retry_response.content
                        if isinstance(retry_text, list):
                            retry_text = "".join(
                                part.get("text", "") if isinstance(part, dict) else str(part)
                                for part in retry_text
                            )

                        retry_files = _parse_file_blocks(retry_text)
                        if retry_files:
                            for path, content in retry_files.items():
                                await _send(websocket, {
                                    "type": "file_written",
                                    "path": path,
                                    "content": content,
                                    "timestamp": _ts(),
                                })
                            await _send(websocket, {
                                "type": "edit_done",
                                "timestamp": _ts(),
                            })
                            response_text = retry_text
                        else:
                            # Send the original files anyway with a warning
                            for path, content in updated_files.items():
                                await _send(websocket, {
                                    "type": "file_written",
                                    "path": path,
                                    "content": content,
                                    "timestamp": _ts(),
                                })
                            await _send(websocket, {
                                "type": "edit_done",
                                "timestamp": _ts(),
                            })

                # Keep conversation history (trimmed to last 6 exchanges)
                conversation.append(HumanMessage(content=user_msg))
                from langchain_core.messages import AIMessage
                conversation.append(AIMessage(content=response_text))
                if len(conversation) > 12:
                    conversation = conversation[-12:]

            except Exception as e:
                await _send(websocket, {
                    "type": "edit_error",
                    "message": str(e),
                    "timestamp": _ts(),
                })

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


def _parse_file_blocks(text: str) -> dict[str, str]:
    """Parse file blocks from LLM response in the format:
    --- path/to/file ---
    content
    --- end ---
    """
    import re
    files: dict[str, str] = {}

    # Pattern: --- filepath --- \n content \n --- end ---
    pattern = r"---\s+(.+?)\s+---\n(.*?)\n---\s*end\s*---"
    matches = re.findall(pattern, text, re.DOTALL)

    if matches:
        for path, content in matches:
            path = path.strip()
            files[path] = content.strip()
    else:
        # Fallback: try to find ```filename patterns
        code_pattern = r"```(?:\w+)?\s*\n?//\s*(.+?)\n(.*?)```"
        code_matches = re.findall(code_pattern, text, re.DOTALL)
        if code_matches:
            for path, content in code_matches:
                path = path.strip()
                files[path] = content.strip()
        else:
            # Last fallback: look for file paths as headers
            block_pattern = r"(?:^|\n)#+\s*`?([^\n`]+\.\w+)`?\s*\n```\w*\n(.*?)```"
            block_matches = re.findall(block_pattern, text, re.DOTALL)
            for path, content in block_matches:
                path = path.strip()
                files[path] = content.strip()

    return files
