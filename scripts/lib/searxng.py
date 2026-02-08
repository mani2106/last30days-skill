"""SearXNG search provider via MCP SearXNG Enhanced Server.

This module uses the MCP SearXNG Enhanced Server to search Reddit, X, and the web.
It follows the same patterns as openai_reddit.py and xai_x.py for consistency.
"""

import re
import sys
from typing import Dict, List, Optional

from . import date_detect, mcp_client

# Depth configurations matching openai_reddit.py
DEPTH_CONFIG = {
    "quick": (15, 25),
    "default": (30, 50),
    "deep": (70, 100),
}


def _log_error(msg: str):
    """Log error to stderr."""
    sys.stderr.write(f"[SEARXNG ERROR] {msg}\n")
    sys.stderr.flush()


def search_reddit(
    mcp: mcp_client.MCPSearXNGClient,
    topic: str,
    from_date: str,
    to_date: str,
    depth: str = "default",
) -> dict:
    """Search Reddit via MCP SearXNG server.

    Uses search_web tool with site:reddit.com operator.

    Args:
        mcp: MCP SearXNG client instance
        topic: Search topic
        from_date: Start date (YYYY-MM-DD) - for reference
        to_date: End date (YYYY-MM-DD) - for reference
        depth: Search depth (quick/default/deep)

    Returns:
        Raw SearXNG response dict
    """
    # Determine number of results to request
    min_items, max_items = DEPTH_CONFIG.get(depth, DEPTH_CONFIG["default"])

    # Construct query with site:reddit.com operator
    query = f"{topic} site:reddit.com"

    try:
        response = mcp.search_web(
            query=query,
            category="social media",
            time_range="month",  # Closest to 30 days
        )
        return response
    except Exception as e:
        _log_error(f"Reddit search failed: {e}")
        return {"error": str(e)}


def search_x(
    mcp: mcp_client.MCPSearXNGClient,
    topic: str,
    from_date: str,
    to_date: str,
    depth: str = "default",
) -> dict:
    """Search X via MCP SearXNG server.

    Uses search_web tool with site:x.com OR site:twitter.com operator.

    Args:
        mcp: MCP SearXNG client instance
        topic: Search topic
        from_date: Start date (YYYY-MM-DD) - for reference
        to_date: End date (YYYY-MM-DD) - for reference
        depth: Search depth (quick/default/deep)

    Returns:
        Raw SearXNG response dict
    """
    # Determine number of results to request
    min_items, max_items = DEPTH_CONFIG.get(depth, DEPTH_CONFIG["default"])

    # Construct query with site:x.com OR site:twitter.com operator
    query = f"{topic} site:x.com OR {topic} site:twitter.com"

    try:
        response = mcp.search_web(
            query=query,
            category="social media",
            time_range="month",  # Closest to 30 days
        )
        return response
    except Exception as e:
        _log_error(f"X search failed: {e}")
        return {"error": str(e)}


def search_web(
    mcp: mcp_client.MCPSearXNGClient,
    topic: str,
    from_date: str,
    to_date: str,
    depth: str = "default",
) -> dict:
    """Search web via MCP SearXNG server.

    Uses search_web tool (general category).

    Args:
        mcp: MCP SearXNG client instance
        topic: Search topic
        from_date: Start date (YYYY-MM-DD) - for reference
        to_date: End date (YYYY-MM-DD) - for reference
        depth: Search depth (quick/default/deep)

    Returns:
        Raw SearXNG response dict
    """
    try:
        response = mcp.search_web(
            query=topic,
            category="general",
            time_range="month",  # Closest to 30 days
        )
        return response
    except Exception as e:
        _log_error(f"Web search failed: {e}")
        return {"error": str(e)}


def parse_reddit_response(
    response: dict,
    from_date: str,
    to_date: str,
) -> List[dict]:
    """Parse SearXNG response into intermediate Reddit dicts.

    Extracts:
    - id, title, url from SearXNG results
    - subreddit from URL (using regex)
    - date from publication_date field OR date detection
    - relevance from score field
    - date_confidence from detection

    Filters:
    - Only reddit.com URLs
    - Excludes business.reddit.com, developers.reddit.com
    - Filters by date range (30-day window)

    Args:
        response: Raw SearXNG response dict
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)

    Returns:
        List of dicts with keys: id, title, url, subreddit, date, relevance,
        why_relevant, date_confidence
    """
    items = []

    # Handle error responses
    if "error" in response:
        return items

    # Extract results
    results = response.get("results", [])

    # Exclude these subreddains/domains
    excluded_patterns = [
        "business.reddit.com",
        "developers.reddit.com",
        "reddit.com/r/ads/",
        "reddit.com/r/redditsecurity/",
    ]

    for result in results:
        url = result.get("url", "")

        # Filter: must be reddit.com URL
        if "reddit.com" not in url:
            continue

        # Filter: exclude certain patterns
        if any(pattern in url for pattern in excluded_patterns):
            continue

        # Extract subreddit from URL
        subreddit = extract_subreddit_from_url(url)
        if not subreddit:
            continue

        # Extract date: try API field first, then detect from URL/snippet
        api_date = result.get("publication_date") or result.get("publish_date")
        snippet = result.get("content", "")
        title = result.get("title", "")

        if api_date:
            # Use API-provided date with high confidence
            date_str = api_date
            date_confidence = "high"
        else:
            # Use date detection
            date_str, date_confidence = date_detect.extract_date_signals(
                url=url,
                snippet=snippet,
                title=title,
            )

        # Filter by date range
        if date_str and not date_detect.is_date_in_range(date_str, from_date, to_date):
            continue

        # Build item dict
        item = {
            "id": _generate_id_from_url(url),
            "title": title,
            "url": url,
            "subreddit": subreddit,
            "date": date_str,
            "relevance": result.get("score", 0.0),
            "why_relevant": snippet[:200],  # First 200 chars of snippet
            "date_confidence": date_confidence,
        }

        items.append(item)

    return items


