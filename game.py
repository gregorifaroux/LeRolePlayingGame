#!/usr/bin/env python3
"""Interactive AI role-playing game, local-Ollama edition.

Runs a Gradio chat UI backed by a local Ollama model. The game master
(the LLM) generates an opening scene from a chosen world/kingdom/town/
character, then continues the story one short beat at a time as the
player types actions.

Config via env vars:
    OLLAMA_URL     Ollama OpenAI-compatible chat endpoint.
                   Default: http://localhost:11434/v1/chat/completions
    OLLAMA_MODEL   Game-master model tag Ollama has pulled.
                   Default: qwen2.5:14b
    GUARD_MODEL    Llama Guard model tag for moderation.
                   Default: llama-guard3:1b
    WORLD_FILE     Path to a world JSON (see Lunevraie_L1.json for shape).
                   Default: Lunevraie_L1.json
    KINGDOM_NAME   Key under world["kingdoms"].   Default: Éclairia
    TOWN_NAME      Key under kingdom["towns"].    Default: Luciere
    CHARACTER_NAME Key under town["npcs"].        Default: Alaric Éclair

Safety:
    Every player input and every game-master reply is classified by
    Llama Guard 3 before anything is shown. Fantasy combat (S1 Violent
    Crimes) is allowed; sex-related hazards are hard-refused:
        S3  Sex Crimes
        S4  Child Sexual Exploitation
        S12 Sexual Content
    On any of those, the turn is replaced with a short in-character
    refusal and the game master is not called.
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
GUARD_MODEL = os.getenv("GUARD_MODEL", "llama-guard3:1b")

BLOCKED_CATEGORIES = frozenset({"S3", "S4", "S12"})
REFUSAL_TEXT = (
    "The game master pauses. \"That is not a path this story will take.\""
)

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


# -- Moderation --------------------------------------------------------------

def moderate(messages: list[Message]) -> tuple[bool, str]:
    """Classify a conversation with Llama Guard 3. Returns (ok, category).

    Llama Guard replies with either "safe" on one line, or "unsafe\\n<Scode>"
    on two lines, where <Scode> is a hazard id like S1, S12, etc.

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
    is_safe, _ = moderate(guard_history)
    if not is_safe:
        return REFUSAL_TEXT

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

    is_safe, _ = moderate(
        guard_history + [{"role": "assistant", "content": reply}]
    )
    if not is_safe:
        return REFUSAL_TEXT
    return reply


# -- UI ----------------------------------------------------------------------

EXAMPLE_ACTIONS = ["Look around", "Continue the story"]

FORCE_LIGHT_JS = """() => {
    const url = new URL(window.location.href);
    if (url.searchParams.get('__theme') !== 'light') {
        url.searchParams.set('__theme', 'light');
        window.location.replace(url.toString());
    }
}"""


def start_game(main_loop, opening: str, share: bool = False) -> None:
    """Launch the Gradio chat UI and block until it is closed.

    `opening` is pre-seeded as the first assistant message so the game
    starts in-scene the moment the page loads, no "start game" prompt
    required.

    Built as a manual Blocks layout, matching the lesson's Gradio 4.x
    ChatInterface shape:

        [ chatbot                                      ]
        [ Retry ] [ Undo ] [ Clear ]
        [ textbox                        ] [ Submit ]
        Examples
        [ Look around ] [ Continue the story ]

    Light mode is forced by redirecting to `?__theme=light` on page
    load, which is the mechanism Gradio 6 reads.
    """
    initial_history: list[Message] = [
        {"role": "assistant", "content": opening},
    ]

    def submit(message: str, history: list[Message]) -> tuple[str, list[Message]]:
        if not message:
            return "", history
        assistant_msg = main_loop(message, history)
        return "", history + [
            {"role": "user", "content": message},
            {"role": "assistant", "content": assistant_msg},
        ]

    def retry(history: list[Message]) -> list[Message]:
        """Regenerate the assistant reply to the last user message."""
        if not history:
            return history
        if history[-1]["role"] == "assistant":
            history = history[:-1]
        if not history or history[-1]["role"] != "user":
            return history
        last_user = history[-1]["content"]
        prior = history[:-1]
        assistant_msg = main_loop(last_user, prior)
        return prior + [
            {"role": "user", "content": last_user},
            {"role": "assistant", "content": assistant_msg},
        ]

    def undo(history: list[Message]) -> list[Message]:
        """Drop the last user/assistant exchange."""
        new = list(history)
        while new and new[-1]["role"] == "assistant":
            new.pop()
        while new and new[-1]["role"] == "user":
            new.pop()
        return new

    def clear() -> list[Message]:
        return list(initial_history)

    with gr.Blocks(title="AI RPG, Lunevraie") as demo:
        chatbot = gr.Chatbot(
            height=400,
            label="Chatbot",
            value=initial_history,
        )
        with gr.Row():
            retry_btn = gr.Button("Retry")
            undo_btn = gr.Button("Undo")
            clear_btn = gr.Button("Clear")
        with gr.Row():
            textbox = gr.Textbox(
                placeholder="What do you do next?",
                container=False,
                scale=7,
            )
            submit_btn = gr.Button("Submit", variant="primary", scale=1)
        gr.Markdown("### Examples")
        with gr.Row():
            for example in EXAMPLE_ACTIONS:
                gr.Button(example).click(
                    lambda h, m=example: submit(m, h),
                    inputs=[chatbot],
                    outputs=[textbox, chatbot],
                )

        submit_btn.click(submit, inputs=[textbox, chatbot], outputs=[textbox, chatbot])
        textbox.submit(submit, inputs=[textbox, chatbot], outputs=[textbox, chatbot])
        retry_btn.click(retry, inputs=[chatbot], outputs=[chatbot])
        undo_btn.click(undo, inputs=[chatbot], outputs=[chatbot])
        clear_btn.click(clear, outputs=[chatbot])

    demo.launch(
        share=share,
        server_name="127.0.0.1",
        theme=gr.themes.Origin(),
        js=FORCE_LIGHT_JS,
    )


def main() -> None:
    game_state = build_game_state()
    print(game_state["start"])

    def main_loop(message: str, history: list[Message]) -> str:
        return run_action(message, history, game_state)

    start_game(main_loop, opening=game_state["start"], share=False)


if __name__ == "__main__":
    main()
