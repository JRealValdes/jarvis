---
title: Jarvis
emoji: 🤖
colorFrom: blue
colorTo: green
sdk: gradio
sdk_version: 5.29.1
app_file: app.py
pinned: false
---

# Jarvis Project (Personal AI with Langchain)

"Jarvis"-style AI using LangGraph and Langchain.
Hello, sir. How can I assist you today?

## Requirements
- Python 3.10+
- OpenAI API key (required for chat / LLM use)

## Installation

Requirement: [uv](https://docs.astral.sh/uv/) (`pip install uv` or the official installer).

```bash
uv sync    # create .venv and install runtime + dev deps (pytest)
```

For deploys that only read `requirements.txt` (e.g. Hugging Face Spaces):

```bash
uv export --no-dev -o requirements.txt
```

Classic install without uv (alternative):

```bash
pip install -r requirements.txt
pip install -e .
```

## How to run

Jarvis has three modes. One CLI dispatches all of them:

| Mode | Command | What it does |
|------|---------|--------------|
| **chat** | `uv run jarvis chat` | Interactive console chatbot |
| **api** | `uv run jarvis api` | HTTP API (FastAPI + uvicorn) |
| **ui** | `uv run jarvis ui` | Gradio web UI |

```bash
uv run jarvis --help
uv run jarvis chat
uv run jarvis api
uv run jarvis ui
```

Hugging Face Spaces still launches Gradio via root `app.py` (`app_file` in the YAML header). Prefer `uv run jarvis ui` locally.

## Development

```bash
uv run pytest
uv run jarvis chat    # or api / ui
```

Docstring convention in production code: module + **Args** / **Returns** / **Raises**.

## Raspberry Pi (headless)

Operator guide for SSH, systemd, secret sync, and code updates on a LAN Pi: [docs/raspberry-pi-ops.md](docs/raspberry-pi-ops.md). Helpers live under [`deploy/`](deploy/).

**Off-LAN:** install Tailscale on the Pi and on clients (same tailnet), then use MagicDNS / Tailscale IP as the API base URL — see [Off-LAN access (Tailscale)](docs/raspberry-pi-ops.md#off-lan-access-tailscale-31). Named Cloudflare Tunnel is a documented alternative only. No in-process tunnel in Jarvis.

## Configuration

App settings live in `jarvis.core.config` as typed defaults. That module is the only place that calls `load_dotenv()` and the only place that reads Jarvis environment variables. Entry points (`uv run jarvis`, root `app.py`, and the API) import it first. Override any setting in `.env` (see `.env.example`). Names stay public as written there (`JARVIS_*`, `JWT_*`, `API_PORT`, `FERNET_KEY`). `OPENAI_API_KEY` is read by the OpenAI client, not by Jarvis code. Built-in tools are listed in `jarvis.tools.builtins.BUILTIN_TOOLS`.

1. Copy `.env.example` to `.env` and fill in secrets (OpenAI, Fernet, JWT) plus any optional flags.
2. Seed users into the local DB (see below).
3. Google Calendar (optional): OAuth files under `data/google/<username>/<account>/` (see `data/google/example_user/`). Interactive flow: `examples/google_api_demo.ipynb`.
4. Job / LinkedIn reply preferences (optional): ask Jarvis to interview you and save them (`show_job_preferences_tool` / `save_job_preferences_tool`), or copy `data/users/example_user/job_preferences.yaml` to `data/users/<real_name>/job_preferences.yaml` and edit. Optional style samples: copy `data/users/example_user/linkedin_reply_examples.yaml` to the same user folder. Used by `draft_linkedin_reply_tool`.
5. MCP (optional): `JARVIS_USE_MCP=1`, edit `data/mcp/server_config.json`; server scripts live under `src/jarvis/mcp/servers/`.
6. Local UI thread (optional): `JARVIS_LOCAL_THREAD_ID` (default `1`) is the checkpoint thread for the CLI and Gradio.
7. Tool traces in chat (optional): `JARVIS_SHOW_TOOL_TRACES=1` paints tool call/result lines into message history for the UI/API. Default is off (final assistant replies only).

The HTTP API listens on the host/LAN (`0.0.0.0:API_PORT`). Off-LAN access is a host concern (**Tailscale** by default — issue #31; named Cloudflare Tunnel optional), not an in-process tunnel.

### Debug observability (LangSmith)

To inspect agent and tool runs without flooding the chat UI, use [LangSmith](https://docs.langchain.com/langsmith/trace-with-langchain). It is the best fit here because Jarvis already runs on LangChain/LangGraph: set the env vars and traces appear in the LangSmith UI with no custom debug surface.

```bash
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=...
# optional: LANGSMITH_PROJECT=jarvis
```

`load_dotenv()` (via `jarvis.core.config`) loads these into the process so the LangSmith SDK can pick them up. Alternatives considered: Langfuse (similar SaaS, less native LangGraph wiring), LangGraph Studio / checkpoint inspection (local, no hosted timeline of every tool call). Prefer LangSmith unless you already run Langfuse.

### Web search and public pages (`web_search_tool`)

Jarvis can search the public web (metasearch via the `ddgs` package, including DuckDuckGo and other engines) and read extracted text from public `http`/`https` pages (`requests` + `trafilatura`). No API key is required.

**Can read:** public HTML pages that allow the Jarvis user-agent in `robots.txt`, within size and timeout caps. After a search, the tool fetches readable text from the top hit URLs by default (not snippets alone).

**Provider failures:** `ddgs` sometimes raises `No results found` when a backend is rate-limited, blocked, or flaky, instead of returning an empty list. That is intermittent and more common on a shared or home IP (typical for the Raspberry Pi) than on a desktop. Jarvis retries a few backends with a short backoff, then returns an error that names `ddgs`, the exception type, the backends tried, and a hint. A successful search with zero hits stays `No search results.` and is a different outcome. No paid search API is required.

**Cannot read:** login-walled content, pages behind captchas/paywalls, credentialed sessions, or Glassdoor (and similar blocked job boards). Search may still return snippets that *mention* those sites; Jarvis must not fetch them. Snippets can be stale—prefer fetched page text and cite the URL used. Jarvis should answer the user in the language of their latest message.

### Inline web images (`web_image_search_tool`)

When a picture would help, Jarvis can search public images (again via `ddgs`, no API key) and embed **at most one** markdown image in the reply: `![alt](direct-image-url)`. The URL must be copied from the tool. If the search returns nothing, the reply stays text-only. Wikimedia hosts are preferred when they show up; this is not a ranked image-search product.

Gradio's chatbot renders Markdown (`render_markdown=True`), so that image appears inline. HTTP clients that render markdown images, including `![alt](url)`, get the same text.



### HTTP speech-to-text (`POST /transcribe`)

Authenticated the same way as `/ask` (`Authorization: Bearer <JWT>`). Remote / Auto-online clients (`jarvis_app`) send short audio; the server reuses OpenAI Whisper (`whisper-1`) and does **not** keep the file after the request.

| | |
|--|--|
| **Method / path** | `POST /transcribe` |
| **Body** | `multipart/form-data` with part `file` (audio bytes) |
| **Response** | `{ "text": "<transcription>" }` |
| **Max size** | 25 MiB (OpenAI Whisper upload limit) |
| **Formats** | `.flac`, `.m4a`, `.mp3`, `.mp4`, `.mpeg`, `.mpga`, `.oga`, `.ogg`, `.wav`, `.webm` |
| **Client policy** | Max **2** audio attachments per chat turn (enforced in the app; each file is one `/transcribe` call) |

Errors: `400` empty/unsupported; `413` too large; `502` Whisper failure; `401`/`403` without a valid JWT. Mic → prompt and attach-audio → context both use this endpoint; the client chooses how to apply `text`. Local app mode calls Whisper on-device and skips this route.

### Multimodal images (`POST /ask`)

`POST /ask` accepts optional images on the same JSON body as the text prompt. Auth is the same Bearer JWT. Images are sent to a vision-capable model (`GPT_4O_MINI`). `GPT_3_5` rejects the turn with `400`.

| | |
|--|--|
| **Field** | `images`: list of `{ "media_type", "data_base64" }` |
| **Text** | `message` may be empty when at least one image is attached |
| **Cap** | **4** images per turn; **4 MiB** decoded bytes each |
| **Types** | `image/jpeg`, `image/png`, `image/gif`, `image/webp` (or a `data:` URL in `data_base64`) |
| **Response** | Unchanged: `{ "response": ["..."] }` |

The checkpoint keeps each attachment on the turn that sent it. Later model calls include image bytes only for the **latest** image-bearing user message, so a follow-up can still refer to that photo without resending every older image. `GET /message-history` does not return base64; each image is the marker `[Image attached]`.

Errors: `400` when the message and images are both empty, the payload is invalid, the cap is exceeded, or the model cannot view images.

### Conversation threads

Each model stores threads in `data/checkpoints/{MODEL}.sqlite`. The same `thread_id` keeps one conversation across process restarts.

| Entry | Default thread |
|-------|----------------|
| HTTP API | JWT `real_name` when the request omits `thread_id`. Admins may pass another thread. |
| CLI and Gradio | `JARVIS_LOCAL_THREAD_ID` (default `1`) |

Set `JARVIS_LOCAL_THREAD_ID` to a user's `real_name` when a local UI should continue that user's API thread. `/message-history` reads the checkpoint file, so history stays available after a restart.

## Local runtime assets (not in git)

These live on each machine and are required (or optional) for a full local setup. Copy/recreate them when moving to a new computer:

| Asset | Path | Required? | How to obtain |
|-------|------|-------------|---------------|
| Environment secrets | `.env` | Yes for real LLM/API use | Copy `.env.example` |
| Users database | `data/users.db` | Yes for identification / API login | Seed with `scripts/users/manage_users.ipynb` from CSV (`example_users_info.csv` / your `secret_users_info.csv`) |
| Google OAuth | `data/google/<user>/<account>/` (`*secret*.json`) | Only for Calendar tools | Google Cloud OAuth client + `examples/google_api_demo.ipynb` |
| Job preferences | `data/users/<real_name>/job_preferences.yaml` | Only for LinkedIn reply drafting | Ask Jarvis to set them up, or copy from `data/users/example_user/job_preferences.yaml` |
| LinkedIn reply samples | `data/users/<real_name>/linkedin_reply_examples.yaml` | Optional style references for drafts | Ask Jarvis to add samples, or copy from `data/users/example_user/linkedin_reply_examples.yaml` |
| MCP config | `data/mcp/server_config.json` | Only if `JARVIS_USE_MCP=1` | Tracked example config is in repo; customize locally if needed |
| Conversation checkpoints | `data/checkpoints/{MODEL}.sqlite` | Created on first chat | Local SQLite; removed by a global memory reset |

Gitignores cover `.env`, `data/users.db`, and `*secret*` files. Do not commit personal credentials.

**Raspberry Pi sync:** paths that must be pushed to the Pi are listed in [`deploy/secret_paths.py`](deploy/secret_paths.py). When you add a new secret/runtime file for the Pi, update that catalog in the same change (see `docs/raspberry-pi-ops.md`).

## Architecture

Installable package `jarvis` under `src/jarvis/`. Layers: `core`, `domain`, `infrastructure`, `agents` (protocol, factory, shared graph, process-wide MCP tool session, `session/`, `implementations/`), `tools` (`registry` + `builtins/`), `api`, `interfaces` (CLI + Gradio), `mcp` (server scripts). Runtime assets live in `data/`; seed/admin helpers in `scripts/`; sample media/docs for future STT/RAG under `examples/fixtures/`.

## Structure
```
jarvis/                          # repository root
├── src/jarvis/                  # Python package
│   ├── __main__.py              # uv run jarvis {chat|api|ui}
│   ├── agents/
│   │   ├── factory.py
│   │   ├── session/             # cache, history, orchestrator
│   │   ├── protocol.py          # JarvisAgent
│   │   ├── graph.py             # shared tool-calling graph
│   │   ├── mcp_session.py       # process-wide MCP tools
│   │   └── implementations/     # memory agent
│   ├── api/                     # FastAPI app (app.py)
│   ├── core/
│   ├── domain/
│   ├── infrastructure/
│   ├── interfaces/              # CLI + Gradio
│   ├── tools/
│   │   ├── registry.py
│   │   └── builtins/
│   └── mcp/servers/             # MCP server scripts
├── data/                        # local runtime (users.db gitignored)
│   ├── google/                  # OAuth credentials per user
│   └── mcp/server_config.json
├── scripts/users/               # CSV + notebook to seed data/users.db
├── deploy/                      # Pi ops: sync secrets, update code, systemd unit
├── docs/                        # operator docs (e.g. raspberry-pi-ops.md)
├── examples/                    # experimental scripts + fixtures/
├── tests/
├── requirements.txt             # uv export for Hugging Face Spaces
├── app.py                       # Gradio shim for Hugging Face Spaces
└── pyproject.toml
```

## Roadmap
- [x] Basic chatbot
- [x] GPT models implemented (OpenAI)
- [x] Conversational memory. Cache management
- [x] Tools functionality
- [x] Gradio UI
- [x] Speech-to-text tool
- [x] Basic API endpoints
- [x] Prompt Engineering - Jarvis background
- [x] User ID pt 1 - DB and secret DB
- [x] User ID pt 2 - Session wrapper class
- [x] MCP - Jarvis MCP Memory Agent
- [x] Upload to Render and expose API
- [x] Google Calendar API
- [x] LinkedIn reply drafting (Stage A: prefs YAML + draft tool + human confirmation)
- [x] Web search and public-page reading (`web_search_tool`)
- [x] JWT Token Security
- [x] Raspberry Pi / Server version
- [x] Remove legacy cloudflared / Firebase / Telegram API exposure (#30)
- [x] Remote API access — Tailscale host-layer docs (#31; named tunnel alternative only)
- [ ] Android app
- [ ] Multi-client management
- [ ] Security layer: MAC Address control
- [ ] Security layer: IP control and log
- [ ] Thread conversation management
- [ ] WhatsApp bot compatibility
- [ ] WhatsApp audio transcription and summarization
- [ ] Microphone - Audio prompting - Speech recognition
- [ ] Messenger: send messages between users.
- [ ] Tool to read PDFs or files
- [ ] RAG system. Vector DB
- [ ] Database implementation and interaction via LLM
- [ ] Fine-tuning functionality - Copy writting style
- [ ] Home devices control
- [ ] CrewAI functionality
- [ ] Prompt Engineering - Prompt injection detection
- [ ] Optimization: build LangGraph agent after identification
