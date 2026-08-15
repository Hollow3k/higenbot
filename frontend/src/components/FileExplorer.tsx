import { useStudioStore } from "../store/useStudioStore";
import { downloadFile, downloadAllAsZip } from "../lib/download";

export function FileExplorer() {
  const files = useStudioStore((s) => s.files);
  const selectedFile = useStudioStore((s) => s.selectedFile);
  const selectFile = useStudioStore((s) => s.selectFile);

  const paths = Object.keys(files).sort();

  if (paths.length === 0) return null;

  return (
    <div className="flex flex-col border-r border-zinc-800 w-52 shrink-0 overflow-y-auto">
      {/* Header with Download All */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-zinc-800">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
          Files
        </span>
        <button
          onClick={() => downloadAllAsZip(files)}
          className="flex items-center gap-1 text-[10px] text-zinc-500 hover:text-zinc-200 transition-colors"
          title="Download all as .zip"
        >
          <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          .zip
        </button>
      </div>

      {/* File list */}
      {paths.map((path) => (
        <div
          key={path}
          className={`group flex items-center justify-between pr-2 transition-colors ${
            selectedFile === path
              ? "bg-zinc-800"
              : "hover:bg-zinc-800/50"
          }`}
        >
          <button
            onClick={() => selectFile(path)}
            className={`flex-1 text-left px-3 py-1.5 text-xs truncate ${
              selectedFile === path
                ? "text-white"
                : "text-zinc-400 hover:text-zinc-200"
            }`}
          >
            {path}
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              downloadFile(path, files[path]);
            }}
            className="shrink-0 opacity-0 group-hover:opacity-100 p-1 text-zinc-500 hover:text-zinc-200 transition-opacity"
            title={`Download ${path}`}
          >
            <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
          </button>
        </div>
      ))}
    </div>
  );
}
