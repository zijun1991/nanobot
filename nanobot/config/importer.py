"""Import MCP configuration from Claude Desktop."""

import json
import platform
from pathlib import Path


def get_claude_desktop_config_path() -> Path:
    """Get Claude Desktop config path based on OS."""
    system = platform.system()
    if system == "Darwin":  # macOS
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    elif system == "Windows":
        return Path.home() / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"
    elif system == "Linux":
        return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"
    else:
        raise ValueError(f"Unsupported platform: {system}")


def load_claude_desktop_mcp_config() -> dict | None:
    """Load MCP config from Claude Desktop."""
    config_path = get_claude_desktop_config_path()
    if not config_path.exists():
        return None

    with open(config_path) as f:
        data = json.load(f)

    return data.get("mcpServers", {})


def import_mcp_config(cloud_config: dict | None = None) -> "MCPClientsConfig":
    """Import Claude Desktop MCP config to nanobot format.

    Args:
        cloud_config: Optional pre-loaded config (for testing)

    Returns:
        MCPClientsConfig instance
    """
    from nanobot.config.schema import MCPClientConfig, MCPClientsConfig

    mcp_servers = cloud_config or load_claude_desktop_mcp_config()
    if not mcp_servers:
        return MCPClientsConfig()

    clients = {}
    for name, server_config in mcp_servers.items():
        clients[name] = {
            "enabled": True,  # 导入的客户端默认启用
            "command": server_config.get("command"),
            "args": server_config.get("args", []),
            "env": server_config.get("env", {}),
        }

    return MCPClientsConfig(**clients)
