interface DisclaimerModalProps {
  onConfirm: () => void;
  onCancel: () => void;
}

export function DisclaimerModal({ onConfirm, onCancel }: DisclaimerModalProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="w-full max-w-md mx-4 bg-zinc-900 border border-zinc-700 rounded-2xl p-6 shadow-2xl space-y-4">
        <div className="space-y-1">
          <h2 className="text-base font-semibold text-zinc-100">
            Before you dive in
          </h2>
          <p className="text-xs text-zinc-500 uppercase tracking-wider">
            A quick note
          </p>
        </div>

        <p className="text-sm text-zinc-300 leading-relaxed">
          Higenbot currently uses <span className="text-zinc-100 font-medium">free / low-cost AI models</span> to keep the demo accessible. Generated games may have rough edges, limited interactivity, or occasional errors.
        </p>

        <p className="text-sm text-zinc-400 leading-relaxed">
          For significantly better results, run the project locally with a higher-tier model like <span className="text-zinc-200">Claude Sonnet</span> or <span className="text-zinc-200">GPT-4o</span>.
        </p>

        <div className="flex items-center gap-3 pt-2">
          <button
            onClick={onConfirm}
            className="flex-1 rounded-lg bg-white text-zinc-900 px-4 py-2.5 text-sm font-medium hover:opacity-90 transition-opacity"
          >
            Got it, let's build
          </button>
          <button
            onClick={onCancel}
            className="rounded-lg border border-zinc-700 text-zinc-400 px-4 py-2.5 text-sm hover:text-zinc-200 hover:border-zinc-500 transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
