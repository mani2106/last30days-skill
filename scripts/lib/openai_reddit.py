"""OpenAI Responses API client for Reddit discovery."""

import json
import re
from typing import Any, Dict, List, Optional

from . import http

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"

# Depth configurations: (min, max) threads to request
DEPTH_CONFIG = {
    "quick": (8, 12),
    "default": (20, 30),
    "deep": (50, 70),
}

REDDIT_SEARCH_PROMPT = """Search Reddit for discussions about: {topic}

Use web search to find {min_items}-{max_items} relevant Reddit threads from the last 30 days.

CRITICAL: After searching, you MUST extract information from the Reddit URLs you found and return them as JSON.

For EACH Reddit thread URL you find in your search results, extract:
- The thread title
- The full Reddit URL
- The subreddit name
- Approximate date if visible
- Why it's relevant to "{topic}"

Return ONLY valid JSON in this exact format:
{{
  "items": [
    {{
      "title": "Actual thread title from Reddit",
      "url": "https://www.reddit.com/r/subreddit/comments/...",
      "subreddit": "subreddit_name",
      "date": "YYYY-MM-DD or null if unknown",
      "why_relevant": "Brief explanation of relevance to {topic}",
      "relevance": 0.85
    }}
  ]
}}

Rules:
- You MUST include threads from the search results - do NOT return empty items
- relevance is 0.0 to 1.0 (1.0 = highly relevant)
- date must be YYYY-MM-DD format or null
- Include threads from diverse subreddits
- Prefer threads with substantive discussions"""


def search_reddit(
    api_key: str,
    model: str,
    topic: str,
    depth: str = "default",
    mock_response: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Search Reddit for relevant threads using OpenAI Responses API.

    Args:
        api_key: OpenAI API key
        model: Model to use
        topic: Search topic
        depth: Research depth - "quick", "default", or "deep"
        mock_response: Mock response for testing

    Returns:
        Raw API response
    """
    if mock_response is not None:
        return mock_response

    min_items, max_items = DEPTH_CONFIG.get(depth, DEPTH_CONFIG["default"])

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # Adjust timeout based on depth
    timeout = 60 if depth == "quick" else 90 if depth == "default" else 120

    payload = {
        "model": model,
        "tools": [
            {
                "type": "web_search",
                "filters": {
                    "allowed_domains": ["reddit.com"]
                }
            }
        ],
        "include": ["web_search_call.action.sources"],
        "input": REDDIT_SEARCH_PROMPT.format(topic=topic, min_items=min_items, max_items=max_items),
    }

    return http.post(OPENAI_RESPONSES_URL, payload, headers=headers, timeout=timeout)


def parse_reddit_response(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse OpenAI response to extract Reddit items.

    Args:
        response: Raw API response

    Returns:
        List of item dicts
    """
    items = []

    # Check for API errors first
    if "error" in response and response["error"]:
        error = response["error"]
        err_msg = error.get("message", str(error)) if isinstance(error, dict) else str(error)
        print(f"[REDDIT ERROR] OpenAI API error: {err_msg}", flush=True)
        return items

    # Try to find the output text
    output_text = ""
    if "output" in response:
        output = response["output"]
        if isinstance(output, str):
            output_text = output
        elif isinstance(output, list):
            for item in output:
                if isinstance(item, dict):
                    if item.get("type") == "message":
                        content = item.get("content", [])
                        for c in content:
                            if isinstance(c, dict) and c.get("type") == "output_text":
                                output_text = c.get("text", "")
                                break
                    elif "text" in item:
                        output_text = item["text"]
                elif isinstance(item, str):
                    output_text = item
                if output_text:
                    break

    # Also check for choices (older format)
    if not output_text and "choices" in response:
        for choice in response["choices"]:
            if "message" in choice:
                output_text = choice["message"].get("content", "")
                break

    if not output_text:
        print(f"[REDDIT WARNING] No output text found in OpenAI response. Keys present: {list(response.keys())}", flush=True)
        return items

    # Extract JSON from the response
    json_match = re.search(r'\{[\s\S]*"items"[\s\S]*\}', output_text)
    if json_match:
        try:
            data = json.loads(json_match.group())
            items = data.get("items", [])
        except json.JSONDecodeError:
            pass

    # Validate and clean items
    clean_items = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue

        url = item.get("url", "")
        if not url or "reddit.com" not in url:
            continue

        clean_item = {
            "id": f"R{i+1}",
            "title": str(item.get("title", "")).strip(),
            "url": url,
            "subreddit": str(item.get("subreddit", "")).strip().lstrip("r/"),
            "date": item.get("date"),
            "why_relevant": str(item.get("why_relevant", "")).strip(),
            "relevance": min(1.0, max(0.0, float(item.get("relevance", 0.5)))),
        }

        # Validate date format
        if clean_item["date"]:
            if not re.match(r'^\d{4}-\d{2}-\d{2}$', str(clean_item["date"])):
                clean_item["date"] = None

        clean_items.append(clean_item)

    return clean_items
