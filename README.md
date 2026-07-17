# AI Short Film Production System

> AI-powered pipeline that turns a screenplay into a fully produced short drama — episode splitting, asset generation, storyboarding, shot-by-shot video synthesis, and final merging, all in one place.

**[中文文档](README.zh.md)**

---

## Overview

This system takes a raw screenplay as input and drives the entire production pipeline through an LLM orchestration layer backed by real image and video generation APIs:

```
Screenplay
  → Episode Splitting
  → Character & Scene Asset Generation (review gated)
  → Shot-level Storyboarding
  → Image Generation per Shot
  → Video Synthesis (shot by shot, chained for continuity)
  → Episode Merging
```

Key design principles:
- **Consistency-first** — characters, scenes, and props maintain visual identity across shots via face-lock and look-lock mechanisms.
- **Human-in-the-loop** — assets and storyboards go through a review step before video generation proceeds.
- **Async by default** — LLM, image, video, and merge tasks run on separate Celery queues; the UI polls for status.

---

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| Frontend | React 18 + TypeScript + Vite + Tailwind CSS + React Router 6 |
| UI Components | Radix UI + shadcn/ui style |
| Backend | Python 3.12 + FastAPI + Beanie (MongoDB ODM) |
| Task Queue | Celery + Redis (separate queues: `llm`, `image`, `video`, `merge`) |
| Database | MongoDB 7 |
| Object Storage | Tencent Cloud COS (STS temp credentials for frontend upload) |
| LLM | OpenRouter (configurable model, default GPT-4o) |
| Image Generation | Volcano Engine Seedream |
| Video Generation | Volcano Engine Seedance (chained shots via `last_frame_url`) |
| Auth | JWT Bearer token |
| Proxy | V2Ray (routes LLM traffic through proxy; image/video calls bypass) |

---

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── agent/          # LLM agent runner & prompt agents
│   │   ├── models/         # Beanie document models
│   │   ├── parsing/        # Script parsing pipeline modules
│   │   ├── routers/        # FastAPI route handlers
│   │   ├── services/       # Storage, auth, task services
│   │   └── tasks/          # Celery task definitions
│   ├── .env.example        # Environment variable template
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/     # Shared UI components
│   │   ├── lib/            # API client, auth, COS context
│   │   └── pages/          # Route-level page components
│   └── Dockerfile
├── docs/
│   ├── workflow-spec.md    # Production workflow specification
│   ├── parse-workflow-spec.md
│   └── backend-plan.md
├── v2ray/
│   └── config.json.example # Proxy config template (copy → config.json)
└── docker-compose.yml
```

---

## Getting Started

### Prerequisites

- Docker & Docker Compose
- A [Tencent Cloud COS](https://cloud.tencent.com/product/cos) bucket
- An [OpenRouter](https://openrouter.ai) API key
- A [Volcano Engine Ark](https://www.volcengine.com/product/ark) API key (for Seedream image and Seedance video models)
- *(Optional)* A V2Ray proxy node if OpenRouter is not directly accessible from your server

### 1. Clone and configure

```bash
git clone https://github.com/wushaojun321/ai-short-film.git
cd ai-short-film
```

Copy and fill in the backend environment file:

```bash
cp backend/.env.example backend/.env
# Edit backend/.env with your actual keys
```

If you need a proxy for LLM traffic, set up V2Ray:

```bash
cp v2ray/config.json.example v2ray/config.json
# Edit v2ray/config.json with your proxy server details
# If you don't need a proxy, remove the v2ray service from docker-compose.yml
#   and remove HTTP_PROXY / HTTPS_PROXY env vars from api / worker services
```

### 2. Start all services

```bash
docker compose up -d
```

This starts: `frontend`, `api`, `worker-llm`, `worker-image`, `worker-video`, `worker-merge`, `mongodb`, `redis`, and optionally `v2ray`.

### 3. Open the app

Visit `http://localhost` (port 80).

Register an account, then create a project and paste your screenplay to begin.

---

## Environment Variables

See `backend/.env.example` for the full list. Key variables:

| Variable | Description |
|----------|-------------|
| `MONGODB_URL` | MongoDB connection string |
| `REDIS_URL` | Redis connection string |
| `COS_SECRET_ID` / `COS_SECRET_KEY` | Tencent Cloud COS credentials |
| `COS_REGION` / `COS_BUCKET` | COS region and bucket name |
| `OPENROUTER_API_KEY` | OpenRouter API key |
| `OPENROUTER_MODEL` | LLM model name (e.g. `openai/gpt-4o`) |
| `ARK_API_KEY` | Volcano Engine Ark API key |
| `ARK_IMAGE_MODEL` | Image model ID (Seedream) |
| `ARK_VIDEO_MODEL` | Video model ID (Seedance) |

---

## Production Pipeline Detail

### Script Parsing
The screenplay goes through a multi-stage parser:
1. `ScriptIndexer` — indexes the raw text into block ranges
2. `ProductionBlueprintPlanner` — uses LLM to produce a structured episode/asset/scene blueprint
3. `EpisodeMaterialBuilder` — back-fills raw text from block ranges (no LLM summarization)
4. `AssetRegistryBuilder` — derives character and scene asset records from the blueprint

### Asset Generation
- Characters get three canonical views: face, full-body, side
- `face_identity` locks the facial baseline across shots
- `look_lock` locks hairstyle, costume, and accessories within a story arc
- Assets go through a manual review step before shots proceed

### Shot Video Generation
- Shots within a segment are generated in order
- Each shot can reference the `last_frame_url` of the previous shot for visual continuity
- Different segments run in parallel across `worker-video` instances

---

## License

MIT
