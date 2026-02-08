"""Claude MCP integration - detects and uses Claude's MCP servers.

When running as a Claude Code skill, this module detects if Claude's MCP
SearXNG Enhanced Server is available and uses it instead of spawning a
local MCP client.

Detection Strategy:
1. Check if running in Claude Code environment
2. Try to detect available MCP tools via introspection
3. Fallback to local MCP client if not available
"""

import os
import sys
from typing import Any, Dict, List, Optional


def is_claude_environment() -> bool:
    """Check if running inside Claude Code.

    Detection methods:
    - CLAUDE_CODE environment variable
    - Parent process checks (platform-specific)

    Returns:
        True if likely running in Claude Code
    """
    # Method 1: Environment variable (most reliable)
    if os.environ.get("CLAUDE_CODE") or os.environ.get("CLAUDE"):
        return True

    # Method 2: Check for Claude-specific environment
    if "claude" in os.environ.get("PATH", "").lower():
        return True

    return False


def detect_mcp_tools() -> List[str]:
    """Detect available MCP tools in current environment.

    This function attempts to detect if Claude's MCP SearXNG Enhanced
    Server tools are available by checking for tool aliases.

    Returns:
        List of available MCP tool names (empty if not available)
    """
    # This is a placeholder - actual detection would require
    # introspection of the available tools in the current environment
    # For now, we rely on runtime checks

    # Common tool names from MCP SearXNG Enhanced Server:
    # - mcp__searxng-enhanced__search_web
    # - mcp__searxng-enhanced__get_website
    # - mcp__searxng-enhanced__get_current_datetime

    # We can't actually detect these from Python without inspecting
    # the Claude Code runtime, so we return a conservative guess
    if is_claude_environment():
        # Assume SearXNG MCP might be available in Claude environment
        return [
            "mcp__searxng-enhanced__search_web",
            "mcp__searxng-enhanced__get_website",
            "mcp__searxng-enhanced__get_current_datetime",
        ]

    return []


def should_use_claude_mcp(config: Dict[str, Any]) -> bool:
    """Determine if we should use Claude's MCP servers.

    Decision factors:
    1. Running in Claude Code environment
    2. MCP tools detected as available
    3. User preference (config: USE_CLAUDE_MCP)

    Args:
        config: Configuration dict from env.get_config()

    Returns:
        True if should use Claude's MCP servers
    """
    # Check user preference
    use_claude_mcp = config.get("USE_CLAUDE_MCP", "").lower()
    if use_claude_mcp == "false":
        return False
    if use_claude_mcp == "true":
        return is_claude_environment()

    # Auto-detect: use Claude MCP if available
    return is_claude_environment() and len(detect_mcp_tools()) > 0


class ClaudeMCPWrapper:
    """Wrapper for Claude's MCP SearXNG Enhanced Server.

    This class provides the same interface as mcp_client.MCPSearXNGClient
    but delegates to Claude's MCP tools when available.
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize wrapper.

        Args:
            config: Configuration dict from env.get_config()
        """
        self.config = config
        self.available_tools = detect_mcp_tools()
        self._available = len(self.available_tools) > 0

    def is_available(self) -> bool:
        """Check if Claude MCP is available."""
        return self._available

    def search_web(
        self,
        query: str,
        category: str = "general",
        engines: Optional[str] = None,
        safesearch: int = 1,
        time_range: Optional[str] = None,
    ) -> dict:
        """Search web using Claude's MCP SearXNG server.

        This is a placeholder - actual implementation would call the
        MCP tool via Claude's runtime. Since we can't directly invoke
        MCP tools from Python code, this raises NotImplementedError.

        In a real Claude Code skill context, the main orchestrator
        (last30days.py) would call the MCP tools directly via the Skill tool.

        Args:
            query: Search query
            category: Search category (general, images, videos, etc.)
            engines: Comma-separated engine list
            safesearch: Safe search level (0=none, 1=moderate, 2=strict)
            time_range: Time filter (day, month, year)

        Returns:
            SearXNG response dict

        Raises:
            NotImplementedError: Cannot directly invoke MCP tools from Python
        """
        # This function cannot be directly implemented because:
        # 1. We don't have access to Claude's MCP runtime from Python
        # 2. MCP tools must be invoked through Claude's tool system
        #
        # Solution: The skill should check Claude MCP availability at
        # the orchestrator level and call MCP tools directly via the
        # Skill tool or Tool tool, not through this wrapper.
        raise NotImplementedError(
            "Claude MCP tools must be called directly from the skill "
            "orchestrator, not via Python wrapper. "
            "Use should_use_claude_mcp() to check availability, then "
            "call MCP tools directly in last30days.py"
        )

    def get_website(self, url: str) -> str:
        """Get website content using Claude's MCP SearXNG server.

        Args:
            url: Website URL

        Returns:
            Website content as string

        Raises:
            NotImplementedError: Cannot directly invoke MCP tools from Python
        """
        raise NotImplementedError(
            "Claude MCP tools must be called directly from the skill "
            "orchestrator, not via Python wrapper."
        )


def get_mcp_client(config: Dict[str, Any]):
    """Get the appropriate MCP client for the current environment.

    Args:
        config: Configuration dict from env.get_config()

    Returns:
        Either ClaudeMCPWrapper or mcp_client.MCPSearXNGClient
    """
    # Import locally to avoid circular dependency
    from . import mcp_client

    if should_use_claude_mcp(config):
        return ClaudeMCPWrapper(config)
    else:
        # Return local MCP client
        return mcp_client.MCPSearXNGClient()
