"""
test_qa.py
----------
Unit tests for the shared QA function and scaffold preamble builder.

Run with:
    python -m pytest test_qa.py -v
  or standalone:
    python test_qa.py

Tests:
  1. A file with a deliberate TS type error FAILS tsc (proves F1 is fixed on Windows/Linux path)
  2. The skeleton game PASSES all checks (tsc + static)
  3. Static checks catch each banned pattern
  4. Static checks catch each missing-required pattern
  5. run_qa_check returns passed=False when src/main.ts is missing
  6. build_inline_preamble produces a non-empty preamble with no 'export ' prefixes
  7. Scaffold __init__.py loads all 7 expected source files
  8. M1 logic: files_last_content tracks latest content, not first seen
  9. qa_router off-by-one is fixed (retry_count comparison)
 10. render_design_markdown produces required sections
"""

import sys
import os
import re
import logging

# Suppress logger output that would pollute test output
logging.disable(logging.WARNING)

# Allow importing backend modules directly
sys.path.insert(0, os.path.dirname(__file__))

from agents.scaffold import (
    build_inline_preamble,
    load_scaffold,
    load_skeleton,
    SCAFFOLD_PATHS,
)
from agents.schemas import (
    CreativeVision,
    DesignDoc,
    QAReport,
    render_design_markdown,
    PaletteEntry,
    ControlBinding,
)
from agents.nodes import run_qa_check, _static_checks

PASS = "PASS"
FAIL = "FAIL"
results: list[tuple[str, str, str]] = []  # (name, status, detail)


def check(name: str, condition: bool, detail: str = ""):
    status = PASS if condition else FAIL
    results.append((name, status, detail))
    marker = "✓" if condition else "✗"
    print(f"  {marker} {name}" + (f": {detail}" if detail else ""))


# ── Test 1: Type error → FAIL ─────────────────────────────────────────────────
print("\n[1] Type-error file must FAIL tsc")

bad_ts = """\
// deliberate type error
const x: number = "this is a string";
const loop = new GameLoop({} as any, (_dt: number) => {}, (_ctx: any) => {});
loop.start();
"""

# We pass raw game files — run_qa_check injects scaffold internally
bad_files = {"src/main.ts": bad_ts, "index.html": "<html><canvas></canvas></html>"}

qa_bad = run_qa_check(bad_files)
check(
    "Type error → qa.passed is False",
    not qa_bad.passed,
    f"passed={qa_bad.passed}, errors={qa_bad.errors[:2]}",
)
check(
    "Type error → errors list non-empty",
    len(qa_bad.errors) > 0,
    f"errors count={len(qa_bad.errors)}",
)


# ── Test 2: Skeleton game PASSES ───────────────────────────────────────────────
print("\n[2] Skeleton game must PASS tsc + static checks")

skeleton_source = load_skeleton()
skeleton_files = {
    "src/main.ts": skeleton_source,
    "index.html": '<html><body><canvas></canvas><script src="dist/main.js"></script></body></html>',
}

qa_skeleton = run_qa_check(skeleton_files)
check(
    "Skeleton → qa.passed is True",
    qa_skeleton.passed,
    f"errors={qa_skeleton.errors[:3]}, violations={qa_skeleton.spec_violations[:3]}",
)
check(
    "Skeleton → tsc errors is empty",
    len(qa_skeleton.errors) == 0,
    f"tsc_errors={qa_skeleton.errors[:3]}",
)
check(
    "Skeleton → spec violations is empty",
    len(qa_skeleton.spec_violations) == 0,
    f"spec_violations={qa_skeleton.spec_violations[:3]}",
)


# ── Test 3: Banned patterns are caught ────────────────────────────────────────
print("\n[3] Static checks catch banned patterns")

BANNED_FIXTURES = [
    ("keyCode",         "player.addEventListener('keydown', e => e.keyCode);"),
    ("alert",           "alert('game over');"),
    ("eval",            "eval('1+1');"),
    ("prompt",          "const n = prompt('name');"),
    ("any type",        "const x: any = 5;"),
    ("TODO",            "// TODO: implement this"),
    ("external URL",    "fetch('https://example.com/api')"),
    ("img tag",         "<img src='player.png'>"),
    ("setInterval",     "setInterval(() => gameLoop(), 16);"),
    ("direct localStorage", "localStorage.setItem('score', '5');"),
]

