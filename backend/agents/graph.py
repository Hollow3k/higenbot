"""
agents/graph.py
---------------
Wires up the LangGraph StateGraph for the game-generation pipeline.

Flow:
  creative_director → game_designer → gameplay_programmer → qa_tester
                                              ↑                  |
                                              └── (retry) ───────┘
                                                                 |
                                                            (pass) → END
"""

from langgraph.graph import StateGraph, END

from agents.state import GraphState
from agents.nodes import (
    creative_director_node,
    game_designer_node,
    gameplay_programmer_node,
    qa_tester_node,
    qa_router,
)

# ── Build the graph ─────────────────────────────────────────────────────────

builder = StateGraph(GraphState)

# Add nodes
builder.add_node("creative_director", creative_director_node)
builder.add_node("game_designer", game_designer_node)
builder.add_node("gameplay_programmer", gameplay_programmer_node)
builder.add_node("qa_tester", qa_tester_node)

# Set entry point
builder.set_entry_point("creative_director")

# Linear edges
builder.add_edge("creative_director", "game_designer")
builder.add_edge("game_designer", "gameplay_programmer")
builder.add_edge("gameplay_programmer", "qa_tester")

# Conditional edge: QA pass → END, QA fail → programmer (up to 3 retries)
builder.add_conditional_edges(
    "qa_tester",
    qa_router,
    {
        "end": END,
        "retry": "gameplay_programmer",
    },
)

# Compile the graph
graph = builder.compile()
