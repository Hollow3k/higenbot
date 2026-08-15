/**
 * WebSocket message types for the agent pipeline stream.
 *
 * These mirror the events sent by the backend at /ws/run/{run_id}.
 * Client sends: { prompt: "..." } to start the run.
 * Server streams these typed events back.
 */

export enum WsMessageType {
  AgentStart = "agent_start",
  AgentDone = "agent_done",
  FileWritten = "file_written",
  RunComplete = "run_complete",
  RunError = "run_error",
}

export type AgentName =
  | "creative_director"
  | "game_designer"
  | "gameplay_programmer"
  | "qa_tester";

// ── Event payloads ──────────────────────────────────────────────────────────

export interface AgentStartEvent {
  type: WsMessageType.AgentStart;
  agent: AgentName;
  timestamp: string;
}

export interface AgentDoneEvent {
  type: WsMessageType.AgentDone;
  agent: AgentName;
  output: Record<string, unknown>;
  timestamp: string;
}

export interface FileWrittenEvent {
  type: WsMessageType.FileWritten;
  path: string;
  content: string;
  timestamp: string;
}

export interface RunCompleteEvent {
  type: WsMessageType.RunComplete;
  qa_passed: boolean;
  timestamp: string;
}

export interface RunErrorEvent {
  type: WsMessageType.RunError;
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
