# Project: Self-Healing Demo Agent (Built for Karumi)

## What We Are Building

A self-healing AI demo agent that crawls a SaaS product, builds a structured knowledge graph of its UI and flows, continuously monitors for changes, and autonomously repairs its own knowledge when the product UI drifts — without any human retraining.

This solves a real operational problem that Karumi (and any demo automation company) will hit at scale: SaaS products ship updates constantly. Every UI change breaks a hardcoded demo agent. This agent fixes itself.

---

## Core Systems

### 1. Crawler & Explorer

- Uses Playwright to open a browser, log in, and systematically navigate a SaaS product
- Discovers every page, interactive element, and navigation path
- Takes screenshots of each state
- Feeds everything into the Knowledge Graph

### 2. Knowledge Graph

- Stores the product's UI as a structured relational graph
- Nodes: pages, UI elements, features, flows
- Edges: navigation paths, dependencies, trigger relationships
- Example: `[Login] -> [Dashboard] -> [Create Project] -> [Setup Flow] -> [Aha Moment]`
- Stored in PostgreSQL initially, structured to migrate to Neo4j if needed

### 3. Drift Detector

- Runs on a schedule (cron)
- Re-visits every node in the knowledge graph
- Takes fresh screenshots and compares against stored state
- Two-level detection:
  - Visual diff: pixel-level comparison using pixelmatch
  - Semantic diff: Claude Vision decides if the change is meaningful
- Flags drifted nodes and triggers the self-healing loop

### 4. Self-Healing Loop

- Triggered when drift is detected on a node
- Agent autonomously re-explores the affected area and surrounding nodes
- Builds an updated subgraph
- Merges with existing knowledge graph
- Logs what changed, when, and what was repaired
- No human in the loop

### 5. Demo Narrator

- Given the current knowledge graph and a prospect persona or use case
- Generates a step-by-step narrated demo script
- Executes the demo path in a real browser via Playwright
- Output: structured demo flow with browser actions and narration text

---

## Tech Stack

| Layer                   | Technology                                            |
| ----------------------- | ----------------------------------------------------- |
| Browser Automation      | Playwright (Python)                                   |
| Backend / Orchestration | FastAPI                                               |
| Database                | PostgreSQL (via SQLAlchemy + Alembic)                 |
| Graph Storage           | PostgreSQL JSONB to start, Neo4j later                |
| Visual Diffing          | pixelmatch (via Node subprocess) or scikit-image SSIM |
| AI Reasoning Core       | Anthropic Claude (claude-sonnet via API)              |
| Screenshot Storage      | Local filesystem, S3-compatible later                 |
| Task Scheduling         | APScheduler or Celery + Redis                         |
| Containerization        | Docker + Docker Compose                               |
| Environment             | Python 3.11+                                          |

---

## Project Structure

```
demo-agent/
├── app/
│   ├── main.py                  # FastAPI entry point
│   ├── api/
│   │   ├── crawl.py             # POST /crawl - trigger a crawl
│   │   ├── graph.py             # GET /graph - return knowledge graph
│   │   ├── drift.py             # GET /drift - run drift detection
│   │   └── demo.py              # POST /demo - generate demo for a persona
│   ├── core/
│   │   ├── crawler.py           # Playwright crawler logic
│   │   ├── graph_builder.py     # Builds and updates the knowledge graph
│   │   ├── drift_detector.py    # Visual + semantic diff logic
│   │   ├── healer.py            # Self-healing loop
│   │   └── narrator.py          # Demo script generator
│   ├── models/
│   │   ├── node.py              # Graph node schema
│   │   ├── edge.py              # Graph edge schema
│   │   └── drift_log.py         # Drift event log schema
│   ├── services/
│   │   ├── claude.py            # Claude API wrapper
│   │   ├── screenshot.py        # Screenshot capture and storage
│   │   └── diff.py              # Visual diffing utilities
│   ├── db/
│   │   ├── session.py           # SQLAlchemy session
│   │   └── base.py              # Base model
│   └── scheduler/
│       └── jobs.py              # Scheduled drift detection jobs
├── alembic/                     # DB migrations
├── screenshots/                 # Stored screenshots per node
├── tests/
├── docker-compose.yml
├── Dockerfile
├── .env
├── requirements.txt
└── CONTEXT.md                   # This file
```

---

## Database Schema

### nodes

```sql
id UUID PRIMARY KEY
product_id UUID
url TEXT
title TEXT
screenshot_path TEXT
html_snapshot TEXT
elements JSONB          -- list of interactive elements found on page
metadata JSONB          -- page type, depth, tags
created_at TIMESTAMP
updated_at TIMESTAMP
```

### edges

```sql
id UUID PRIMARY KEY
from_node_id UUID REFERENCES nodes(id)
to_node_id UUID REFERENCES nodes(id)
trigger TEXT            -- what action causes this transition (click, form submit, etc)
metadata JSONB
created_at TIMESTAMP
```

### drift_logs

```sql
id UUID PRIMARY KEY
node_id UUID REFERENCES nodes(id)
detected_at TIMESTAMP
visual_diff_score FLOAT -- 0.0 = identical, 1.0 = completely different
semantic_diff TEXT      -- Claude's description of what changed
healed BOOLEAN
healed_at TIMESTAMP
```

### products

```sql
id UUID PRIMARY KEY
name TEXT
base_url TEXT
login_url TEXT
credentials JSONB       -- encrypted
created_at TIMESTAMP
```

