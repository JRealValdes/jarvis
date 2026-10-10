"""Live smoke test: start the math MCP server and call ``add`` (stdio, no LLM)."""

import asyncio

import pytest

from jarvis.agents.mcp_session import McpToolSession
from jarvis.core.paths import MCP_SERVER_CONFIG_PATH


def _tool_result_texts(result: object) -> list[str]:
    """
    Extract text payloads from an MCP / LangChain tool result.

    Args:
        result: Return value of ``StructuredTool.ainvoke``.

    Returns:
        Text fragments found in content blocks or a stringified scalar.
    """
    if isinstance(result, list):
        texts: list[str] = []
        for item in result:
            if isinstance(item, dict) and "text" in item:
                texts.append(str(item["text"]))
            else:
                texts.append(str(item))
        return texts
    if isinstance(result, tuple) and result:
        return _tool_result_texts(result[0])
    return [str(result)]


@pytest.mark.skipif(
    not MCP_SERVER_CONFIG_PATH.is_file(),
    reason="data/mcp/server_config.json is missing",
)
def test_math_mcp_server_add_tool():
    session = McpToolSession()

    async def _run() -> None:
        try:
            tools = await session.connect()
            add = next((tool for tool in tools if tool.name == "add"), None)
            assert add is not None, f"add tool missing; got {[t.name for t in tools]}"
            result = await add.ainvoke({"a": 2, "b": 3})
            assert "5" in _tool_result_texts(result)
            assert session.is_broken is False
        finally:
            await session.close()

    asyncio.run(_run())
