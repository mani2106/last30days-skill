"""Date detection utilities - shared by WebSearch and SearXNG."""

import re
from datetime import datetime, timedelta
from typing import Optional, Tuple


def extract_date_signals(
    url: str,
    snippet: str = "",
    title: str = "",
) -> Tuple[Optional[str], str]:
    """Extract date with confidence level.

    Args:
        url: URL to search for date patterns
        snippet: Text snippet from search result
        title: Title from search result

    Returns:
        Tuple of (date_str, confidence) where confidence is 'high', 'med', 'low', or 'none'
    """
    # Try URL patterns first (highest confidence)
    date = extract_date_from_url(url)
    if date:
        return date, 'high'

    # Try snippet (medium confidence)
    date = extract_date_from_text(snippet)
    if date:
        return date, 'med'

    # Try title (low confidence)
    date = extract_date_from_text(title)
    if date:
        return date, 'low'

    return None, 'none'


def extract_date_from_url(url: str) -> Optional[str]:
    """Extract date from URL patterns.

    Supports:
    - /2026/01/24/article-title
    - /2026-01-24/article
    - /20260124/title

    Args:
        url: URL string to search

    Returns:
        Date string in YYYY-MM-DD format or None
    """
    patterns = [
        r'/(\d{4})/(\d{2})/(\d{2})/',  # /2026/01/24/
        r'/(\d{4})-(\d{2})-(\d{2})/',  # /2026-01-24/
        r'/(\d{4})(\d{2})(\d{2})',     # /20260124
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            year, month, day = match.groups()
            return f"{year}-{month}-{day}"

    return None


def extract_date_from_text(text: str) -> Optional[str]:
    """Extract date from text using natural language patterns.

    Args:
        text: Text to search for date patterns

    Returns:
        Date string in YYYY-MM-DD format or None
    """
    if not text:
        return None

    # Try relative dates first
    relative_patterns = {
        r'\btoday\b': 'today',
        r'\byesterday\b': 'yesterday',
    }

    for pattern, replacement in relative_patterns.items():
        if re.search(pattern, text, re.IGNORECASE):
            return replacement

    # Try "X days ago" pattern
    days_ago_match = re.search(r'(\d+)\s+days?\s+ago', text, re.IGNORECASE)
    if days_ago_match:
        days = int(days_ago_match.group(1))
        date = datetime.now() - timedelta(days=days)
        return date.strftime('%Y-%m-%d')

    # Try absolute date patterns: January 24, 2026 | 24 January 2026
    months = {
        'january': '01', 'february': '02', 'march': '03', 'april': '04',
        'may': '05', 'june': '06', 'july': '07', 'august': '08',
        'september': '09', 'october': '10', 'november': '11', 'december': '12'
    }

    # Pattern: "January 24, 2026" or "24 January 2026"
    date_pattern = r'(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)[,\.]?\s+(\d{4})'
    match = re.search(date_pattern, text, re.IGNORECASE)
    if match:
        day, month_name, year = match.groups()
        month = months.get(month_name.lower(), '01')
        return f"{year}-{month}-{day.zfill(2)}"

    # Pattern: "2026-01-24" or "2026/01/24"
    iso_pattern = r'(\d{4})[-/](\d{2})[-/](\d{2})'
    match = re.search(iso_pattern, text)
    if match:
        year, month, day = match.groups()
        return f"{year}-{month}-{day}"

    return None


def is_date_in_range(
    date_str: str,
    from_date: str,
    to_date: str,
) -> bool:
    """Check if extracted date falls within range.

    Args:
        date_str: Date string (YYYY-MM-DD or 'today'/'yesterday')
        from_date: Start date in YYYY-MM-DD format
        to_date: End date in YYYY-MM-DD format

    Returns:
        True if date is within range (inclusive)
    """
    if not date_str or date_str == 'none':
        return True  # Can't filter, so include it

    try:
        # Parse the extracted date
        if date_str == 'today':
            extracted = datetime.now()
        elif date_str == 'yesterday':
            extracted = datetime.now() - timedelta(days=1)
        else:
            extracted = datetime.strptime(date_str, '%Y-%m-%d')

        # Parse range dates
        start = datetime.strptime(from_date, '%Y-%m-%d')
        end = datetime.strptime(to_date, '%Y-%m-%d')

        # Check if within range (inclusive)
        return start <= extracted <= end

    except (ValueError, TypeError):
        # If parsing fails, include the item
        return True
