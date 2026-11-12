interface DisclaimerModalProps {
  onConfirm: () => void;
  onCancel?: () => void;
}

export function DisclaimerModal({ onConfirm, onCancel }: DisclaimerModalProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-md p-4 animate-in fade-in duration-200">
      <div className="w-full max-w-md bg-zinc-900/95 border border-zinc-700/80 rounded-2xl p-6 shadow-2xl space-y-5 text-zinc-100 relative">
        <button
          onClick={onCancel ?? onConfirm}
          className="absolute top-4 right-4 text-zinc-400 hover:text-zinc-100 transition-colors p-1 rounded-lg hover:bg-zinc-800 cursor-pointer"
          aria-label="Close"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        <div className="space-y-2 pr-8">
          <h2 className="text-lg font-semibold text-zinc-100 leading-tight">
            Heads up
          </h2>
          <p className="text-sm text-zinc-300 leading-relaxed">
            Higenbot runs on free LLM APIs, so generation can be slow and the
            output may feel rough around the edges.
          </p>
        </div>

        <button
          onClick={onConfirm}
          className="w-full rounded-xl bg-white text-zinc-950 px-4 py-2.5 text-sm font-semibold hover:bg-zinc-200 transition-colors shadow-sm cursor-pointer"
        >
          Got it
        </button>
      </div>
    </div>
  );
}
