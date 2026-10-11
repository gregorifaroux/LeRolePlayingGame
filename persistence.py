"""Cross-session persistence for the role-playing game.

One `save.json` holds the latest `game_state` dict and chat history.
The game writes to it after every turn (submit / retry / undo) and
reads from it at startup. `Clear` deletes it to reset the story.

Config via env vars:
    SAVE_FILE  Path to the save file. Default: save.json
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

Message = dict[str, str]

SAVE_FILE = Path(os.getenv("SAVE_FILE", "save.json"))


def load_save() -> dict[str, Any] | None:
    """Return the parsed save (dict with keys 'state', 'history') or None."""
    if not SAVE_FILE.exists():
        return None
    try:
        data = json.loads(SAVE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or "state" not in data or "history" not in data:
        return None
    return data


def save_game(state: dict[str, Any], history: list[Message]) -> None:
    """Write state + history to the save file atomically."""
    payload = {"state": state, "history": history}
    tmp = SAVE_FILE.with_suffix(SAVE_FILE.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp.replace(SAVE_FILE)


def delete_save() -> None:
    """Remove the save file. No-op if it doesn't exist."""
    SAVE_FILE.unlink(missing_ok=True)
