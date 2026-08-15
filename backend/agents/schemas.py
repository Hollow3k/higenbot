"""
agents/schemas.py
-----------------
Pydantic output schemas used as structured outputs from the LLM nodes.
"""

from pydantic import BaseModel, Field


class CreativeVision(BaseModel):
    """High-level creative direction for the game."""

    game_title: str = Field(description="A catchy, memorable title for the game")
    theme: str = Field(description="Core theme or narrative premise (e.g. 'space exploration', 'dungeon escape')")
    visual_style: str = Field(description="Art direction description (e.g. 'pixel-art retro', 'minimalist neon')")
    mood: str = Field(description="Emotional tone the game should evoke (e.g. 'tense', 'playful', 'serene')")
    target_feel: str = Field(description="How the gameplay should feel moment-to-moment (e.g. 'fast and frantic', 'methodical and strategic')")


class DesignDoc(BaseModel):
    """Concrete game-design specification derived from the creative vision."""

    player_controls: str = Field(description="How the player interacts (keyboard keys, mouse, touch) and what actions are available")
    core_loop: str = Field(description="The repeating gameplay cycle the player engages in")
    win_condition: str = Field(description="What the player must achieve to win")
    lose_condition: str = Field(description="What causes the player to lose")
    entities: list[str] = Field(description="List of game entities/objects (player, enemies, collectibles, obstacles, etc.)")
    level_structure: str = Field(description="How the level/world is organized (single screen, scrolling, procedural, etc.)")


class QAReport(BaseModel):
    """Result of the QA/type-check pass on generated code."""

    passed: bool = Field(description="Whether the code compiled without errors")
    errors: list[str] = Field(default_factory=list, description="List of compilation or lint errors found")
    suggestions: list[str] = Field(default_factory=list, description="Improvement suggestions for the next iteration")
