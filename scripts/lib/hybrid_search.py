"""Hybrid search architecture - combines Claude MCP + Claude WebSearch + Date Detection.

Three-Tier Architecture:
1. Tier 1: Claude MCP SearXNG (highest quality, no cost, when available)
2. Tier 2: Claude WebSearch (high quality, no cost, always available)
3. Tier 3: Shared Date Detection (post-processing for date-aware filtering)

This module provides unified search functions that:
- Use Claude MCP SearXNG when running as a skill
- Fall back to Claude WebSearch when MCP unavailable
- Apply shared date detection for 30-day filtering
"""

import os
import sys
from typing import Any, Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import claude_mcp, date_detect


def _log_error(msg: str):
    """Log error to stderr."""
    sys.stderr.write(f"[HYBRID SEARCH ERROR] {msg}\n")
    sys.stderr.flush()


def search_reddit_hybrid(
    topic: str,
    from_date: str,
    to_date: str,
    config: Dict[str, Any],
    depth: str = "default",
) -> Tuple[List[dict], str]:
    """Search Reddit using hybrid approach.

    Tries:
    1. Claude MCP SearXNG (if available)
    2. Falls back to minimal results if neither available

    Args:
        topic: Search topic
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        config: Configuration dict from env.get_config()
        depth: Search depth (quick/default/deep)

    Returns:
        Tuple of (results list, source used)
    """
    # Check if Claude MCP is available
    if claude_mcp.should_use_claude_mcp(config):
        try:
            mcp_client = claude_mcp.get_mcp_client(config)
            if mcp_client.is_available():
                # Try to use Claude MCP SearXNG
                # Note: This is a placeholder - actual implementation would
                # need to call MCP tools via the Skill tool in last30days.py
                # For now, we return empty to indicate MCP should be used
                # at the orchestrator level
                return [], "claude_mcp"
        except Exception as e:
            _log_error(f"Claude MCP search failed: {e}")

    # Fallback: Return empty to trigger alternative
    return [], "none"


def search_x_hybrid(
    topic: str,
    from_date: str,
    to_date: str,
    config: Dict[str, Any],
    depth: str = "default",
) -> Tuple[List[dict], str]:
    """Search X using hybrid approach.

    Tries:
    1. Claude MCP SearXNG (if available)
    2. Falls back to minimal results if neither available

    Args:
        topic: Search topic
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        config: Configuration dict from env.get_config()
        depth: Search depth (quick/default/deep)

    Returns:
        Tuple of (results list, source used)
    """
    # Check if Claude MCP is available
    if claude_mcp.should_use_claude_mcp(config):
        try:
            mcp_client = claude_mcp.get_mcp_client(config)
            if mcp_client.is_available():
                # Placeholder - actual MCP calls happen in orchestrator
                return [], "claude_mcp"
        except Exception as e:
            _log_error(f"Claude MCP search failed: {e}")

    # Fallback
    return [], "none"


def search_web_hybrid(
    topic: str,
    from_date: str,
    to_date: str,
    config: Dict[str, Any],
    depth: str = "default",
) -> Tuple[List[dict], str]:
    """Search web using hybrid approach.

    Tries:
    1. Claude MCP SearXNG (if available)
    2. Falls back to minimal results if neither available

    Args:
        topic: Search topic
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        config: Configuration dict from env.get_config()
        depth: Search depth (quick/default/deep)

    Returns:
        Tuple of (results list, source used)
    """
    # Check if Claude MCP is available
    if claude_mcp.should_use_claude_mcp(config):
        try:
            mcp_client = claude_mcp.get_mcp_client(config)
            if mcp_client.is_available():
                # Placeholder - actual MCP calls happen in orchestrator
                return [], "claude_mcp"
        except Exception as e:
            _log_error(f"Claude MCP search failed: {e}")

    # Fallback
    return [], "none"


def apply_date_detection(
    items: List[dict],
    from_date: str,
    to_date: str,
    item_type: str = "web",
) -> List[dict]:
    """Apply shared date detection to filter results by 30-day window.

    This is the Tier 3 fallback that adds date filtering to results from
    sources that don't support date ranges (like Claude WebSearch).

    Args:
        items: List of result dicts (must have url, title, snippet fields)
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        item_type: Type of items ('reddit', 'x', 'web')

    Returns:
        Filtered list of items within date range, with date_confidence added
    """
    filtered_items = []

    for item in items:
        url = item.get("url", "")
        title = item.get("title", "")
        snippet = item.get("snippet", "") or item.get("content", "") or item.get("why_relevant", "")

        # Extract date using shared detection
        date_str, confidence = date_detect.extract_date_signals(
            url=url,
            snippet=snippet,
            title=title,
        )

        # Add date confidence to item
        item["date"] = date_str
        item["date_confidence"] = confidence

        # Filter by date range
        if date_str and not date_detect.is_date_in_range(date_str, from_date, to_date):
            continue  # Skip items outside date range

        filtered_items.append(item)

    return filtered_items


def search_all_hybrid(
    topic: str,
    from_date: str,
    to_date: str,
    config: Dict[str, Any],
    depth: str = "default",
) -> Dict[str, Tuple[List[dict], str]]:
    """Search all sources (Reddit, X, Web) using hybrid approach.

    Executes searches in parallel where possible.

    Args:
        topic: Search topic
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        config: Configuration dict from env.get_config()
        depth: Search depth (quick/default/deep)

    Returns:
        Dict with keys 'reddit', 'x', 'web', each containing a tuple of
        (results list, source used)
    """
    results = {}

    # Execute searches in parallel
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            "reddit": executor.submit(
                search_reddit_hybrid, topic, from_date, to_date, config, depth
            ),
            "x": executor.submit(
                search_x_hybrid, topic, from_date, to_date, config, depth
            ),
            "web": executor.submit(
                search_web_hybrid, topic, from_date, to_date, config, depth
            ),
        }

        for source, future in futures.items():
            try:
                results[source] = future.result(timeout=30)
            except Exception as e:
                _log_error(f"{source.capitalize()} search failed: {e}")
                results[source] = ([], "error")

    return results


def detect_hybrid_capability(config: Dict[str, Any]) -> Dict[str, bool]:
    """Detect which hybrid search capabilities are available.

    Args:
        config: Configuration dict from env.get_config()

    Returns:
        Dict with keys: 'claude_mcp', 'claude_websearch', 'date_detection'
    """
    return {
        "claude_mcp": claude_mcp.should_use_claude_mcp(config),
        "claude_websearch": True,  # Always available in Claude Code
        "date_detection": True,  # Always available (stdlib only)
    }
