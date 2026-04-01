# D&D Session Bot — Project Guide

## What This Is

A Discord bot (and eventually web app) for Dungeons & Dragons groups. It joins voice channels, transcribes sessions, tracks characters, summarizes what happened, generates per-player art for key moments, and coaches the DM.

## Tech Stack

- **Language**: Python 3.12+
- **Discord**: Pycord (has built-in voice recording sink system)
- **Transcription**: Deepgram (real-time during session), AssemblyAI (post-session batch for accuracy)
- **AI/LLM**: Anthropic Claude API (summaries, DM coaching, key moment extraction)
- **Image Gen**: Flux 1.1 Pro via API (high quality, fast) — with fallback to GPT Image
- **Database**: PostgreSQL (campaign data, session history, character refs) via SQLAlchemy + Alembic
- **Web API**: FastAPI (REST API for web dashboard + future integrations)
- **Web Frontend**: React + Vite (player dashboard)
- **Storage**: S3-compatible (character reference images, generated art, audio archives)
- **Task Queue**: Celery + Redis (async post-session processing pipeline)

## Architecture Overview

The system is built around a **pipeline architecture**:

1. **Capture** — Bot records voice channel audio per-speaker using Pycord sinks
2. **Transcribe** — Audio chunks sent to Deepgram (live) or AssemblyAI (post-session)
3. **Process** — Claude API identifies speakers, maps to characters, extracts narrative
4. **Summarize** — Claude generates session summary, key moments, DM coaching notes
5. **Generate** — Flux creates per-player key moment art using uploaded character references
6. **Deliver** — Results posted to Discord channel + stored for web dashboard

Each stage is a separate module so we can swap providers or add new input sources (Zoom, Meet) later.

## Project Structure

```
dnd-session-bot/
├── CLAUDE.md                    # This file — project context for Claude Code
├── README.md                    # User-facing docs
├── pyproject.toml               # Python project config (dependencies, scripts)
├── .env.example                 # Template for required env vars
├── docker-compose.yml           # Local dev: Postgres, Redis, MinIO (S3)
├── alembic/                     # Database migrations
│   └── versions/
│
├── bot/                         # Discord bot package
│   ├── __init__.py
│   ├── main.py                  # Bot entrypoint, loads cogs
│   ├── config.py                # Settings from env vars (pydantic-settings)
│   ├── cogs/                    # Discord command groups
│   │   ├── __init__.py
│   │   ├── session.py           # /session start, /session stop, /session status
│   │   ├── character.py         # /character upload, /character list, /character view
│   │   ├── campaign.py          # /campaign create, /campaign sourcebooks, /campaign homebrew
│   │   ├── summary.py           # /summary last, /summary history, /summary regenerate
│   │   └── dm_coach.py          # /coach tips, /coach thread (linking session advice)
│   ├── voice/                   # Voice capture subsystem
│   │   ├── __init__.py
│   │   ├── recorder.py          # Pycord sink management, per-user audio capture
│   │   ├── audio_buffer.py      # Chunked audio buffering for streaming transcription
│   │   └── speaker_tracker.py   # Maps Discord users to campaign characters
│   └── ui/                      # Discord UI components
│       ├── __init__.py
│       ├── embeds.py            # Rich embed builders for summaries, character cards
│       └── views.py             # Button/select menus for interactive flows
│
├── core/                        # Shared business logic (bot + API both use this)
│   ├── __init__.py
│   ├── models/                  # SQLAlchemy models
│   │   ├── __init__.py
│   │   ├── campaign.py          # Campaign, Sourcebook, HomebrewContent
│   │   ├── character.py         # Character, CharacterReference (images)
│   │   ├── session.py           # Session, SessionRecording, Transcript
│   │   └── summary.py           # SessionSummary, KeyMoment, GeneratedArt
│   ├── services/                # Business logic layer
│   │   ├── __init__.py
│   │   ├── transcription.py     # Deepgram + AssemblyAI abstraction
│   │   ├── summarizer.py        # Claude API — session summarization
│   │   ├── key_moments.py       # Claude API — extract pivotal moments per player
│   │   ├── image_gen.py         # Flux API — generate art from key moment + char ref
│   │   ├── dm_coach.py          # Claude API — DM coaching and session linking
│   │   ├── campaign_context.py  # Build context from sourcebooks + homebrew for prompts
│   │   └── storage.py           # S3 upload/download abstraction
│   ├── prompts/                 # LLM prompt templates (Jinja2 or plain text)
│   │   ├── summarize_session.md
│   │   ├── extract_key_moments.md
│   │   ├── dm_coaching.md
│   │   └── image_scene_description.md
│   └── pipeline/                # Post-session processing orchestration
│       ├── __init__.py
│       ├── tasks.py             # Celery tasks
│       └── orchestrator.py      # Chains: transcribe → summarize → generate → deliver
│
├── api/                         # FastAPI web backend
│   ├── __init__.py
│   ├── main.py                  # FastAPI app entrypoint
│   ├── auth.py                  # Discord OAuth2 login
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── campaigns.py         # CRUD for campaigns
│   │   ├── sessions.py          # Session history, transcripts, summaries
│   │   ├── characters.py        # Character management + image upload
│   │   └── webhooks.py          # Future: Zoom/Meet webhook receivers
│   └── deps.py                  # Dependency injection (DB session, current user)
│
├── web/                         # React frontend (Vite)
│   ├── package.json
│   ├── src/
│   │   ├── App.tsx
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx     # Campaign overview
│   │   │   ├── SessionDetail.tsx # Full session view: transcript, summary, art
│   │   │   └── Characters.tsx    # Character gallery + upload
│   │   └── components/
│   │       ├── SessionCard.tsx
│   │       ├── KeyMomentCard.tsx
│   │       └── ImageGallery.tsx
│   └── vite.config.ts
│
└── tests/
    ├── conftest.py
    ├── test_transcription.py
    ├── test_summarizer.py
    ├── test_key_moments.py
    ├── test_image_gen.py
    └── test_pipeline.py
```

