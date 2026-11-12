import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import { useAuth } from '../providers/AuthProvider'

type AuthMode = 'sign-in' | 'sign-up'

const pipeline = [
  {
    n: '01',
    role: 'Creative Director',
    text: 'Turns your idea into a vision: genre, palette, visual style, and the one hook that makes it memorable.',
  },
  {
    n: '02',
    role: 'Game Designer',
    text: 'Writes the spec: entities, controls, mechanics, balance numbers, difficulty curve, and game-feel effects.',
  },
  {
    n: '03',
    role: 'Gameplay Programmer',
    text: 'Implements the spec as a TypeScript and HTML5 Canvas game. No engine, no assets to download.',
  },
  {
    n: '04',
    role: 'QA Tester',
    text: 'Type-checks the result and sends failures back to the programmer to repair, automatically.',
  },
]

const features = [
  {
    title: 'Real source files',
    text: 'You get index.html and a TypeScript game file, not a screenshot. Read them, edit them, download them as a zip.',
  },
  {
    title: 'Instant preview',
    text: 'The game compiles and runs in your browser the moment it is generated.',
  },
  {
    title: 'Edit by chatting',
    text: 'Ask for changes in plain language, like "make the player faster", and the code updates in place.',
  },
  {
    title: 'Watch the team work',
    text: 'A live activity log shows each agent starting, finishing, and writing files as it happens.',
  },
  {
    title: 'Checked before you see it',
    text: 'Every build is type-checked and tested for structure, then fixed automatically when it fails.',
  },
  {
    title: 'Your projects, saved',
    text: 'Every game stays in your projects list so you can reopen it and keep iterating.',
  },
]

const examplePrompts = [
  'A penalty shootout where I aim by clicking the net',
  'A neon asteroid dodger that speeds up every 15 seconds',
  'A cozy fishing game with one button and a combo meter',
  'An endless runner with a ghost that replays my last run',
]

const sectionLabel = 'text-xs uppercase tracking-[0.28em] text-sky-800 font-inter'

