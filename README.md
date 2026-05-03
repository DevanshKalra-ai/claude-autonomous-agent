# claude-autonomous-agent

Autonomous AI agent powered by Claude tool use (function calling). Ask any multi-step question — the agent searches the web, runs code, reads files, and synthesizes a cited answer automatically.

---

## Tools

| Tool | What it does |
|------|-------------|
| `web_search` | DuckDuckGo search — no API key required, returns title + URL + snippet |
| `wikipedia_lookup` | Fetches Wikipedia article summary for any topic |
| `run_python` | Executes sandboxed Python snippets — numpy available, stdout captured |
| `read_file` | Reads uploaded files from `./workspace/` |
| `calculator` | Evaluates math expressions — `sqrt`, `log`, `sin`, `pi`, `e`, etc. |

The agent runs a multi-turn Claude tool-use loop (up to 12 turns) until it has enough information to answer. Events stream to the frontend via Server-Sent Events.

---

## Tech Stack

| Layer | Tech |
|-------|------|
| LLM | Claude (`claude-opus-4-7`) with adaptive thinking + tool use |
| Backend | FastAPI + SSE streaming |
| Frontend | Vanilla HTML + Tailwind CSS |
| Search | DuckDuckGo (`duckduckgo-search`) |
| Wiki | `wikipedia-api` |

---

## Quick Start

```bash
git clone https://github.com/DevanshKalra-ai/claude-autonomous-agent.git
cd claude-autonomous-agent
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-...   # Windows: $env:ANTHROPIC_API_KEY="sk-..."
uvicorn main:app --reload --port 8000
```

Open `http://localhost:8000`

---

## Example Queries

- *"What is the current price of gold and why is it moving?"*
- *"Explain transformer attention and calculate the score for Q=[1,0], K=[1,1]"*
- *"Who is Sam Altman and what has he done recently?"*
- *"Compound interest: ₹50,000 at 8% for 10 years compounded monthly"*
- Upload a file → *"Read report.pdf and summarize the key findings"*

---

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/chat/stream` | SSE stream of agent events (`tool_call`, `tool_result`, `answer`) |
| POST | `/upload` | Upload file to `./workspace/` for the agent to read |
| GET | `/workspace` | List uploaded files |
| GET | `/health` | Health check |

### Stream event types

```jsonc
{"type": "tool_call",   "tool": "web_search", "input": {"query": "gold price 2026"}}
{"type": "tool_result", "tool": "web_search", "output": {"results": [...]}}
{"type": "answer",      "text": "Gold is currently trading at..."}
```

---

## Project Structure

```
claude-autonomous-agent/
├── agent.py          # Claude tool-use loop — streaming + sync variants
├── tools.py          # All 5 tool implementations + Claude tool definitions
├── main.py           # FastAPI — /chat/stream (SSE), /upload, /workspace
├── requirements.txt
└── static/
    └── index.html    # Chat UI with live tool call badges + streaming answer
```
