"""Optional local MCP integration; importing this module needs no MCP dependencies."""


def main() -> None:
    """Start the local stdio server, reserving stdout for MCP messages."""
    try:
        from .server import create_server
    except ModuleNotFoundError as exc:
        if exc.name != "mcp":
            raise
        raise SystemExit('MCP support requires: pip install "hadith-detector[mcp]"') from None
    create_server().run(transport="stdio")
