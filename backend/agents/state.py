"""
agents/state.py
---------------
Shared graph state that flows between all agent nodes in the LangGraph pipeline.

New optional fields added with get() defaults so existing initial states
(which don't set them) continue to work without modification.
"""

from typing import TypedDict

from agents.schemas import CreativeVision, DesignDoc, QAReport


class GraphState(TypedDict, total=False):
    """State dictionary shared across all agent nodes."""

    # ── Required fields (present from initial_state) ──────────────────────
    user_prompt: str
    creative_vision: CreativeVision | None
    design_doc: DesignDoc | None
    files: dict[str, str]           # path → file content (includes scaffold)
    qa_report: QAReport | None
    retry_count: int
    errors: list[str]               # tsc errors carried to programmer on retry

    # ── New optional fields ───────────────────────────────────────────────
    # Rendered markdown from render_design_markdown(); passed to programmer
    # and emitted as DESIGN.md.  Populated by game_designer_node.
    design_markdown: str

    # Spec violations from static checks / LLM review; carried to programmer
    spec_violations: list[str]
