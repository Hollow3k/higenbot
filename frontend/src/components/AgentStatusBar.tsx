import { useStudioStore } from "../store/useStudioStore";
import type { AgentName } from "../types/ws";

const AGENTS: { name: AgentName; label: string }[] = [
  { name: "creative_director", label: "Creative Director" },
  { name: "game_designer", label: "Game Designer" },
  { name: "gameplay_programmer", label: "Programmer" },
  { name: "qa_tester", label: "QA Tester" },
];

export function AgentStatusBar() {
  const currentAgent = useStudioStore((s) => s.currentAgent);
  const runStatus = useStudioStore((s) => s.runStatus);

  if (runStatus === "idle") return null;

  return (
    <div className="flex items-center gap-1 px-4 py-3">
      {AGENTS.map((agent, i) => {
        const isActive = currentAgent === agent.name;
        const isDone =
          currentAgent === null
            ? runStatus === "done"
            : AGENTS.findIndex((a) => a.name === currentAgent) > i;

        return (
          <div key={agent.name} className="flex items-center gap-1">
            {i > 0 && (
              <div
                className={`h-px w-4 transition-colors ${
                  isDone ? "bg-emerald-400" : "bg-zinc-700"
                }`}
              />
            )}
            <div
              className={`flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-medium transition-all ${
                isActive
                  ? "bg-zinc-800 text-white ring-1 ring-zinc-600"
                  : isDone
                    ? "bg-zinc-800/50 text-emerald-400"
                    : "bg-zinc-900 text-zinc-500"
              }`}
            >
              {isActive && (
                <span className="relative flex h-2 w-2">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-400 opacity-75" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-amber-400" />
                </span>
              )}
              {isDone && !isActive && (
                <svg
                  className="h-3 w-3 text-emerald-400"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2.5}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M5 13l4 4L19 7"
                  />
                </svg>
              )}
              {agent.label}
            </div>
          </div>
        );
      })}
    </div>
  );
}
