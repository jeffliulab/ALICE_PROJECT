# Generative Agents — Modern Reproduction

A modern, faithful reproduction of [**"Generative Agents: Interactive Simulacra of Human Behavior"**](https://arxiv.org/abs/2304.03442) (Park et al., UIST 2023) — the landmark paper that demonstrated believable AI agents living in a virtual town called Smallville.

This project **reproduces the complete cognitive architecture** described in the original paper using a modern tech stack, with local LLM inference via Ollama for zero-cost operation.

> **Note on ALICE PROJECT:** This reproduction serves as the technical foundation for **ALICE PROJECT**, an AI-driven social simulation currently under active development. The ALICE PROJECT source code is not yet public. It will be released in stages as the project reaches milestone goals. See [ALICE PROJECT](#alice-project) section below.

---

## What This Reproduction Implements

- **Complete Cognitive Loop**: `perceive → retrieve → plan → reflect → execute` — every module faithfully reimplemented from the original paper
- **Three-Factor Memory Retrieval**: Recency (exponential decay) + Importance (LLM-scored 1–10) + Relevance (embedding cosine similarity), with min-max normalization and configurable weights `[0.5, 3, 2]`
- **Three-Level Plan Decomposition**: Daily plan → Hourly schedule → 5–15 minute subtask decomposition (the level most reproductions miss)
- **Full Reaction System**: Self-event filtering → chat/wait/ignore decision → conversation generation → schedule replanning
- **Reflection with Evidence**: Triggered by importance threshold, generates focal questions, retrieves evidence, produces insights stored as thought nodes with evidence chain links
- **Iterative Conversation** (`agent_chat_v2`): Turn-by-turn dialogue with per-turn memory retrieval, relationship summarization, and `[END]` detection
- **Original Smallville World**: 25 agents, 140×100 tile map, 285 address mappings, all loaded from the paper's original data format

---

## Architecture Comparison

| Aspect | Original Paper | This Reproduction |
|--------|---------------|-------------------|
| **LLM** | GPT-3.5 (cloud, ~$1000/2 days) | Ollama + Qwen3 14B (local, free) |
| **Backend** | Django + file-based IPC | FastAPI + REST API |
| **Frontend** | Phaser.js + Django templates | Phaser 3 + React + Vite |
| **Simulation** | Live only (slow) | **Simulate + Replay** split |
| **Data Format** | Custom CSV + pickle | JSON throughout |
| **Embedding** | OpenAI ada-002 (cloud) | sentence-transformers MiniLM (local, free) |

---

## Simulate + Replay Architecture

Unlike the original which runs in real-time (very slow with cloud LLMs), this project separates simulation and playback:

1. **Simulation Mode** (`python -m backend.simulate`): Headless CLI that runs the cognitive loop and saves `master_movement.json` — let it run overnight for hundreds of steps
2. **Replay Mode** (frontend): Loads saved simulations and replays them instantly with playback controls (play/pause, seek, speed 1×–20×, progress bar)

This matches how the original paper's online demo actually works — the "instant" demo at `reverie.herokuapp.com` is a pre-computed replay, not live simulation.

---

## Quick Start

### Prerequisites

- Python 3.11+ (conda recommended: `conda activate alice`)
- [Ollama](https://ollama.ai) installed and running
- Node.js 18+

### Setup

```bash
# 1. Pull the LLM model (~9 GB, requires 12 GB+ VRAM)
ollama pull qwen3:14b

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Install frontend dependencies
cd frontend && npm install && cd ..
```

### Run a Simulation

```bash
# Run 100 steps of Smallville (takes ~30–60 min with local LLM)
python -m backend.simulate --steps 100

# With custom output and checkpoints
python -m backend.simulate --steps 500 --output backend/data/saves/my_run --checkpoint-every 50
```

Progress bar output:
```
╔══════════════════════════════════════════════════════════╗
║         Generative Agents — World Simulation            ║
╠══════════════════════════════════════════════════════════╣
║  World:      the_ville                                  ║
║  Steps:      100                                        ║
╚══════════════════════════════════════════════════════════╝

  ██████████████░░░░░░░░░░░░░░░░ 47/100 (47.0%) | 23.5m elapsed | ETA 26.6m
```

### Replay in Browser

```bash
# Terminal 1: Start backend API
uvicorn backend.main:app --host 127.0.0.1 --port 5000

# Terminal 2: Start frontend dev server
cd frontend && npm run dev
```

Open `http://localhost:3000` → Select a saved simulation → Watch the replay with full Smallville map rendering.

### LLM Configuration

Edit `.env` (copy from `.env.example`) to switch LLM providers:

```bash
# Ollama local (default, free)
LLM_API_KEY=ollama
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=qwen3:14b

# Or Gemini cloud (fast, paid)
LLM_API_KEY=your_key
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_MODEL=gemini-2.5-flash
```

---

## Project Structure

```
├── backend/                        # Python backend (FastAPI)
│   ├── simulate.py                 # CLI simulation runner with progress bar
│   ├── main.py                     # FastAPI server (replay API)
│   ├── world_engine.py             # Simulation engine (from reverie.py)
│   ├── maze.py                     # Tile-based world map (140×100)
│   ├── recorder.py                 # Saves movements for replay
│   ├── path_finder.py              # A* pathfinding
│   ├── config.py                   # LLM + paths config
│   ├── llm/
│   │   ├── llm_client.py           # OpenAI-compatible client (works with Ollama)
│   │   └── embedding.py            # Local sentence-transformers
│   ├── persona/
│   │   ├── persona.py              # Agent class with move() cognitive loop
│   │   ├── cognitive_modules/
│   │   │   ├── perceive.py         # Same-arena event perception
│   │   │   ├── retrieve.py         # Three-factor retrieval + normalization
│   │   │   ├── plan.py             # Three-level decomposition + replanning
│   │   │   ├── reflect.py          # Importance-triggered reflection
│   │   │   ├── execute.py          # A* movement execution
│   │   │   └── converse.py         # Iterative conversation (v2)
│   │   └── memory_structures/
│   │       ├── associative_memory.py  # ConceptNode + keyword indexing
│   │       ├── spatial_memory.py      # Hierarchical world tree
│   │       └── scratch.py             # Working memory (40+ fields)
│   └── data/
│       └── the_ville/              # Smallville world data (25 agents)
├── frontend/                       # React + Phaser 3 + Vite
│   ├── src/
│   │   ├── App.tsx                 # Replay viewer with playback controls
│   │   ├── GameScene.ts            # Phaser 3 Tiled map rendering
│   │   └── api.ts                  # REST client for replay data
│   └── public/assets/              # Smallville tilesets + sprites
├── paper-generative-agent/         # Original paper's source code (reference)
│   ├── ANALYSIS.md                 # Deep analysis of original code (Chinese)
│   └── reverie/backend_server/     # Original Python implementation
├── requirements.txt
└── .env.example
```

---

## Key Technical Details

### Memory Retrieval Formula

```
score = recency_w  * recency_normalized   * 0.5
      + relevance_w * relevance_normalized * 3.0
      + importance_w * importance_normalized * 2.0
```

Each component independently min-max normalized to \[0, 1\]. Per-persona weights default to 1.0. See [ANALYSIS.md](paper-generative-agent/ANALYSIS.md) for the full breakdown with original code comparison.

### Reflection Trigger

When `importance_trigger_curr <= 0` (each perceived event decrements by its poignancy score), the agent generates 3 focal questions, retrieves relevant memories, and synthesizes insights stored as thought nodes with evidence links.

### Plan Decomposition

1. **Daily**: "wake up, work at pharmacy, have lunch, ..." (4–6 items)
2. **Hourly**: `[["sleeping", 360], ["morning routine", 60], ...]` (24 h schedule)
3. **5–15 min**: Runtime decomposition of ≥ 60 min blocks — the key feature most reproductions omit

---

## ALICE PROJECT

**ALICE PROJECT** is an AI-driven social simulation built on top of this reproduction system. It features an original world, original characters, and an extended knowledge and memory architecture tailored for long-horizon narrative simulation.

The ALICE PROJECT source code is **not yet public**. Development is ongoing, and source code will be released in stages as the project reaches public milestone goals. Stay tuned.

---

## References

- **Paper**: [Generative Agents: Interactive Simulacra of Human Behavior](https://arxiv.org/abs/2304.03442) (Park et al., UIST 2023)
- **Original Code**: [joonspk-research/generative_agents](https://github.com/joonspk-research/generative_agents)
- **Deep Analysis**: [ANALYSIS.md](paper-generative-agent/ANALYSIS.md) — 15-section analysis of the original paper and code, including precise formula verification and diff analysis
