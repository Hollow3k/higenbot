"""
agents/state.py
---------------
Shared graph state that flows between all nodes in the LangGraph pipeline.
"""

from typing import TypedDict

from agents.schemas import CreativeVision, DesignDoc, QAReport


class GraphState(TypedDict):
    """State dictionary shared across all agent nodes."""

    user_prompt: str
    creative_vision: CreativeVision | None
    design_doc: DesignDoc | None
    files: dict[str, str]  # path → file content
    qa_report: QAReport | None
    retry_count: int
    errors: list[str]
