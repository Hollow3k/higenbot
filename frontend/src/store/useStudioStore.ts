import { create } from "zustand";
import type { AgentName, WsEvent } from "../types/ws";
import { saveLocalProject } from "../lib/projectStorage";

export type RunStatus = "idle" | "running" | "done" | "error";

export interface LogEntry {
  id: string;
  type: "agent_start" | "agent_done" | "file_written" | "info" | "error";
  message: string;
  timestamp: string;
}

interface StudioState {
  // Run state
  runStatus: RunStatus;
  currentAgent: AgentName | null;
  prompt: string;
  runId: string | null;

  // Generated output
  files: Record<string, string>;
  selectedFile: string | null;

  // Activity log
  log: LogEntry[];

  // QA
  qaPassed: boolean | null;
  errorMessage: string | null;

  // Actions
  setPrompt: (prompt: string) => void;
  setRunId: (runId: string) => void;
  startRun: () => void;
  handleEvent: (event: WsEvent) => void;
  selectFile: (path: string | null) => void;
  reset: () => void;
}

let logId = 0;
const nextId = () => String(++logId);

export const useStudioStore = create<StudioState>((set, get) => ({
  runStatus: "idle",
  currentAgent: null,
  prompt: "",
  runId: null,
  files: {},
  selectedFile: null,
  log: [],
  qaPassed: null,
  errorMessage: null,

  setPrompt: (prompt) => set({ prompt }),

  setRunId: (runId) => set({ runId }),

  startRun: () =>
    set({
      runStatus: "running",
      currentAgent: null,
      files: {},
      selectedFile: null,
      log: [],
      qaPassed: null,
      errorMessage: null,
    }),

  handleEvent: (event) =>
    set((state) => {
      switch (event.type) {
        case "agent_start":
          return {
            currentAgent: event.agent,
            log: [
              ...state.log,
              {
                id: nextId(),
                type: "agent_start",
                message: `${formatAgent(event.agent)} started`,
                timestamp: event.timestamp,
              },
            ],
          };

        case "agent_done":
          return {
            currentAgent: null,
            log: [
              ...state.log,
              {
                id: nextId(),
                type: "agent_done",
                message: `${formatAgent(event.agent)} finished`,
                timestamp: event.timestamp,
              },
            ],
          };

        case "file_written":
          return {
            files: { ...state.files, [event.path]: event.content },
            selectedFile: state.selectedFile ?? event.path,
            log: [
              ...state.log,
              {
                id: nextId(),
                type: "file_written",
                message: event.path,
                timestamp: event.timestamp,
              },
            ],
          };

        case "run_complete": {
          // Save to localStorage
          const { runId, prompt, files } = get();
          if (runId && prompt) {
            saveLocalProject({
              id: runId,
              prompt,
              status: event.qa_passed ? "done" : "error",
              created_at: new Date().toISOString(),
              files: { ...files, ...state.files },
            });
          }

          return {
            runStatus: "done",
            currentAgent: null,
            qaPassed: event.qa_passed,
            log: [
              ...state.log,
              {
                id: nextId(),
                type: "info",
                message: event.qa_passed
                  ? "Build complete — QA passed"
                  : "Build complete — QA failed",
                timestamp: event.timestamp,
              },
            ],
          };
        }

        case "run_error": {
          // Save error to localStorage
          const { runId: rId, prompt: p } = get();
          if (rId && p) {
            saveLocalProject({
              id: rId,
              prompt: p,
              status: "error",
              created_at: new Date().toISOString(),
              files: {},
            });
          }

          return {
            runStatus: "error",
            currentAgent: null,
            errorMessage: event.message,
            log: [
              ...state.log,
              {
                id: nextId(),
                type: "error",
                message: event.message,
                timestamp: event.timestamp,
              },
            ],
          };
        }

        default:
          return {};
      }
    }),

  selectFile: (path) => set({ selectedFile: path }),

  reset: () =>
    set({
      runStatus: "idle",
      currentAgent: null,
      prompt: "",
      runId: null,
      files: {},
      selectedFile: null,
      log: [],
      qaPassed: null,
      errorMessage: null,
    }),
}));

function formatAgent(name: AgentName): string {
  const map: Record<AgentName, string> = {
    creative_director: "Creative Director",
    game_designer: "Game Designer",
    gameplay_programmer: "Programmer",
    qa_tester: "QA Tester",
  };
  return map[name] ?? name;
}
