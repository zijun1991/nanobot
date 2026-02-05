"""Agent loop: the core processing engine."""

import asyncio
import json
from pathlib import Path
from typing import Any

from loguru import logger

from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.providers.base import LLMProvider
from nanobot.agent.context import ContextBuilder
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.agent.tools.filesystem import ReadFileTool, WriteFileTool, EditFileTool, ListDirTool
from nanobot.agent.tools.shell import ExecTool
from nanobot.agent.tools.web import WebSearchTool, WebFetchTool
from nanobot.agent.tools.message import MessageTool
from nanobot.agent.tools.spawn import SpawnTool
from nanobot.agent.subagent import SubagentManager
from nanobot.session.manager import SessionManager
from nanobot.mcp.client import MCPClientManager
from nanobot.mcp.tools.adapter import MCPToolAdapter


class AgentLoop:
    """
    The agent loop is the core processing engine.
    
    It:
    1. Receives messages from the bus
    2. Builds context with history, memory, skills
    3. Calls the LLM
    4. Executes tool calls
    5. Sends responses back
    """
    
    def __init__(
        self,
        bus: MessageBus,
        provider: LLMProvider,
        workspace: Path,
        model: str | None = None,
        max_iterations: int = 20,
        brave_api_key: str | None = None,
        exec_config: "ExecToolConfig | None" = None,
        mcp_config: "MCPConfig | None" = None,
        silent: bool = False,
    ):
        from nanobot.config.schema import ExecToolConfig, MCPConfig
        self.bus = bus
        self.provider = provider
        self.workspace = workspace
        self.model = model or provider.get_default_model()
        self.max_iterations = max_iterations
        self.brave_api_key = brave_api_key
        self.exec_config = exec_config or ExecToolConfig()
        self.mcp_config = mcp_config or MCPConfig()
        self.silent = silent

        self.context = ContextBuilder(workspace)
        self.sessions = SessionManager(workspace)
        self.tools = ToolRegistry()
        self.subagents = SubagentManager(
            provider=provider,
            workspace=workspace,
            bus=bus,
            model=self.model,
            brave_api_key=brave_api_key,
            exec_config=self.exec_config,
        )

        self._running = False
        self._mcp_manager = None
        self._register_default_tools()
    
    def _register_default_tools(self) -> None:
        """Register the default set of tools."""
        # File tools
        self.tools.register(ReadFileTool())
        self.tools.register(WriteFileTool())
        self.tools.register(EditFileTool())
        self.tools.register(ListDirTool())
        
        # Shell tool
        self.tools.register(ExecTool(
            working_dir=str(self.workspace),
            timeout=self.exec_config.timeout,
            restrict_to_workspace=self.exec_config.restrict_to_workspace,
        ))
        
        # Web tools
        self.tools.register(WebSearchTool(api_key=self.brave_api_key))
        self.tools.register(WebFetchTool())
        
        # Message tool
        message_tool = MessageTool(send_callback=self.bus.publish_outbound)
        self.tools.register(message_tool)
        
        # Spawn tool (for subagents)
        spawn_tool = SpawnTool(manager=self.subagents)
        self.tools.register(spawn_tool)

        # Initialize MCP manager (will start in run())
        self._init_mcp_clients()

    def _init_mcp_clients(self) -> None:
        """Initialize MCP client manager if configured."""
        clients_config = {}
        if self.mcp_config and self.mcp_config.clients:
            for name, client in self.mcp_config.clients.model_dump(exclude_unset=True).items():
                if not client.get("enabled", False):
                    continue

                client_type = client.get("type", "stdio")

                # 根据类型验证配置
                if client_type == "stdio" and client.get("command"):
                    clients_config[name] = client
                elif client_type in ("http", "streamable_http") and client.get("url"):
                    clients_config[name] = client
                else:
                    logger.warning(f"MCP client '{name}' has incomplete config, skipping")

        if clients_config:
            self._mcp_manager = MCPClientManager(clients_config, silent=self.silent)
            logger.info(f"Initialized {len(clients_config)} MCP client(s)")

    async def _register_mcp_tools(self) -> None:
        """Register tools from MCP servers."""
        if not self._mcp_manager:
            return

        try:
            all_tools = await self._mcp_manager.list_all_tools()
            registered_count = 0

            for client_name, tools in all_tools.items():
                client = self._mcp_manager.get_client(client_name)
                if not client:
                    continue

                for tool_def in tools:
                    try:
                        adapter = MCPToolAdapter(
                            client_name=client_name,
                            mcp_tool=tool_def,
                            client_session=client.session,
                        )
                        self.tools.register(adapter)
                        registered_count += 1
                        logger.debug(f"Registered MCP tool: {adapter.name}")
                    except Exception as e:
                        logger.error(f"Failed to register MCP tool {tool_def.get('name')}: {e}")

            logger.info(f"Registered {registered_count} MCP tool(s)")
        except Exception as e:
            logger.error(f"Failed to register MCP tools: {e}")

    def _get_mcp_info(self) -> str | None:
        """Get information about connected MCP servers for system prompt."""
        if not self._mcp_manager:
            logger.debug("No MCP manager configured")
            return None

        clients = self._mcp_manager.get_all_clients()
        logger.debug(f"Connected MCP clients: {list(clients.keys())}")

        if not clients:
            logger.debug("No MCP clients connected")
            return None

        # Build info about connected MCP servers
        server_info = []
        for name, client in clients.items():
            client_type = client.client_type
            info = f"- **{name}** (type: {client_type})"

            # Add additional info based on type
            if client_type == "stdio":
                command = client.config.get("command", "")
                info += f" - 命令: `{command}`"
            elif client_type in ["http", "streamable_http"]:
                url = client.config.get("url", "")
                info += f" - URL: `{url}`"

            server_info.append(info)

        if not server_info:
            logger.debug("No MCP server info to display")
            return None

        mcp_info = "\n".join(server_info)

        logger.debug(f"MCP Info for system prompt:\n{mcp_info}")
        return mcp_info
    
    async def run(self) -> None:
        """Run the agent loop, processing messages from the bus."""
        self._running = True
        logger.info("Agent loop started")

        # Start MCP clients if configured
        if self._mcp_manager:
            await self._mcp_manager.start()
            await self._register_mcp_tools()

        while self._running:
            try:
                # Wait for next message
                msg = await asyncio.wait_for(
                    self.bus.consume_inbound(),
                    timeout=1.0
                )

                # Process it
                try:
                    response = await self._process_message(msg)
                    if response:
                        await self.bus.publish_outbound(response)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    # Send error response
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content=f"Sorry, I encountered an error: {str(e)}"
                    ))
            except asyncio.TimeoutError:
                continue

        # Clean up MCP clients after loop exits (same task)
        if self._mcp_manager:
            try:
                await self._mcp_manager.stop()
            except Exception as e:
                logger.error(f"Error stopping MCP clients: {e}")
        logger.info("Agent loop stopped")
    
    def stop(self) -> None:
        """Stop the agent loop.

        Note: This is a synchronous stop that only sets the flag.
        For proper cleanup, use stop_async() instead.
        """
        self._running = False
        logger.info("Agent loop stopping")

    async def stop_async(self) -> None:
        """Async version of stop for proper cleanup.

        Note: If the agent is running via run(), MCP clients will be
        cleaned up automatically when run() exits. This method is
        primarily for cleanup when using process_direct().
        """
        self._running = False
        logger.info("Agent loop stopping")
    
    async def _process_message(self, msg: InboundMessage) -> OutboundMessage | None:
        """
        Process a single inbound message.
        
        Args:
            msg: The inbound message to process.
        
        Returns:
            The response message, or None if no response needed.
        """
        # Handle system messages (subagent announces)
        # The chat_id contains the original "channel:chat_id" to route back to
        if msg.channel == "system":
            return await self._process_system_message(msg)
        
        logger.info(f"Processing message from {msg.channel}:{msg.sender_id}")
        
        # Get or create session
        session = self.sessions.get_or_create(msg.session_key)
        
        # Update tool contexts
        message_tool = self.tools.get("message")
        if isinstance(message_tool, MessageTool):
            message_tool.set_context(msg.channel, msg.chat_id)
        
        spawn_tool = self.tools.get("spawn")
        if isinstance(spawn_tool, SpawnTool):
            spawn_tool.set_context(msg.channel, msg.chat_id)
        
        # Build initial messages (use get_history for LLM-formatted messages)
        mcp_info = self._get_mcp_info()
        logger.debug(f"MCP info to pass to build_messages: {mcp_info is not None}")
        messages = self.context.build_messages(
            history=session.get_history(),
            current_message=msg.content,
            media=msg.media if msg.media else None,
            mcp_info=mcp_info,
        )
        
        # Agent loop
        iteration = 0
        final_content = None
        
        while iteration < self.max_iterations:
            iteration += 1
            
            # Call LLM
            response = await self.provider.chat(
                messages=messages,
                tools=self.tools.get_definitions(),
                model=self.model
            )
            
            # Handle tool calls
            if response.has_tool_calls:
                # Add assistant message with tool calls
                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments)  # Must be JSON string
                        }
                    }
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages, response.content, tool_call_dicts
                )
                
                # Execute tools
                for tool_call in response.tool_calls:
                    args_str = json.dumps(tool_call.arguments)
                    logger.debug(f"Executing tool: {tool_call.name} with arguments: {args_str}")
                    result = await self.tools.execute(tool_call.name, tool_call.arguments)
                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_call.name, result
                    )
            else:
                # No tool calls, we're done
                final_content = response.content
                break
        
        if final_content is None:
            final_content = "I've completed processing but have no response to give."
        
        # Save to session
        session.add_message("user", msg.content)
        session.add_message("assistant", final_content)
        self.sessions.save(session)
        
        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=final_content
        )
    
    async def _process_system_message(self, msg: InboundMessage) -> OutboundMessage | None:
        """
        Process a system message (e.g., subagent announce).
        
        The chat_id field contains "original_channel:original_chat_id" to route
        the response back to the correct destination.
        """
        logger.info(f"Processing system message from {msg.sender_id}")
        
        # Parse origin from chat_id (format: "channel:chat_id")
        if ":" in msg.chat_id:
            parts = msg.chat_id.split(":", 1)
            origin_channel = parts[0]
            origin_chat_id = parts[1]
        else:
            # Fallback
            origin_channel = "cli"
            origin_chat_id = msg.chat_id
        
        # Use the origin session for context
        session_key = f"{origin_channel}:{origin_chat_id}"
        session = self.sessions.get_or_create(session_key)
        
        # Update tool contexts
        message_tool = self.tools.get("message")
        if isinstance(message_tool, MessageTool):
            message_tool.set_context(origin_channel, origin_chat_id)
        
        spawn_tool = self.tools.get("spawn")
        if isinstance(spawn_tool, SpawnTool):
            spawn_tool.set_context(origin_channel, origin_chat_id)
        
        # Build messages with the announce content
        messages = self.context.build_messages(
            history=session.get_history(),
            current_message=msg.content
        )
        
        # Agent loop (limited for announce handling)
        iteration = 0
        final_content = None
        
        while iteration < self.max_iterations:
            iteration += 1
            
            response = await self.provider.chat(
                messages=messages,
                tools=self.tools.get_definitions(),
                model=self.model
            )
            
            if response.has_tool_calls:
                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments)
                        }
                    }
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages, response.content, tool_call_dicts
                )
                
                for tool_call in response.tool_calls:
                    args_str = json.dumps(tool_call.arguments)
                    logger.debug(f"Executing tool: {tool_call.name} with arguments: {args_str}")
                    result = await self.tools.execute(tool_call.name, tool_call.arguments)
                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_call.name, result
                    )
            else:
                final_content = response.content
                break
        
        if final_content is None:
            final_content = "Background task completed."
        
        # Save to session (mark as system message in history)
        session.add_message("user", f"[System: {msg.sender_id}] {msg.content}")
        session.add_message("assistant", final_content)
        self.sessions.save(session)
        
        return OutboundMessage(
            channel=origin_channel,
            chat_id=origin_chat_id,
            content=final_content
        )
    
    async def process_direct(self, content: str, session_key: str = "cli:direct") -> str:
        """
        Process a message directly (for CLI usage).

        Args:
            content: The message content.
            session_key: Session identifier.

        Returns:
            The agent's response.
        """
        # Start MCP clients if needed (for CLI usage)
        if self._mcp_manager and not getattr(self, '_mcp_started', False):
            await self._mcp_manager.start()
            await self._register_mcp_tools()
            self._mcp_started = True

        try:
            msg = InboundMessage(
                channel="cli",
                sender_id="user",
                chat_id="direct",
                content=content
            )

            response = await self._process_message(msg)
            return response.content if response else ""
        finally:
            # Immediately clean up MCP clients in the same task
            if self._mcp_manager and getattr(self, '_mcp_started', False):
                try:
                    await asyncio.wait_for(self._mcp_manager.stop(), timeout=2.0)
                except (asyncio.TimeoutError, RuntimeError, asyncio.CancelledError):
                    # Expected errors during shutdown - ignore
                    pass
                self._mcp_started = False
