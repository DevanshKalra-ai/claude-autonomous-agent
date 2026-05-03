import math
import traceback
import wikipediaapi
from duckduckgo_search import DDGS
from pathlib import Path
from typing import Any

ALLOWED_READ_DIR = Path("./workspace")
ALLOWED_READ_DIR.mkdir(exist_ok=True)

# ── Tool definitions (sent to Claude) ────────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "name": "web_search",
        "description": (
            "Search the web using DuckDuckGo. Use this to find current information, "
            "recent events, facts, prices, or anything that benefits from a live web search. "
            "Returns up to 5 results with title, URL, and snippet."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query"},
                "max_results": {"type": "integer", "description": "Number of results (1-5)", "default": 3},
            },
            "required": ["query"],
        },
    },
    {
        "name": "wikipedia_lookup",
        "description": (
            "Look up a topic on Wikipedia. Returns a summary of the article. "
            "Best for well-known concepts, people, places, historical events, or scientific topics."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "The topic to look up on Wikipedia"},
                "sentences": {"type": "integer", "description": "Number of sentences to return (default 5)", "default": 5},
            },
            "required": ["topic"],
        },
    },
    {
        "name": "run_python",
        "description": (
            "Execute a Python code snippet and return stdout + the result of the last expression. "
            "Use this for calculations, data processing, string manipulation, or any computation. "
            "Standard library is available. numpy and math are pre-imported. "
            "Do NOT use for file I/O or network calls — use the dedicated tools instead."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python code to execute"},
            },
            "required": ["code"],
        },
    },
    {
        "name": "read_file",
        "description": (
            "Read a text file from the ./workspace/ directory. "
            "Use this when the user asks questions about an uploaded or local file."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "Filename inside ./workspace/ (e.g. 'notes.txt')"},
            },
            "required": ["filename"],
        },
    },
    {
        "name": "calculator",
        "description": (
            "Evaluate a mathematical expression and return the numeric result. "
            "Supports +, -, *, /, **, sqrt(), log(), sin(), cos(), pi, e, etc. "
            "Use this for quick arithmetic — use run_python for complex logic."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "Math expression to evaluate, e.g. 'sqrt(144) + log(100)'"},
            },
            "required": ["expression"],
        },
    },
]


# ── Tool implementations ──────────────────────────────────────────────────────

def web_search(query: str, max_results: int = 3) -> dict:
    max_results = max(1, min(5, max_results))
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return {"results": [], "message": "No results found."}
        return {
            "results": [
                {"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")}
                for r in results
            ]
        }
    except Exception as e:
        return {"error": str(e)}


def wikipedia_lookup(topic: str, sentences: int = 5) -> dict:
    try:
        wiki = wikipediaapi.Wikipedia(user_agent="claude-autonomous-agent/1.0", language="en")
        page = wiki.page(topic)
        if not page.exists():
            return {"error": f"No Wikipedia article found for '{topic}'. Try a different search term."}
        summary = page.summary
        # Truncate to requested sentence count
        sentence_list = summary.split(". ")
        truncated = ". ".join(sentence_list[:sentences])
        if not truncated.endswith("."):
            truncated += "."
        return {
            "title": page.title,
            "summary": truncated,
            "url": page.fullurl,
        }
    except Exception as e:
        return {"error": str(e)}


def run_python(code: str) -> dict:
    import io, sys, contextlib
    # Blocked patterns — prevent network/filesystem abuse
    blocked = ["import os", "import sys", "import subprocess", "import socket",
               "__import__", "open(", "eval(", "exec(", "compile("]
    for b in blocked:
        if b in code:
            return {"error": f"Blocked: '{b}' is not allowed in run_python. Use read_file for files."}
    buf = io.StringIO()
    local_ns: dict[str, Any] = {"math": math, "sqrt": math.sqrt, "log": math.log,
                                  "pi": math.pi, "e": math.e}
    try:
        import numpy as np
        local_ns["np"] = np
    except ImportError:
        pass
    try:
        with contextlib.redirect_stdout(buf):
            lines = code.strip().split("\n")
            if len(lines) > 1:
                exec("\n".join(lines[:-1]), local_ns)
            result = eval(lines[-1], local_ns)
        output = buf.getvalue()
        return {"result": repr(result), "stdout": output}
    except SyntaxError:
        # Last line is a statement, not an expression — exec the whole thing
        try:
            with contextlib.redirect_stdout(buf):
                exec(code, local_ns)
            return {"result": None, "stdout": buf.getvalue()}
        except Exception as e:
            return {"error": traceback.format_exc(limit=3)}
    except Exception as e:
        return {"error": traceback.format_exc(limit=3)}


def read_file(filename: str) -> dict:
    safe_name = Path(filename).name  # strip any path traversal
    path = ALLOWED_READ_DIR / safe_name
    if not path.exists():
        return {"error": f"File '{safe_name}' not found in ./workspace/. Upload it first."}
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        if len(content) > 8000:
            content = content[:8000] + "\n\n[... truncated at 8000 chars ...]"
        return {"filename": safe_name, "content": content, "size_bytes": path.stat().st_size}
    except Exception as e:
        return {"error": str(e)}


def calculator(expression: str) -> dict:
    allowed_names = {k: v for k, v in math.__dict__.items() if not k.startswith("_")}
    allowed_names.update({"abs": abs, "round": round, "min": min, "max": max, "sum": sum})
    try:
        result = eval(expression, {"__builtins__": {}}, allowed_names)
        return {"expression": expression, "result": result}
    except Exception as e:
        return {"error": str(e)}


# ── Dispatcher ────────────────────────────────────────────────────────────────

def execute_tool(name: str, inputs: dict) -> Any:
    dispatch = {
        "web_search": web_search,
        "wikipedia_lookup": wikipedia_lookup,
        "run_python": run_python,
        "read_file": read_file,
        "calculator": calculator,
    }
    fn = dispatch.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}"}
    return fn(**inputs)
