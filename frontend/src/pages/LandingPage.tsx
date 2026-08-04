import { useState, type FormEvent } from 'react'

import { useAuth } from '../providers/AuthProvider'

type AuthMode = 'sign-in' | 'sign-up'

function LandingPage() {
  const { signUp, signInWithPassword, signInWithGoogle } = useAuth()
  const [authOpen, setAuthOpen] = useState(false)
  const [authMode, setAuthMode] = useState<AuthMode>('sign-in')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const openAuth = (mode: AuthMode) => {
    setAuthMode(mode)
    setMessage('')
    setError('')
    setAuthOpen(true)
  }

  const closeAuth = () => {
    setAuthOpen(false)
    setError('')
    setMessage('')
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setSubmitting(true)
    setError('')
    setMessage('')

    try {
      if (authMode === 'sign-up') {
        const { error: signUpError } = await signUp({ email, password })
        if (signUpError) {
          throw signUpError
        }

        setMessage('Account created. Check your inbox if email confirmation is enabled.')
      } else {
        const { error: signInError } = await signInWithPassword({ email, password })
        if (signInError) {
          throw signInError
        }

        setMessage('Signed in successfully.')
        setAuthOpen(false)
      }
    } catch (authError) {
      setError(authError instanceof Error ? authError.message : 'Authentication failed')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="min-h-screen bg-[#01061c] text-slate-100">
      <section className="relative h-screen w-full overflow-hidden">
        <img
          className="absolute inset-0 h-full w-full object-cover object-center"
          src="/higen_landing.png"
          alt="Higen landing page background"
        />
        <div className="absolute inset-0 bg-linear-to-b from-sky-100/20 via-sky-100/10 to-slate-950/10" />

        <div className="relative z-10 h-full px-4 pb-16 pt-3 sm:px-6 lg:px-10 lg:pt-4">
          <header className="absolute left-0 right-0 top-18 mx-auto w-full max-w-5xl px-4 sm:px-6 lg:px-10">
            <nav
              className="grid grid-cols-[auto_auto_auto] justify-center items-baseline gap-x-32 text-[11px] uppercase tracking-[0.18em] text-slate-800/80 sm:text-xs"
              aria-label="Primary"
            >
              <div className="flex items-center justify-start gap-32 pt-1 font-inter">
                <a href="#about" className="transition hover:text-slate-950">
                  About
                </a>
                <a href="#features" className="transition hover:text-slate-950">
                  Features
                </a>
              </div>

              <a
                href="/"
                className="font-bm-hanna text-center text-[3.35rem] normal-case tracking-[0.01em] text-slate-950 sm:text-[3.7rem]"
              >
                Higenbot
              </a>

              <div className="flex items-center justify-end gap-32 pt-1 font-inter">
                <a href="#pricing" className="transition hover:text-slate-950">
                  Pricing
                </a>
                <button
                  type="button"
                  onClick={() => openAuth('sign-in')}
                  className="transition hover:text-slate-950"
                >
                  Login
                </button>
              </div>
            </nav>
          </header>

          <section className="flex min-h-[calc(100vh-5rem)] items-center justify-center px-2 pb-10 sm:px-6">
            <div className="max-w-screen text-center">
              <p className="font-baskerville text-[clamp(2rem,4.8vw,4.2rem)] font-bold italic leading-[1.08] tracking-[-0.03em] text-slate-950 drop-shadow-[0_1px_0_rgba(255,255,255,0.32)] sm:text-[clamp(2.3rem,4.2vw,4.6rem)]">
                <span className="block">Every world begins as</span>
                <span className="block">imagination, but only creation</span>
                <span className="block">gives it a chance to exist.</span>
              </p>
            </div>
          </section>
        </div>
      </section>

      <section id="about" className="mx-auto w-full max-w-5xl border-t border-white/10 px-4 pb-12 pt-10 text-slate-100 sm:px-6">
        <div className="max-w-2xl">
          <p className="text-xs uppercase tracking-[0.28em] text-cyan-200/60 font-inter">
            What HigenBot is
          </p>
          <h2 className="mt-3 font-baskerville text-3xl font-bold italic text-slate-50 sm:text-4xl">
            A prompt-to-game studio that works like a small production team.
          </h2>
          <p className="mt-4 text-sm leading-7 text-slate-300 sm:text-base">
            The product turns a natural-language game idea into a playable Phaser + TypeScript project. The plan describes a Creative Director, Game Designer, Gameplay Programmer, and QA Tester working in sequence to turn one prompt into real files and a browser preview.
          </p>
        </div>

        <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4" id="features">
          <article className="rounded-2xl border border-white/10 bg-white/5 p-5 shadow-sm">
            <p className="text-xs uppercase tracking-[0.24em] text-cyan-200/60 font-inter">01</p>
            <h3 className="mt-3 text-sm font-semibold text-slate-50">Prompt in</h3>
            <p className="mt-2 text-sm leading-7 text-slate-300">The user describes the game in plain language.</p>
          </article>
          <article className="rounded-2xl border border-white/10 bg-white/5 p-5 shadow-sm">
            <p className="text-xs uppercase tracking-[0.24em] text-cyan-200/60 font-inter">02</p>
            <h3 className="mt-3 text-sm font-semibold text-slate-50">Plan it</h3>
            <p className="mt-2 text-sm leading-7 text-slate-300">Agents shape the vision, mechanics, and build structure.</p>
          </article>
          <article className="rounded-2xl border border-white/10 bg-white/5 p-5 shadow-sm">
            <p className="text-xs uppercase tracking-[0.24em] text-cyan-200/60 font-inter">03</p>
            <h3 className="mt-3 text-sm font-semibold text-slate-50">Generate files</h3>
            <p className="mt-2 text-sm leading-7 text-slate-300">The programmer writes actual TypeScript and Phaser files.</p>
          </article>
          <article className="rounded-2xl border border-white/10 bg-white/5 p-5 shadow-sm">
            <p className="text-xs uppercase tracking-[0.24em] text-cyan-200/60 font-inter">04</p>
            <h3 className="mt-3 text-sm font-semibold text-slate-50">Preview it</h3>
            <p className="mt-2 text-sm leading-7 text-slate-300">A browser-based preview keeps the result immediate.</p>
          </article>
        </div>

        <div id="pricing" className="mt-8 grid gap-4 lg:grid-cols-[1fr_1fr]">
          <article className="rounded-3xl border border-white/10 bg-white/5 p-6 shadow-sm">
            <p className="text-xs uppercase tracking-[0.24em] text-cyan-200/60 font-inter">Why it matters</p>
            <p className="mt-3 text-sm leading-7 text-slate-300">
              Instead of a single chat response, HigenBot is designed around a staged build process. That makes the output easier to understand, easier to debug, and much closer to how a real studio hands work between roles.
            </p>
          </article>
          <article id="login" className="rounded-3xl border border-white/10 bg-white/5 p-6 shadow-sm">
            <p className="text-xs uppercase tracking-[0.24em] text-cyan-200/60 font-inter">What ships</p>
            <p className="mt-3 text-sm leading-7 text-slate-300">
              The implementation plan points to a FastAPI backend, Supabase auth, WebSockets for live updates, and WebContainers for in-browser preview. This landing page keeps the tone minimal and simply introduces that workflow.
            </p>
          </article>
        </div>

        {authOpen ? (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 px-4 py-8 backdrop-blur-sm"
            role="presentation"
            onClick={closeAuth}
          >
            <div
              className="w-full max-w-md rounded-4xl border border-white/10 bg-[#071225] p-6 text-slate-100 shadow-2xl shadow-black/40"
              role="dialog"
              aria-modal="true"
              aria-labelledby="auth-title"
              onClick={(event) => event.stopPropagation()}
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-xs uppercase tracking-[0.28em] text-cyan-200/70 font-inter">Account access</p>
                  <h3 id="auth-title" className="mt-2 font-baskerville text-3xl italic text-white">
                    {authMode === 'sign-up' ? 'Create your account' : 'Welcome back'}
                  </h3>
                </div>
                <button
                  type="button"
                  onClick={closeAuth}
                  className="rounded-full border border-white/10 px-3 py-1 text-sm text-slate-200 transition hover:bg-white/10"
                  aria-label="Close auth popup"
                >
                  ×
                </button>
              </div>

              <div className="mt-5 grid grid-cols-2 rounded-full border border-white/10 bg-white/5 p-1 text-sm">
                <button
                  type="button"
                  onClick={() => setAuthMode('sign-in')}
                  className={`rounded-full px-4 py-2 transition ${authMode === 'sign-in' ? 'bg-white text-slate-950' : 'text-slate-300 hover:text-white'}`}
                >
                  Sign in
                </button>
                <button
                  type="button"
                  onClick={() => setAuthMode('sign-up')}
                  className={`rounded-full px-4 py-2 transition ${authMode === 'sign-up' ? 'bg-white text-slate-950' : 'text-slate-300 hover:text-white'}`}
                >
                  Sign up
                </button>
              </div>

              <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
                <label className="block">
                  <span className="mb-2 block text-xs uppercase tracking-[0.22em] text-slate-300 font-inter">Email</span>
                  <input
                    type="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    className="w-full rounded-2xl border border-white/10 bg-white/6 px-4 py-3 text-sm text-white outline-none transition placeholder:text-slate-500 focus:border-cyan-300/60 focus:bg-white/10"
                    placeholder="you@example.com"
                    autoComplete="email"
                    required
                  />
                </label>

                <label className="block">
                  <span className="mb-2 block text-xs uppercase tracking-[0.22em] text-slate-300 font-inter">Password</span>
                  <input
                    type="password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    className="w-full rounded-2xl border border-white/10 bg-white/6 px-4 py-3 text-sm text-white outline-none transition placeholder:text-slate-500 focus:border-cyan-300/60 focus:bg-white/10"
                    placeholder="••••••••"
                    autoComplete={authMode === 'sign-up' ? 'new-password' : 'current-password'}
                    required
                  />
                </label>

                {error ? (
                  <p className="rounded-2xl border border-rose-400/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
                    {error}
                  </p>
                ) : null}

                {message ? (
                  <p className="rounded-2xl border border-emerald-400/20 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-100">
                    {message}
                  </p>
                ) : null}

                <button
                  type="submit"
                  disabled={submitting}
                  className="w-full rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-100 disabled:cursor-not-allowed disabled:opacity-70"
                >
                  {submitting ? 'Working...' : authMode === 'sign-up' ? 'Create account' : 'Sign in'}
                </button>
              </form>

              <div className="mt-4">
                <button
                  type="button"
                  onClick={() => {
                    void signInWithGoogle()
                  }}
                  className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm font-semibold text-white transition hover:bg-white/10"
                >
                  Continue with Google
                </button>
              </div>
            </div>
          </div>
        ) : null}
      </section>
    </main>
  )
}

export default LandingPage