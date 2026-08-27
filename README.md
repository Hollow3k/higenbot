# Higenbot

A multi-agent platform that turns a text prompt into a playable browser game through collaborating AI agents with real-time streaming and iterative editing.

> **Note:** The live demo uses free/low-cost LLM APIs, so generated game quality may vary. Locally with higher-tier models (Claude, GPT-4o, etc.) the output is significantly better.

## What is Higenbot?

Higenbot is an AI-powered game generation platform where four specialized AI agents work in sequence to transform a natural-language description into a fully playable HTML5 Canvas + TypeScript game — all in real time.

You describe a game, and within seconds you can watch each agent contribute its piece:

1. **Creative Director** — Interprets your prompt into a structured creative vision (theme, mood, visual style)
2. **Game Designer** — Translates the vision into a concrete design document (controls, core loop, win/lose conditions)
3. **Gameplay Programmer** — Generates the actual TypeScript + HTML5 Canvas game files
4. **QA Tester** — Runs TypeScript type-checking, feeds errors back to the programmer for automatic retries

Once generated, you can request changes through a built-in chat interface that modifies game files on request and runs QA checks before applying changes.

## Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                        Frontend (React)                          │
│                                                                  │
│  Landing Page → Auth → Projects Page → Studio Page               │
│                                                                  │
│  Studio:                                                         │
│  ┌────────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐          │
│  │Agent Status│ │ Activity │ │  Code    │ │ Preview │          │
│  │    Bar     │ │   Log    │ │  Viewer  │ │ (iframe)│          │
│  └────────────┘ └──────────┘ └──────────┘ └─────────┘          │
│                                                                  │
│  WebSocket ◀─────────────────────────────────────────────────    │
└───────────────────────────────┬──────────────────────────────────┘
                                │ wss://
                                ▼
┌────────────────────────────────────────────────────────────────┐
│                      Backend (FastAPI)                           │
│                                                                  │
│  /ws/run/{id} ─── LangGraph Pipeline:                            │
│                                                                  │
│    ┌──────────────┐   ┌──────────────┐   ┌──────────────┐       │
│    │   Creative   │──▶│    Game      │──▶│  Gameplay    │       │
│    │   Director   │   │   Designer   │   │  Programmer  │◀──┐   │
│    └──────────────┘   └──────────────┘   └──────┬───────┘   │   │
│                                                  │           │   │
│                                                  ▼           │   │
│                                           ┌──────────────┐   │   │
│                                           │  QA Tester   │   │   │
│                                           └──────┬───────┘   │   │
│                                                  │           │   │
│                                         ┌────────┴────────┐  │   │
│                                         │                 │  │   │
│                                       pass              fail │   │
│                                         │            (retry) │   │
│                                         ▼                 └──┘   │
│                                        END                       │
│                                                                  │
│  /ws/edit/{id} ─── Edit Chat (LLM + QA) ────────────────────     │
│                                                                  │
│  /api/projects ─── CRUD (SQLAlchemy + PostgreSQL) ───────────     │
└───────────────────────────────┬──────────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────────┐
│                     Supabase (Auth + DB)                         │
│                                                                  │
│  Auth: Email/password, Google OAuth                              │
│  DB: projects, generation_runs, agent_steps, generated_files     │
└────────────────────────────────────────────────────────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React, TypeScript, Tailwind CSS, Zustand, Vite |
| Backend | FastAPI, LangGraph, LangChain, WebSockets, SQLAlchemy |
| AI Models | Gemini 2.5 Flash (code generation), Groq GPT-oss-120b (planning agents) |
| Database | Supabase (PostgreSQL) |
| Auth | Supabase Auth (email + Google OAuth) |
| Deployment | Render (backend), Vercel (frontend) |

## Project Structure

```
higenbot/
├── backend/
│   ├── agents/
│   │   ├── graph.py       # LangGraph state graph wiring
│   │   ├── nodes.py       # 4 agent node implementations
│   │   ├── schemas.py     # Pydantic models (CreativeVision, DesignDoc, QAReport)
│   │   └── state.py       # Shared graph state TypedDict
│   ├── api/
│   │   └── projects.py    # REST endpoints for project CRUD
│   ├── core/
│   │   ├── config.py      # pydantic-settings configuration
│   │   └── security.py    # Supabase JWT verification
│   ├── db/
│   │   ├── database.py    # Async SQLAlchemy engine
│   │   └── models.py      # ORM models
│   └── main.py            # FastAPI app + WebSocket handlers
├── frontend/
│   ├── src/
│   │   ├── components/    # AgentStatusBar, ActivityLog, ChatPane, etc.
│   │   ├── hooks/         # useStudioWebSocket
│   │   ├── lib/           # API client, download utils, localStorage
│   │   ├── pages/         # Landing, Auth, Projects, Studio
│   │   ├── providers/     # AuthProvider (Supabase)
│   │   ├── store/         # Zustand store
│   │   └── types/         # WebSocket event types
│   └── index.html
├── render.yaml
└── README.md
```

## Local Development

### Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate  # or source .venv/bin/activate on Mac/Linux
pip install -r requirements.txt
cp .env.example .env    # fill in your API keys
uvicorn main:app --reload
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env    # fill in your URLs
npm run dev
```

## Environment Variables

### Backend (.env)

| Variable | Description |
|----------|-------------|
| DATABASE_URL | Supabase PostgreSQL connection string |
| GROQ_API_KEY | Groq API key for planning agents |
| GEMINI_API_KEY | Google Gemini API key for code generation |
| SUPABASE_URL | Supabase project URL |
| SUPABASE_ANON_KEY | Supabase public anon key |
| SUPABASE_JWT_SECRET | Supabase JWT secret for token verification |
| ALLOWED_ORIGINS | Comma-separated CORS origins |

### Frontend (.env)

| Variable | Description |
|----------|-------------|
| VITE_API_URL | Backend API URL |
| VITE_WS_URL | Backend WebSocket URL |
| VITE_SUPABASE_URL | Supabase project URL |
| VITE_SUPABASE_ANON_KEY | Supabase public anon key |
