import { type FormEvent, useState } from "react";
import { useStudioStore } from "../store/useStudioStore";
import { useStudioWebSocket } from "../hooks/useStudioWebSocket";
import { apiFetch } from "../lib/api";

export function PromptInput() {
  const { setPrompt, setRunId, startConnecting, runStatus } = useStudioStore();
  const { connect } = useStudioWebSocket();
  const [input, setInput] = useState("");

  const isBusy = runStatus === "connecting" || runStatus === "running";

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || isBusy) return;

    setPrompt(trimmed);
    // Show progress while the project API wakes up and creates the run.
    startConnecting();

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

  const buttonLabel = () => {
    if (runStatus === "connecting") return "Connecting…";
    if (runStatus === "running") return "Running…";
    return "Generate";
  };

  return (
    <form onSubmit={handleSubmit} className="flex items-center gap-2 px-4 py-3">
      <input
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="Describe a game..."
        disabled={isBusy}
        className="flex-1 bg-zinc-900 border border-zinc-700 rounded-lg px-4 py-2.5 text-sm text-zinc-100 placeholder-zinc-500 outline-none transition-colors focus:border-zinc-500 disabled:opacity-50"
      />
      <button
        type="submit"
        disabled={isBusy || !input.trim()}
        className="shrink-0 flex items-center gap-2 rounded-lg bg-white text-zinc-900 px-4 py-2.5 text-sm font-medium transition-opacity hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {isBusy && (
          <span className="w-3.5 h-3.5 border-2 border-zinc-400 border-t-zinc-800 rounded-full animate-spin" />
        )}
        {buttonLabel()}
      </button>
    </form>
  );
}
