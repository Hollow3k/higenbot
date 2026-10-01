import { useMemo, useRef, useState, useEffect, useCallback } from "react";
import { useStudioStore } from "../store/useStudioStore";
import ts from "typescript";

export function PreviewPane() {
  const files     = useStudioStore((s) => s.files);
  const runStatus = useStudioStore((s) => s.runStatus);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [focused, setFocused] = useState(false);

  // ── Compile TypeScript → srcdoc ─────────────────────────────────────────
  const previewHtml = useMemo(() => {
    if (runStatus !== "done") return null;

    const html     = files["index.html"];
    const tsSource = files["src/main.ts"];

    if (!html || !tsSource) return null;

    // Compile the single-file bundle (scaffold is already inlined as preamble)
    const result = ts.transpileModule(tsSource, {
      compilerOptions: {
        target: ts.ScriptTarget.ES2020,
        // module:None — scaffold preamble is plain script, no imports
        module: ts.ModuleKind.None,
        strict: false,
        esModuleInterop: true,
        skipLibCheck: true,
      },
    });

    const js = result.outputText;

    // Replace the external script tag with inline JS so the sandboxed iframe
    // can run it without needing allow-same-origin
    const rendered = html.replace(
      /<script[^>]*src=['"][^'"]*['"][^>]*><\/script>/i,
      `<script>${js}<\/script>`,
    );

    return rendered;
  }, [files, runStatus]);

  // Reset focused state whenever a new game loads
  useEffect(() => {
    setFocused(false);
  }, [previewHtml]);

  // ── Focus handling ────────────────────────────────────────────────────────
  // The iframe needs focus so its canvas receives keydown events.
  // We display a "Click to play" overlay that disappears on first click,
  // at which point we focus the iframe content window.
  const handleOverlayClick = useCallback(() => {
    setFocused(true);
    // Give the iframe focus so keyboard events go to the canvas inside it
    iframeRef.current?.contentWindow?.focus();
    iframeRef.current?.focus();
  }, []);

  // Also focus on any click directly on the iframe (after overlay dismissed)
  const handleIframeClick = useCallback(() => {
    iframeRef.current?.contentWindow?.focus();
    iframeRef.current?.focus();
  }, []);

  // Prevent Arrow/Space from scrolling the host page while the game is focused.
  // The iframe's own document handles these keys internally; the host page should
  // not receive them at all while the user interacts with the game.
  useEffect(() => {
    if (!focused) return;
    const prevent = (e: KeyboardEvent) => {
      const scrollKeys = ["Space", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"];
      if (scrollKeys.includes(e.code)) {
        // Only prevent if the iframe is the active element or has focus
        if (
          document.activeElement === iframeRef.current ||
          document.activeElement === document.body
        ) {
          e.preventDefault();
        }
      }
    };
    window.addEventListener("keydown", prevent, { capture: true });
    return () => window.removeEventListener("keydown", prevent, { capture: true });
  }, [focused]);

  // ── Render states ─────────────────────────────────────────────────────────

  if (runStatus === "idle") {
    return (
      <div className="flex-1 flex items-center justify-center text-zinc-600 text-sm">
        Submit a prompt to generate a game
      </div>
    );
  }

  if (runStatus === "running") {
    return (
      <div className="flex-1 flex items-center justify-center text-zinc-500 text-sm">
        <div className="flex items-center gap-2">
          <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
            />
          </svg>
          Generating game...
        </div>
      </div>
    );
  }

  if (runStatus === "error" || !previewHtml) {
    return (
      <div className="flex-1 flex items-center justify-center text-zinc-500 text-sm">
        {runStatus === "error"
          ? "Generation failed — check the activity log"
          : "Preview unavailable — missing index.html or src/main.ts"}
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center px-3 py-1.5 border-b border-zinc-800 bg-zinc-900/50">
        <span className="text-[10px] uppercase tracking-wider text-zinc-500">
          Preview
        </span>
        {focused && (
          <span className="ml-auto text-[10px] text-zinc-600">
            Click elsewhere to release keyboard
          </span>
        )}
      </div>

      {/* iframe + overlay wrapper */}
      <div className="relative flex-1 overflow-hidden">
        <iframe
          ref={iframeRef}
          title="Game Preview"
          // allow-scripts only — no allow-same-origin (security)
          // storage.ts handles sandboxed localStorage gracefully
          sandbox="allow-scripts"
          srcDoc={previewHtml}
          className="absolute inset-0 w-full h-full bg-black"
          tabIndex={0}
          onClick={handleIframeClick}
        />

        {/* "Click to play" overlay — dismisses on first click */}
        {!focused && (
          <div
            className="absolute inset-0 flex items-center justify-center cursor-pointer bg-black/60 backdrop-blur-[1px] select-none"
            onClick={handleOverlayClick}
            // Also handle keyboard activation (Enter/Space) for a11y
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                handleOverlayClick();
              }
            }}
            role="button"
            tabIndex={0}
            aria-label="Click to play"
          >
            <div className="flex flex-col items-center gap-2 text-zinc-300">
              {/* Play triangle */}
              <svg
                className="w-12 h-12 opacity-80"
                viewBox="0 0 48 48"
                fill="none"
                aria-hidden="true"
              >
                <circle cx="24" cy="24" r="22" stroke="currentColor" strokeWidth="2" />
                <polygon points="19,14 36,24 19,34" fill="currentColor" />
              </svg>
              <span className="text-sm font-medium tracking-wide">Click to play</span>
              <span className="text-xs text-zinc-500">Keyboard and touch controls active after click</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
