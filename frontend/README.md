# Frontend: Network Knowledge Assistant

Web chat client for field engineers and NOC operators. An engineer describes a device and a symptom
("TRN-031: SFP replaced, link up but no traffic") and gets a streamed answer plus **knowledge cards**: the steps
to take, what to avoid, which devices the tip applies to, how sure we are, and the original expert sources
(Teams chats, emails, calls). Engineers rate the advice, and their feedback flows back into the knowledge graph.

It is the user interface of the Elisa × Since AI 2026 project; the API it talks to lives in [`../backend`](../backend).

---

## Contents

1. [Features](#features)
2. [Architecture](#architecture)
3. [Tech stack](#tech-stack)
4. [Getting started](#getting-started)
5. [Configuration](#configuration)
6. [Scripts](#scripts)
7. [Project structure](#project-structure)
8. [Backend integration](#backend-integration)
9. [Testing](#testing)
10. [Development workflow (Lovable)](#development-workflow-lovable)
11. [Building and deployment](#building-and-deployment)
12. [Troubleshooting](#troubleshooting)
13. [Design and accessibility](#design-and-accessibility)
14. [Known limitations](#known-limitations)

---

## Features

| Area | What it does |
|---|---|
| **Chat** | Streams the answer token by token (Server-Sent Events) with a typing indicator; Stop aborts the request; Retry after errors. Markdown is rendered and sanitised. |
| **Knowledge cards** | Type and status badges (✅ Confirmed · ⚠️ Disputed · 🕓 Outdated · ❓ Unconfirmed), confidence meter, numbered steps, ⛔ avoid list, scope ("Transmission nodes installed before 2020, firmware below 3.4"), validity period, copyable details (codes, part numbers) and expandable source quotes. |
| **Special states** | "What didn't work" (failed attempts attached to the fix), "Experts disagree" (conflicting opinions side by side), firmware notes ("Not needed on TRN-077" / "Not yet on TRN-031, upgrade fixes this"), and a clear "no captured knowledge" state. |
| **Device panel** | Device facts, all knowledge that applies to the device, and an event timeline (alarms, work orders, firmware upgrades, hardware replacements, dispatches). Opens from any device chip. |
| **Feedback** | 👍 This worked · 👎 Didn't work · ⏭ Skip on every card, plus an optional "What actually happened?" note that the backend turns into new knowledge. |
| **Mock mode** | Complete built-in sample data (real cases from our dataset), so the UI works and can be demoed without the backend. |
| **Usability** | Light/dark mode, phone layout (≥ 375 px, side panels become drawers), keyboard navigation, reduced-motion support, recent chats kept in the browser. |

## Architecture

```
┌──────────────────────── Browser ────────────────────────┐
│  React UI (TanStack Start + Vite)                       │
│    components/assistant/*  ── hooks/use-chat, use-stats │
│                │                                        │
│          src/api/index.ts  (picks the client)           │
│           ├── mock.ts + mockData.ts   (mock mode)       │
│           └── client.ts + sse.ts + adapter.ts (live)    │
└────────────────────────────┬────────────────────────────┘
                             │ HTTP / SSE (JSON)
                             ▼
              FastAPI backend  (../backend, port 8000)
              understand (Gemini) → retrieve (Neo4j) → answer (Gemini)
```

- **One interface, two clients.** `mock` and `live` clients implement the same `ApiClient` interface
  (`src/api/types.ts`), so components never know which one is active.
- **Adapter layer.** The backend's JSON contract is converted to the UI's internal types in one place,
  `src/api/adapter.ts`. If the backend contract changes, only the adapter (and its tests) need updating.
- **No backend logic in the frontend.** No database, auth or server functions: everything comes from the API.

## Tech stack

| | |
|---|---|
| Framework | React 19, [TanStack Start](https://tanstack.com/start) (file-based routing, SSR) on Vite 8 |
| Language | TypeScript 5 |
| Styling | Tailwind CSS 4, shadcn/ui (Radix UI primitives), lucide-react icons |
| Markdown | react-markdown + remark-gfm (no raw HTML) |
| Tests | Vitest + Testing Library (jsdom) |
| Package manager | **npm 11+** or **Bun** (Lovable uses Bun; `bun.lock` is the committed lockfile) |
| Generated with | [Lovable](https://lovable.dev), see [workflow](#development-workflow-lovable) |

## Getting started

### Prerequisites

| Tool | Required version | Check | Why |
|---|---|---|---|
| **Node.js** | **22.12.0 or newer** (22 LTS or 24 LTS recommended) | `node -v` | TanStack Start requires `>=22.12.0` (Vite 8 alone would accept 20.19) |
| **npm** | **11 or newer** | `npm -v` | npm **10 fails** on this project with `Cannot read properties of null (reading 'edgesOut')` (an npm 10 dependency-resolution bug); npm 11.21 and 12.2 were verified to install it |
| *or* **Bun** | 1.x | `bun --version` | Alternative to npm; what Lovable uses |

For live mode you also need the backend running on `http://localhost:8000` (see [`../backend/README.md`](../backend/README.md)).

#### Updating Node.js and npm

**Node.js** (with [nvm](https://github.com/nvm-sh/nvm); this folder has an `.nvmrc`):

```bash
nvm install          # installs the version in .nvmrc (22)
nvm use              # switches this terminal to it
node -v              # v22.12.0 or newer
```

On Windows use [nvm-windows](https://github.com/coreybutler/nvm-windows) (`nvm install 22` then `nvm use 22`) or the
installer from [nodejs.org](https://nodejs.org) (LTS).

**npm** (Node 22 ships with npm 10, so upgrade it once):

```bash
npm install -g npm@11
npm -v               # 11.x
```

npm 12 also works but needs Node `^22.22.2 || ^24.15.0 || >=26`; npm 11 works with any Node 22.12+.

**Bun** (optional, instead of npm):

```bash
curl -fsSL https://bun.sh/install | bash        # macOS / Linux
powershell -c "irm bun.sh/install.ps1 | iex"     # Windows
```

### Install and run

With **npm**:

```bash
cd frontend
npm install
cp .env.example .env.local      # Windows: copy .env.example .env.local   (then edit if needed, see Configuration)
npm run dev
```

With **Bun**:

```bash
cd frontend
bun install
cp .env.example .env.local
bun run dev
```

> `npm install` creates a `package-lock.json`. Don't commit it: the committed lockfile is `bun.lock` (Lovable's),
> and two lockfiles would drift apart. It is ignored in the root `.gitignore`.

Open **http://localhost:8080**. The header badge shows the mode: **Live** (backend reachable), **Mock**
(sample data) or **Offline** (live mode but the backend can't be reached).

### Quick check with the backend

1. Start the backend: `cd backend && uvicorn api.main:app --reload --port 8000`
2. Start the frontend as above and confirm the badge says **Live**.
3. Click the example "TRN-031: SFP replaced, link up but no traffic…": the answer should stream in,
   followed by the bounce-interface card with 4 sources and a "What didn't work" section.

## Configuration

### Environment variables (`.env.local`, not committed)

| Variable | Example | Meaning |
|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8000` | Default backend address. |
| `VITE_USE_MOCK` | `false` | `true` forces mock mode. If no API URL is set, mock mode is used anyway. |

Values are read at **build/dev-server start**: restart the dev server after changing them.

### Settings dialog (⚙ in the header)

At runtime the API address and the mock switch can be changed in **Settings** ("Test connection" calls
`/api/health`). Saved values are stored in the browser (`localStorage` keys `apiBaseUrl`, `useMock`) and
**take precedence over the environment variables**. "Reset to defaults" clears them.

Precedence: **Settings (saved in this browser) → `.env.local` → mock mode.**

This lets one build be pointed at a different backend (for example a tunnel URL on demo day) without rebuilding.

## Scripts

Use `npm run <script>` or `bun run <script>`; they are the same scripts.

| Script | What it does |
|---|---|
| `dev` | Development server with hot reload (http://localhost:8080) |
| `build` | Production build |
| `build:dev` | Build in development mode (easier debugging) |
| `preview` | Serve the production build locally |
| `test` | Run the test suite once |
| `test:watch` | Tests in watch mode |
| `lint` | ESLint |
| `format` | Prettier (writes changes) |

## Project structure

```
frontend/
├── src/
│   ├── api/                    # everything that talks to (or imitates) the backend
│   │   ├── index.ts            # settings (env + localStorage), picks mock or live client
│   │   ├── types.ts            # internal types used by the UI (ApiClient, KnowledgeCard, …)
│   │   ├── client.ts           # live client: fetch, SSE streaming, JSON fallback
│   │   ├── sse.ts              # incremental Server-Sent Events parser
│   │   ├── adapter.ts          # backend JSON → internal types (single point of contract mapping)
│   │   ├── mock.ts             # mock client (same interface, simulated streaming)
│   │   └── mockData.ts         # sample answers, cards, devices, events
│   ├── components/
│   │   ├── assistant/          # app shell and screens
│   │   │   ├── AssistantApp.tsx     # layout: header, sidebar, chat, device panel
│   │   │   ├── MessageList.tsx      # chat messages, streaming, errors
│   │   │   ├── Composer.tsx         # input, device selector, send/stop
│   │   │   ├── EmptyState.tsx       # greeting + example prompts
│   │   │   ├── DevicePanel.tsx      # device facts, knowledge, event timeline
│   │   │   └── SettingsDialog.tsx   # API address, mock switch, connection test
│   │   ├── KnowledgeCard.tsx   # the knowledge card and its special states
│   │   ├── FeedbackBar.tsx     # 👍 / 👎 / ⏭ + optional comment
│   │   └── ui/                 # shadcn/ui primitives (generated; avoid editing)
│   ├── hooks/                  # use-chat (conversation + streaming), use-api-status, use-stats, use-mobile
│   ├── lib/                    # chat-store (localStorage), device-refs (ID detection), error handling, utils
│   ├── routes/                 # TanStack file-based routes (__root.tsx, index.tsx)
│   ├── test/                   # Vitest tests (adapter, settings, cards, device panel, mock API, routing)
│   ├── router.tsx, start.ts, server.ts   # TanStack Start entry points
│   └── styles.css              # Tailwind + theme tokens (light/dark)
├── public/                     # static files
├── .env.example                # template for .env.local
├── .nvmrc                      # Node version for `nvm use`
├── package.json, bun.lock, bunfig.toml
├── vite.config.ts, vitest.config.ts, tsconfig.json, eslint.config.js, components.json
└── README.md
```

Generated files you should not edit by hand: `src/routeTree.gen.ts`, `src/components/ui/*` (regenerate with shadcn instead).

## Backend integration

All requests go to `${apiBaseUrl}` (see [Configuration](#configuration)); the backend allows cross-origin
requests from any origin. The full contract is in [`../backend/api/README.md`](../backend/api/README.md) and live at
http://localhost:8000/docs.

| Method | Path | Used for |
|---|---|---|
| `POST` | `/api/chat` | Ask a question. Response is an SSE stream: `meta` → `token`… → `cards` → `done` (or `error`). Falls back to plain JSON if the server doesn't stream. |
| `GET` | `/api/nodes` | Device selector |
| `GET` | `/api/nodes/{node_id}` | Device panel (facts, knowledge, events) |
| `GET` | `/api/stats` | Header counter ("28 tips · 25 devices · 33 sources") |
| `POST` | `/api/feedback` | 👍 / 👎 / ⏭ and comments (`verdict`: `worked` \| `failed` \| `skipped`) |
| `GET` | `/api/health` | Connection badge and the "Test connection" button |

Chat request body:

```json
{ "conversation_id": null, "message": "TRN-031: SFP replaced, link up but no traffic", "node_id": "TRN-031" }
```

Notes:
- `conversation_id` from the `meta` event is sent with follow-up questions so the backend keeps context.
- `message_id` from the `done` event is sent with feedback so it applies to every merged assertion behind a card.
- Timeouts: 60 s for chat, 10 s for other calls. When the backend is unreachable, a banner appears and
  `/api/health` is retried with backoff.

## Testing

```bash
npm run test        # or: bun run test
```

The suite covers the backend adapter (all contract shapes), settings precedence, knowledge-card states, the
device panel, the mock API and routing. Add an adapter test whenever the backend contract changes.

Manual checklist before a demo:

- [ ] Each example prompt streams an answer and shows the expected cards (mock **and** live).
- [ ] TRN-031: bounce-fix card with sources and "What didn't work"; firmware 3.4 card with "Upgrade fixes this".
- [ ] MW-405: "Experts disagree" with both opinions; TRN-042 access: lockbox code with working copy button.
- [ ] Device panel opens from any device chip; TRN-077 shows the greyed "Not needed" card.
- [ ] Feedback buttons highlight; a comment of 8+ characters shows "will be added to the knowledge base".
- [ ] Phone width (375 px), dark mode, Stop during streaming, backend stopped → "Offline" banner.

## Development workflow (Lovable)

This app was generated and is maintained with **Lovable**. Lovable keeps its own GitHub repository in sync with
the Lovable editor; that repository is the **source of truth** for the frontend code. This `frontend/` folder is a
copy of it.

```
Lovable editor  ⇄  Lovable repository (two-way sync, branch main)
                            │ copy (rsync)
                            ▼
                 this repository: frontend/
```

**Rules**

1. Make UI changes in **Lovable** (or in the Lovable repository). Changes made directly in `frontend/` are
   overwritten by the next copy, unless they are also made in the Lovable repository.
2. Do not copy Lovable-only files into this repository: `.git`, `node_modules`, `.env.local`, `.lovable/`,
   `AGENTS.md`, `roadmap.md` and Lovable's generic `README.md`.
3. Never commit `.env.local`.

**Updating `frontend/` from the Lovable repository** (run from the root of this repository; adjust the path to
your clone of the Lovable repository):

```bash
LOVABLE_REPO=~/workspace/UI
(cd "$LOVABLE_REPO" && git pull)

rsync -av --delete \
  --exclude .git --exclude node_modules --exclude .env.local \
  --exclude .lovable --exclude AGENTS.md --exclude roadmap.md \
  --exclude README.md --exclude .env.example --exclude .nvmrc \
  "$LOVABLE_REPO"/ frontend/

git checkout -b frontend-update
git add frontend
git commit -m "frontend: sync from Lovable"
git push -u origin frontend-update      # then open a pull request
```

`--exclude README.md --exclude .env.example --exclude .nvmrc` keeps this README, the env template and the Node
version file, which exist only here. Tip: keep the whole `rsync` command on one line if your terminal breaks
multi-line pastes; if rsync reports `total size is 0`, the source path was lost and nothing was copied.

## Building and deployment

```bash
npm run build        # or: bun run build
npm run preview      # check the production build locally
```

TanStack Start builds with Nitro (Cloudflare target by default, see `vite.config.ts`); the output is in `.output/`.

**Demo options**

| Option | How | Notes |
|---|---|---|
| Local (most reliable) | Backend + `npm run dev` on the same laptop | No network dependencies apart from Neo4j and Gemini. |
| Lovable hosting | **Publish** in Lovable (`*.lovable.app`) | Runs in mock mode unless pointed at a reachable backend. |
| Hosted UI + local backend | `cloudflared tunnel --url http://localhost:8000` (or `ngrok http 8000`), then enter the tunnel URL in ⚙ Settings | The backend's CORS settings already allow Lovable domains. |

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `npm install` → `Cannot read properties of null (reading 'edgesOut')` | You are on npm 10. Upgrade: `npm install -g npm@11`, then `rm -rf node_modules package-lock.json && npm install`. Or use `bun install`. |
| `npm install` / `npm run dev` complains about the Node version (`EBADENGINE`, `Unsupported engine`) | Node is older than 22.12. Run `nvm install && nvm use` in `frontend/` (or install Node 22 LTS). |
| Badge stays **Mock** | No API URL configured, or "Use mock data" is on. Set `VITE_API_BASE_URL` in `.env.local` and restart, or set it in ⚙ Settings (saved values win; use "Reset to defaults"). |
| Badge **Offline** / "Can't reach the knowledge service" | Backend not running or wrong URL. Check `curl http://localhost:8000/api/health`. |
| Answers look like templates, `meta.understood_by` is `fallback` | The backend can't reach Gemini (key, model or quota). See the backend log and `/api/health?deep=true`. |
| "Knowledge service error" in the chat | Backend error; usually Neo4j settings missing (`backend/.env`) or the database is unreachable. |
| "This page didn't load" | A rendering error. Open the browser console (F12) for the message; if it mentions a missing field, the backend contract changed: update `src/api/adapter.ts` and its tests. |
| Network URL (`http://<laptop-ip>:8080`) fails | Use `http://localhost:8080` on the laptop. For a phone, also start the backend with `--host 0.0.0.0` and set the API URL to the laptop's IP. |
| Port 8080 already in use | Stop the other process, or run `npm run dev -- --port 5173`. |

## Design and accessibility

- Calm operational look: slate neutrals with one deep-blue accent; status colours (green, amber, red, grey) are
  only used for meaning and always paired with an icon and a label.
- Monospace for device IDs, firmware versions and codes; timestamps in Europe/Helsinki.
- Keyboard navigable with visible focus, ARIA labels on icon buttons, WCAG AA contrast in light and dark mode,
  tap targets ≥ 44 px, `prefers-reduced-motion` respected.

## Known limitations

- Chat history is stored only in the browser (`localStorage`); the backend keeps conversation context in memory.
- No authentication: intended for a demo or an internal network.
- Mock data covers five demo scenarios; any other question returns "No captured expert knowledge".
- The UI language is English; answers follow the language of the question (English or Finnish).
