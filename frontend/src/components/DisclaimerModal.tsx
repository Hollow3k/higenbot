import { useState } from 'react';

interface DisclaimerModalProps {
  onConfirm: () => void;
  onCancel?: () => void;
}

export function DisclaimerModal({ onConfirm, onCancel }: DisclaimerModalProps) {
  const [showDetails, setShowDetails] = useState(false);

  const handleClose = () => {
    if (onConfirm) {
      onConfirm();
    } else if (onCancel) {
      onCancel();
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-md p-4 animate-in fade-in duration-200">
      <div className="w-full max-w-lg bg-zinc-900/95 border border-zinc-700/80 rounded-2xl p-6 shadow-2xl space-y-5 text-zinc-100 relative">
        <button
          onClick={handleClose}
          className="absolute top-4 right-4 text-zinc-400 hover:text-zinc-100 transition-colors p-1 rounded-lg hover:bg-zinc-800 cursor-pointer"
          aria-label="Close modal"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <div>
            <h2 className="text-lg font-semibold text-zinc-100 leading-tight">
              Service Availability Notice
            </h2>
            <p className="text-xs text-amber-400/90 font-medium uppercase tracking-wider mt-0.5">
              Rate Limit & Setup Disclaimer
            </p>
          </div>
        </div>

        <div className="space-y-3 text-sm text-zinc-300 leading-relaxed">
          <div className="rounded-xl border border-amber-500/20 bg-amber-500/10 p-3.5 text-amber-200/90">
            <p className="font-medium text-amber-300 mb-1 flex items-center gap-1.5">
              <span>⚠️</span> Free Model Rate Limits
            </p>
            <p className="text-xs sm:text-sm text-amber-200/80">
              Due to low rate limits of free models, the product might not be working currently.
            </p>
          </div>

          <p className="text-zinc-300">
            The <span className="text-zinc-100 font-semibold underline decoration-cyan-500/50 underline-offset-2">best way to run it</span> is setting it up locally with your own API keys.
          </p>

          {showDetails && (
            <div className="mt-3 p-3 bg-zinc-950/80 border border-zinc-800 rounded-xl text-xs space-y-2 text-zinc-400 font-mono">
              <p className="text-zinc-200 font-sans font-medium">Quick Local Setup Guide:</p>
              <p>1. Clone repository: <code className="text-cyan-300">git clone https://github.com/Hollow3k/higenbot.git</code></p>
              <p>2. Configure API keys in <code className="text-cyan-300">backend/.env</code></p>
              <p>3. Start backend: <code className="text-cyan-300">cd backend && uvicorn main:app --reload</code></p>
              <p>4. Start frontend: <code className="text-cyan-300">cd frontend && npm run dev</code></p>
            </div>
          )}
        </div>

        <div className="flex items-center gap-3 pt-2">
          <button
            onClick={handleClose}
            className="flex-1 rounded-xl bg-white text-zinc-950 px-4 py-2.5 text-sm font-semibold hover:bg-zinc-200 transition-colors shadow-sm cursor-pointer"
          >
            I Understand
          </button>
          <button
            onClick={() => setShowDetails(!showDetails)}
            className="rounded-xl border border-zinc-700 text-zinc-300 px-4 py-2.5 text-sm font-medium hover:bg-zinc-800 hover:text-zinc-100 transition-colors cursor-pointer"
          >
            {showDetails ? "Hide Setup Steps" : "How to Run Locally"}
          </button>
        </div>
      </div>
    </div>
  );
}
