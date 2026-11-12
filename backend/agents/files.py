"""
agents/files.py
---------------
Parsing and sanitizing of files returned by the LLM.

The model is asked to answer in this format:

    --- path/to/file.ts ---
    <full file content>
    --- end ---

Plain text blocks are used instead of JSON tool-call arguments because long
source files inside JSON strings need heavy escaping, and a response cut off
by the output limit then yields invalid JSON and loses the whole file.
"""

import re

from agents.limits import MAX_PROJECT_FILES, normalize_path

# One file may be at most this many characters (~25k tokens).
MAX_FILE_CHARS = 80_000

# Only these files can be part of a game project.
_ALLOWED_PATH = re.compile(r"^(index\.html|tsconfig\.json|src/[\w.\-/]+\.ts)$")

# Fixed tsconfig. Written by us, never by the model, so QA always checks the
# same strict settings.
TSCONFIG = (
    '{\n'
    '  "compilerOptions": {\n'
    '    "target": "ES2020",\n'
    '    "module": "ES2020",\n'
    '    "lib": ["ES2020", "DOM"],\n'
    '    "outDir": "dist",\n'
    '    "strict": true,\n'
    '    "skipLibCheck": true\n'
    '  },\n'
    '  "include": ["src/**/*.ts"]\n'
    '}\n'
)

_SCRIPT_TAG = re.compile(r"<script[^>]*src=['\"][^'\"]*['\"][^>]*>\s*</script>", re.IGNORECASE)


def _strip_fence(body: str) -> str:
    body = body.strip()
    m = re.match(r"^```[\w+-]*\n(.*?)\n?```$", body, re.DOTALL)
    return (m.group(1) if m else body).strip()


def parse_file_blocks(text: str) -> dict[str, str]:
    """Parse `--- path --- ... --- end ---` blocks (with several fallbacks) into {path: content}."""
    files: dict[str, str] = {}

    # Normalise: line endings and reasoning-model <think> blocks
    text = text.replace("\r\n", "\n")
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)

    pattern = r"^[ \t]*-{3,}[ \t]*([^\n]+?\.\w+)[ \t]*-{3,}[ \t]*\n(.*?)\n[ \t]*-{3,}[ \t]*end[ \t]*-{3,}"
    matches = re.findall(pattern, text, re.DOTALL | re.MULTILINE | re.IGNORECASE)

    if not matches:
        # Tolerate a missing "--- end ---": split on header lines instead
        header = re.compile(r"^[ \t]*-{3,}[ \t]*([^\n]+?\.\w+)[ \t]*-{3,}[ \t]*$", re.MULTILINE)
        heads = list(header.finditer(text))
        for i, h in enumerate(heads):
            end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
            body = re.sub(
                r"\n[ \t]*-{3,}[ \t]*end[ \t]*-{3,}\s*$", "",
                text[h.end():end].rstrip(), flags=re.IGNORECASE,
            )
            matches.append((h.group(1), body))

    if matches:
        for path, content in matches:
            files[path.strip().strip("`")] = _strip_fence(content)
    else:
        # Fallback: ```lang\n// path\n...``` blocks
        for path, content in re.findall(r"```(?:\w+)?\s*\n?//\s*(.+?)\n(.*?)```", text, re.DOTALL):
            files[path.strip()] = content.strip()
        if not files:
            # Markdown headers with a path, followed by a fence
            for path, content in re.findall(
                r"(?:^|\n)#+\s*`?([^\n`]+\.\w+)`?\s*\n```\w*\n(.*?)```", text, re.DOTALL
            ):
                files[path.strip()] = content.strip()
        if not files:
            # Last resort: unlabeled fences. First html fence is the page,
            # first ts/typescript fence is the game.
            for lang, body in re.findall(r"```(\w+)[^\n]*\n(.*?)```", text, re.DOTALL):
                lang = lang.lower()
                if lang == "html" and "index.html" not in files:
                    files["index.html"] = body.strip()
                elif lang in ("ts", "typescript") and "src/main.ts" not in files:
                    files["src/main.ts"] = body.strip()

    return files


def _canonical_path(raw: str) -> str | None:
    """
    Map the paths a model tends to invent onto the project layout:
    'game/index.html' -> 'index.html', 'football/src/main.ts' -> 'src/main.ts',
    'main.ts' -> 'src/main.ts'. Unsafe paths still return None.
    """
    path = normalize_path(raw)
    if path is None:
        return None
    low = path.lower()
    if low.endswith("index.html"):
        return "index.html"
    if low.endswith("tsconfig.json"):
        return "tsconfig.json"
    m = re.search(r"(?:^|/)src/([^/].*\.ts)$", path)
    if m:
        return f"src/{m.group(1)}"
    if low.endswith(".ts"):
        return f"src/{path.rsplit('/', 1)[-1]}"
    return path


def sanitize_files(files: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    """
    Keep only safe, allowed, reasonably sized files.
    Returns (clean_files, problems). Problems are human-readable and are meant
    to be fed back to the model.
    """
    clean: dict[str, str] = {}
    problems: list[str] = []

    # If the model named its single TypeScript file something else (game.ts),
    # treat it as the entry point.
    ts_paths = [p for p in (_canonical_path(r) for r in files) if p and p.startswith("src/")]
    rename_to_main = len(ts_paths) == 1 and ts_paths[0] != "src/main.ts"

    for raw_path, content in files.items():
        path = _canonical_path(raw_path)
        if path is not None and rename_to_main and path == ts_paths[0]:
            path = "src/main.ts"
        if path is None or not _ALLOWED_PATH.match(path):
            problems.append(
                f"Ignored file '{raw_path}'. Only index.html and src/*.ts files are allowed."
            )
            continue
        if not isinstance(content, str) or not content.strip():
            problems.append(f"Ignored empty file '{path}'.")
            continue
        if len(content) > MAX_FILE_CHARS:
            problems.append(
                f"'{path}' is {len(content):,} characters; the limit is {MAX_FILE_CHARS:,}. Make it more compact."
            )
            continue
        clean[path] = content
    if len(clean) > MAX_PROJECT_FILES:
        keep = list(clean)[:MAX_PROJECT_FILES]
        problems.append(f"Too many files; kept the first {MAX_PROJECT_FILES}.")
        clean = {p: clean[p] for p in keep}
    return clean, problems


def finalize_project(files: dict[str, str]) -> dict[str, str]:
    """
    Make a generated file set loadable by the preview and the type-checker:
      * tsconfig.json is always our fixed version
      * index.html always has a <script src=...> tag, because the preview
        inlines the compiled JS in place of that tag
    """
    out = dict(files)
    out["tsconfig.json"] = TSCONFIG

    html = out.get("index.html")
    if html and not _SCRIPT_TAG.search(html):
        tag = '<script src="dist/main.js"></script>'
        if re.search(r"</body>", html, re.IGNORECASE):
            html = re.sub(r"</body>", f"{tag}\n</body>", html, count=1, flags=re.IGNORECASE)
        else:
            html = html.rstrip() + f"\n{tag}\n"
        out["index.html"] = html
    return out
