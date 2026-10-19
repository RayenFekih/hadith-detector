"""SDK stdio probe, runnable with an installed wheel outside the source checkout."""

import asyncio
import json
import sys
from pathlib import Path

from jsonschema import validate
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def probe(config: dict, text: str, key: str) -> None:
    parameters = StdioServerParameters(**config["mcpServers"]["hadith-detector"])
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write) as session:
            initialized = await session.initialize()
            assert "candidate textual matches" in initialized.instructions
            tools = {tool.name: tool for tool in (await session.list_tools()).tools}
            assert set(tools) == {"detect_hadith", "annotate_hadith", "get_hadith"}
            for name, arguments in (
                ("get_hadith", {"hadith_key": key}),
                ("detect_hadith", {"text": text}),
                ("annotate_hadith", {"text": text}),
            ):
                response = await session.call_tool(name, arguments)
                assert not response.isError, response
                validate(response.structuredContent, tools[name].outputSchema)
                if name == "get_hadith":
                    assert response.structuredContent["record"]["hadith_key"] == key
                elif name == "detect_hadith":
                    assert response.structuredContent["matches"]
                    for match in response.structuredContent["matches"]:
                        assert text[match["start"] : match["end"]] == match["text"]
                else:
                    assert response.structuredContent["original_text"] == text
                    assert "<mark " in response.structuredContent["html"]
            assert (await session.call_tool("get_hadith", {"hadith_key": "invalid"})).isError
            assert not (await session.call_tool("detect_hadith", {"text": ""})).isError


if __name__ == "__main__":
    config = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    asyncio.run(probe(config, sys.argv[2], sys.argv[3]))
    print("MCP stdio probe passed")
