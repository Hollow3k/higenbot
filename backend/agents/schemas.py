"""
agents/schemas.py
-----------------
Pydantic output schemas used as structured outputs from the LLM nodes.

ALL existing fields are preserved so previously stored runs continue to load.
New fields use defaults so they are optional on deserialization.
Nesting is ONE level deep (flat submodels) so the planner model doesn't degrade.
"""

from typing import Literal
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# Sub-models (one level deep)
# ─────────────────────────────────────────────────────────────────────────────

class PaletteEntry(BaseModel):
    role: str = Field(
        description=(
            "Semantic role of this color. Must be one of: "
            "background, primary, secondary, accent, danger, ui_text, highlight"
        )
    )
    hex: str = Field(
        description="Hex color code, e.g. '#1a1a2e'. UI text must contrast strongly against its background."
    )


class ControlBinding(BaseModel):
    action: str = Field(
        description="Action identifier used in code, e.g. 'move_left', 'jump', 'fire', 'pause', 'restart', 'mute'"
    )
    keyboard_keys: list[str] = Field(
        default_factory=list,
        description=(
            "All keyboard keys that trigger this action. Use event.code values: "
            "'ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Space', 'KeyW', 'KeyA', 'KeyS', 'KeyD', "
            "'KeyR', 'KeyP', 'Escape', 'Enter', 'ShiftLeft', 'KeyZ', 'KeyX', 'KeyM'. "
            "Movement: BOTH Arrows AND WASD. Primary action: Space. Pause: P and Escape. "
            "Restart: R and Enter. Mute: M."
        )
    )
    touch: str = Field(
        default="",
        description=(
            "Concrete touch scheme for this action. Examples: "
            "'virtual joystick left side', 'tap button labeled JUMP at bottom-right (r=40px)', "
            "'tap anywhere', 'left half of screen', 'swipe up'"
        )
    )
    mouse: str = Field(
        default="",
        description="Mouse behavior if relevant, e.g. 'click to fire', 'drag to move', 'n/a'"
    )
    trigger: Literal["press", "hold"] = Field(
        default="press",
        description=(
            "'press' = one-shot on keydown (jump, restart, pause). "
            "'hold' = continuous while held (move, thrust, charge)."
        )
    )
    behavior: str = Field(
        default="",
        description=(
            "Exact behavioral contract: opposing keys cancel to zero, diagonals normalized, "
            "key repeat ignored for press actions, input buffer 100ms, coyote time 100ms, etc."
        )
    )


class GameState(BaseModel):
    name: str = Field(
        description="State machine name: 'menu', 'playing', 'paused', 'game_over', etc."
    )
    draws: str = Field(
        description="What is rendered in this state. Be specific: 'title text centered, one-line goal, controls table, best score bottom-right'"
    )
    accepts_input: str = Field(
        description="Which actions are live in this state, e.g. 'any key or tap starts game', 'move_left, move_right, jump, pause', 'restart'"
    )
    transitions: str = Field(
        description="Exit conditions. e.g. 'any input → playing', 'lives==0 → game_over', 'P/Escape → paused'"
    )


class EntityDetail(BaseModel):
    name: str = Field(description="Entity name, e.g. 'player', 'enemy', 'bullet', 'coin', 'platform'")
    size: str = Field(description="Width × height in logical pixels, e.g. '32×32'")
    collision_shape: str = Field(description="'rect' or 'circle'. Specify radius if circle.")
    hitbox_note: str = Field(
        description="Hitbox is 10–20% smaller than visual to make deaths feel fair. e.g. 'hitbox 24×24, centered'"
    )
    speed: str = Field(default="", description="Max speed in logical px/s, e.g. '320 px/s horizontal, 600 px/s vertical (gravity)'")
    acceleration: str = Field(default="", description="Acceleration in px/s², e.g. '2400 px/s² ground, 1600 px/s² air'")
    health: str = Field(default="", description="HP or lives, e.g. '3 lives', '1 hit kill', '100 HP'")
    spawn_rule: str = Field(default="", description="Where and when: 'start at (48, canvas_h/2)', 'every 3s from right edge, max 5 on screen'")
    behavior: str = Field(default="", description="AI or movement: 'tracks player horizontally at 80 px/s', 'bounces off walls', 'fires every 2s'")
    drawing: str = Field(
        default="",
        description="Canvas 2D drawing instructions using palette roles: 'filled rect primary color, white 2px border, rounded 4px'"
    )
    on_death: str = Field(default="", description="Spawn 8 particles (accent color), +10 score, play sweep sound 880→220Hz 150ms")


