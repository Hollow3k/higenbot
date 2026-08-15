import { useCallback, useRef } from "react";
import { useStudioStore } from "../store/useStudioStore";
import type { WsEvent } from "../types/ws";

const WS_BASE = import.meta.env.VITE_WS_URL ?? "ws://127.0.0.1:8000";

export function useStudioWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const { handleEvent, startRun } = useStudioStore();

  const connect = useCallback(
    (runId: string, prompt: string) => {
      if (wsRef.current) {
        wsRef.current.close();
      }

      startRun();

      const ws = new WebSocket(`${WS_BASE}/ws/run/${runId}`);
      wsRef.current = ws;

      ws.onopen = () => {
        ws.send(JSON.stringify({ prompt }));
      };

      ws.onmessage = (e) => {
        try {
          const event: WsEvent = JSON.parse(e.data);
          handleEvent(event);
        } catch {
          // ignore malformed messages
        }
      };

      ws.onerror = () => {
        useStudioStore.getState().handleEvent({
          type: "run_error" as const,
          message: "WebSocket connection error",
          timestamp: new Date().toISOString(),
        });
      };

      ws.onclose = () => {
        wsRef.current = null;
      };
    },
    [handleEvent, startRun]
  );

  const disconnect = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
  }, []);

  return { connect, disconnect };
}
