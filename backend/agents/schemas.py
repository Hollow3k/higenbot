"""
agents/schemas.py
-----------------
Pydantic models for the structured output of the planning agents.

Design goals
  * Concrete over vague: colors are hex codes, speeds are numbers, entities
    have sizes and spawn rules. The programmer should never have to invent
    the numbers that decide how a game feels.
  * Bounded size: every string and list has a length cap, so a reply cannot
    outgrow the output budget, and the programmer's input stays small.
  * Self-correcting: validators reject vague or inconsistent answers, and the
    error text is sent back to the model for a retry.
"""

import re
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, Field, field_validator, model_validator


# ─────────────────────────────────────────────────────────────────────────────
# Normalizers
# ─────────────────────────────────────────────────────────────────────────────

def _norm_hex(value: Any) -> Any:
    """Accept 'fff', '#FFF', '#ffffff' and return '#ffffff'."""
    if not isinstance(value, str):
        return value
    v = value.strip().lower().lstrip("#")
    if re.fullmatch(r"[0-9a-f]{3}", v):
        v = "".join(ch * 2 for ch in v)
    return f"#{v}"


HexColor = Annotated[
    str,
    Field(pattern=r"^#[0-9a-f]{6}$", json_schema_extra={"format": "hex-color"}),
    BeforeValidator(_norm_hex),
]

_ROLE_ALIASES = {
    "collectible": "pickup", "powerup": "pickup", "power-up": "pickup", "item": "pickup",
    "boss": "enemy", "monster": "enemy", "opponent": "enemy", "ai": "enemy",
    "npc": "ally", "teammate": "ally",
    "wall": "obstacle", "platform": "obstacle", "barrier": "obstacle",
    "bullet": "projectile", "ball": "projectile", "missile": "projectile",
    "goal": "target", "objective": "target",
    "background": "decoration", "effect": "decoration", "particle": "decoration",
}
ENTITY_ROLES = (
    "player", "enemy", "ally", "pickup", "hazard",
    "projectile", "obstacle", "target", "decoration",
)


def _clip(text: str, limit: int) -> str:
    """Trim overlong prose at a sentence or word boundary instead of rejecting it."""
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    for sep in (". ", "; ", ", ", " "):
        i = cut.rfind(sep)
        if i >= limit * 0.6:
            return cut[: i + (1 if sep == ". " else 0)].rstrip(" ,;")
    return cut.rstrip(" ,;")


