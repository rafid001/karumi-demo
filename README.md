# Self-Healing Demo Agent

Autonomous SaaS demo agent that crawls products, builds a knowledge graph, detects UI drift, and self-heals.

## Quick Start

```bash
cp .env.example .env
# Add your GROQ_API_KEY (default), GOOGLE_API_KEY (Gemini), or ANTHROPIC_API_KEY (Claude)

docker compose up --build
```

API runs at `http://localhost:8000`. Docs at `http://localhost:8000/docs`.

## LLM Provider

Groq is the default (fast, generous free tier). Switch providers via `.env`:

```env
# Groq (default) — vision + text
LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_key_here

# Gemini
LLM_PROVIDER=gemini
GOOGLE_API_KEY=your_gemini_key_here

# Claude
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=your_claude_key_here
```

## Week 1 Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/crawl` | Trigger BFS crawl of a SaaS product |
| GET | `/graph` | Return knowledge graph (all products or by `product_id`) |
| GET | `/drift` | Run drift detection against stored baselines |
| GET | `/drift/logs` | List recent drift events |
| POST | `/demo` | Demo generation (Week 4 stub) |

## Example: Crawl a Product

```bash
curl -X POST http://localhost:8000/crawl \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "product_name": "Example SaaS",
    "max_pages": 10
  }'
```

## Local Development (without Docker)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# Start PostgreSQL locally, then:
uvicorn app.main:app --reload
```

## Project Structure

See `context.md` for full architecture, flows, and build roadmap.
