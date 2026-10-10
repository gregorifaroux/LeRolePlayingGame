"""Llama Guard 3 moderation for the role-playing game.

Classifies every player input and every game-master reply via a
local Ollama Llama Guard 3 instance. A hazard code from a configured
blocklist hard-refuses the turn.

Config via env vars:
    OLLAMA_URL   Ollama OpenAI-compatible chat endpoint.
                 Default: http://localhost:11434/v1/chat/completions
    GUARD_MODEL  Llama Guard model tag.
                 Default: llama-guard3:1b

Policy:
    Blocked hazards hard-refuse the turn. Everything else passes.
    Defaults:
        S3  Sex Crimes
        S4  Child Sexual Exploitation
        S12 Sexual Content
    S1 Violent Crimes (fantasy combat) is intentionally allowed.
"""

from __future__ import annotations

import os

import requests

OLLAMA_URL = os.getenv(
    "OLLAMA_URL", "http://localhost:11434/v1/chat/completions"
)
GUARD_MODEL = os.getenv("GUARD_MODEL", "llama-guard3:1b")

BLOCKED_CATEGORIES = frozenset({"S3", "S4", "S12"})
REFUSAL_TEXT = (
    "The game master pauses. \"That is not a path this story will take.\""
)

Message = dict[str, str]


def moderate(messages: list[Message]) -> tuple[bool, str]:
    """Classify a conversation with Llama Guard 3. Returns (ok, category).

    Llama Guard replies with either "safe" on one line, or
    "unsafe\\n<Scode>" on two lines, where <Scode> is a hazard id like
    S1, S12, etc.

    Only categories in BLOCKED_CATEGORIES fail the check. Everything
    else, including S1 Violent Crimes (fantasy combat), passes.
    """
    r = requests.post(
        OLLAMA_URL,
        json={
            "model": GUARD_MODEL,
            "messages": messages,
            "temperature": 0,
            "stream": False,
        },
        timeout=120,
    )
    r.raise_for_status()
    reply = r.json()["choices"][0]["message"]["content"].strip()
    lines = reply.splitlines()
    if lines and lines[0].strip().lower() == "unsafe":
        category = lines[1].strip() if len(lines) > 1 else ""
        if category in BLOCKED_CATEGORIES:
            return False, category
    return True, ""
