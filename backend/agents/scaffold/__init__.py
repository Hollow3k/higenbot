# Scaffold package — TypeScript source files for the game engine.
# Use load_scaffold() to get all files as a dict[path, content].

from pathlib import Path

_SCAFFOLD_DIR = Path(__file__).parent


def load_scaffold() -> dict[str, str]:
    """
    Return all scaffold TypeScript source files as {relative_path: content}.

    Paths are relative to the project root (e.g. "src/input.ts").
    These are injected into the programmer's file set and into the QA temp dir.
    """
    result: dict[str, str] = {}
    src_dir = _SCAFFOLD_DIR / "src"
    for ts_file in sorted(src_dir.glob("*.ts")):
        rel = f"src/{ts_file.name}"
        result[rel] = ts_file.read_text(encoding="utf-8")
    return result


def load_tsconfig() -> str:
    """Return the canonical tsconfig.json content."""
    return (_SCAFFOLD_DIR / "tsconfig.json").read_text(encoding="utf-8")


def load_api_summary() -> str:
    """Return the compact scaffold API summary (for Programmer prompt)."""
    return (_SCAFFOLD_DIR / "api_summary.md").read_text(encoding="utf-8")


def load_skeleton() -> str:
    """Return the skeleton_main.ts reference game (for Programmer prompt)."""
    return (_SCAFFOLD_DIR / "skeleton_main.ts").read_text(encoding="utf-8")


# Scaffold paths — the programmer must never overwrite these
SCAFFOLD_PATHS: frozenset[str] = frozenset({
    "src/input.ts",
    "src/loop.ts",
    "src/canvas.ts",
    "src/audio.ts",
    "src/fx.ts",
    "src/state.ts",
    "src/storage.ts",
    "tsconfig.json",
})


def build_inline_preamble() -> str:
    """
    Build the inlined scaffold preamble for src/main.ts.

    Since the frontend compiles only src/main.ts with module:None,
    all scaffold classes must be available in the same scope.
    This function concatenates scaffold sources with 'export' keywords
    stripped so they compile as a plain script (no module system).

    ORDER matters: dependencies first.
    """
    ORDER = [
        "src/canvas.ts",
        "src/audio.ts",
        "src/input.ts",
        "src/loop.ts",
        "src/fx.ts",
        "src/state.ts",
        "src/storage.ts",
    ]
    scaffold = load_scaffold()
    parts: list[str] = [
        "// ── ENGINE SCAFFOLD (auto-injected, do not edit) ────────────────────────────",
    ]
    for path in ORDER:
        content = scaffold.get(path, "")
        if not content:
            continue
        # Strip export keyword from declarations so the code compiles
        # under module:None (no module system)
        import re
        content = re.sub(r"\bexport\s+(class|function|const|let|var|interface|type|enum)\b",
                         r"\1", content)
        # Strip standalone 'export {}' or 'export default ...' lines
        content = re.sub(r"^export\s*\{[^}]*\}\s*;?\s*$", "", content, flags=re.MULTILINE)
        content = re.sub(r"^export\s+default\b.*$", "", content, flags=re.MULTILINE)
        # Strip import statements (scaffold files don't import each other,
        # but be safe)
        content = re.sub(r"^import\s+.*?;?\s*$", "", content, flags=re.MULTILINE)
        parts.append(f"\n// ── {path} ────────────────────────────────────────────────────────────────")
        parts.append(content.strip())
    parts.append("\n// ── END SCAFFOLD ────────────────────────────────────────────────────────────\n")
    return "\n".join(parts)
