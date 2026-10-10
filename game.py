#!/usr/bin/env python3
"""Interactive AI role-playing game, local-Ollama edition.

Runs a Gradio chat UI backed by a local Ollama model. The game master
(the LLM) generates an opening scene from a chosen world/kingdom/town/
character, then continues the story one short beat at a time as the
player types actions.

Config via env vars:
    OLLAMA_URL     Ollama OpenAI-compatible chat endpoint.
                   Default: http://localhost:11434/v1/chat/completions
    OLLAMA_MODEL   Model tag Ollama has pulled.
                   Default: qwen2.5:14b
    WORLD_FILE     Path to a world JSON (see Lunevraie_L1.json for shape).
                   Default: Lunevraie_L1.json
    KINGDOM_NAME   Key under world["kingdoms"].   Default: Éclairia
    TOWN_NAME      Key under kingdom["towns"].    Default: Luciere
    CHARACTER_NAME Key under town["npcs"].        Default: Alaric Éclair
"""

from __future__ import annotations

import os
from typing import Any

import gradio as gr
import requests

from helper import load_world, save_world


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


def run_action(message: str, history: list[list[str]],
               game_state: dict[str, Any]) -> str:
    """Produce the next beat of the story.

    `history` comes from Gradio ChatInterface as [[user, bot], ...].
    The sentinel 'start game' returns the pre-generated opening instead
    of calling the LLM, matching the lesson's UX.
    """
    if message == "start game":
        return game_state["start"]

    world_info = (
        f"\nWorld: {game_state['world']}"
        f"\nKingdom: {game_state['kingdom']}"
        f"\nTown: {game_state['town']}"
        f"\nYour Character: {game_state['character']}"
    )

    messages: list[Message] = [
        {"role": "system", "content": ACTION_SYSTEM_PROMPT},
        {"role": "user", "content": world_info},
    ]
    for user_msg, bot_msg in history:
        messages.append({"role": "user", "content": user_msg})
        messages.append({"role": "assistant", "content": bot_msg})
    messages.append({"role": "user", "content": message})

    return chat(messages)


# -- UI ----------------------------------------------------------------------

def start_game(main_loop, share: bool = False) -> None:
    """Launch the Gradio chat UI and block until it is closed."""
    demo = gr.ChatInterface(
        main_loop,
        chatbot=gr.Chatbot(
            height=250,
            placeholder="Type 'start game' to begin",
        ),
        textbox=gr.Textbox(
            placeholder="What do you do next?",
            container=False,
            scale=7,
        ),
        title="AI RPG, Lunevraie",
        theme="soft",
        examples=["start game", "Look around", "Continue the story"],
        cache_examples=False,
        retry_btn="Retry",
        undo_btn="Undo",
        clear_btn="Clear",
    )
    demo.launch(share=share, server_name="127.0.0.1")


def main() -> None:
    game_state = build_game_state()
    print(game_state["start"])

    def main_loop(message: str, history: list[list[str]]) -> str:
        return run_action(message, history, game_state)

    start_game(main_loop, share=False)


if __name__ == "__main__":
    main()