## Key Design Decisions

### Provider Abstraction
Every external service (transcription, LLM, image gen, storage) has an abstract interface in `core/services/`. This means swapping Deepgram for Whisper, or Flux for DALL-E, is a config change — not a rewrite. This is critical for the business model (different tiers could use different providers).

### Prompt Templates as Files
LLM prompts live in `core/prompts/` as markdown files with Jinja2 template variables. This makes them easy to iterate on without touching code, and they can include campaign context, sourcebook rules, and homebrew lore dynamically.

### Character Reference Pipeline
When a player uploads a reference image:
1. Stored in S3 with metadata
2. When generating key moment art, the reference is passed as a style/character guide to the image gen API
3. The prompt includes the scene description from Claude + "maintain consistency with this character reference"

### Session Pipeline Flow
```
Discord Voice → Pycord Sink (per-user PCM)
    → Audio Buffer (5-second chunks)
    → Deepgram Streaming (live captions, optional)
    → Full recording saved to S3
    → AssemblyAI batch transcription (high accuracy)
    → Claude: speaker identification + character mapping
    → Claude: session summary + key moments
    → Flux: per-player art generation
    → Discord embeds + web dashboard update
```

## Environment Variables Needed

```
DISCORD_BOT_TOKEN=
DISCORD_CLIENT_ID=
DISCORD_CLIENT_SECRET=
ANTHROPIC_API_KEY=
DEEPGRAM_API_KEY=
ASSEMBLYAI_API_KEY=
FLUX_API_KEY=
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
S3_ENDPOINT=
S3_ACCESS_KEY=
S3_SECRET_KEY=
S3_BUCKET=
```

## Build Order (Suggested Phases)

### Phase 1 — Foundation
- Project setup (pyproject.toml, docker-compose, config)
- Database models + migrations
- Discord bot skeleton with Pycord, basic slash commands
- `/session start` and `/session stop` — join voice, record audio

### Phase 2 — Transcription
- Voice recording with per-user audio separation
- Deepgram integration for real-time transcription
- AssemblyAI integration for post-session high-accuracy transcription
- Speaker identification + character mapping

### Phase 3 — Intelligence
- Claude integration for session summarization
- Key moment extraction per player
- Prompt template system with campaign context injection
- DM coaching module

### Phase 4 — Image Generation
- Character reference upload + storage
- Flux integration for key moment art
- Scene description generation (Claude → Flux prompt pipeline)

### Phase 5 — Web Dashboard
- FastAPI backend with Discord OAuth
- React frontend for session history, character gallery
- Real-time session status via WebSockets

### Phase 6 — Polish & Business
- Sourcebook integration (SRD content for D&D 5e/2024)
- Homebrew campaign content upload
- Multi-server support (one bot instance, many Discord servers)
- Usage tracking + subscription tiers
