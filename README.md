# Bridge — Telecom Communication Bridge

**A visual communication automation platform that uses telecommunications and AI to connect people across language and connectivity barriers — without requiring an app or internet connection.**

A person with an ordinary phone (no smartphone, no data, no app) can call or send an SMS and communicate with someone who speaks another language or uses another channel.

```
Phone Call → Speech → Speech-to-Text → Translation → Text-to-Speech → Phone Call
SMS → Language Detection → Translation → SMS
Voice Call → Speech-to-Text → Translation → SMS
```

## Architecture

FastAPI modular monolith + Nuxt/Vue frontend + PostgreSQL + Africa's Talking.

```
                    ┌─────────────────────┐
                    │    Bridge Web UI    │
                    │    Nuxt + Vue Flow  │
                    └──────────┬──────────┘
                               │ REST
                               ↓
                    ┌─────────────────────┐
                    │      FastAPI        │
                    │   Modular Monolith  │
                    └──────────┬──────────┘
             ┌─────────────────┼─────────────────┐
             ↓                 ↓                 ↓
      ┌─────────────┐   ┌──────────────┐   ┌──────────────┐
      │   Workflow  │   │Communications│   │      AI      │
      │    Engine   │   │    Module    │   │    Module    │
      └──────┬──────┘   └──────┬───────┘   └──────┬───────┘
             │                 ↓                   ↓
             │          Africa's Talking      AI Providers
             ↓
      ┌─────────────┐
      │ PostgreSQL  │
      └─────────────┘
```

**Core technical idea:** `Telecom Event → Workflow → Transformation → Telecom Response`. The workflow engine makes the combinations (Voice→Text→Translation→Voice, SMS→Translation→SMS, Voice→…→SMS) programmable — that is what makes Bridge more than a single translation demo.

## Project structure

```
bridge/
├── backend/
│   ├── app/
│   │   ├── core/                 # config, database, structured logging
│   │   ├── api/routes/           # workflows, runs, conversations, stats, webhooks
│   │   └── modules/
│   │       ├── workflows/        # models, registry, engine, nodes/, validation
│   │       ├── communications/   # provider abstraction + Africa's Talking adapter
│   │       ├── ai/               # STT / translation / TTS / detection abstractions
│   │       ├── conversations/    # session records + timelines
│   │       └── contacts/
│   ├── tests/                    # pytest: engine, validation, webhooks, idempotency
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/                     # Nuxt 3 + Vue 3 + Vue Flow builder
├── render.yaml                   # Render: API + web + PostgreSQL
└── README.md
```

## Running locally

### Backend (FastAPI)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

- API: http://localhost:8000 — interactive docs: http://localhost:8000/docs
- Boots with three seeded demo workflows: **Voice Translator**, **SMS Translator**, **Voice to SMS**
- Without Africa's Talking credentials the platform runs on the **mock provider** — the full pipeline works offline

### Tests

```bash
cd backend && .venv/bin/python -m pytest tests/ -v
```

23 tests cover workflow validation, node execution, branching, run pausing/resuming,
webhook idempotency and the complete translation flows.

### Frontend (Nuxt + Vue Flow)

```bash
cd frontend
npm install
npm run dev
```

- UI: http://localhost:3000 — `/api/**` and `/webhooks/**` are proxied to the backend

### Try the demo pipeline without a phone

```bash
# SMS translation (English → Hausa)
curl -X POST http://localhost:8000/webhooks/africastalking/sms \
  -d "from=%2B234801234567&text=Where are you?&id=demo1"

# Voice: first event pauses at Collect Speech and returns AT actions
curl -X POST http://localhost:8000/webhooks/africastalking/voice \
  -d "sessionId=demoCall&callerNumber=%2B234802&isActive=1"

# Voice: the recording event resumes the run through STT → Translate → TTS → Play
curl -X POST http://localhost:8000/webhooks/africastalking/voice \
  -d "sessionId=demoCall&callerNumber=%2B234802&isActive=1&recordingUrl=https://rec.at/x.mp3&id=evt2"
```

Then open the dashboard: conversations, timelines, run traces and node-level
execution history are all recorded.

## Workflow builder

The builder has three areas (palette | Vue Flow canvas | inspector). Node categories:

| Category | Nodes |
|----------|-------|
| Trigger | Incoming Call, Incoming SMS, USSD Request |
| Voice | Make Call, Collect Speech, Play Audio, Play Voice, Hang Up |
| AI | Speech to Text, Text to Speech, Translate, Detect Language |
| Messaging | Send SMS |
| Logic | Condition, Switch, Delay, Set Variable |
| Flow | Start, End |

Workflows are stored as JSON (`{"nodes": [...], "edges": [...]}`), **versioned** on every
change (runs keep the version they started with), and **validated** before deployment
(missing triggers, disconnected nodes, missing required configuration, broken edges).

## Africa's Talking integration

Point your AT dashboard at the public webhook endpoints (spec §35):

```
https://<your-api-host>/webhooks/africastalking/voice
https://<your-api-host>/webhooks/africastalking/sms
```

Credentials go in environment variables (`BRIDGE_AT_USERNAME`, `BRIDGE_AT_API_KEY`,
`BRIDGE_AT_SENDER_ID`, with `BRIDGE_COMMS_PROVIDER=africastalking`). Provider retries are
idempotent — one SMS produces exactly one workflow execution.

## Deployment

```bash
render blueprint launch   # provisions API + web + PostgreSQL per render.yaml
```

## Security & reliability

- Optional bearer token on workflow mutations (`BRIDGE_API_TOKEN`)
- Structured JSON logs with correlation IDs (`workflow_run_id`, `conversation_id`, `call_id`)
- Idempotent webhooks, timeout/error handling on every external call, controlled failure paths

## MVP definition of done

The hackathon version is successful when a **real phone call enters the system, passes
through a workflow, gets transformed, and produces a real response** — and the same
system demonstrates SMS translation, with everything configurable through the visual builder.
