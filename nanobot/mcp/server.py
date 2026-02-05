"""MCP server implementation for nanobot."""

import asyncio
from contextlib import asynccontextmanager
from typing import Any

from loguru import logger
from mcp.server.models import InitializationOptions
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from nanobot.agent.tools.registry import ToolRegistry


class NanobotMCPServer:
    """MCP server that exposes nanobot tools."""

    def __init__(self, tool_registry: ToolRegistry, name: str = "nanobot"):
        """
        Initialize MCP server.

        Args:
            tool_registry: Nanobot tool registry to expose
            name: Server name
        """
        self.name = name
        self.tool_registry = tool_registry
        self.server = Server(name)

        # Register handlers
        self._setup_handlers()

    def _setup_handlers(self):
        """Setup MCP server handlers."""

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """List available tools."""
            tools = []
            for tool_name, tool in self.tool_registry.list_tools().items():
                # Convert nanobot tool to MCP tool format
                tools.append(Tool(
                    name=tool_name,
                    description=tool.description,
                    inputSchema=tool.parameters,
                ))
            return tools

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[TextContent]:
            """Call a tool."""
            try:
                # Execute the tool
                result = await self.tool_registry.execute(name, arguments)

                # Return as text content
                return [TextContent(type="text", text=str(result))]
            except Exception as e:
                logger.error(f"Error calling tool {name}: {e}")
                return [TextContent(type="text", text=f"Error: {str(e)}")]

    async def run_stdio(self) -> None:
        """Run the MCP server using stdio transport."""
        logger.info("Starting MCP server with stdio transport")
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name=self.name,
                    server_version="0.1.0",
                    capabilities=self.server.get_capabilities(
                        notification_options=None,
                        experimental_capabilities=None,
                    ),
                ),
            )

    async def run_sse(self, host: str = "0.0.0.0", port: int = 18791) -> None:
        """Run the MCP server using SSE transport."""
        from starlette.applications import Starlette
        from starlette.routing import Route
        import uvicorn

        logger.info(f"Starting MCP server with SSE transport on {host}:{port}")

        # Create SSE transport
        transport = SseServerTransport("/messages")

        # Starlette app
        app = Starlette(
            routes=[
                Route("/sse", endpoint=transport.handle_sse),
            ],
        )

        # Run server
        config = uvicorn.Config(app, host=host, port=port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()


@asynccontextmanager
async def mcp_server_lifespan(tool_registry: ToolRegistry):
    """
    Context manager for MCP server lifecycle.

    Args:
        tool_registry: Tool registry to expose

    Yields:
        NanobotMCPServer instance
    """
    server = NanobotMCPServer(tool_registry)
    try:
        yield server
    finally:
        # Cleanup if needed
        pass
