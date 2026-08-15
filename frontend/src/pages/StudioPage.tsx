import { useEffect } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { useStudioStore } from "../store/useStudioStore";
import { useStudioWebSocket } from "../hooks/useStudioWebSocket";
import { AgentStatusBar } from "../components/AgentStatusBar";
import { ActivityLog } from "../components/ActivityLog";
import { FileExplorer } from "../components/FileExplorer";
import { CodeViewer } from "../components/CodeViewer";
import { PreviewPane } from "../components/PreviewPane";
import { PromptInput } from "../components/PromptInput";
import { ChatPane } from "../components/ChatPane";

export default function StudioPage() {
  const { runId } = useParams();
  const location = useLocation();
  const { connect } = useStudioWebSocket();
  const runStatus = useStudioStore((s) => s.runStatus);
  const setPrompt = useStudioStore((s) => s.setPrompt);
  const hasFiles = useStudioStore(
    (s) => Object.keys(s.files).length > 0
  );

  // Auto-start if navigated from projects page with a prompt in state
  useEffect(() => {
    const state = location.state as { prompt?: string } | null;
    if (state?.prompt && runId && runStatus === "idle") {
      setPrompt(state.prompt);
      connect(runId, state.prompt);
    }
  }, [runId, location.state, runStatus, setPrompt, connect]);

  return (
    <div className="flex flex-col h-screen bg-zinc-950 text-zinc-100 font-inter">
      {/* Top bar */}
      <header className="flex items-center justify-between border-b border-zinc-800 px-4 py-2">
        <Link to="/projects" className="font-bm-hanna text-xl text-zinc-100 hover:text-zinc-300 transition-colors">
          Higenbot
        </Link>
        <div className="flex items-center gap-3">
          {runStatus !== "idle" && (
            <span className="text-[10px] uppercase tracking-wider text-zinc-500">
              studio
            </span>
          )}
          <Link
            to="/projects"
            className="text-xs text-zinc-500 hover:text-zinc-200 transition-colors"
          >
            Projects
          </Link>
        </div>
      </header>

      {/* Agent progress */}
      <AgentStatusBar />

      {/* Main content area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {runStatus === "idle" ? (
          /* Idle state: centered prompt */
          <div className="flex-1 flex flex-col items-center justify-center px-4">
            <div className="w-full max-w-xl space-y-4">
              <div className="text-center space-y-2 mb-8">
                <h2 className="text-2xl font-semibold text-zinc-100">
                  What game should we build?
                </h2>
                <p className="text-sm text-zinc-500">
                  Describe a game and our AI agents will design and code it for you.
                </p>
              </div>
              <PromptInput />
            </div>
          </div>
        ) : (
          /* Active state: split layout */
          <>
            {/* Prompt bar stays at top during run */}
            <PromptInput />

            {/* Activity log */}
            <div className="border-t border-zinc-800">
              <ActivityLog />
            </div>

            {/* Code + Preview split */}
            {hasFiles && (
              <div className="flex-1 flex border-t border-zinc-800 overflow-hidden">
                {/* Left: files + code */}
                <div className="flex flex-1 overflow-hidden">
                  <FileExplorer />
                  <CodeViewer />
                </div>

                {/* Right: preview + chat */}
                <div className="flex flex-col w-1/2 border-l border-zinc-800">
                  <PreviewPane />
                  {runStatus === "done" && (
                    <div className="h-64 border-t border-zinc-800">
                      <ChatPane />
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Preview when no files yet */}
            {!hasFiles && (
              <div className="flex-1 border-t border-zinc-800">
                <PreviewPane />
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
