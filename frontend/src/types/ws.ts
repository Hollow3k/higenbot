/**
 * WebSocket message types for the agent pipeline stream.
 *
 * These mirror the events sent by the backend at /ws/run/{run_id}.
 * Client sends: { prompt: "..." } to start the run.
 * Server streams these typed events back.
 */

export const WsMessageType = {
  AgentStart: "agent_start",
  AgentDone: "agent_done",
  FileWritten: "file_written",
  RunComplete: "run_complete",
  RunError: "run_error",
} as const;

export type WsMessageType = (typeof WsMessageType)[keyof typeof WsMessageType];

export type AgentName =
  | "creative_director"
  | "game_designer"
  | "gameplay_programmer"
  | "qa_tester";

// ── Event payloads ──────────────────────────────────────────────────────────

export interface AgentStartEvent {
  type: typeof WsMessageType.AgentStart;
  agent: AgentName;
  timestamp: string;
}

export interface AgentDoneEvent {
  type: typeof WsMessageType.AgentDone;
  agent: AgentName;
  output: Record<string, unknown>;
  timestamp: string;
}

export interface FileWrittenEvent {
  type: typeof WsMessageType.FileWritten;
  path: string;
  content: string;
  timestamp: string;
}

export interface RunCompleteEvent {
  type: typeof WsMessageType.RunComplete;
  qa_passed: boolean;
  timestamp: string;
}

export interface RunErrorEvent {
  type: typeof WsMessageType.RunError;
  message: string;
  timestamp: string;
}

// ── Union type for all possible server messages ─────────────────────────────

export type WsEvent =
  | AgentStartEvent
  | AgentDoneEvent
  | FileWrittenEvent
  | RunCompleteEvent
  | RunErrorEvent;

// ── Client → Server message ─────────────────────────────────────────────────

export interface WsRunRequest {
  prompt: string;
}
