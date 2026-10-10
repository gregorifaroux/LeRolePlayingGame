"""Character class, experience points, and leveling.

Shape of a progression slice on `game_state`:

    class: "Mage" | "Warrior" | "Healer"
    level: int
    xp:    int

Three class presets:

    Mage     — arcane focus, French spell incantations, starts with
               cloth robes, silver moon pendant, spellbook, 5 gold.
    Warrior  — martial focus, blunt tactics, starts with leather
               armor, shortsword, shield, 5 gold.
    Healer   — restorative focus, calm demeanor, starts with linen
               robes, herb pouch, healing tome, 5 gold.

XP is awarded per turn by a second JSON-mode LLM call that reads the
player's action and the GM's reply and returns `{"xpGained": N}`.
Pure-Python math then advances `level` across the thresholds in
`LEVEL_THRESHOLDS`.

Config via env vars:
    OLLAMA_URL         Ollama OpenAI-compatible chat endpoint.
                       Default: http://localhost:11434/v1/chat/completions
    PROGRESSION_MODEL  Model tag for the XP extraction call.
                       Default: qwen2.5:14b
"""

from __future__ import annotations

import json
import os

import requests

OLLAMA_URL = os.getenv(
    "OLLAMA_URL", "http://localhost:11434/v1/chat/completions"
)
PROGRESSION_MODEL = os.getenv("PROGRESSION_MODEL", "qwen2.5:14b")

CLASSES = ("Mage", "Warrior", "Healer")

CLASS_PROMPTS: dict[str, str] = {
    "Mage": (
        "The player is a Mage. They solve problems with arcane magic. "
        "Spell names and incantations are in French. The Mage knows "
        "basic cantrips at level 1 and unlocks new spells at each "
        "level-up."
    ),
    "Warrior": (
        "The player is a Warrior. They solve problems with martial "
        "skill, steel, and resolve. Narrate combat in plain, physical "
        "terms. The Warrior gains new combat techniques at each "
        "level-up."
    ),
    "Healer": (
        "The player is a Healer. They solve problems with restorative "
        "magic, herbcraft, and compassion. Narrate healing acts in "
        "warm, gentle terms. The Healer gains new restorative powers "
        "at each level-up."
    ),
}

CLASS_INVENTORIES: dict[str, dict[str, int]] = {
    "Mage": {
        "cloth robes": 1,
        "silver moon pendant": 1,
        "spellbook": 1,
        "gold": 5,
    },
    "Warrior": {
        "leather armor": 1,
        "shortsword": 1,
        "shield": 1,
        "gold": 5,
    },
    "Healer": {
        "linen robes": 1,
        "herb pouch": 1,
        "healing tome": 1,
        "gold": 5,
    },
}

# XP totals required to reach each level. Level 1 is the floor.
LEVEL_THRESHOLDS: dict[int, int] = {
    1: 0,
    2: 10,
    3: 25,
    4: 50,
    5: 100,
    6: 200,
    7: 400,
    8: 800,
}

Message = dict[str, str]

# Few-shot for the XP judge. Small wins = 1-5, moderate wins = 10-20,
# boss/milestone = 30+. No change = 0.
_FEW_SHOT: list[Message] = [
    {
        "role": "system",
        "content": (
            "You are a JSON-only XP judge for a role-playing game. "
            "You only output valid JSON with the key 'xpGained' and "
            "an integer value. No other text ever. Reward meaningful "
            "progress: 0 for idle narration, 1-5 for small wins "
            "(solved a puzzle, haggled a merchant), 10-20 for "
            "defeating a foe or finishing a side quest beat, 30-50 "
            "for defeating a boss or a major story milestone."
        ),
    },
    {
        "role": "user",
        "content": (
            "Player action: Look around.\n"
            "Story: You see sorcerers chatting in the moonlit square."
        ),
    },
    {"role": "assistant", "content": '{"xpGained": 0}'},
    {
        "role": "user",
        "content": (
            "Player action: Attack the goblin with my sword.\n"
            "Story: Your blade finds its mark and the goblin falls."
        ),
    },
    {"role": "assistant", "content": '{"xpGained": 15}'},
    {
        "role": "user",
        "content": (
            "Player action: Cast Lumière de Lune to banish the lich.\n"
            "Story: The lich dissolves into silver light. The crypt "
            "falls silent. Your quest is complete."
        ),
    },
    {"role": "assistant", "content": '{"xpGained": 40}'},
]


def detect_xp_gain(player_action: str, story: str) -> int:
    """Judge the XP earned by this turn. Returns a non-negative int."""
    messages = _FEW_SHOT + [
        {
            "role": "user",
            "content": f"Player action: {player_action}\nStory: {story}",
        }
    ]
    r = requests.post(
        OLLAMA_URL,
        json={
            "model": PROGRESSION_MODEL,
            "messages": messages,
            "temperature": 0.3,
            "stream": False,
            "response_format": {"type": "json_object"},
        },
        timeout=120,
    )
    r.raise_for_status()
    raw = r.json()["choices"][0]["message"]["content"]
    try:
        gained = int(json.loads(raw).get("xpGained", 0))
    except (json.JSONDecodeError, TypeError, ValueError, AttributeError):
        return 0
    return max(0, gained)


def level_for_xp(xp: int) -> int:
    """Highest level whose threshold is <= xp."""
    reached = 1
    for lvl, needed in LEVEL_THRESHOLDS.items():
        if xp >= needed:
            reached = max(reached, lvl)
    return reached


def apply_xp(game_state: dict, xp_gained: int) -> str:
    """Add XP to `game_state`, promote on crossed thresholds.

    Returns a summary line suitable for appending to the chatbot
    message. Empty string if nothing changed.
    """
    if xp_gained <= 0:
        return ""
    prior_level = game_state.get("level", 1)
    game_state["xp"] = game_state.get("xp", 0) + xp_gained
    new_level = level_for_xp(game_state["xp"])
    game_state["level"] = new_level

    msg = f"\nXP +{xp_gained} (total {game_state['xp']})"
    if new_level > prior_level:
        msg += f"\n✨ Level up! {prior_level} → {new_level}"
    return msg