class PhysicsConfig(BaseModel):
    gravity: str = Field(default="", description="e.g. '1800 px/s² downward'")
    friction: str = Field(default="", description="e.g. '1800 px/s² ground deceleration'")
    max_speed: str = Field(default="", description="e.g. '320 px/s horizontal, 900 px/s vertical'")
    acceleration: str = Field(default="", description="e.g. '2400 px/s² player ground acceleration'")
    jump_velocity: str = Field(default="", description="e.g. '-640 px/s (variable: release early for shorter jump)'")
    terminal_velocity: str = Field(default="", description="e.g. '900 px/s downward'")
    bounce: str = Field(default="n/a", description="Bounce coefficient or 'n/a'")
    notes: str = Field(default="", description="Any other physics notes: coyote time 100ms, jump buffer 100ms, etc.")


class DifficultyStep(BaseModel):
    at: str = Field(description="Trigger: 'score 500', 'time 30s', 'wave 3'")
    change: str = Field(description="Parameter change: 'enemy spawn interval 3s→2s', 'enemy speed +20 px/s'")


class GameFeel(BaseModel):
    event: str = Field(description="Triggering event: 'jump', 'land', 'shoot', 'hit', 'pickup', 'death', 'score', 'level_up'")
    shake: str = Field(default="n/a", description="Screen shake: amplitude px, duration ms. e.g. '4px, 200ms' or 'n/a'")
    particles: str = Field(default="n/a", description="e.g. '8 particles, accent color, 300ms lifetime, burst outward' or 'n/a'")
    sound: str = Field(
        default="n/a",
        description="WebAudio synth: 'square, 220→440Hz, 80ms' or 'noise, 100ms' or 'n/a'"
    )
    hit_pause: str = Field(default="n/a", description="Freeze frames: e.g. '3 frames (50ms)' or 'n/a'")
    other: str = Field(default="", description="Squash/stretch, flicker, color flash, floating text, etc.")


class AudioCue(BaseModel):
    event: str = Field(description="Event name: 'jump', 'land', 'shoot', 'hit', 'pickup', 'death', 'game_over', 'level_up'")
    waveform: str = Field(description="'sine', 'square', 'sawtooth', 'triangle', 'noise'")
    freq_start: float = Field(description="Starting frequency in Hz, e.g. 440.0")
    freq_end: float = Field(description="Ending frequency in Hz (same as start for flat tone), e.g. 220.0")
    duration_ms: int = Field(description="Duration in milliseconds, e.g. 120")


class SpecViolation(BaseModel):
    item: str = Field(description="Checklist item or control action that was violated")
    file: str = Field(description="Source file where the violation was found")
    problem: str = Field(description="Specific problem found")
    fix: str = Field(description="Concrete fix required")


# ─────────────────────────────────────────────────────────────────────────────
# Top-level schemas
# ─────────────────────────────────────────────────────────────────────────────