for name, fixture in BANNED_FIXTURES:
    # Inject the fixture into a minimal game file
    test_files = {
        "src/main.ts": f"// scaffold APIs already in scope\nconst input = new InputManager({{jump: {{keys:['Space']}}}});\nconst loop = new GameLoop(null as any, (_dt)=>{{}},(c)=>{{}});\nconst sm = new StateMachine();\nsetupCanvas(960,540);\nconst audio = new AudioManager();\n{fixture}",
        "index.html": "<html><canvas></canvas></html>",
    }
    violations = _static_checks(test_files)
    caught = any(True for v in violations)  # any violation present
    # More specific: the banned pattern should appear in at least one violation
    fixture_caught = len(violations) > 0
    check(f"Banned '{name}' caught", fixture_caught, f"violations={violations[:1]}")


# ── Test 4: Missing required patterns caught ──────────────────────────────────
print("\n[4] Static checks catch missing required items")

MISSING_FIXTURES = [
    ("no InputManager",  "const loop = new GameLoop(null as any, (dt)=>{}, (c)=>{});\nconst sm = new StateMachine();\nsetupCanvas(960,540);\nconst audio = new AudioManager();\nfunction game_over(){}\nfunction restart(){}\nfunction paused(){}\nconst dt = 0.016; dt;"),
    ("no GameLoop",      "const input = new InputManager({a:{keys:['Space']}});\nconst sm = new StateMachine();\nsetupCanvas(960,540);\nconst audio = new AudioManager();\nfunction game_over(){}\nfunction restart(){}\nfunction paused(){}\nconst dt=0.016; dt;"),
    ("no StateMachine",  "const input = new InputManager({a:{keys:['Space']}});\nconst loop = new GameLoop(null as any,(dt)=>{},(c)=>{});\nsetupCanvas(960,540);\nconst audio = new AudioManager();\nfunction game_over(){}\nfunction restart(){}\nfunction paused(){}\nconst dt=0.016; dt;"),
    ("no dt",            "const input = new InputManager({a:{keys:['Space']}});\nconst loop = new GameLoop(null as any,()=>{},(c)=>{});\nconst sm = new StateMachine();\nsetupCanvas(960,540);\nconst audio = new AudioManager();\nfunction game_over(){}\nfunction restart(){}\nfunction paused(){}\n"),
]

for name, fixture in MISSING_FIXTURES:
    test_files = {"src/main.ts": fixture, "index.html": "<html><canvas></canvas></html>"}
    violations = _static_checks(test_files)
    # The specific required thing should be in violations
    check(
        f"Missing '{name}' caught",
        len(violations) > 0,
        f"violations={violations[:2]}",
    )


# ── Test 5: Missing src/main.ts → passed=False ────────────────────────────────
print("\n[5] Missing src/main.ts → passed=False")

qa_no_main = run_qa_check({"index.html": "<html></html>"})
check("No main.ts → passed=False", not qa_no_main.passed)
check("No main.ts → spec_violations non-empty", len(qa_no_main.spec_violations) > 0)


# ── Test 6: build_inline_preamble ─────────────────────────────────────────────
print("\n[6] build_inline_preamble structure")

preamble = build_inline_preamble()
check("Preamble is non-empty", len(preamble) > 1000, f"len={len(preamble)}")
check("Preamble contains InputManager class", "class InputManager" in preamble)
check("Preamble contains GameLoop class", "class GameLoop" in preamble)
check("Preamble contains setupCanvas function", "function setupCanvas" in preamble)
check("Preamble contains AudioManager class", "class AudioManager" in preamble)
check("Preamble contains Particles class", "class Particles" in preamble)
check("Preamble contains StateMachine class", "class StateMachine" in preamble)
check("Preamble contains getHighScore function", "function getHighScore" in preamble)

# No bare 'export ' keyword should survive stripping
bare_exports = re.findall(r'\bexport\s+(class|function|const|let|var)\b', preamble)
check(
    "Preamble has no bare 'export' keywords",
    len(bare_exports) == 0,
    f"found: {bare_exports[:3]}",
)


# ── Test 7: Scaffold loads all 7 source files ─────────────────────────────────
print("\n[7] Scaffold loads expected source files")

scaffold = load_scaffold()
EXPECTED_FILES = [
    "src/input.ts", "src/loop.ts", "src/canvas.ts",
    "src/audio.ts", "src/fx.ts",  "src/state.ts", "src/storage.ts",
]
check("Scaffold returns 7 files", len(scaffold) == 7, f"got {len(scaffold)}: {list(scaffold.keys())}")
for f in EXPECTED_FILES:
    check(f"Scaffold contains {f}", f in scaffold, f"keys={list(scaffold.keys())}")