---

## Key Flows

### Crawl Flow

```
POST /crawl { url, credentials }
  -> Playwright opens browser
  -> Logs in
  -> BFS traversal of all reachable pages
  -> For each page:
      -> Take screenshot
      -> Extract all interactive elements (buttons, links, forms, inputs)
      -> Ask Claude: "What is this page? What is its purpose? What is the key action here?"
      -> Store as node in knowledge graph
      -> Store edges for all navigation paths discovered
  -> Return graph summary
```

### Drift Detection Flow

```
Scheduler triggers every N hours
  -> For each node in graph:
      -> Playwright navigates to node URL
      -> Takes fresh screenshot
      -> pixelmatch compares to stored screenshot
      -> If visual_diff_score > threshold:
          -> Claude Vision compares old vs new screenshot
          -> Claude decides: meaningful change or cosmetic?
          -> If meaningful: flag node as drifted, trigger healer
          -> Log drift event
```

### Self-Healing Flow

```
Healer triggered on drifted node
  -> Playwright re-explores node and N surrounding nodes
  -> Rebuilds subgraph for affected area
  -> Claude reconciles old graph with new observations
  -> Merges updated subgraph into main knowledge graph
  -> Updates screenshots
  -> Marks drift_log as healed
  -> Logs summary of what changed
```

### Demo Narration Flow

```
POST /demo { product_id, persona }
  -> Load current knowledge graph for product
  -> Claude reasons over graph: "Given this persona, what is the ideal demo path?"
  -> Returns ordered list of nodes with narration for each step
  -> Playwright executes path in browser
  -> Each step returns: action, screenshot, narration text
```

---

## Claude Usage Patterns

### Page Understanding (during crawl)

```python
prompt = """
You are analyzing a screenshot of a SaaS product page.

Page URL: {url}
HTML elements found: {elements}

Answer the following:
1. What is this page called?
2. What is its primary purpose?
3. What is the most important action a user takes here?
4. What page does the primary action lead to?
5. Is this a key moment in the user journey? (onboarding, aha moment, core feature)

Respond in JSON.
"""
```

### Semantic Diff (during drift detection)

```python
prompt = """
You are comparing two screenshots of the same page in a SaaS product.

The visual diff score is {score} (0 = identical, 1 = completely different).

Old screenshot: [image]
New screenshot: [image]

Answer the following:
1. What changed between these two screenshots?
2. Is this a meaningful functional change or a cosmetic change?
3. If meaningful: which user flows might be affected?
4. Severity: low / medium / high

Respond in JSON.
"""
```

### Demo Path Generation

```python
prompt = """
You are a world-class SaaS sales engineer.

You have access to the following knowledge graph of a product:
{graph}

Your prospect is: {persona}

Generate the ideal demo path for this prospect. Focus on reaching the "aha moment" as fast as possible.

Return an ordered list of steps. Each step:
- node_id: the graph node to navigate to
- action: what to do on this page
- narration: what to say to the prospect at this moment (natural, conversational, not salesy)

Respond in JSON.
"""
```

---

## Environment Variables

```env
DATABASE_URL=postgresql://user:password@localhost:5432/demo_agent
ANTHROPIC_API_KEY=your_key_here
SCREENSHOT_DIR=./screenshots
DRIFT_CHECK_INTERVAL_HOURS=6
DRIFT_VISUAL_THRESHOLD=0.05
PLAYWRIGHT_HEADLESS=true
```

---

## Build Order

### Week 1: Crawler

- [ ] Project setup, Docker, FastAPI boilerplate
- [ ] Playwright integration
- [ ] Basic BFS crawler that maps pages and elements
- [ ] Claude page understanding integration
- [ ] Knowledge graph storage in PostgreSQL
- [ ] GET /graph endpoint returning current graph

### Week 2: Drift Detector

- [ ] Screenshot storage and retrieval
- [ ] pixelmatch visual diffing
- [ ] Claude semantic diff integration
- [ ] Drift detection runner
- [ ] drift_logs table and logging
- [ ] GET /drift endpoint to trigger manually

### Week 3: Self-Healing Loop

- [ ] Healer module triggered on drift events
- [ ] Subgraph re-exploration logic
- [ ] Graph merge logic
- [ ] Healing confirmation and logging
- [ ] APScheduler for automated drift checks

### Week 4: Demo Narrator + Dashboard

- [ ] Demo path generation via Claude
- [ ] Playwright demo execution
- [ ] POST /demo endpoint
- [ ] Simple React dashboard showing:
  - Current graph visualization
  - Drift events log
  - Healing history
  - Demo playback

---

## What Makes This Different From a Normal Crawl Bot

A normal crawler maps a website. This agent:

1. **Understands** the product semantically, not just structurally
2. **Monitors** itself for staleness continuously
3. **Repairs** itself without human input
4. **Reasons** about user journeys, not just page structure
5. **Narrates** demos dynamically based on prospect context

The knowledge graph is a living document. It stays current because the agent maintains it.

---

## Who This Is Built For

This is a proof of concept built to demonstrate deep understanding of Karumi's problem space and technical approach. Karumi builds AI agents that deliver personalized SaaS demos autonomously. This project solves the next hard problem in that space: keeping the agent's product knowledge accurate as products evolve.

Built by Rafid — SWE at Visa, building in the AI agent space independently.