function LandingPage() {
  const { signUp, signInWithPassword, signInWithGoogle, session, signOut } = useAuth()
  const navigate = useNavigate()
  const [authOpen, setAuthOpen] = useState(false)
  const [authMode, setAuthMode] = useState<AuthMode>('sign-in')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const isLoggedIn = !!session

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

  const handleHeroCta = () => {
    if (isLoggedIn) {
      navigate('/projects')
    } else {
      openAuth('sign-in')
    }
  }

  const handleNavAuth = async () => {
    if (isLoggedIn) {
      await signOut()
    } else {
      openAuth('sign-in')
    }
  }

  return (
    <main className="min-h-screen bg-white text-slate-900">
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
                <button
                  type="button"
                  onClick={handleNavAuth}
                  className="whitespace-nowrap transition hover:text-slate-950"
                >
                  {isLoggedIn ? 'SIGN OUT' : 'LOGIN'}
                </button>
              </div>
            </nav>
          </header>

          <section className="flex min-h-[calc(100vh-5rem)] flex-col items-center justify-center px-2 pb-10 sm:px-6">
            <div className="max-w-screen text-center">
              <p className="font-baskerville text-[clamp(2rem,4.8vw,4.2rem)] font-bold italic leading-[1.08] tracking-[-0.03em] text-slate-950 drop-shadow-[0_1px_0_rgba(255,255,255,0.32)] sm:text-[clamp(2.3rem,4.2vw,4.6rem)]">
                <span className="block">Every world begins as</span>
                <span className="block">imagination, but only creation</span>
                <span className="block">gives it a chance to exist.</span>
              </p>
            </div>

            <button
              type="button"
              onClick={handleHeroCta}
              className="mt-10 rounded-full border border-slate-900/20 bg-slate-950 px-8 py-3 text-[11px] uppercase tracking-[0.18em] font-inter text-white shadow-lg transition hover:bg-slate-800 sm:text-xs"
            >
              {isLoggedIn ? 'ENTER STUDIO' : 'START NOW'}
            </button>
          </section>
        </div>
      </section>

      {/* Intro: the only blue band, taken from the hero sky */}
      <section id="about" className="bg-[#00051b]">
        <div className="mx-auto grid w-full max-w-5xl gap-8 px-4 py-16 sm:px-6 lg:grid-cols-[1.1fr_1fr] lg:gap-16 lg:py-20">
          <div>
            <p className="text-xs uppercase tracking-[0.28em] text-sky-300 font-inter">What Higenbot is</p>
            <h2 className="mt-4 font-baskerville text-3xl font-bold italic leading-tight text-slate-50 sm:text-4xl">
              A prompt-to-game studio that works like a small production team.
            </h2>
          </div>
          <p className="text-base leading-7 text-slate-300 lg:pt-9">
            Describe a game in plain language and get a playable TypeScript and HTML5 Canvas project back.
            Instead of a single chat reply, four specialized agents hand the work down the line, the way a
            real studio would. That makes the result easier to follow, easier to debug, and easier to change.
          </p>
        </div>
      </section>

      {/* How it works */}
      <section id="how-it-works" className="mx-auto w-full max-w-5xl px-4 py-20 sm:px-6">
        <p className={sectionLabel}>How it works</p>
        <ol className="mt-10 grid gap-x-8 gap-y-10 sm:grid-cols-2 lg:grid-cols-4">
          {pipeline.map((step) => (
            <li key={step.n} className="relative border-t border-slate-300 pt-6">
              <span className="absolute -top-[3px] left-0 h-1.5 w-1.5 rounded-full bg-sky-600" />
              <p className="text-xs tracking-[0.24em] text-sky-800 font-inter">{step.n}</p>
              <h3 className="mt-3 font-baskerville text-xl italic text-slate-950">{step.role}</h3>
              <p className="mt-2 text-sm leading-7 text-slate-600">{step.text}</p>
            </li>
          ))}
        </ol>
      </section>

      {/* Features */}
      <section id="features" className="scroll-mt-8 border-y border-slate-200 bg-slate-50">
        <div className="mx-auto w-full max-w-5xl px-4 py-20 sm:px-6">
          <p className={sectionLabel}>What you get</p>
          <h2 className="mt-4 font-baskerville text-3xl font-bold italic leading-tight text-slate-950 sm:text-4xl">
            More than a preview.
          </h2>
          <div className="mt-12 grid gap-px overflow-hidden rounded-2xl border border-slate-200 bg-slate-200 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((feature) => (
              <article key={feature.title} className="bg-white p-6">
                <h3 className="text-sm font-semibold text-slate-950">{feature.title}</h3>
                <p className="mt-2 text-sm leading-7 text-slate-600">{feature.text}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* Example prompts */}
      <section id="examples" className="mx-auto w-full max-w-5xl px-4 py-20 sm:px-6">
        <p className={sectionLabel}>Try something like</p>
        <ul className="mt-8 divide-y divide-slate-200 border-y border-slate-200">
          {examplePrompts.map((prompt) => (
            <li
              key={prompt}
              className="py-5 font-baskerville text-lg italic text-slate-800 sm:text-xl"
            >
              <span className="mr-4 text-sky-600">&ldquo;</span>
              {prompt}
            </li>
          ))}
        </ul>
      </section>

      {/* Closing call to action */}
      <section className="border-t border-slate-200 px-4 py-24 text-center sm:px-6">
        <div className="mx-auto max-w-2xl">
          <h2 className="font-baskerville text-3xl font-bold italic leading-tight text-slate-950 sm:text-5xl">
            Describe a game.
            <span className="block">Watch a team build it.</span>
          </h2>
          <button
            type="button"
            onClick={handleHeroCta}
            className="mt-10 rounded-full border border-slate-900/20 bg-slate-950 px-8 py-3 text-[11px] font-inter uppercase tracking-[0.18em] text-white shadow-lg transition hover:bg-slate-800 sm:text-xs"
          >
            {isLoggedIn ? 'Enter studio' : 'Start now'}
          </button>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-200">
        <div className="mx-auto flex w-full max-w-5xl flex-col items-center justify-between gap-4 px-4 py-8 sm:flex-row sm:px-6">
          <a href="/" className="font-bm-hanna text-2xl text-slate-950">
            Higenbot
          </a>
          <p className="text-[11px] uppercase tracking-[0.22em] text-slate-500 font-inter">
            FastAPI &middot; LangGraph &middot; React &middot; Supabase
          </p>
        </div>
      </footer>

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
    </main>
  )
}

export default LandingPage
