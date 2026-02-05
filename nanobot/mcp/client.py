"""MCP client manager for connecting to external MCP servers."""

import asyncio
from contextlib import asynccontextmanager
from typing import Any

from loguru import logger

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamable_http_client


class MCPClient:
    """Manages a single MCP server connection."""

    def __init__(self, name: str, config: dict, silent: bool = False):
        """
        Initialize MCP client.

        Args:
            name: Client name for identification
            config: Client configuration dict (supports 'stdio' and 'http' types)
            silent: If True, suppress subprocess stdout/stderr for stdio clients
        """
        self.name = name
        self.config = config
        self.client_type = config.get("type", "stdio")  # 默认为 stdio 保持向后兼容
        self.silent = silent
        self.session: ClientSession | None = None
        self._transport_context = None
        self._session_context = None

    async def connect(self) -> None:
        """Connect to the MCP server."""
        if self.client_type == "stdio":
            await self._connect_stdio()
        elif self.client_type == "http":
            await self._connect_http()
        elif self.client_type == "streamable_http":
            await self._connect_streamable_http()
        else:
            raise ValueError(f"Unsupported MCP client type: {self.client_type}")

    async def _connect_stdio(self) -> None:
        """Connect to MCP server via stdio."""
        import os
        import subprocess

        try:
            logger.info(f"Connecting to MCP server '{self.name}' (stdio)...")

            command = self.config.get("command")
            if not command:
                raise ValueError(f"stdio client '{self.name}' missing 'command' field")

            args = self.config.get("args", [])
            env = self.config.get("env", {})

            # Merge environment variables with current environment
            merged_env = os.environ.copy()
            if env:
                merged_env.update(env)

            # In silent mode, wrap command to redirect stderr to /dev/null
            if self.silent:
                # Create a wrapper script that redirects stderr
                if os.name == 'nt':  # Windows
                    # On Windows, use NUL
                    wrapper_command = ['cmd', '/c', command + ' 2>NUL'] + [f'"{arg}"' if ' ' in arg else arg for arg in args]
                    # Remove original args since they're now in the wrapper command
                    args = []
                    command = wrapper_command[0]
                    wrapper_command = wrapper_command[2:]  # Skip 'cmd' and '/c'
                    # This is complex, let's use a simpler approach
                    # Reset to original and use shell=True
                    wrapper_command = command + ' ' + ' '.join([f'"{arg}"' if ' ' in arg else arg for arg in args]) + ' 2>NUL'
                    server_params = StdioServerParameters(
                        command=wrapper_command,
                        args=[],
                        env=merged_env,
                    )
                else:  # Unix/Linux/macOS
                    # On Unix, use sh -c to redirect stderr
                    shell_command = command + ' ' + ' '.join([shlex.quote(arg) for arg in args]) + ' 2>/dev/null'
                    import shlex
                    server_params = StdioServerParameters(
                        command='sh',
                        args=['-c', shell_command],
                        env=merged_env,
                    )
            else:
                # Create stdio server parameters normally
                server_params = StdioServerParameters(
                    command=command,
                    args=args,
                    env=merged_env,
                )

            # Connect to server
            self._transport_context = stdio_client(server_params)
            stdio_transport = await self._transport_context.__aenter__()

            # Create session
            self._session_context = ClientSession(stdio_transport[0], stdio_transport[1])
            self.session = await self._session_context.__aenter__()

            # Initialize session
            await self.session.initialize()

            logger.info(f"Connected to MCP server '{self.name}' (stdio)")

        except Exception as e:
            logger.error(f"Failed to connect to MCP server '{self.name}': {e}")
            self.session = None
            raise

    async def _connect_http(self) -> None:
        """Connect to MCP server via HTTP/SSE."""
        try:
            logger.info(f"Connecting to MCP server '{self.name}' (http)...")

            url = self.config.get("url")
            if not url:
                raise ValueError(f"http client '{self.name}' missing 'url' field")

            headers = self.config.get("headers", {})
            timeout = self.config.get("timeout", 5.0)
            sse_read_timeout = self.config.get("sse_read_timeout", 300.0)

            # Connect to server via SSE
            self._transport_context = sse_client(
                url=url,
                headers=headers,
                timeout=timeout,
                sse_read_timeout=sse_read_timeout,
            )
            sse_transport = await self._transport_context.__aenter__()

            # Create session
            self._session_context = ClientSession(sse_transport[0], sse_transport[1])
            self.session = await self._session_context.__aenter__()

            # Initialize session
            await self.session.initialize()

            logger.info(f"Connected to MCP server '{self.name}' (http)")

        except Exception as e:
            logger.error(f"Failed to connect to MCP server '{self.name}': {e}")
            self.session = None
            raise

    async def _connect_streamable_http(self) -> None:
        """Connect to MCP server via StreamableHTTP (direct HTTP JSON-RPC)."""
        import httpx

        try:
            logger.info(f"Connecting to MCP server '{self.name}' (streamable_http)...")

            url = self.config.get("url")
            if not url:
                raise ValueError(f"streamable_http client '{self.name}' missing 'url' field")

            headers = self.config.get("headers", {})

            # Create httpx client with headers
            http_client = httpx.AsyncClient(
                headers=headers,
                timeout=httpx.Timeout(30.0)
            )

            # Connect to server via StreamableHTTP
            # Use terminate_on_close=False to prevent DELETE request during cleanup
            self._transport_context = streamable_http_client(
                url=url,
                http_client=http_client,
                terminate_on_close=False
            )
            streams = await self._transport_context.__aenter__()

            # Create session
            self._session_context = ClientSession(streams[0], streams[1])
            self.session = await self._session_context.__aenter__()

            # Initialize session
            await self.session.initialize()

            logger.info(f"Connected to MCP server '{self.name}' (streamable_http)")

        except Exception as e:
            logger.error(f"Failed to connect to MCP server '{self.name}': {e}")
            self.session = None
            raise

    async def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        try:
            if self._session_context:
                try:
                    await self._session_context.__aexit__(None, None, None)
                except RuntimeError as e:
                    if "cancel scope" in str(e):
                        # Ignore cancel scope errors during event loop shutdown
                        logger.debug(f"Ignoring cancel scope error during session cleanup: {e}")
                    else:
                        raise
                self._session_context = None

            if self._transport_context:
                try:
                    await self._transport_context.__aexit__(None, None, None)
                except RuntimeError as e:
                    if "cancel scope" in str(e):
                        # Ignore cancel scope errors during event loop shutdown
                        logger.debug(f"Ignoring cancel scope error during transport cleanup: {e}")
                    else:
                        raise
                self._transport_context = None

            self.session = None
            logger.info(f"Disconnected from MCP server '{self.name}'")

        except Exception as e:
            # Log but don't raise during cleanup
            logger.debug(f"Error during disconnect from '{self.name}': {e}")
            self.session = None

    async def list_tools(self) -> list[dict]:
        """
        List available tools from the MCP server.

        Returns:
            List of tool definitions
        """
        if not self.session:
            logger.warning(f"MCP server '{self.name}' not connected")
            return []

        try:
            response = await self.session.list_tools()
            return response.tools if hasattr(response, "tools") else []
        except Exception as e:
            logger.error(f"Error listing tools from MCP server '{self.name}': {e}")
            return []

    async def call_tool(self, tool_name: str, arguments: dict) -> Any:
        """
        Call a tool on the MCP server.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            Tool result
        """
        if not self.session:
            raise RuntimeError(f"MCP server '{self.name}' not connected")

        return await self.session.call_tool(tool_name, arguments)


