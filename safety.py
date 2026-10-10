"""Llama Guard 3 moderation using the native S1-S14 hazard taxonomy.

The 1b model is accurate on the categories it was trained on but
mis-maps content when the prompt tries to override those categories.
This module uses the trained taxonomy as-is via Ollama's
`/v1/chat/completions` endpoint and chooses which hazards block the
turn with a Python-side allowlist, so the moderation decision stays
local and auditable.

Config via env vars:
    OLLAMA_URL   Ollama OpenAI-compatible chat endpoint.
                 Default: http://localhost:11434/v1/chat/completions
    GUARD_MODEL  Llama Guard model tag.
                 Default: llama-guard3:1b

Policy (what each S-code means and whether we block it):
    S1  Violent Crimes            allowed (fantasy combat)
    S2  Non-Violent Crimes        allowed
    S3  Sex Crimes                blocked
    S4  Child Sexual Exploitation blocked
    S5  Defamation                allowed
    S6  Specialized Advice        allowed
    S7  Privacy                   allowed
    S8  Intellectual Property     allowed
    S9  Indiscriminate Weapons    allowed
    S10 Hate                      blocked
    S11 Self-Harm                 blocked
    S12 Sexual Content            blocked
    S13 Elections                 allowed
    S14 Code Interpreter Abuse    allowed

Gaps vs. the DeepLearning.AI course policy: profanity and drug use
are not covered by the native taxonomy and are not filtered here.
"""

from __future__ import annotations

import os

import requests

OLLAMA_URL = os.getenv(
    "OLLAMA_URL", "http://localhost:11434/v1/chat/completions"
)
GUARD_MODEL = os.getenv("GUARD_MODEL", "llama-guard3:1b")

BLOCKED_CATEGORIES = frozenset({"S3", "S4", "S10", "S11", "S12"})

REFUSAL_TEXT = (
    "The game master pauses. \"That is not a path this story will take.\""
)

CATEGORY_TITLES = {
    "S1": "Violent Crimes",
    "S2": "Non-Violent Crimes",
    "S3": "Sex Crimes",
    "S4": "Child Sexual Exploitation",
    "S5": "Defamation",
    "S6": "Specialized Advice",
    "S7": "Privacy",
    "S8": "Intellectual Property",
    "S9": "Indiscriminate Weapons",
    "S10": "Hate",
    "S11": "Self-Harm",
    "S12": "Sexual Content",
    "S13": "Elections",
    "S14": "Code Interpreter Abuse",
}

Message = dict[str, str]


def format_refusal(categories: str) -> str:
    """Refusal line, with a parenthetical list of violated categories.

    `categories` is the comma-separated category string Llama Guard
    returned on the second line of an "unsafe" reply.
    """
    if not categories:
        return REFUSAL_TEXT
    labeled = []
    for code in (c.strip() for c in categories.split(",")):
        title = CATEGORY_TITLES.get(code)
        labeled.append(f"{code}: {title}" if title else code)
    return f"{REFUSAL_TEXT} (violated: {', '.join(labeled)})"


def moderate(messages: list[Message]) -> tuple[bool, str]:
    """Classify a conversation with Llama Guard 3. Returns (ok, categories).

    Llama Guard replies "safe" on one line, or "unsafe\\n<Scode>" on
    two lines, where <Scode> is a hazard id (S1, S12, etc.).

    Only categories in BLOCKED_CATEGORIES fail the check. S1 Violent
    Crimes passes so fantasy combat still works.
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
        categories = lines[1].strip() if len(lines) > 1 else ""
        codes = {c.strip() for c in categories.split(",") if c.strip()}
        if codes & BLOCKED_CATEGORIES:
            return False, categories
    return True, ""
