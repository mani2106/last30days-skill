"""Minimal MCP client for communicating with MCP SearXNG Enhanced Server.

This module implements a minimal Model Context Protocol (MCP) client that can
communicate with MCP servers via JSON-RPC 2.0 over stdin/stdout.

The client is designed to be stdlib-only (no external dependencies) and follows
the JSON-RPC 2.0 specification for tool calling.
"""

import json
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional


class MCPSearXNGClient:
    """Minimal MCP client for SearXNG Enhanced server.

    Communicates via JSON-RPC protocol (stdin/stdout).

    The client can either:
    1. Connect to an already-running MCP server (stdin/stdout of current process)
    2. Start an MCP server subprocess and communicate via its stdin/stdout

    Example:
        # Connect to already-running server
        client = MCPSearXNGClient()

        # Or start server via subprocess
        client = MCPSearXNGClient(command=["docker", "run", "-i", "mcp-searxng"])

        # Use the client
        results = client.search_web("query", category="social media")
        client.close()
    """

    def __init__(self, command: Optional[List[str]] = None, timeout: int = 120):
        """Initialize MCP client.

        Args:
            command: Command to start MCP server as subprocess (e.g., ["docker", "run", "-i", "..."])
                     If None, assumes server is already running and uses stdin/stdout directly.
            timeout: Default timeout for requests in seconds
        """
        self.command = command
        self.timeout = timeout
        self.request_id = 0
        self.process: Optional[subprocess.Popen] = None

        if command:
            # Start MCP server as subprocess
            try:
                self.process = subprocess.Popen(
                    command,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,  # Use text mode for JSON
                    encoding='utf-8',  # Explicit UTF-8 encoding
                    errors='replace',  # Replace invalid chars instead of failing
                    bufsize=0,  # Unbuffered
                )
            except Exception as e:
                raise RuntimeError(f"Failed to start MCP server: {e}")
        else:
            # Use stdin/stdout directly (server already running)
            self.process = None

    def _generate_request_id(self) -> int:
        """Generate unique request ID."""
        self.request_id += 1
        return self.request_id

    def _send_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send JSON-RPC request and read response.

        Args:
            method: JSON-RPC method name (e.g., "tools/call")
            params: Method parameters

        Returns:
            JSON-RPC response result

        Raises:
            RuntimeError: On communication errors or JSON-RPC errors
        """
        request = {
            "jsonrpc": "2.0",
            "id": self._generate_request_id(),
            "method": method,
            "params": params,
        }

        request_json = json.dumps(request) + "\n"

        sys.stderr.write(f"[MCP DEBUG] Sending: {request_json[:500]}\n")  # Debug: log first 500 chars
        sys.stderr.flush()

        # Send request
        if self.process:
            # Write to subprocess stdin
            try:
                self.process.stdin.write(request_json)
                self.process.stdin.flush()
            except (BrokenPipeError, OSError) as e:
                raise RuntimeError(f"Failed to send request to MCP server: {e}")
        else:
            # Write to stdout (assuming parent process connected to MCP server)
            sys.stdout.write(request_json)
            sys.stdout.flush()

        # Read response
        response_lines = []
        start_time = time.time()

        while True:
            # Check timeout
            if time.time() - start_time > self.timeout:
                raise RuntimeError(f"Request timeout after {self.timeout}s")

            # Read line
            try:
                if self.process:
                    line = self.process.stdout.readline()
                else:
                    line = sys.stdin.readline()
            except Exception as e:
                raise RuntimeError(f"Failed to read response from MCP server: {e}")

            if not line:
                if self.process and self.process.poll() is not None:
                    stderr = self.process.stderr.read()
                    raise RuntimeError(f"MCP server process exited: {stderr}")
                raise RuntimeError("Unexpected EOF from MCP server")

            line = line.strip()
            if not line:
                continue  # Skip empty lines

            try:
                response = json.loads(line)
                sys.stderr.write(f"[MCP DEBUG] Received: {line[:500]}\n")  # Debug: log first 500 chars
                sys.stderr.flush()

                # Handle MCP notifications (events) - skip them and continue reading
                # Notifications have "method" field but no "result" field
                if "method" in response and "result" not in response:
                    sys.stderr.write(f"[MCP DEBUG] Skipping notification: {response.get('method', 'unknown')}\n")
                    sys.stderr.flush()
                    continue  # This is a notification, not our response

                # Check if this is our response (has "result" or "error" field)
                if "result" in response or "error" in response:
                    break  # Got our response

                # Otherwise, keep reading
                sys.stderr.write("[MCP DEBUG] Got unexpected response, continuing to read...\n")
                sys.stderr.flush()

            except json.JSONDecodeError:
                # Not a complete JSON object yet, keep reading
                # (shouldn't happen with line-buffered input, but handle gracefully)
                response_lines.append(line)
                # Try parsing accumulated lines
                try:
                    response = json.loads("\n".join(response_lines))
                    sys.stderr.write(f"[MCP DEBUG] Received (multi-line): {str(response)[:500]}\n")
                    sys.stderr.flush()

                    # Handle notifications in multi-line responses too
                    if "method" in response and "result" not in response:
                        response_lines = []  # Clear and continue
                        continue

                    if "result" in response or "error" in response:
                        break
                except json.JSONDecodeError:
                    continue

        # Check for JSON-RPC error
        if "error" in response:
            error = response["error"]
            raise RuntimeError(f"MCP error: {error.get('message', 'Unknown error')} (code: {error.get('code', 'Unknown')})")

        # Return result
        if "result" not in response:
            raise RuntimeError(f"Invalid MCP response: missing 'result' field")

        return response["result"]

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call an MCP tool.

        Args:
            tool_name: Name of tool (e.g., "search_web", "get_website")
            arguments: Tool arguments

        Returns:
            Tool result (structure depends on tool)

        Raises:
            RuntimeError: On MCP errors or communication failures
        """
        params = {
            "name": tool_name,
            "arguments": arguments,
        }

        return self._send_request("tools/call", params)

    def search_web(
        self,
        query: str,
        category: str = "general",
        engines: Optional[str] = None,
        time_range: Optional[str] = None,
        safesearch: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Call search_web tool.

        Args:
            query: Search query
            category: SearXNG category (general, social media, news, images, videos, etc.)
            engines: Comma-separated engine list (e.g., "google,duckduckgo")
            time_range: Time filter (day, month, year)
            safesearch: Safe search level (0=None, 1=Moderate, 2=Strict)

        Returns:
            SearXNG search results dict with 'results' list

        Raises:
            RuntimeError: On MCP errors or communication failures
        """
        arguments = {"query": query}

        if category:
            arguments["category"] = category
        if engines:
            arguments["engines"] = engines
        if time_range:
            arguments["time_range"] = time_range
        if safesearch is not None:
            arguments["safesearch"] = safesearch

        return self.call_tool("search_web", arguments)

    def get_website(self, url: str) -> Dict[str, Any]:
        """Call get_website tool.

        Args:
            url: Website URL to scrape

        Returns:
            Scraped website content dict

        Raises:
            RuntimeError: On MCP errors or communication failures
        """
        return self.call_tool("get_website", {"url": url})

    def close(self):
        """Close MCP server connection.

        If the MCP server was started as a subprocess, this will terminate it.
        If using stdin/stdout directly, this does nothing.
        """
        if self.process:
            try:
                # Send EOF to stdin (signals server to shut down gracefully)
                self.process.stdin.close()
            except Exception:
                pass  # Ignore errors during cleanup

            try:
                # Wait for process to exit (with timeout)
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # Force kill if doesn't exit gracefully
                self.process.kill()

            self.process = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures connection is closed."""
        self.close()
        return False