class MCPClientManager:
    """Manages multiple MCP client connections."""

    def __init__(self, clients_config: dict[str, dict], silent: bool = False):
        """
        Initialize MCP client manager.

        Args:
            clients_config: Dictionary of client name -> client config
                Each config has: command, args, env
            silent: If True, suppress MCP server stdout/stderr output
        """
        self.clients_config = clients_config
        self.clients: dict[str, MCPClient] = {}
        self.silent = silent

    async def start(self) -> None:
        """Connect to all enabled MCP servers."""
        for name, config in self.clients_config.items():
            if not config.get("enabled", False):
                continue

            # 根据类型验证配置
            client_type = config.get("type", "stdio")

            if client_type == "stdio":
                if not config.get("command"):
                    logger.warning(f"MCP client '{name}' has no command configured, skipping")
                    continue
            elif client_type == "http" or client_type == "streamable_http":
                if not config.get("url"):
                    logger.warning(f"MCP client '{name}' has no url configured, skipping")
                    continue
            else:
                logger.warning(f"MCP client '{name}' has unsupported type: {client_type}, skipping")
                continue

            try:
                client = MCPClient(name=name, config=config, silent=self.silent)
                await client.connect()
                self.clients[name] = client
            except Exception as e:
                logger.error(f"Failed to start MCP client '{name}': {e}")
                # Continue with other clients

    async def stop(self) -> None:
        """Disconnect from all MCP servers."""
        for name, client in list(self.clients.items()):
            try:
                await client.disconnect()
            except Exception as e:
                logger.error(f"Error stopping MCP client '{name}': {e}")

        self.clients.clear()

    def get_client(self, name: str) -> MCPClient | None:
        """Get a connected MCP client by name."""
        return self.clients.get(name)

    def get_all_clients(self) -> dict[str, MCPClient]:
        """Get all connected MCP clients."""
        return self.clients.copy()

    async def list_all_tools(self) -> dict[str, list[dict]]:
        """
        List tools from all connected MCP servers.

        Returns:
            Dictionary mapping client name to list of tools
        """
        all_tools = {}
        for name, client in self.clients.items():
            tools = await client.list_tools()
            all_tools[name] = tools
        return all_tools


@asynccontextmanager
async def mcp_client_lifespan(clients_config: dict[str, dict]):
    """
    Context manager for MCP client lifecycle.

    Args:
        clients_config: Configuration for MCP clients

    Yields:
        MCPClientManager instance
    """
    manager = MCPClientManager(clients_config)
    try:
        await manager.start()
        yield manager
    finally:
        await manager.stop()
