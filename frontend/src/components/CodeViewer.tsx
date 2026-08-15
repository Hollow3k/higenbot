import { useStudioStore } from "../store/useStudioStore";

export function CodeViewer() {
  const files = useStudioStore((s) => s.files);
  const selectedFile = useStudioStore((s) => s.selectedFile);

  const content = selectedFile ? files[selectedFile] : null;

  if (!selectedFile || !content) {
    return (
      <div className="flex-1 flex items-center justify-center text-zinc-600 text-sm">
        Select a file to view
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="flex items-center px-4 py-2 border-b border-zinc-800 bg-zinc-900/50">
        <span className="text-xs text-zinc-400 font-mono">{selectedFile}</span>
      </div>
      <pre className="flex-1 overflow-auto p-4 text-xs leading-relaxed text-zinc-300 font-mono bg-zinc-950">
        <code>{content}</code>
      </pre>
    </div>
  );
}
