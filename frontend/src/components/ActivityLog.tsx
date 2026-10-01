import { useEffect, useRef } from "react";
import { useStudioStore } from "../store/useStudioStore";
import type { LogEntry } from "../store/useStudioStore";

export function ActivityLog() {
  const log      = useStudioStore((s) => s.log);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [log.length]);

  if (log.length === 0) return null;

  return (
    <div className="flex flex-col gap-0.5 overflow-y-auto px-4 py-2 font-mono text-xs max-h-48">
      {log.map((entry) => (
        <LogLine key={entry.id} entry={entry} />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}

function LogLine({ entry }: { entry: LogEntry }) {
  const color = entryColor(entry);
  const prefix = entryPrefix(entry);

  return (
    <div className="flex items-start gap-2 py-0.5">
      <span className="shrink-0 text-zinc-600 select-none">
        {formatTime(entry.timestamp)}
      </span>
      <span className={color}>
        {prefix && <span className="text-zinc-500 mr-1">{prefix}</span>}
        {entry.message}
      </span>
    </div>
  );
}

function entryColor(entry: LogEntry): string {
  switch (entry.type) {
    case "error":       return "text-red-400";
    case "file_written": return "text-sky-400";
    case "agent_start": return "text-zinc-400";
    case "info":
      // QA pass/fail distinguished by message content
      if (entry.message.startsWith("✓")) return "text-emerald-400";
      if (entry.message.startsWith("✗")) return "text-yellow-400";
      return "text-emerald-400";
    default:            return "text-zinc-300";
  }
}

function entryPrefix(entry: LogEntry): string {
  switch (entry.type) {
    case "file_written": return "wrote";
    default:             return "";
  }
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString("en-US", {
      hour12: false,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return "";
  }
}
