"""Bird CLI client for X (Twitter) search."""

import json
import shutil
import subprocess
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# Depth configurations: number of results to request
DEPTH_CONFIG = {
    "quick": 12,
    "default": 30,
    "deep": 60,
}


def _log(msg: str):
    """Log to stderr."""
    sys.stderr.write(f"[Bird] {msg}\n")
    sys.stderr.flush()


def is_bird_installed() -> bool:
    """Check if Bird CLI is installed.

    Returns:
        True if 'bird' command is available in PATH, False otherwise.
    """
    return shutil.which("bird") is not None


def is_bird_authenticated() -> Optional[str]:
    """Check if Bird is authenticated by running 'bird whoami'.

    Returns:
        Username if authenticated, None otherwise.
    """
    if not is_bird_installed():
        return None

    try:
        result = subprocess.run(
            ["bird", "whoami"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            # Output is typically the username
            return result.stdout.strip().split('\n')[0]
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        return None


def check_npm_available() -> bool:
    """Check if npm is available for installation.

    Returns:
        True if 'npm' command is available in PATH, False otherwise.
    """
    return shutil.which("npm") is not None


def install_bird() -> Tuple[bool, str]:
    """Install Bird CLI via npm.

    Returns:
        Tuple of (success, message).
    """
    if not check_npm_available():
        return False, "npm not found. Install Node.js first, or install Bird manually: https://github.com/steipete/bird"

    try:
        _log("Installing Bird CLI...")
        result = subprocess.run(
            ["npm", "install", "-g", "@steipete/bird"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            return True, "Bird CLI installed successfully!"
        else:
            error = result.stderr.strip() or result.stdout.strip() or "Unknown error"
            return False, f"Installation failed: {error}"
    except subprocess.TimeoutExpired:
        return False, "Installation timed out"
    except Exception as e:
        return False, f"Installation error: {e}"


def get_bird_status() -> Dict[str, Any]:
    """Get comprehensive Bird status.

    Returns:
        Dict with keys: installed, authenticated, username, can_install
    """
    installed = is_bird_installed()
    username = is_bird_authenticated() if installed else None

    return {
        "installed": installed,
        "authenticated": username is not None,
        "username": username,
        "can_install": check_npm_available(),
    }


def search_x(
    topic: str,
    from_date: str,
    to_date: str,
    depth: str = "default",
) -> Dict[str, Any]:
    """Search X using Bird CLI.

    Args:
        topic: Search topic
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD) - unused but kept for API compatibility
        depth: Research depth - "quick", "default", or "deep"

    Returns:
        Raw Bird JSON response or error dict.
    """
    count = DEPTH_CONFIG.get(depth, DEPTH_CONFIG["default"])

    # Build command
    cmd = [
        "bird", "search",
        topic,
        "--since", from_date,
        "-n", str(count),
        "--json",
    ]

    # Adjust timeout based on depth
    timeout = 30 if depth == "quick" else 45 if depth == "default" else 60

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode != 0:
            error = result.stderr.strip() or "Bird search failed"
            return {"error": error, "items": []}

        # Parse JSON output
        output = result.stdout.strip()
        if not output:
            return {"items": []}

        return json.loads(output)

    except subprocess.TimeoutExpired:
        return {"error": "Search timed out", "items": []}
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON response: {e}", "items": []}
    except Exception as e:
        return {"error": str(e), "items": []}