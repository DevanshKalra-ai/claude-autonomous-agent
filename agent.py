import json
import anthropic
from typing import Generator
from tools import TOOL_DEFINITIONS, execute_tool

MODEL = "claude-opus-4-7"
MAX_TURNS = 12

SYSTEM_PROMPT = """You are an autonomous AI assistant with access to real-world tools.

When answering a question:
1. Think about which tools you need — use them proactively, not lazily.
2. You can call multiple tools in sequence; each result informs the next step.
3. Synthesize tool results into a clear, well-structured final answer.
4. Cite sources (URLs) when you use web search or Wikipedia.
5. If a tool returns an error, try an alternative approach.

Available tools: web_search, wikipedia_lookup, run_python, read_file, calculator."""

client = anthropic.Anthropic()


def run_agent(user_message: str) -> Generator[dict, None, None]:
    """
    Runs the Claude tool-use loop and yields events:
      {"type": "tool_call",   "tool": name, "input": {...}}
      {"type": "tool_result", "tool": name, "output": {...}}
      {"type": "answer",      "text": final_response_text}
      {"type": "error",       "text": error_message}
    """
    messages = [{"role": "user", "content": user_message}]

    for turn in range(MAX_TURNS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            thinking={"type": "adaptive"},
            system=SYSTEM_PROMPT,
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )

        # Collect tool uses from this response
        tool_uses = [b for b in response.content if b.type == "tool_use"]

        # Append assistant message
        messages.append({"role": "assistant", "content": response.content})

        # If no tool calls or stop_reason is end_turn — we have the final answer
        if response.stop_reason == "end_turn" or not tool_uses:
            text_blocks = [b.text for b in response.content if hasattr(b, "text") and b.text]
            final_text = "\n\n".join(text_blocks) if text_blocks else "(No text response)"
            yield {"type": "answer", "text": final_text}
            return

        # Execute each tool and collect results
        tool_results = []
        for tool_use in tool_uses:
            yield {"type": "tool_call", "tool": tool_use.name, "input": tool_use.input}

            output = execute_tool(tool_use.name, tool_use.input)

            yield {"type": "tool_result", "tool": tool_use.name, "output": output}

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": json.dumps(output),
            })

        # Feed tool results back
        messages.append({"role": "user", "content": tool_results})

    yield {"type": "error", "text": f"Agent reached maximum turn limit ({MAX_TURNS})."}


def run_agent_sync(user_message: str) -> dict:
    """Non-streaming version — returns final answer + tool trace."""
    tool_trace = []
    answer = ""
    error = ""

    for event in run_agent(user_message):
        if event["type"] == "tool_call":
            tool_trace.append({"call": event["tool"], "input": event["input"]})
        elif event["type"] == "tool_result":
            if tool_trace:
                tool_trace[-1]["output"] = event["output"]
        elif event["type"] == "answer":
            answer = event["text"]
        elif event["type"] == "error":
            error = event["text"]

    return {"answer": answer, "tool_trace": tool_trace, "error": error}