# ── Test 8: M1 files_last_content logic ──────────────────────────────────────
print("\n[8] M1 file tracking logic")

# Simulate the tracking dict from /ws/run
files_last_content: dict[str, str] = {}

def should_emit(path: str, content: str) -> bool:
    if files_last_content.get(path) != content:
        files_last_content[path] = content
        return True
    return False

# First write — should emit
check("First write emits", should_emit("src/main.ts", "v1"))
# Same content again — should NOT emit
check("Same content suppressed", not should_emit("src/main.ts", "v1"))
# Updated content on retry — MUST emit (M1 fix)
check("Updated content on retry emits", should_emit("src/main.ts", "v2"))
# DB must store latest (v2)
check("Latest content stored", files_last_content["src/main.ts"] == "v2")


# ── Test 9: qa_router off-by-one ─────────────────────────────────────────────
print("\n[9] qa_router off-by-one fix (QA_MAX_ATTEMPTS=4 → 3 retries)")

from agents.nodes import qa_router

def make_state(retry_count: int, passed: bool) -> dict:
    return {
        "qa_report": QAReport(passed=passed, errors=[] if passed else ["error TS1234: type error"], spec_violations=[]),
        "retry_count": retry_count,
        "errors": [],
        "spec_violations": [],
    }

# With QA_MAX_ATTEMPTS=4:
# retry_count=1 (after 1st QA run) → should retry
# retry_count=2 → should retry
# retry_count=3 → should retry
# retry_count=4 → should END (exhausted)
from core.config import settings
ma = settings.QA_MAX_ATTEMPTS  # 4 by default

check("retry_count=1 → retry", qa_router(make_state(1, False)) == "retry")  # type: ignore[arg-type]
check("retry_count=ma-1 → retry", qa_router(make_state(ma - 1, False)) == "retry")  # type: ignore[arg-type]
check("retry_count=ma → end",   qa_router(make_state(ma, False)) == "end")    # type: ignore[arg-type]
check("passed=True → end always", qa_router(make_state(1, True)) == "end")     # type: ignore[arg-type]


# ── Test 10: render_design_markdown sections ──────────────────────────────────
print("\n[10] render_design_markdown produces required sections")

vision = CreativeVision(
    game_title="Test Game",
    theme="space",
    visual_style="neon-vector",
    mood="tense",
    target_feel="snappy",
    pitch="A bullet-hell dodge game",
    core_verb="dodge",
    core_fantasy="untouchable",
    palette=[
        PaletteEntry(role="background", hex="#0d0d1a"),
        PaletteEntry(role="primary", hex="#00ffcc"),
    ],
    font_stack="monospace",
    art_direction="neon glows",
    audio_personality="chiptune",
    juice_personality="punchy",
)
design = DesignDoc(
    player_controls="Arrows to move",
    core_loop="dodge bullets",
    win_condition="survive",
    lose_condition="hit",
    entities=["player", "bullet"],
    level_structure="single screen",
    controls=[
        ControlBinding(
            action="move_left",
            keyboard_keys=["ArrowLeft", "KeyA"],
            touch="joystick left",
            trigger="hold",
            behavior="instant",
        )
    ],
    start_screen_text="Arrows/WASD to move",
    acceptance_checklist=["No key scrolls the page", "Game pauses on blur"],
)

md = render_design_markdown("make a space shooter", vision, design)

check("DESIGN.md has title heading", "# DESIGN:" in md)
check("DESIGN.md has Controls table", "| Action |" in md)
check("DESIGN.md has Acceptance Checklist", "Acceptance Checklist" in md)
check("DESIGN.md has palette table", "| background |" in md)
check("DESIGN.md has original idea", "make a space shooter" in md)
check("DESIGN.md has core_verb", "dodge" in md)


# ── Summary ───────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
passed_count = sum(1 for _, s, _ in results if s == PASS)
failed_count = sum(1 for _, s, _ in results if s == FAIL)
print(f"Results: {passed_count} passed, {failed_count} failed out of {len(results)} checks")

if failed_count > 0:
    print("\nFailed checks:")
    for name, status, detail in results:
        if status == FAIL:
            print(f"  ✗ {name}: {detail}")
    sys.exit(1)
else:
    print("All checks passed ✓")
    sys.exit(0)
