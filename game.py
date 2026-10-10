#!/usr/bin/env python3
"""Interactive AI role-playing game, local-Ollama edition.

Entrypoint. The game master (an Ollama-hosted LLM) generates an
opening scene from a chosen world/kingdom/town/character, then
continues the story one short beat at a time as the player types
actions. Every turn is moderated by Llama Guard 3 (see safety.py).

Module layout:
    game.py    (this file) config, chat client, prompts, game state,
               run_action, main() entrypoint
    safety.py  Llama Guard moderation + refusal policy
    ui.py      Gradio Blocks layout and launch

Config via env vars:
    OLLAMA_URL     Ollama OpenAI-compatible chat endpoint.
                   Default: http://localhost:11434/v1/chat/completions
    OLLAMA_MODEL   Game-master model tag Ollama has pulled.
                   Default: qwen2.5:14b
    WORLD_FILE     Path to a world JSON (see Lunevraie_L1.json for shape).
                   Default: Lunevraie_L1.json
    KINGDOM_NAME   Key under world["kingdoms"].   Default: Éclairia
    TOWN_NAME      Key under kingdom["towns"].    Default: Luciere
    CHARACTER_NAME Key under town["npcs"].        Default: Alaric Éclair

safety.py reads its own GUARD_MODEL env var.
"""

from __future__ import annotations

import os
from typing import Any

import requests

from helper import load_world, save_world
from safety import format_refusal, moderate
from ui import start_game


# -- Config ------------------------------------------------------------------

OLLAMA_URL = os.getenv(
    "OLLAMA_URL", "http://localhost:11434/v1/chat/completions"
)
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")

WORLD_FILE = os.getenv("WORLD_FILE", "Lunevraie_L1.json")
KINGDOM_NAME = os.getenv("KINGDOM_NAME", "Éclairia")
TOWN_NAME = os.getenv("TOWN_NAME", "Luciere")
CHARACTER_NAME = os.getenv("CHARACTER_NAME", "Alaric Éclair")

RUN_WORLD_FILE = "Lunevraie_L1_run.json"


# -- LLM ---------------------------------------------------------------------

Message = dict[str, str]


def chat(messages: list[Message], temperature: float = 1.0,
         max_tokens: int = 1800) -> str:
    """Send an OpenAI-shaped chat request to Ollama and return the text.

    Ollama exposes an OpenAI-compatible endpoint, so no SDK is needed:
    a plain POST with {model, messages, ...} is enough.
    """
    r = requests.post(
        OLLAMA_URL,
        json={
            "model": OLLAMA_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        },
        timeout=600,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


# -- Prompts -----------------------------------------------------------------

START_SYSTEM_PROMPT = (
    "You are an AI Game master. Your job is to create a start to an "
    "adventure based on the world, kingdom, town and character a player "
    "is playing as.\n"
    "Instructions:\n"
    "You must only use 2-4 sentences.\n"
    'Write in second person. For example: "You are Jack".\n'
    'Write in present tense. For example "You stand at...".\n'
    "First describe the character and their backstory.\n"
    "Then describes where they start and what they see around them."
)

ACTION_SYSTEM_PROMPT = (
    "You are an AI Game master. Your job is to write what happens next "
    "in a player's adventure game.\n"
    "Instructions:\n"
    "You must only write 1-3 sentences in response.\n"
    "Always write in second person present tense.\n"
    "Ex. (You look north and see...)"
)


# -- Game state --------------------------------------------------------------

def build_game_state() -> dict[str, Any]:
    """Load the world, select scope, generate an opening, return game state.

    This talks to the LLM to produce the opening scene, so it is slow
    and should be called once at startup.
    """
    world = load_world(WORLD_FILE)
    kingdom = world["kingdoms"][KINGDOM_NAME]
    town = kingdom["towns"][TOWN_NAME]
    character = town["npcs"][CHARACTER_NAME]

    world_info = (
        f"\nWorld: {world}"
        f"\nKingdom: {kingdom}"
        f"\nTown: {town}"
        f"\nYour Character: {character}\n"
    )

    start = chat(
        [
            {"role": "system", "content": START_SYSTEM_PROMPT},
            {"role": "user", "content": world_info + "\nYour Start:"},
        ]
    )
    world["start"] = start
    save_world(world, RUN_WORLD_FILE)

    return {
        "world": world["description"],
        "kingdom": kingdom["description"],
        "town": town["description"],
        "character": character["description"],
        "start": start,
    }


def run_action(message: str, history: list[Message],
               game_state: dict[str, Any]) -> str:
    """Produce the next beat of the story.

    `history` is a list of {"role": ..., "content": ...} messages
    (Gradio 5+ chat format). The opening scene is pre-seeded into the
    chatbot before the first turn, so this function always calls the
    game master, unless Llama Guard blocks the turn.

    Flow:
        1. Moderate the player's input in context. On block, hard-refuse
           and skip the game master entirely.
        2. Call the game master.
        3. Moderate the game master's reply. On block, hard-refuse.
    """
    guard_history = history + [{"role": "user", "content": message}]
    is_safe, categories = moderate(guard_history)
    if not is_safe:
        return format_refusal(categories)

    world_info = (
        f"\nWorld: {game_state['world']}"
        f"\nKingdom: {game_state['kingdom']}"
        f"\nTown: {game_state['town']}"
        f"\nYour Character: {game_state['character']}"
    )

    messages: list[Message] = [
        {"role": "system", "content": ACTION_SYSTEM_PROMPT},
        {"role": "user", "content": world_info},
        *history,
        {"role": "user", "content": message},
    ]
    reply = chat(messages)

    is_safe, categories = moderate(
        guard_history + [{"role": "assistant", "content": reply}]
    )
    if not is_safe:
        return format_refusal(categories)
    return reply


# -- Entrypoint --------------------------------------------------------------

def main() -> None:
    game_state = build_game_state()
    print(game_state["start"])

    def main_loop(message: str, history: list[Message]) -> str:
        return run_action(message, history, game_state)

    start_game(main_loop, opening=game_state["start"], share=False)


if __name__ == "__main__":
    main()
