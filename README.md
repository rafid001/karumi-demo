# Self-Healing Demo Agent

> Built as a proof of concept for Karumi — a solution to a real operational problem that every AI demo agent hits at scale.

---

## The Problem

Karumi's AI agent learns a SaaS product and delivers live personalized demos to prospects. But SaaS products ship updates constantly. Copy changes. Buttons move. Features get added or renamed.

Every time that happens, the agent's internal understanding of the product goes stale. It either demos something that no longer exists, or misses a new feature entirely. At one or two products, you notice and fix it manually. At fifty customers, it becomes an operational bottleneck.

**There's no public solution to this problem. So I built one.**

---

## What This Does

A self-healing demo agent that:

1. **Crawls a product** and builds a structured knowledge graph of every page, flow, and interactive element — understood semantically, not just mapped structurally
2. **Monitors itself** by periodically re-visiting every node in its knowledge graph and comparing against the stored baseline
3. **Detects meaningful drift** — distinguishing a real functional change ("the CTA changed from Get Started to Start Free Trial") from cosmetic noise ("a pixel shifted")
4. **Heals itself autonomously** — re-explores affected pages, rebuilds the relevant subgraph, and updates its own knowledge without any human intervention

No retraining. No manual fix. The agent stays current on its own.

---

## How It Works

### 1. Crawl & Knowledge Graph

The agent opens a real browser, logs into the product, and performs a BFS traversal of every reachable page. For each page it finds, it:

- Extracts all interactive elements (buttons, links, forms, inputs)
- Takes a screenshot for visual baseline
- Asks an LLM: _"What is this page for? What's the key action here? Where does it lead?"_
- Stores everything as a node in a relational knowledge graph (PostgreSQL)

The result is a living map of the product that understands _what_ each page does, not just _that_ it exists.

![Knowledge Graph](./docs/knowledge-graph.png)

The graph above shows the "Pulse" demo product mapped across 4 pages: Homepage, Projects, Team, and Settings — with 12 navigation edges between them. Each node shows the page's purpose, primary CTA, and whether it's a key moment in the user journey.

---

### 2. Drift Detection

On a schedule (or triggered manually), the agent re-visits every node, takes a fresh screenshot, and runs a two-layer comparison:

- **Visual diff** (pixelmatch): fast pixel-level check. If the diff score exceeds a threshold, escalate to semantic analysis.
- **Semantic diff** (LLM Vision): the model looks at old vs new screenshots and decides — is this a meaningful functional change or cosmetic noise? It outputs the specific changes, which user flows are affected, and a severity rating.

Only meaningful changes get flagged. Cosmetic changes are ignored.

![Drift Events](./docs/drift-events.png)

In this example, the agent detected:

- The hero heading changed from _"Manage your team's work in one place"_ to _"The fastest way to ship with your team"_
- The CTA changed from "Get Started" to "Start Free Trial" + "Book a Demo"
- A new team member was added and a search bar appeared on the Team page
- **Settings page: zero drift detected** — the control page that didn't change correctly registered nothing

That last point matters. The detector isn't flagging everything. It's actually telling the difference.

---

### 3. Self-Healing

When meaningful drift is detected, the healer kicks in automatically:

- Re-explores the affected node and its neighbors
- Rebuilds the updated subgraph
- Merges it into the existing knowledge graph
- Logs exactly what changed, what was updated, and when

![Healing History](./docs/healing-history.png)

The healing history above shows two pages healed: Homepage (8 edges updated) and Team (metadata updated across 3 related nodes including Projects and Settings — because the agent understands graph relationships, not just the one flagged page).

No human was involved. The agent diagnosed and fixed itself.

---

### 4. Interactive Dashboard

Everything above is accessible from a single UI:

- **Run Agent tab**: paste a URL, watch it crawl live page by page, or re-check any previously crawled product for drift with one click
- **Knowledge Graph tab**: visual interactive graph of the current product understanding
- **Drift Events tab**: full log of detected changes with semantic descriptions and severity
- **Healing History tab**: log of every self-healing event with a summary of what the agent updated

![Run Agent](./docs/run-agent.png)

---

## Stack

| Layer              | Technology                 |
| ------------------ | -------------------------- |
| Browser Automation | Playwright (Python)        |
| Backend            | FastAPI                    |
| Database           | PostgreSQL + SQLAlchemy    |
| Visual Diffing     | pixelmatch                 |
| Semantic Reasoning | LLM Vision (Claude / Groq) |
| Scheduling         | APScheduler                |
| Frontend           | React + Vite               |
| Infra              | Docker + Docker Compose    |

---

## Why This Matters for Karumi

Karumi's core value prop is delivering the "aha moment" instantly, 24/7, at scale. That value prop degrades silently every time a customer ships a product update and the agent doesn't know about it.

This project is a working prototype of the infrastructure layer that keeps a demo agent accurate over time — automatically. The crawler, knowledge graph, drift detector, and self-healing loop are all functional and tested against a real multi-page product.

It was built in two weeks, outside of a full-time job, specifically because I thought it was the most honest way to say I want to work on this problem for real.

---

## Running Locally

```bash
# Clone the repo
git clone https://github.com/yourusername/demo-agent
cd demo-agent

# Start the backend
docker-compose up -d

# Install and run the frontend
cd ui
npm install
npm run dev

# Visit the dashboard
open http://localhost:5173/ui
```

Requires an Anthropic or Groq API key in `.env`:

```env
ANTHROPIC_API_KEY=your_key_here
DATABASE_URL=postgresql://user:password@localhost:5432/demo_agent
```

---

## Built by

Rafid — SWE at Visa, building in the AI agent space independently.

[LinkedIn](https://linkedin.com/in/yourhandle) · [GitHub](https://github.com/yourusername)
