"""Inventory mechanics: detect item changes in GM output, apply them.

Mirrors the DeepLearning.AI course lesson L4, local-Ollama edition.
After the game master writes a story beat, a second LLM pass (in JSON
mode) extracts item deltas:

    "You buy a sword from the merchant for 5 gold."
        -> [{"name": "sword", "change_amount": 1},
            {"name": "gold",  "change_amount": -5}]

`update_inventory` applies them to a mutable dict and returns a short
summary line that gets appended to the chatbot message so the player
can see what changed.

Config via env vars:
    OLLAMA_URL         Ollama OpenAI-compatible chat endpoint.
                       Default: http://localhost:11434/v1/chat/completions
    INVENTORY_MODEL    Model tag for the JSON extraction call.
                       Default: qwen2.5:14b (same as the game master)
"""

from __future__ import annotations

import json
import os

import requests

OLLAMA_URL = os.getenv(
    "OLLAMA_URL", "http://localhost:11434/v1/chat/completions"
)
INVENTORY_MODEL = os.getenv("INVENTORY_MODEL", "qwen2.5:14b")

STARTING_INVENTORY = {
    "cloth robes": 1,
    "silver moon pendant": 1,
    "spellbook": 1,
    "gold": 5,
}

Message = dict[str, str]
ItemUpdate = dict[str, int | str]

# Few-shot primes the model on the exact output shape. Instruct models
# otherwise wander into prose or wrap the JSON in markdown fences.
_FEW_SHOT: list[Message] = [
    {
        "role": "system",
        "content": (
            "You are a JSON-only inventory tracker. You only output "
            "valid JSON with the key 'itemUpdates'. No other text ever."
        ),
    },
    {
        "role": "user",
        "content": (
            "Inventory: {'cloth pants': 1, 'cloth shirt': 1, 'gold': 5}\n"
            "Story: You buy a sword from the merchant for 5 gold."
        ),
    },
    {
        "role": "assistant",
        "content": (
            '{"itemUpdates": [{"name": "sword", "change_amount": 1}, '
            '{"name": "gold", "change_amount": -5}]}'
        ),
    },
    {
        "role": "user",
        "content": (
            "Inventory: {'cloth pants': 1, 'gold': 3}\n"
            "Story: You walk through the forest and see a river."
        ),
    },
    {"role": "assistant", "content": '{"itemUpdates": []}'},
]


def detect_inventory_changes(inventory: dict[str, int],
                             story: str) -> list[ItemUpdate]:
    """Return the list of inventory deltas implied by a story beat.

    JSON mode is enabled server-side (`response_format: json_object`)
    so the model is forced to emit parseable JSON.
    """
    messages = _FEW_SHOT + [
        {
            "role": "user",
            "content": f"Inventory: {inventory}\nStory: {story}",
        }
    ]
    r = requests.post(
        OLLAMA_URL,
        json={
            "model": INVENTORY_MODEL,
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
        return json.loads(raw).get("itemUpdates", [])
    except (json.JSONDecodeError, AttributeError):
        return []


def update_inventory(inventory: dict[str, int],
                     item_updates: list[ItemUpdate]) -> str:
    """Apply item deltas in place. Returns a human-readable summary.

    - Positive deltas add to an existing count or create a new entry.
    - Negative deltas only subtract from items the player already holds.
    - Entries that would drop to zero or below are removed.
    """
    update_msg = ""
    for update in item_updates:
        name = update["name"]
        change_amount = update["change_amount"]
        if not isinstance(name, str) or not isinstance(change_amount, int):
            continue

        if change_amount > 0:
            inventory[name] = inventory.get(name, 0) + change_amount
            update_msg += f"\nInventory: {name} +{change_amount}"
        elif change_amount < 0 and name in inventory:
            inventory[name] += change_amount
            update_msg += f"\nInventory: {name} {change_amount}"

        if name in inventory and inventory[name] <= 0:
            del inventory[name]

    return update_msg