class CreativeVision(BaseModel):
    """High-level creative direction for the game."""

    # ── Existing fields (unchanged) ──────────────────────────────────────────
    game_title: str = Field(description="A catchy, memorable title for the game")
    theme: str = Field(
        description="Core theme or narrative premise (e.g. 'neon-grid space', 'haunted forest escape')"
    )
    visual_style: str = Field(
        description=(
            "Art direction for procedural Canvas 2D only (no images, no web fonts). "
            "Choose one: neon-vector, flat-geometric, pixel-block, paper-cut, silhouette, synthwave, pastel-minimal. "
            "e.g. 'neon-vector: glowing lines on dark background, heavy shadowBlur, sharp angles'"
        )
    )
    mood: str = Field(
        description="Emotional tone: 'tense and claustrophobic', 'playful and bouncy', 'serene and meditative'"
    )
    target_feel: str = Field(
        description="Moment-to-moment feel: 'snappy, punchy — every input has instant feedback', 'floaty and momentum-driven'"
    )

    # ── New fields ───────────────────────────────────────────────────────────
    pitch: str = Field(
        default="",
        description=(
            "One-sentence pitch combining genre + twist + tone. "
            "e.g. 'A momentum-based wall-jumper where your trail becomes lethal after 5 seconds.'"
        )
    )
    core_verb: str = Field(
        default="",
        description=(
            "The single verb describing the primary player action. "
            "Must work on both keyboard AND touch. "
            "e.g. 'dodge', 'jump', 'shoot', 'stack', 'slide', 'merge'"
        )
    )
    core_fantasy: str = Field(
        default="",
        description=(
            "The power fantasy or emotional loop the player experiences. "
            "e.g. 'feel like an untouchable speedrunner threading impossible gaps'"
        )
    )
    palette: list[PaletteEntry] = Field(
        default_factory=list,
        description=(
            "5–7 colors with semantic roles. Required roles: background, primary, secondary, accent, danger, ui_text. "
            "Optional: highlight. ui_text must have WCAG-AA contrast against background. "
            "Example: [{role: 'background', hex: '#0d0d1a'}, {role: 'primary', hex: '#00ffcc'}, ...]"
        )
    )
    font_stack: str = Field(
        default="",
        description=(
            "System font stack for all text. No web fonts. "
            "e.g. \"'Courier New', Courier, monospace\" or \"'Segoe UI', Arial, sans-serif\""
        )
    )
    art_direction: str = Field(
        default="",
        description=(
            "Procedural Canvas 2D style rules for the programmer. Concrete, not vague. "
            "e.g. 'All game objects: filled rect + 1px stroke in secondary. Glow via ctx.shadowBlur=12, shadowColor=primary. "
            "Background: solid fill then subtle radial gradient center. Text: 14px monospace, ui_text color, "
            "1px shadow for readability. No shadowBlur on HUD elements (perf).'"
        )
    )
    audio_personality: str = Field(
        default="",
        description=(
            "WebAudio synthesis mood. e.g. 'chiptune: square waves, short sharp attacks, "
            "no reverb, tempo 160bpm feel' or 'sci-fi: sine sweeps, long fades, occasional noise bursts'"
        )
    )
    juice_personality: str = Field(
        default="",
        description=(
            "How hits, pickups, deaths and score-ups should FEEL. "
            "e.g. 'everything punchy: 3-frame hit-pause on every collision, large particle bursts, "
            "camera shake on death, floating +score text on every pickup'"
        )
    )


