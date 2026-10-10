#!/usr/bin/env python
# coding: utf-8

# Interactive AI Role Playing Game, local Ollama edition.
# Model: qwen2.5:14b via Ollama's OpenAI-compatible endpoint.
# World: Lunevraie_L1.json (local file).

import os
import requests
import gradio as gr

from helper import load_world, save_world

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/v1/chat/completions")
MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")

WORLD_FILE = "Lunevraie_L1.json"
KINGDOM_NAME = "Éclairia"
TOWN_NAME = "Luciere"
CHARACTER_NAME = "Alaric Éclair"


def chat(messages, temperature=1.0, max_tokens=1800):
    r = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        },
        timeout=600,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


world = load_world(WORLD_FILE)
kingdom = world["kingdoms"][KINGDOM_NAME]
town = kingdom["towns"][TOWN_NAME]
character = town["npcs"][CHARACTER_NAME]

start_system_prompt = """You are an AI Game master. Your job is to create a
start to an adventure based on the world, kingdom, town and character
a player is playing as.
Instructions:
You must only use 2-4 sentences.
Write in second person. For example: "You are Jack".
Write in present tense. For example "You stand at...".
First describe the character and their backstory.
Then describes where they start and what they see around them."""

world_info = f"""
World: {world}
Kingdom: {kingdom}
Town: {town}
Your Character: {character}
"""

start = chat(
    [
        {"role": "system", "content": start_system_prompt},
        {"role": "user", "content": world_info + "\nYour Start:"},
    ]
)
print(start)
world["start"] = start
save_world(world, "Lunevraie_L1_run.json")


def run_action(message, history, game_state):
    if message == "start game":
        return game_state["start"]

    system_prompt = """You are an AI Game master. Your job is to write what \
happens next in a player's adventure game. \
Instructions: \
You must on only write 1-3 sentences in response. \
Always write in second person present tense. \
Ex. (You look north and see...)"""

    world_info = f"""
World: {game_state['world']}
Kingdom: {game_state['kingdom']}
Town: {game_state['town']}
Your Character:  {game_state['character']}"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": world_info},
    ]
    for action in history:
        messages.append({"role": "assistant", "content": action[0]})
        messages.append({"role": "user", "content": action[1]})
    messages.append({"role": "user", "content": message})

    return chat(messages)


game_state = {
    "world": world["description"],
    "kingdom": kingdom["description"],
    "town": town["description"],
    "character": character["description"],
    "start": start,
}


def main_loop(message, history):
    return run_action(message, history, game_state)


demo = None


def start_game(main_loop, share=False):
    global demo
    if demo is not None:
        demo.close()
    demo = gr.ChatInterface(
        main_loop,
        chatbot=gr.Chatbot(height=250, placeholder="Type 'start game' to begin"),
        textbox=gr.Textbox(placeholder="What do you do next?", container=False, scale=7),
        title="AI RPG, Lunevraie",
        theme="soft",
        examples=["start game", "Look around", "Continue the story"],
        cache_examples=False,
        retry_btn="Retry",
        undo_btn="Undo",
        clear_btn="Clear",
    )
    demo.launch(share=share, server_name="127.0.0.1")


if __name__ == "__main__":
    start_game(main_loop, share=False)
