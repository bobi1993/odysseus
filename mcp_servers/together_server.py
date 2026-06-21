"""
together_server.py

MCP server exposing Together AI chat completions via the `together` SDK.

Tools:
  - together_chat: Chat completion with any Together model
  - together_models: List available Together models
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

log = logging.getLogger("mcp.together")

server = Server("together_ai")


def _get_client():
    """Create a Together client from env or settings."""
    api_key = os.environ.get("TOGETHER_API_KEY", "")
    if not api_key:
        try:
            from src.settings import get_setting
            api_key = get_setting("together_api_key", "")
        except Exception:
            pass
    if not api_key:
        raise ValueError(
            "Together API key not configured. "
            "Set TOGETHER_API_KEY in .env or together_api_key in settings."
        )
    from together import Together
    return Together(api_key=api_key)


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="together_chat",
            description=(
                "Chat completion via Together AI. Supports all Together models "
                "including Llama 4 Scout/Maverick, DeepSeek R1, Qwen, and custom LoRA fine-tunes."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "model": {
                        "type": "string",
                        "description": (
                            "Together model ID, e.g. "
                            "'meta-llama/Llama-4-Scout-17B-16E-Instruct', "
                            "'deepseek-ai/DeepSeek-R1', "
                            "'dehorn93_47fa/meta-llama/Llama-4-Scout-17B-16E-Instruct-FP8-Lora-b6465c16'. "
                            "Use together_models to list available models."
                        ),
                    },
                    "messages": {
                        "type": "array",
                        "description": "Chat messages: list of {role: user|assistant|system, content: string}",
                        "items": {
                            "type": "object",
                            "properties": {
                                "role": {"type": "string"},
                                "content": {"type": "string"},
                            },
                            "required": ["role", "content"],
                        },
                    },
                    "max_tokens": {
                        "type": "integer",
                        "description": "Max tokens to generate (default: 512)",
                    },
                    "temperature": {
                        "type": "number",
                        "description": "Sampling temperature 0.0-2.0 (default: 0.7)",
                    },
                    "top_p": {
                        "type": "number",
                        "description": "Top-p nucleus sampling (default: 0.7)",
                    },
                    "repetition_penalty": {
                        "type": "number",
                        "description": "Repetition penalty 1.0-2.0 (default: 1.0)",
                    },
                },
                "required": ["model", "messages"],
            },
        ),
        Tool(
            name="together_models",
            description="List available Together AI models. Filter by type (chat, image, embedding) or search by name.",
            inputSchema={
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "description": "Filter: 'chat', 'image', 'embedding', or empty for all",
                    },
                    "search": {
                        "type": "string",
                        "description": "Search string to filter model names, e.g. 'llama-4' or 'deepseek'",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max models to return (default: 50)",
                    },
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "together_chat":
        return await _handle_chat(arguments)
    if name == "together_models":
        return await _handle_models(arguments)
    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def _handle_chat(args: dict) -> list[TextContent]:
    model = args.get("model", "")
    messages = args.get("messages", [])
    max_tokens = args.get("max_tokens", 512)
    temperature = args.get("temperature", 0.7)
    top_p = args.get("top_p", 0.7)
    repetition_penalty = args.get("repetition_penalty", 1.0)

    if not model:
        return [TextContent(type="text", text="Error: model is required")]
    if not messages:
        return [TextContent(type="text", text="Error: messages is required")]

    try:
        client = _get_client()
    except ValueError as e:
        return [TextContent(type="text", text=f"Error: {e}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error initializing Together client: {e}")]

    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=int(max_tokens),
                temperature=float(temperature),
                top_p=float(top_p),
                repetition_penalty=float(repetition_penalty),
            ),
        )

        content = response.choices[0].message.content or ""

        # Build usage info
        usage_str = ""
        if response.usage:
            u = response.usage
            usage_str = (
                f"\n\n---\n"
                f"tokens: {u.prompt_tokens or 0} in / "
                f"{u.completion_tokens or 0} out / "
                f"{u.total_tokens or 0} total"
            )

        return [TextContent(type="text", text=f"{content}{usage_str}")]

    except Exception as e:
        log.error(f"Together chat failed: {e}")
        return [TextContent(type="text", text=f"Error: Together chat failed: {e}")]


async def _handle_models(args: dict) -> list[TextContent]:
    model_type = (args.get("type") or "").strip().lower()
    search = (args.get("search") or "").strip().lower()
    limit = int(args.get("limit", 50))

    try:
        client = _get_client()
    except ValueError as e:
        return [TextContent(type="text", text=f"Error: {e}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error initializing Together client: {e}")]

    try:
        loop = asyncio.get_event_loop()
        models = await loop.run_in_executor(None, client.models.list)

        results = []
        for m in models:
            m_id = getattr(m, "id", "") or ""
            m_type = getattr(m, "type", "") or ""
            m_display = getattr(m, "display_name", "") or m_id
            m_ctx = getattr(m, "context_length", None)

            # Filter by type if requested
            if model_type and model_type not in m_type.lower():
                continue

            # Filter by search string
            if search and search not in m_id.lower() and search not in m_display.lower():
                continue

            entry = f"{m_id}"
            if m_display and m_display != m_id:
                entry += f"  ({m_display})"
            if m_ctx:
                entry += f"  ctx={m_ctx}"
            results.append(entry)

            if len(results) >= limit:
                break

        if not results:
            return [TextContent(type="text", text="No models found matching the filter.")]

        header = f"Together AI models ({len(results)} shown"
        if model_type:
            header += f", type={model_type}"
        if search:
            header += f", search={search}"
        header += "):\n"

        return [TextContent(type="text", text=header + "\n".join(f"  {r}" for r in results))]

    except Exception as e:
        log.error(f"Together models list failed: {e}")
        return [TextContent(type="text", text=f"Error: Failed to list models: {e}")]


async def run():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(run())