class DesignDoc(BaseModel):
    """Concrete game-design specification derived from the creative vision."""

    # ── Existing fields (unchanged) ──────────────────────────────────────────
    player_controls: str = Field(
        description=(
            "Legacy summary of controls (kept for backward compat). "
            "New code uses the 'controls' list instead."
        )
    )
    core_loop: str = Field(description="The repeating gameplay cycle the player engages in")
    win_condition: str = Field(description="What the player must achieve to win (or 'survive as long as possible')")
    lose_condition: str = Field(description="What causes the player to lose")
    entities: list[str] = Field(
        description="Legacy list of entity names (kept for backward compat). New code uses entities_detail."
    )
    level_structure: str = Field(
        description="How the level/world is organized: 'single screen', 'horizontal scroll', 'procedural chunks', etc."
    )

    # ── New fields ───────────────────────────────────────────────────────────
    canvas_width: int = Field(
        default=960,
        description="Logical canvas width in pixels. Use 960 for landscape, 540 for portrait."
    )
    canvas_height: int = Field(
        default=540,
        description="Logical canvas height in pixels. Use 540 for landscape, 960 for portrait."
    )
    orientation: Literal["landscape", "portrait"] = Field(
        default="landscape",
        description="'landscape' for keyboard-primary games, 'portrait' for one-thumb mobile games."
    )

    controls: list[ControlBinding] = Field(
        default_factory=list,
        description=(
            "EVERY player action with keyboard AND touch bindings. "
            "Required actions for ALL games: move_left, move_right, jump/primary_action, pause, restart, mute. "
            "Add game-specific actions as needed. "
            "Every keyboard_keys list must have BOTH primary (Arrow/Space) AND alternate (WASD/Enter) keys."
        )
    )
    start_screen_text: str = Field(
        default="",
        description=(
            "Exact one-line help shown on the menu for keyboard users. "
            "e.g. 'Arrows/WASD to move · Space to jump · P to pause'"
        )
    )
    touch_help_text: str = Field(
        default="",
        description=(
            "Exact one-line help shown on the menu for touch users. "
            "e.g. 'Left joystick to move · JUMP button to jump · tap to start'"
        )
    )

    states: list[GameState] = Field(
        default_factory=list,
        description=(
            "EVERY state machine state. Required: menu, playing, paused, game_over. "
            "menu: shows title + goal + controls + best score, any input starts. "
            "game_over: shows score + best + restart prompt. "
            "paused: overlay, resume on P/Escape. "
            "Blur auto-pauses."
        )
    )

    entities_detail: list[EntityDetail] = Field(
        default_factory=list,
        description=(
            "Detailed spec for every entity. For each: size, hitbox, speed, spawn rule, AI, drawing, on_death. "
            "All numbers in logical pixels and px/s."
        )
    )

    physics: PhysicsConfig = Field(
        default_factory=PhysicsConfig,
        description=(
            "Concrete physics numbers. All in logical pixels and px/s. "
            "If the game has no gravity, set gravity to 'n/a' and explain friction."
        )
    )

    scoring: str = Field(
        default="",
        description=(
            "Scoring formula with exact numbers. "
            "e.g. 'Enemy kill: +10 pts. Combo ×2 if next kill within 1s. High score persisted in localStorage.'"
        )
    )
    lives_or_health: str = Field(
        default="",
        description="e.g. '3 lives, displayed top-left' or '100 HP bar top-center' or 'one-hit kill'"
    )
    invincibility: str = Field(
        default="",
        description="e.g. '1.2s invincibility after hit, flicker at 10Hz (every 100ms toggle)'"
    )

    difficulty_curve: list[DifficultyStep] = Field(
        default_factory=list,
        description=(
            "Ordered list of difficulty increases. First 15s must be easy. "
            "Example: [{at:'time 0s', change:'1 enemy, slow'}, {at:'time 15s', change:'spawn interval 4s→3s'}, ...]"
        )
    )
    level_generation_rules: str = Field(
        default="",
        description=(
            "Rules for procedural generation. Must guarantee solvability: no unavoidable damage, no impossible gaps. "
            "e.g. 'Platforms: min gap 64px, max gap 200px, guaranteed path exists, no spike directly under a forced landing'"
        )
    )

    game_feel: list[GameFeel] = Field(
        default_factory=list,
        description=(
            "Game-feel spec for EVERY key event. Required events: jump, land, shoot/fire (if applicable), "
            "hit (player takes damage), pickup, death, score_milestone, game_over."
        )
    )

    hud: str = Field(
        default="",
        description=(
            "HUD layout per state. Exact positions using corner anchors. "
            "e.g. 'playing: score top-left (16,16), lives top-right (canvas_w-16,16), mute btn bottom-right. "
            "game_over: large score centered, best score below, PRESS R/TAP TO RESTART below that.'"
        )
    )

    audio_cues: list[AudioCue] = Field(
        default_factory=list,
        description=(
            "WebAudio synth spec for EVERY game event. "
            "Required: jump, land, hit, pickup, death, game_over. Add more as needed."
        )
    )

    edge_cases: list[str] = Field(
        default_factory=list,
        description=(
            "Edge cases the programmer must handle. "
            "e.g. ['Key held during state transition resets to unpressed in new state', "
            "'Resize during gameplay re-centers canvas without resetting game', "
            "'dt spike >50ms clamped to 50ms', 'Rapid restart: old entities cleared before new game starts']"
        )
    )
    acceptance_checklist: list[str] = Field(
        default_factory=list,
        description=(
            "10–15 testable statements the QA tester will verify. "
            "Examples: "
            "'Holding Left and Right simultaneously gives zero horizontal velocity', "
            "'Pressing R on game_over starts a new run within 1 frame', "
            "'On touch device, virtual joystick appears under left thumb', "
            "'No key press scrolls the host page', "
            "'Game auto-pauses when browser tab loses focus', "
            "'Audio plays after first gesture and respects mute toggle', "
            "'High score persists across page reloads (or degrades gracefully in sandboxed iframe)'"
        )
    )


