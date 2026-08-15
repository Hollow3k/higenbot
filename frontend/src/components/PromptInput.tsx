import { type FormEvent, useState } from "react";
import { useStudioStore } from "../store/useStudioStore";
import { useStudioWebSocket } from "../hooks/useStudioWebSocket";
import { apiFetch } from "../lib/api";

export function PromptInput() {
  const { setPrompt, setRunId, runStatus } = useStudioStore();
  const { connect } = useStudioWebSocket();
  const [input, setInput] = useState("");

  const isRunning = runStatus === "running";

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || isRunning) return;

    setPrompt(trimmed);

    // Try to create a project via API (will fail gracefully if not authed/no DB)
    let runId = `run-${Date.now()}`;
    try {
      const res = await apiFetch("/api/projects/", {
        method: "POST",
        body: JSON.stringify({ prompt: trimmed }),
      });
      if (res.ok) {
        const data = await res.json();
        runId = data.run_id;
      }
    } catch {
      // Fall through with generated runId — works without DB
    }

    setRunId(runId);
    connect(runId, trimmed);
  };

  return (
    <form onSubmit={handleSubmit} className="flex items-center gap-2 px-4 py-3">
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="Describe a game..."
        disabled={isRunning}
        className="flex-1 bg-zinc-900 border border-zinc-700 rounded-lg px-4 py-2.5 text-sm text-zinc-100 placeholder-zinc-500 outline-none transition-colors focus:border-zinc-500 disabled:opacity-50"
      />
      <button
        type="submit"
        disabled={isRunning || !input.trim()}
        className="shrink-0 rounded-lg bg-white text-zinc-900 px-4 py-2.5 text-sm font-medium transition-opacity hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {isRunning ? "Running..." : "Generate"}
      </button>
    </form>
  );
}
