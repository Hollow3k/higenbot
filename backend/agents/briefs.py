"""
agents/briefs.py
----------------
Turn the structured CreativeVision / DesignDoc into compact plain-text briefs
for the next agent. Plain text with code-shaped sections is shorter than the
JSON dump and easier for a model to follow.
"""

import json

from agents.schemas import CreativeVision, DesignDoc


def _num(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(round(value, 4))


def vision_brief(v: CreativeVision) -> str:
    p = v.palette
    notes = "\n".join(f"  - {n}" for n in v.rendering_notes)
    return (
        f"TITLE: {v.game_title}\n"
        f"GENRE: {v.genre}\n"
        f"PITCH: {v.pitch}\n"
        f"THEME: {v.theme}\n"
        f"VISUAL STYLE: {v.visual_style}\n"
        f"PALETTE: background {p.background}, background_alt {p.background_alt}, primary {p.primary}, "
        f"secondary {p.secondary}, accent {p.accent}, danger {p.danger}, text {p.text}\n"
        f"RENDERING TECHNIQUES:\n{notes}\n"
        f"MOOD: {v.mood}\n"
        f"FEEL: {v.target_feel}\n"
        f"AUDIO: {v.audio_style}\n"
        f"HOOK: {v.hook}"
    )


def design_brief(d: DesignDoc) -> str:
    lines: list[str] = []
    lines.append(f"CANVAS: {d.canvas_width}x{d.canvas_height} logical pixels. CAMERA: {d.perspective}")

    lines.append("\nCONTROLS:")
    lines += [f"  - {c.input}: {c.action}" for c in d.controls]

    lines.append("\nENTITIES:")
    for e in d.entities:
        lines.append(
            f"  - {e.name} [{e.role}] {e.shape}, {_num(e.size_px)}px, {e.color}, "
            f"speed {_num(e.speed_px_per_sec)}px/s, health {e.health}\n"
            f"      look: {e.appearance}\n"
            f"      behavior: {e.behavior}\n"
            f"      spawn: {e.spawn_rule}"
        )

    lines.append("\nCORE LOOP:")
    lines += [f"  {i}. {s}" for i, s in enumerate(d.core_loop, 1)]

    lines.append("\nMECHANICS:")
    lines += [f"  - {m.name}: {m.rule}" for m in d.mechanics]

    lines.append("\nCONSTANTS (declare these verbatim at the top of the code):")
    for t in d.tunables:
        unit = f" ({t.unit})" if t.unit else ""
        lines.append(f"  const {t.name} = {_num(t.value)}; // {t.purpose}{unit}")

    lines.append(f"\nSCORING: {d.scoring}")
    lines.append(f"WIN: {d.win_condition}")
    lines.append(f"LOSE: {d.lose_condition}")

    lines.append("\nDIFFICULTY:")
    lines += [f"  - {s.when}: {s.change}" for s in d.difficulty_curve]

    lines.append("\nHUD:")
    lines += [f"  - {h}" for h in d.hud]

    lines.append("\nFEEDBACK (game feel):")
    lines += [f"  - on {f.trigger}: {f.visual}; sound: {f.sound}" for f in d.feedback_effects]

    lines.append(f"\nLEVEL: {d.level_structure}")
    lines.append(f"FIRST 10 SECONDS: {d.first_ten_seconds}")

    lines.append("\nEDGE CASES TO HANDLE:")
    lines += [f"  - {c}" for c in d.edge_cases]

    return "\n".join(lines)


def compact_json(model) -> str:
    return json.dumps(model.model_dump(), separators=(",", ":"))