def parse_x_response(
    response: dict,
    from_date: str,
    to_date: str,
) -> List[dict]:
    """Parse SearXNG response into intermediate X dicts.

    Extracts:
    - id, text, url
    - author_handle from URL (x.com/author/status/...)
    - date from publication_date OR date detection
    - date_confidence from detection

    Filters:
    - Only x.com and twitter.com URLs
    - Filters by date range (30-day window)

    Args:
        response: Raw SearXNG response dict
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)

    Returns:
        List of dicts with keys: id, text, url, author_handle, date, relevance,
        date_confidence
    """
    items = []

    # Handle error responses
    if "error" in response:
        return items

    # Extract results
    results = response.get("results", [])

    for result in results:
        url = result.get("url", "")

        # Filter: must be x.com or twitter.com URL
        if "x.com" not in url and "twitter.com" not in url:
            continue

        # Extract author handle from URL
        author_handle = extract_author_from_x_url(url)

        # Extract date: try API field first, then detect
        api_date = result.get("publication_date") or result.get("publish_date")
        content = result.get("content", "")
        title = result.get("title", "")

        if api_date:
            # Use API-provided date with high confidence
            date_str = api_date
            date_confidence = "high"
        else:
            # Use date detection
            date_str, date_confidence = date_detect.extract_date_signals(
                url=url,
                snippet=content,
                title=title,
            )

        # Filter by date range
        if date_str and not date_detect.is_date_in_range(date_str, from_date, to_date):
            continue

        # Build item dict
        item = {
            "id": _generate_id_from_url(url),
            "text": title or content,
            "url": url,
            "author_handle": author_handle,
            "date": date_str,
            "relevance": result.get("score", 0.0),
            "date_confidence": date_confidence,
        }

        items.append(item)

    return items


def parse_web_response(
    response: dict,
    from_date: str,
    to_date: str,
) -> List[dict]:
    """Parse SearXNG response into intermediate web dicts.

    Extracts:
    - id, title, url, source_domain, snippet
    - date from publication_date OR date detection
    - date_confidence from detection

    Filters:
    - Filters by date range (30-day window)

    Args:
        response: Raw SearXNG response dict
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)

    Returns:
        List of dicts with keys: id, title, url, source_domain, snippet, date,
        relevance, date_confidence
    """
    items = []

    # Handle error responses
    if "error" in response:
        return items

    # Extract results
    results = response.get("results", [])

    for result in results:
        url = result.get("url", "")

        # Extract source domain from URL
        source_domain = _extract_domain_from_url(url)

        # Extract date: try API field first, then detect
        api_date = result.get("publication_date") or result.get("publish_date")
        content = result.get("content", "")
        title = result.get("title", "")

        if api_date:
            # Use API-provided date with high confidence
            date_str = api_date
            date_confidence = "high"
        else:
            # Use date detection
            date_str, date_confidence = date_detect.extract_date_signals(
                url=url,
                snippet=content,
                title=title,
            )

        # Filter by date range
        if date_str and not date_detect.is_date_in_range(date_str, from_date, to_date):
            continue

        # Build item dict
        item = {
            "id": _generate_id_from_url(url),
            "title": title,
            "url": url,
            "source_domain": source_domain,
            "snippet": content,
            "date": date_str,
            "relevance": result.get("score", 0.0),
            "date_confidence": date_confidence,
        }

        items.append(item)

    return items


def extract_subreddit_from_url(url: str) -> str:
    """Extract subreddit name from Reddit URL.

    Handles: /r/subreddit/, /r/subreddit/comments/...

    Args:
        url: Reddit URL

    Returns:
        Subreddit name (without /r/) or empty string if not found
    """
    match = re.search(r'/r/([^/]+)', url)
    return match.group(1) if match else ""


def extract_author_from_x_url(url: str) -> str:
    """Extract author handle from X URL.

    Handles: x.com/author/status/..., twitter.com/author/status/...

    Args:
        url: X/Twitter URL

    Returns:
        Author handle or empty string if not found
    """
    match = re.search(r'(?:x\.com|twitter\.com)/([^/]+)/', url)
    return match.group(1) if match else ""


def _generate_id_from_url(url: str) -> str:
    """Generate a unique ID from URL.

    Args:
        url: URL string

    Returns:
        Simple hash-based ID
    """
    # Use a simple hash of the URL for ID
    # This is consistent and reversible for our purposes
    return str(abs(hash(url)))


def _extract_domain_from_url(url: str) -> str:
    """Extract domain from URL.

    Args:
        url: URL string

    Returns:
        Domain (e.g., "example.com") or empty string if not found
    """
    match = re.search(r'https?://(?:www\.)?([^/]+)', url)
    return match.group(1) if match else ""
