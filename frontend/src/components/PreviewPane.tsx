import { useMemo } from "react";
import { useStudioStore } from "../store/useStudioStore";
import ts from "typescript";

export function PreviewPane() {
  const files = useStudioStore((s) => s.files);
  const runStatus = useStudioStore((s) => s.runStatus);

  const previewHtml = useMemo(() => {
    if (runStatus !== "done") return null;

    const html = files["index.html"];
    const tsSource = files["src/main.ts"];

    if (!html || !tsSource) return null;

    // Compile TypeScript to JavaScript using the real TS compiler
    const result = ts.transpileModule(tsSource, {
      compilerOptions: {
        target: ts.ScriptTarget.ES2020,
        module: ts.ModuleKind.None,
        strict: false,
        esModuleInterop: true,
        skipLibCheck: true,
      },
    });

    const js = result.outputText;

    // Replace the external script tag with inline JS
    const rendered = html.replace(
      /<script[^>]*src=['"][^'"]*['"][^>]*><\/script>/i,
      `<script>${js}<\/script>`
    );

    return rendered;
  }, [files, runStatus]);

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
      <div className="flex items-center px-3 py-1.5 border-b border-zinc-800 bg-zinc-900/50">
        <span className="text-[10px] uppercase tracking-wider text-zinc-500">
          Preview
        </span>
      </div>
      <iframe
        title="Game Preview"
        sandbox="allow-scripts"
        srcDoc={previewHtml}
        className="flex-1 w-full bg-black"
      />
    </div>
  );
}
