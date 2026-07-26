#!/usr/bin/env python3
"""Ask the market baskets a question in plain language.

A tool-calling loop over the OpenAI Responses API, using the tools in
`agent_tools.py`. This is the abstraction layer in its smallest useful form:
instead of clicking through views, you type a question and the model composes
`run_sql` / `compare_baskets` / `basket_detail` calls to answer it.

    python agent.py "how did metals do against semis, and what drove it"
    python agent.py --trace "which holdings have rising short interest and positive sentiment"
    python agent.py            # interactive

Set OPENAI_API_KEY (or put it in .env.local). Override the model with
AIO_AGENT_MODEL.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

from env_config import load_dotenv

load_dotenv()

import agent_tools
from universe import load_universe


API_URL = "https://api.openai.com/v1/responses"
# Multi-step tool calling needs more than the nano tier the classification
# stages use. Override with AIO_AGENT_MODEL.
DEFAULT_MODEL = "gpt-5.4-mini"
MAX_STEPS = 8
REQUEST_TIMEOUT = 120


SYSTEM_PROMPT = """\
You are an analyst working inside a market-basket research system. The user tracks
themed baskets of stocks (equal-weighted) and cares about performance, risk,
positioning, fundamentals, and news sentiment.

Answer questions by calling tools. Guidelines:
- Call `list_baskets` when you need to know what exists, and `describe_tables`
  before writing SQL so you use real column names. Never guess a column.
- Prefer `compare_baskets` and `basket_detail` for common questions; drop to
  `run_sql` when you need a join or filter they do not cover.
- Ticker-level tables join to `holdings` on ticker to filter by basket.
- Ground every number in a tool result. If a tool errors, read the message and
  retry with a correction rather than guessing.
- If the data cannot answer the question, say so plainly and say what is missing.

Answer in prose, short and specific. Lead with the direct answer, then the
numbers that support it, rounded sensibly and with units. Mention the analysis
window when it matters. Do not describe your tool calls or your process.
"""


class AgentError(RuntimeError):
    pass


def resolve_api_key(explicit: str = "") -> str:
    key = (explicit or os.environ.get("OPENAI_API_KEY", "")).strip()
    if not key:
        raise AgentError(
            "No OPENAI_API_KEY found. Add it to .env.local at the project root or export it."
        )
    return key


def resolve_model(explicit: str = "") -> str:
    return (
        explicit
        or os.environ.get("AIO_AGENT_MODEL", "")
        or os.environ.get("OPENAI_MODEL", "")
        or DEFAULT_MODEL
    ).strip()


def post_responses(body: dict[str, Any], api_key: str, timeout: int = REQUEST_TIMEOUT) -> dict[str, Any]:
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:600]
        raise AgentError(f"OpenAI returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise AgentError(f"Could not reach the OpenAI API: {exc.reason}") from exc


def extract_text(response: dict[str, Any]) -> str:
    if isinstance(response.get("output_text"), str) and response["output_text"].strip():
        return response["output_text"].strip()
    chunks = []
    for item in response.get("output", []):
        if item.get("type") != "message":
            continue
        for part in item.get("content", []):
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                chunks.append(part["text"])
    return "\n".join(chunks).strip()


def function_calls(response: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in response.get("output", []) if item.get("type") == "function_call"]


def context_note() -> str:
    """Ground the model in the current analysis window and basket list."""
    universe = load_universe()
    return (
        f"Analysis window {universe.start_date.isoformat()} to {universe.end_date.isoformat()}. "
        f"Baskets: {', '.join(universe.basket_ids)}."
    )


def ask(
    question: str,
    *,
    api_key: str = "",
    model: str = "",
    max_steps: int = MAX_STEPS,
    trace: bool = False,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run the tool-calling loop until the model produces a text answer."""
    api_key = resolve_api_key(api_key)
    model = resolve_model(model)

    conversation: list[dict[str, Any]] = list(history or [])
    if not conversation:
        conversation.append({"role": "system", "content": SYSTEM_PROMPT})
        conversation.append({"role": "system", "content": context_note()})
    conversation.append({"role": "user", "content": question})

    tools = agent_tools.openai_tool_definitions()
    calls_made: list[dict[str, Any]] = []

    for step in range(max_steps):
        response = post_responses(
            {"model": model, "input": conversation, "tools": tools, "tool_choice": "auto"},
            api_key,
        )
        pending = function_calls(response)
        if not pending:
            answer = extract_text(response)
            if not answer:
                raise AgentError(
                    f"Model returned no answer (status {response.get('status')!r}). "
                    "It may have hit a token limit."
                )
            return {
                "answer": answer,
                "toolCalls": calls_made,
                "steps": step + 1,
                "model": model,
                "history": conversation + [{"role": "assistant", "content": answer}],
            }

        # Echo the model's calls back, then append each result.
        conversation.extend(pending)
        for call in pending:
            name = call.get("name", "")
            try:
                arguments = json.loads(call.get("arguments") or "{}")
            except json.JSONDecodeError as exc:
                result = {"error": f"Arguments were not valid JSON: {exc}"}
                arguments = {}
            else:
                result = agent_tools.dispatch(name, arguments)
            calls_made.append({"tool": name, "arguments": arguments, "isError": "error" in result})
            if trace:
                flag = "!" if "error" in result else " "
                print(f"  {flag} {name}({json.dumps(arguments, default=str)[:110]})", file=sys.stderr)
                if "error" in result:
                    print(f"      -> {result['error'][:160]}", file=sys.stderr)
            conversation.append(
                {
                    "type": "function_call_output",
                    "call_id": call.get("call_id"),
                    "output": json.dumps(result, default=str),
                }
            )

    raise AgentError(
        f"Gave up after {max_steps} tool-calling steps without a final answer. "
        "Try a narrower question."
    )


def repl(model: str, trace: bool) -> int:
    print("Ask about your baskets. Ctrl-D or 'exit' to quit.\n")
    history: list[dict[str, Any]] | None = None
    while True:
        try:
            question = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not question:
            continue
        if question.lower() in {"exit", "quit"}:
            return 0
        try:
            result = ask(question, model=model, trace=trace, history=history)
        except AgentError as exc:
            print(f"error: {exc}\n", file=sys.stderr)
            continue
        history = result["history"]
        print(f"\n{result['answer']}\n")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Ask the market baskets a question.")
    parser.add_argument("question", nargs="*", help="Question to ask. Omit for interactive mode.")
    parser.add_argument("--model", default="", help=f"Model id (default {DEFAULT_MODEL}).")
    parser.add_argument("--trace", action="store_true", help="Print tool calls to stderr.")
    parser.add_argument("--json", action="store_true", help="Emit the full result as JSON.")
    parser.add_argument("--max-steps", type=int, default=MAX_STEPS)
    args = parser.parse_args(argv[1:])

    if not args.question:
        return repl(args.model, args.trace)

    try:
        result = ask(
            " ".join(args.question),
            model=args.model,
            trace=args.trace,
            max_steps=args.max_steps,
        )
    except AgentError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps({k: v for k, v in result.items() if k != "history"}, indent=2, default=str))
    else:
        print(result["answer"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
