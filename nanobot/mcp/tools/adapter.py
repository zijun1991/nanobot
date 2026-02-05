"""Adapter for converting MCP tools to nanobot tools."""

import json
from typing import Any

from loguru import logger

from nanobot.agent.tools.base import Tool


class MCPToolAdapter(Tool):
    """Adapter that wraps an MCP tool as a nanobot Tool."""

    def __init__(self, client_name: str, mcp_tool: Any, client_session: Any):
        """
        Initialize the MCP tool adapter.

        Args:
            client_name: Name of the MCP client (for prefixing)
            mcp_tool: MCP tool definition from the server (can be dict or Pydantic model)
            client_session: MCP client session for executing the tool
        """
        self.client_name = client_name
        self.mcp_tool = mcp_tool
        self.client_session = client_session

        # Extract tool properties (handle both dict and Pydantic model)
        if isinstance(mcp_tool, dict):
            self._name = mcp_tool.get("name", "")
            self._description = mcp_tool.get("description", "")
            self._input_schema = mcp_tool.get("inputSchema", {})
        else:
            # Pydantic model
            self._name = getattr(mcp_tool, "name", "")
            self._description = getattr(mcp_tool, "description", "")
            self._input_schema = getattr(mcp_tool, "inputSchema", {})

    @property
    def name(self) -> str:
        """Tool name with client prefix."""
        return f"mcp_{self.client_name}_{self._name}"

    @property
    def description(self) -> str:
        """Tool description."""
        desc = self._description or f"MCP tool: {self._name}"
        return f"[MCP:{self.client_name}] {desc}"

    @property
    def parameters(self) -> dict:
        """Tool parameters schema."""
        return self._input_schema

    async def execute(self, **kwargs) -> str:
        """
        Execute the MCP tool.

        Args:
            **kwargs: Tool arguments

        Returns:
            Tool result as string
        """
        try:
            logger.debug(f"Executing MCP tool {self.name} with args: {kwargs}")

            # Call the MCP tool
            result = await self.client_session.call_tool(self._name, kwargs)

            # Extract content from result
            if isinstance(result, dict):
                if "content" in result:
                    content = result["content"]
                    if isinstance(content, list):
                        # Handle multiple content items
                        parts = []
                        for item in content:
                            if isinstance(item, dict):
                                if item.get("type") == "text":
                                    parts.append(item.get("text", ""))
                                elif item.get("type") == "resource":
                                    # Handle resource outputs
                                    uri = item.get("uri", "")
                                    parts.append(f"Resource: {uri}")
                                else:
                                    # Other types, convert to string
                                    parts.append(str(item))
                            else:
                                parts.append(str(item))
                        return "\n".join(parts)
                    elif isinstance(content, str):
                        return content
                    else:
                        return str(content)
                else:
                    # No content field, return whole result
                    return json.dumps(result, indent=2)
            elif isinstance(result, list):
                # Handle list results
                return "\n".join(str(item) for item in result)
            else:
                return str(result)

        except Exception as e:
            logger.error(f"Error executing MCP tool {self.name}: {e}")
            return f"Error: {str(e)}"
