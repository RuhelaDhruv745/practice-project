# Technology Stack

Keep it small: every tool here maps to a requirement or a deliverable.

## Chosen stack

| Layer | Choice | Why | Owner |
|---|---|---|---|
| Language (backend) | Python 3.13 | Team skill; Pydantic/FastAPI; one env for all Python modules | All Python members |
| API | FastAPI + Pydantic v2 | Typed contracts, automatic OpenAPI for the React types | M1 |
| Persistence | SQLAlchemy 2 + SQLite | Zero setup now; PostgreSQL-compatible models for later | M1 |
| Policy | Plain Python rules + YAML (PyYAML) | Deterministic, explainable, policy editable without code | M3 |
| LLM | `anthropic` SDK (Claude, default) + `openai` SDK (Groq fallback, OpenAI-compatible) | Structured JSON output; provider switch by `LLM_PROVIDER` (PS risk table) | M2 |
| Reviewer UI (PS deliverable) | Streamlit | PS deliverable #1 is "A Streamlit app"; fastest working reviewer screen | M4 |
| Dashboard UI | React + TypeScript + Vite, Tailwind CSS, shadcn/ui, React Query, React Router | Richer reviewer dashboard; typed API client generated from OpenAPI | M4 |
| Python tests | pytest (+ FastAPI `TestClient`/httpx) | Unit, API, integration; LLM always mocked | M1, M2, M3, M5 |
| Frontend tests | Vitest + React Testing Library; Playwright for e2e | Component and browser workflow tests | M4, M5 |
| Lint/format | ruff (Python); ESLint + Prettier (frontend) | One formatter per language | All |
| Containers | Docker + Docker Compose | `docker compose up --build` reproducible run | M5 |
| CI/CD | GitHub Actions | Source is on GitHub | M5 |
| Cloud (optional) | Azure Container Apps; App Service for Containers as alternative; Azure Container Registry | Managed containers without Kubernetes | M5 |
| Config/secrets | `.env` via python-dotenv locally; platform secrets in Azure | Secrets never in the repo | A, M5 |

## Versions and tooling

| Tool | Version on the lead's machine | Note |
|---|---|---|
| Python | 3.13.1 (`py -3.13`); default `python` is 3.12 | Use `.venv` created with 3.13 |
| Node / npm | 22.9.0 / 11.3.0 | Node 22 LTS for the frontend |
| Docker / Compose | 28.1.1 / 2.35.1 | Docker Desktop must be running |
| GitHub CLI | 2.106.0 | |
| Azure CLI | not installed | `winget install -e --id Microsoft.AzureCLI` |
| make | **not installed on Windows** | Use the commands in `docs/DEVELOPMENT_GUIDE.md`, or `winget install ezwinports.make` |

## Dependency rules

- Each module lists its own Python dependencies in `<module>/requirements.txt`; the root
  `requirements.txt` only includes them. Members change only their own file.
- Adding a dependency needs a line in the PR description saying why.
- Dev-only tools (pytest, ruff) go in `requirements-dev.txt` (architect-owned).

## Decisions

| Decision | Options considered | Chosen | Reason |
|---|---|---|---|
| UI | Streamlit only / React only / both | Both, as thin API clients | Streamlit satisfies the PS deliverable; React is the richer dashboard; neither holds logic |
| LLM provider | Claude only / Groq only / configurable | Configurable, Claude default, Groq fallback | PS risk table asks for provider switch through configuration |
| Validator owner | AI member / policy member | Policy member (M3) | The generator must not grade its own output |
| Database | SQLite / PostgreSQL | SQLite with SQLAlchemy | No setup; migration path kept |
| Python layout | Package per module / single app | Top-level packages (`backend`, `policy_engine`, `ai_engine`, `contracts`) in one environment | Exclusive folder ownership, simple imports |

## Not used, and why

| Technology | Why not |
|---|---|
| Vector database / RAG | Facts come from structured data; no retrieval problem |
| Message queue | One reviewer-driven message at a time; no bulk sending (out of scope) |
| Kubernetes | Container Apps covers hosting; too heavy for a hackathon |
| Real email provider / SMTP | Real delivery is out of scope; mock outbox only |
| ML segmentation / churn models | Out of scope; rules must be explainable |
| Extra MCP servers / plugins | Only add when a concrete need appears |
