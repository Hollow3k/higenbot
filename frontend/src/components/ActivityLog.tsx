import { useEffect, useRef } from "react";
import { useStudioStore } from "../store/useStudioStore";

export function ActivityLog() {
  const log = useStudioStore((s) => s.log);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [log.length]);

  if (log.length === 0) return null;

  return (
    <div className="flex flex-col gap-0.5 overflow-y-auto px-4 py-2 font-mono text-xs max-h-48">
      {log.map((entry) => (
        <div key={entry.id} className="flex items-start gap-2 py-0.5">
          <span className="shrink-0 text-zinc-600 select-none">
            {formatTime(entry.timestamp)}
          </span>
          <span
            className={
              entry.type === "error"
                ? "text-red-400"
                : entry.type === "file_written"
                  ? "text-sky-400"
                  : entry.type === "agent_start"
                    ? "text-zinc-400"
                    : entry.type === "info"
                      ? "text-emerald-400"
                      : "text-zinc-300"
            }
          >
            {entry.type === "file_written" && (
              <span className="text-zinc-500 mr-1">wrote</span>
            )}
            {entry.message}
          </span>
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString("en-US", {
      hour12: false,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return "";
  }
}