class QAReport(BaseModel):
    """Result of the QA/type-check pass on generated code."""

    # ── Existing fields (unchanged) ──────────────────────────────────────────
    passed: bool = Field(description="Whether all checks passed (tsc + static + spec review)")
    errors: list[str] = Field(
        default_factory=list,
        description="TypeScript compilation errors (error TS* lines)"
    )
    suggestions: list[str] = Field(
        default_factory=list,
        description="Improvement suggestions for the next iteration"
    )

    # ── New field ────────────────────────────────────────────────────────────
    spec_violations: list[str] = Field(
        default_factory=list,
        description=(
            "Static check failures and LLM spec-review violations. "
            "e.g. 'src/main.ts: uses keyCode (banned)', "
            "'InputManager not imported', "
            "'action jump has no touch binding in code'"
        )
    )


# ─────────────────────────────────────────────────────────────────────────────
# Design markdown renderer
# ─────────────────────────────────────────────────────────────────────────────

def render_design_markdown(user_prompt: str, vision: CreativeVision, design: DesignDoc) -> str:
    """
    Render the full design as readable markdown.

    This is injected into the Programmer prompt (replacing lossy f-string summaries)
    and emitted as DESIGN.md in the file output so it travels through file_written,
    the DB, and the edit-chat context unchanged.
    """
    lines: list[str] = []

    lines.append(f"# DESIGN: {vision.game_title}")
    lines.append("")
    lines.append(f"**Original idea:** {user_prompt}")
    lines.append("")

    # ── Creative Vision ──────────────────────────────────────────────────────
    lines.append("## Creative Vision")
    lines.append("")
    if vision.pitch:
        lines.append(f"**Pitch:** {vision.pitch}")
    lines.append(f"**Theme:** {vision.theme}")
    lines.append(f"**Core verb:** {vision.core_verb}")
    lines.append(f"**Core fantasy:** {vision.core_fantasy}")
    lines.append(f"**Visual style:** {vision.visual_style}")
    lines.append(f"**Mood:** {vision.mood}")
    lines.append(f"**Target feel:** {vision.target_feel}")
    lines.append(f"**Font stack:** {vision.font_stack or 'monospace'}")
    lines.append(f"**Audio personality:** {vision.audio_personality}")
    lines.append(f"**Juice personality:** {vision.juice_personality}")
    lines.append("")

    if vision.palette:
        lines.append("### Palette")
        lines.append("")
        lines.append("| Role | Hex |")
        lines.append("|------|-----|")
        for p in vision.palette:
            lines.append(f"| {p.role} | `{p.hex}` |")
        lines.append("")

    if vision.art_direction:
        lines.append("### Art Direction")
        lines.append("")
        lines.append(vision.art_direction)
        lines.append("")

    # ── Design Doc ───────────────────────────────────────────────────────────
    lines.append("## Game Design")
    lines.append("")
    lines.append(f"**Canvas:** {design.canvas_width}×{design.canvas_height} logical px ({design.orientation})")
    lines.append(f"**Core loop:** {design.core_loop}")
    lines.append(f"**Win condition:** {design.win_condition}")
    lines.append(f"**Lose condition:** {design.lose_condition}")
    lines.append(f"**Level structure:** {design.level_structure}")
    lines.append("")

    if design.scoring:
        lines.append(f"**Scoring:** {design.scoring}")
    if design.lives_or_health:
        lines.append(f"**Lives/health:** {design.lives_or_health}")
    if design.invincibility:
        lines.append(f"**Invincibility:** {design.invincibility}")
    lines.append("")

    # Controls table
    if design.controls:
        lines.append("### Controls")
        lines.append("")
        lines.append("| Action | Keys | Touch | Trigger | Behavior |")
        lines.append("|--------|------|-------|---------|----------|")
        for c in design.controls:
            keys = ", ".join(c.keyboard_keys) if c.keyboard_keys else "—"
            touch = c.touch or "—"
            behavior = c.behavior[:80] + "…" if len(c.behavior) > 80 else (c.behavior or "—")
            lines.append(f"| `{c.action}` | {keys} | {touch} | {c.trigger} | {behavior} |")
        lines.append("")

    if design.start_screen_text:
        lines.append(f"**Keyboard help text:** \"{design.start_screen_text}\"")
    if design.touch_help_text:
        lines.append(f"**Touch help text:** \"{design.touch_help_text}\"")
    lines.append("")

    # State machine
    if design.states:
        lines.append("### State Machine")
        lines.append("")
        for s in design.states:
            lines.append(f"**{s.name}**")
            lines.append(f"- Draws: {s.draws}")
            lines.append(f"- Input: {s.accepts_input}")
            lines.append(f"- Transitions: {s.transitions}")
            lines.append("")

    # Physics
    p = design.physics
    if any([p.gravity, p.friction, p.max_speed, p.acceleration, p.jump_velocity]):
        lines.append("### Physics")
        lines.append("")
        if p.gravity:
            lines.append(f"- Gravity: {p.gravity}")
        if p.jump_velocity:
            lines.append(f"- Jump velocity: {p.jump_velocity}")
        if p.terminal_velocity:
            lines.append(f"- Terminal velocity: {p.terminal_velocity}")
        if p.max_speed:
            lines.append(f"- Max speed: {p.max_speed}")
        if p.acceleration:
            lines.append(f"- Acceleration: {p.acceleration}")
        if p.friction:
            lines.append(f"- Friction: {p.friction}")
        if p.bounce:
            lines.append(f"- Bounce: {p.bounce}")
        if p.notes:
            lines.append(f"- Notes: {p.notes}")
        lines.append("")

    # Entities
    if design.entities_detail:
        lines.append("### Entities")
        lines.append("")
        for e in design.entities_detail:
            lines.append(f"**{e.name}** ({e.size}, {e.collision_shape})")
            lines.append(f"- Hitbox: {e.hitbox_note}")
            if e.speed:
                lines.append(f"- Speed: {e.speed}")
            if e.acceleration:
                lines.append(f"- Acceleration: {e.acceleration}")
            if e.health:
                lines.append(f"- Health: {e.health}")
            if e.spawn_rule:
                lines.append(f"- Spawn: {e.spawn_rule}")
            if e.behavior:
                lines.append(f"- Behavior: {e.behavior}")
            if e.drawing:
                lines.append(f"- Drawing: {e.drawing}")
            if e.on_death:
                lines.append(f"- On death: {e.on_death}")
            lines.append("")

    # Difficulty curve
    if design.difficulty_curve:
        lines.append("### Difficulty Curve")
        lines.append("")
        lines.append("| At | Change |")
        lines.append("|----|--------|")
        for d in design.difficulty_curve:
            lines.append(f"| {d.at} | {d.change} |")
        lines.append("")

    if design.level_generation_rules:
        lines.append(f"**Level generation:** {design.level_generation_rules}")
        lines.append("")

    # Game feel
    if design.game_feel:
        lines.append("### Game Feel")
        lines.append("")
        lines.append("| Event | Shake | Particles | Sound | Hit-pause | Other |")
        lines.append("|-------|-------|-----------|-------|-----------|-------|")
        for g in design.game_feel:
            lines.append(
                f"| {g.event} | {g.shake} | {g.particles} | {g.sound} | {g.hit_pause} | {g.other} |"
            )
        lines.append("")

    # Audio cues
    if design.audio_cues:
        lines.append("### Audio Cues")
        lines.append("")
        lines.append("| Event | Waveform | Freq start | Freq end | Duration |")
        lines.append("|-------|----------|-----------|---------|---------|")
        for a in design.audio_cues:
            lines.append(
                f"| {a.event} | {a.waveform} | {a.freq_start} Hz | {a.freq_end} Hz | {a.duration_ms} ms |"
            )
        lines.append("")

    # HUD
    if design.hud:
        lines.append("### HUD")
        lines.append("")
        lines.append(design.hud)
        lines.append("")

    # Edge cases
    if design.edge_cases:
        lines.append("### Edge Cases")
        lines.append("")
        for ec in design.edge_cases:
            lines.append(f"- {ec}")
        lines.append("")

    # Acceptance checklist
    if design.acceptance_checklist:
        lines.append("### Acceptance Checklist")
        lines.append("")
        for item in design.acceptance_checklist:
            lines.append(f"- [ ] {item}")
        lines.append("")

    return "\n".join(lines)