class _Model(BaseModel):
    """
    Base for all LLM-facing models. Prose that is slightly too long is trimmed
    and lists with too many items are cut, so a small overrun cannot fail a
    whole (slow) generation. Structural problems still raise and trigger a retry.
    The prompt asks the model for SOFT_FACTOR of each limit to leave headroom.
    """

    @model_validator(mode="before")
    @classmethod
    def _apply_soft_limits(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        out = dict(data)
        for name, field in cls.model_fields.items():
            value = out.get(name)
            max_len = next(
                (getattr(m, "max_length", None) for m in field.metadata if getattr(m, "max_length", None)),
                None,
            )
            if not max_len:
                continue
            if isinstance(value, str) and len(value.strip()) > max_len:
                out[name] = _clip(value, max_len)
            elif isinstance(value, list) and len(value) > max_len:
                out[name] = value[:max_len]
        return out



# ─────────────────────────────────────────────────────────────────────────────
# Node 1 output: Creative Director
# ─────────────────────────────────────────────────────────────────────────────

class Palette(_Model):
    """The game's whole color scheme. Every drawn thing must use these colors."""

    background: HexColor = Field(description="Main background color, usually dark or muted so gameplay colors stand out")
    background_alt: HexColor = Field(description="Second background color, used for gradients or arena patterns")
    primary: HexColor = Field(description="Player and main interactive color")
    secondary: HexColor = Field(description="Supporting color for allies, pickups, or UI accents")
    accent: HexColor = Field(description="Highlight color for glow, score pops, and important feedback")
    danger: HexColor = Field(description="Enemies, hazards, and damage")
    text: HexColor = Field(description="HUD text color; must contrast strongly with the background")


class CreativeVision(_Model):
    """High-level creative direction for the game."""

    game_title: str = Field(min_length=2, max_length=40, description="Short, memorable title")
    genre: str = Field(max_length=40, description="Genre in 1-3 words, e.g. 'top-down shooter', 'endless runner', 'arcade sports'")
    pitch: str = Field(max_length=220, description="One sentence: what the player does and why it is fun")
    theme: str = Field(max_length=200, description="Setting or narrative premise")
    visual_style: str = Field(max_length=200, description="Specific art direction achievable with Canvas 2D shapes, gradients, and glow. No image assets.")
    palette: Palette
    rendering_notes: list[str] = Field(
        min_length=3, max_length=6,
        description="3-6 specific Canvas 2D techniques that give the look polish, each under 150 chars. "
                    "Examples: 'shadowBlur glow on player and pickups', 'two-layer parallax starfield', 'vignette overlay'",
    )
    mood: str = Field(max_length=100, description="Emotional tone, e.g. 'tense', 'playful'")
    target_feel: str = Field(max_length=160, description="Moment-to-moment feel, e.g. 'fast, twitchy, forgiving collisions'")
    audio_style: str = Field(max_length=160, description="Sound design using WebAudio oscillators only, e.g. 'short square-wave blips, low saw thud on damage'")
    hook: str = Field(max_length=200, description="The one memorable moment or mechanic that makes this game feel special")

    @field_validator("rendering_notes")
    @classmethod
    def _notes_not_long(cls, notes: list[str]) -> list[str]:
        return [n.strip()[:150] for n in notes if n.strip()]


# ─────────────────────────────────────────────────────────────────────────────
# Node 2 output: Game Designer
# ─────────────────────────────────────────────────────────────────────────────

class ControlBinding(_Model):
    input: str = Field(max_length=50, description="Physical input, e.g. 'ArrowLeft / A', 'Mouse move', 'Left click', 'Space'")
    action: str = Field(max_length=120, description="What it does, with direction or amount if relevant")


class EntitySpec(_Model):
    """One kind of thing that exists in the game world."""

    name: str = Field(min_length=1, max_length=30, description="Short name, e.g. 'Asteroid'")
    role: str = Field(description=f"One of: {', '.join(ENTITY_ROLES)}")
    shape: str = Field(max_length=20, description="Base shape: circle, rectangle, triangle, polygon, line, or composite")
    size_px: float = Field(ge=4, le=400, description="Width or diameter in logical canvas pixels")
    color: HexColor = Field(description="Main fill color; use a palette color unless there is a reason not to")
    appearance: str = Field(max_length=220, description="How to draw it with Canvas 2D primitives (outline, glow, details, animation)")
    behavior: str = Field(max_length=260, description="Exactly how it moves and acts, with numbers where possible")
    speed_px_per_sec: float = Field(default=0, ge=0, le=2500, description="Typical movement speed in pixels per second; 0 if static")
    health: int = Field(default=1, ge=0, le=1000, description="Hits it can take; 0 if indestructible")
    spawn_rule: str = Field(max_length=200, description="When, where, and how many spawn, e.g. 'every 1.2s at a random top edge x, max 10 alive'")

    @field_validator("role", mode="before")
    @classmethod
    def _normalize_role(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        v = value.strip().lower()
        v = _ROLE_ALIASES.get(v, v)
        if v not in ENTITY_ROLES:
            raise ValueError(f"role must be one of {', '.join(ENTITY_ROLES)}, got '{value}'")
        return v


class Mechanic(_Model):
    name: str = Field(max_length=40, description="Mechanic name, e.g. 'Dash', 'Combo multiplier'")
    rule: str = Field(max_length=320, description="Precise rule including trigger, effect, numbers, and cooldowns")


class Tunable(_Model):
    """A named constant that the programmer must declare verbatim."""

    name: str = Field(max_length=32, description="UPPER_SNAKE_CASE constant name, e.g. PLAYER_SPEED")
    value: float = Field(description="Numeric value")
    unit: str = Field(default="", max_length=20, description="Unit, e.g. 'px/s', 's', 'px', 'count', 'x'")
    purpose: str = Field(max_length=100, description="What this value controls")

    @field_validator("name", mode="before")
    @classmethod
    def _upper_snake(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        v = re.sub(r"[^A-Za-z0-9]+", "_", value.strip()).strip("_").upper()
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", v):
            raise ValueError(f"'{value}' cannot be converted to an UPPER_SNAKE_CASE identifier")
        return v


class DifficultyStep(_Model):
    when: str = Field(max_length=60, description="Trigger, e.g. 'every 15 seconds', 'score >= 500', 'level 3'")
    change: str = Field(max_length=160, description="What gets harder, with numbers")


class FeedbackEffect(_Model):
    """Game feel: what the player sees and hears when something happens."""

    trigger: str = Field(max_length=80, description="Event, e.g. 'player collects pickup', 'player takes damage'")
    visual: str = Field(max_length=160, description="Visual response, e.g. '12 gold particles burst, score text floats up'")
    sound: str = Field(max_length=120, description="WebAudio sound, e.g. 'square wave 440->880Hz over 0.08s'")


class DesignDoc(_Model):
    """Concrete, implementable game specification derived from the creative vision."""

    canvas_width: int = Field(ge=480, le=1280, description="Logical canvas width in pixels, typically 800-1024")
    canvas_height: int = Field(ge=360, le=900, description="Logical canvas height in pixels, typically 540-720")
    perspective: str = Field(max_length=60, description="Camera, e.g. 'top-down fixed screen', 'side view scrolling', 'fixed screen'")
    controls: list[ControlBinding] = Field(min_length=1, max_length=8, description="Every input the game uses")
    entities: list[EntitySpec] = Field(min_length=2, max_length=10, description="Every kind of object; exactly one must have role 'player'")
    core_loop: list[str] = Field(min_length=3, max_length=6, description="3-6 short steps of the repeating gameplay cycle, each under 120 chars")
    mechanics: list[Mechanic] = Field(min_length=2, max_length=8, description="The rules that make the game work")
    tunables: list[Tunable] = Field(min_length=6, max_length=24, description="Balance constants (speeds, timers, counts, damage) the code will declare as constants")
    scoring: str = Field(max_length=300, description="How points are earned, including combos or multipliers")
    win_condition: str = Field(max_length=200, description="How the player wins, or 'None - endless, score chase' for endless games")
    lose_condition: str = Field(max_length=200, description="What ends the run")
    difficulty_curve: list[DifficultyStep] = Field(min_length=2, max_length=5, description="How difficulty ramps over time")
    hud: list[str] = Field(min_length=2, max_length=8, description="HUD elements and their screen positions, each under 100 chars")
    feedback_effects: list[FeedbackEffect] = Field(min_length=3, max_length=10, description="Juice: particles, shake, flashes, and sounds for key events")
    level_structure: str = Field(max_length=300, description="How the playfield is laid out and whether it scrolls, changes, or is procedural")
    first_ten_seconds: str = Field(max_length=300, description="What the player sees and does in the first 10 seconds, so the game feels alive immediately")
    edge_cases: list[str] = Field(min_length=2, max_length=8, description="Pitfalls the code must handle, e.g. 'spawns never overlap the player', 'player clamped to canvas'")

    @field_validator("core_loop", "hud", "edge_cases")
    @classmethod
    def _clean_strings(cls, items: list[str]) -> list[str]:
        return [i.strip()[:160] for i in items if i.strip()]

    @model_validator(mode="after")
    def _check_consistency(self) -> "DesignDoc":
        players = [e for e in self.entities if e.role == "player"]
        if len(players) != 1:
            raise ValueError(f"exactly one entity must have role 'player', found {len(players)}")

        names = [t.name for t in self.tunables]
        dupes = sorted({n for n in names if names.count(n) > 1})
        if dupes:
            raise ValueError(f"duplicate tunable names: {', '.join(dupes)}")

        entity_names = [e.name.strip().lower() for e in self.entities]
        dupes = sorted({n for n in entity_names if entity_names.count(n) > 1})
        if dupes:
            raise ValueError(f"duplicate entity names: {', '.join(dupes)}")

        return self


# ─────────────────────────────────────────────────────────────────────────────
# Node 4 output: QA
# ─────────────────────────────────────────────────────────────────────────────

class QAReport(BaseModel):
    """Result of the QA/type-check pass on generated code."""

    passed: bool = Field(description="Whether the code compiled without errors")
    errors: list[str] = Field(default_factory=list, description="List of compilation or lint errors found")
    suggestions: list[str] = Field(default_factory=list, description="Improvement suggestions for the next iteration")


# ─────────────────────────────────────────────────────────────────────────────
# Prompt helpers
# ─────────────────────────────────────────────────────────────────────────────

SOFT_FACTOR = 0.8  # ask the model for 80% of each hard limit


def schema_hint(model_class: type[BaseModel]) -> str:
    """
    Render a model as pseudo-JSON with each field's description and limits as
    comments. Gives the LLM a precise template including nested objects, list
    sizes, and string length caps.
    """
    schema = model_class.model_json_schema()
    defs = schema.get("$defs", {})

    def resolve(node: dict) -> dict:
        if "$ref" in node:
            return defs[node["$ref"].split("/")[-1]]
        if "anyOf" in node:
            options = [n for n in node["anyOf"] if n.get("type") != "null"]
            return resolve(options[0]) if options else node
        return node

    def limits(node: dict) -> str:
        bits = []
        if "maxLength" in node:
            bits.append(f"max {int(node['maxLength'] * SOFT_FACTOR)} chars")
        if "minItems" in node or "maxItems" in node:
            bits.append(f"{node.get('minItems', 0)}-{node.get('maxItems', '')} items")
        if "minimum" in node and "maximum" in node:
            bits.append(f"{node['minimum']} to {node['maximum']}")
        return ", ".join(bits)

    def render(node: dict, pad: str) -> str:
        node = resolve(node)
        kind = node.get("type")
        if kind == "object":
            props = node.get("properties", {})
            required = set(node.get("required", []))
            lines = ["{"]
            for i, (name, sub) in enumerate(props.items()):
                sub_resolved = resolve(sub)
                notes = [sub.get("description") or sub_resolved.get("description") or ""]
                lim = limits(sub_resolved) or limits(sub)
                if lim:
                    notes.append(f"({lim})")
                if name not in required:
                    notes.append("[optional]")
                note = " ".join(n for n in notes if n)
                body = render(sub, pad + "  ")
                comma = "," if i < len(props) - 1 else ""
                comment = f"  // {note}" if note else ""
                lines.append(f'{pad}  "{name}": {body}{comma}{comment}')
            lines.append(f"{pad}}}")
            return "\n".join(lines)
        if kind == "array":
            item = render(node.get("items", {}), pad + "  ")
            return f"[\n{pad}  {item},\n{pad}  ...\n{pad}]"
        if kind == "string":
            return '"#rrggbb"' if node.get("format") == "hex-color" else '"string"'
        if kind in ("number", "integer"):
            return "0" if kind == "integer" else "0.0"
        if kind == "boolean":
            return "true"
        return "null"

    return render(schema, "")
