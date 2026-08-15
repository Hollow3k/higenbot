import { useState, useRef, useEffect, type FormEvent } from "react";
import { useStudioStore } from "../store/useStudioStore";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
}

const WS_BASE = import.meta.env.VITE_WS_URL ?? "ws://127.0.0.1:8000";

export function ChatPane() {
  const files = useStudioStore((s) => s.files);
  const runId = useStudioStore((s) => s.runId);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, loading]);

  // Connect to edit WebSocket
  const ensureConnection = (): WebSocket | null => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      return wsRef.current;
    }

    const id = runId ?? `edit-${Date.now()}`;
    const ws = new WebSocket(`${WS_BASE}/ws/edit/${id}`);
    wsRef.current = ws;

    ws.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data);

        if (event.type === "file_written") {
          // Update files in store
          const currentFiles = useStudioStore.getState().files;
          useStudioStore.setState({
            files: { ...currentFiles, [event.path]: event.content },
          });
        }

        if (event.type === "edit_done") {
          setMessages((prev) => [
            ...prev,
            {
              id: String(Date.now()),
              role: "assistant",
              content: "Done — files updated. Check the preview.",
            },
          ]);
          setLoading(false);
        }

        if (event.type === "edit_error") {
          setMessages((prev) => [
            ...prev,
            {
              id: String(Date.now()),
              role: "assistant",
              content: `Error: ${event.message}`,
            },
          ]);
          setLoading(false);
        }
      } catch {
        // ignore
      }
    };

    ws.onerror = () => {
      setLoading(false);
      setMessages((prev) => [
        ...prev,
        {
          id: String(Date.now()),
          role: "assistant",
          content: "Connection error. Try again.",
        },
      ]);
    };

    ws.onclose = () => {
      wsRef.current = null;
    };

    return ws;
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || loading) return;

    setMessages((prev) => [
      ...prev,
      { id: String(Date.now()), role: "user", content: trimmed },
    ]);
    setInput("");
    setLoading(true);

    const ws = ensureConnection();
    if (!ws) {
      setLoading(false);
      return;
    }

    // Wait for connection to open if needed
    const sendMessage = () => {
      ws.send(JSON.stringify({ message: trimmed, files }));
    };

    if (ws.readyState === WebSocket.OPEN) {
      sendMessage();
    } else {
      ws.addEventListener("open", sendMessage, { once: true });
    }
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      wsRef.current?.close();
    };
  }, []);

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
        {messages.length === 0 && (
          <p className="text-xs text-zinc-600 text-center pt-4">
            Ask for changes to your game
          </p>
        )}
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[85%] rounded-lg px-3 py-2 text-xs ${
                msg.role === "user"
                  ? "bg-zinc-800 text-zinc-200"
                  : "bg-zinc-900 text-zinc-400 border border-zinc-800"
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-500">
              <span className="animate-pulse">Editing...</span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form
        onSubmit={handleSubmit}
        className="flex items-center gap-2 px-3 py-2 border-t border-zinc-800"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Make the player faster..."
          disabled={loading}
          className="flex-1 bg-zinc-900 border border-zinc-800 rounded-md px-3 py-2 text-xs text-zinc-100 placeholder-zinc-600 outline-none focus:border-zinc-600 disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="shrink-0 rounded-md bg-zinc-800 text-zinc-300 px-3 py-2 text-xs hover:bg-zinc-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Send
        </button>
      </form>
    </div>
  );
}
