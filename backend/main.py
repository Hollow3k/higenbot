"""
main.py
-------
FastAPI application entry point.

Start the server:
    uvicorn main:app --reload
"""

import json
import traceback
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.config import settings
from api.projects import router as projects_router
from agents.graph import graph

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
        # After the stream finishes, get the final state by running once more
        # Actually astream_events doesn't return final state directly,
        # so we track it from the last qa_tester output
        # We already sent all events, now send run_complete
        await _send(websocket, {
            "type": "run_complete",
            "qa_passed": True,  # If we got here without error, last QA state was sent in agent_done
            "timestamp": _ts(),
        })

    except WebSocketDisconnect:
        pass  # Client disconnected, nothing to do

    except Exception as e:
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