"""Gradio chat UI for the role-playing game.

Two-column Blocks layout:

    [ chatbot                            ] | [ inventory ]
    [ textbox              ] [ Submit ]   | [           ]
    [🔄] [↩️] [🗑️]                          | [           ]
    Examples
    [ Look around ] [ Continue the story ]

Retry / Undo / Clear are small icon-only buttons under the input so
they stay out of the player's way until needed. Light mode is forced
via a page-load JS redirect to `?__theme=light` because Gradio 6 reads
the theme mode from the URL query, not from a CSS class.
"""

from __future__ import annotations

from typing import Callable

import gradio as gr

Message = dict[str, str]

MainLoop = Callable[[str, list[Message]], str]
InventoryGetter = Callable[[], dict[str, int]]

EXAMPLE_ACTIONS = ["Look around", "Continue the story"]

FORCE_LIGHT_JS = """() => {
    const url = new URL(window.location.href);
    if (url.searchParams.get('__theme') !== 'light') {
        url.searchParams.set('__theme', 'light');
        window.location.replace(url.toString());
    }
}"""


# Unicode icons for inventory items. Keys are lowercase. Compound item
# names (e.g. "silver moon pendant") also match by substring, so a
# magical sword and a plain sword both get the sword icon.
ITEM_ICONS: dict[str, str] = {
    "gold": "🪙",
    "coin": "🪙",
    "spellbook": "📖",
    "book": "📚",
    "scroll": "📜",
    "map": "🗺️",
    "silver moon pendant": "📿",
    "pendant": "📿",
    "amulet": "📿",
    "necklace": "📿",
    "ring": "💍",
    "gem": "💎",
    "crystal": "💎",
    "cloth robes": "🧥",
    "robes": "🧥",
    "cloak": "🧥",
    "cloth pants": "👖",
    "pants": "👖",
    "cloth shirt": "👕",
    "shirt": "👕",
    "sword": "⚔️",
    "dagger": "🗡️",
    "bow": "🏹",
    "staff": "🪄",
    "wand": "🪄",
    "shield": "🛡️",
    "potion": "🧪",
    "elixir": "🧪",
    "key": "🗝️",
    "lantern": "🏮",
    "torch": "🔥",
    "candle": "🕯️",
}
FALLBACK_ICON = "🎒"


def icon_for(name: str) -> str:
    """Pick an icon for an item name. Exact match wins, then substring."""
    key = name.lower().strip()
    if key in ITEM_ICONS:
        return ITEM_ICONS[key]
    for item_key, icon in ITEM_ICONS.items():
        if item_key in key:
            return icon
    return FALLBACK_ICON


def render_inventory(inventory: dict[str, int]) -> str:
    """Render the inventory as a plain markdown list with icons."""
    if not inventory:
        return "### Inventory\n\n_Empty_"
    lines = ["### Inventory", ""]
    for name, count in inventory.items():
        # Two trailing spaces + newline gives a soft line break in
        # Markdown without turning the row into a bullet.
        lines.append(f"{icon_for(name)} **{name}** × {count}  ")
    return "\n".join(lines)


def start_game(main_loop: MainLoop, opening: str,
               get_inventory: InventoryGetter, share: bool = False) -> None:
    """Launch the Gradio chat UI and block until it is closed.

    `opening` is pre-seeded as the first assistant message so the game
    is in-scene the moment the page loads, no "start game" prompt
    required. `Clear` resets back to the opening, not an empty chat.

    `get_inventory` returns the current inventory dict so the right
    column can refresh after every turn, retry, or clear.
    """
    initial_history: list[Message] = [
        {"role": "assistant", "content": opening},
    ]

    def submit(message: str,
               history: list[Message]) -> tuple[str, list[Message], str]:
        if not message:
            return "", history, render_inventory(get_inventory())
        assistant_msg = main_loop(message, history)
        new_history = history + [
            {"role": "user", "content": message},
            {"role": "assistant", "content": assistant_msg},
        ]
        return "", new_history, render_inventory(get_inventory())

    def retry(history: list[Message]) -> tuple[list[Message], str]:
        """Regenerate the assistant reply to the last user message."""
        if not history:
            return history, render_inventory(get_inventory())
        if history[-1]["role"] == "assistant":
            history = history[:-1]
        if not history or history[-1]["role"] != "user":
            return history, render_inventory(get_inventory())
        last_user = history[-1]["content"]
        prior = history[:-1]
        assistant_msg = main_loop(last_user, prior)
        new_history = prior + [
            {"role": "user", "content": last_user},
            {"role": "assistant", "content": assistant_msg},
        ]
        return new_history, render_inventory(get_inventory())

    def undo(history: list[Message]) -> tuple[list[Message], str]:
        """Drop the last user/assistant exchange."""
        new = list(history)
        while new and new[-1]["role"] == "assistant":
            new.pop()
        while new and new[-1]["role"] == "user":
            new.pop()
        return new, render_inventory(get_inventory())

    def clear() -> tuple[list[Message], str]:
        return list(initial_history), render_inventory(get_inventory())

    with gr.Blocks(title="AI RPG, Lunevraie") as demo:
        with gr.Row():
            with gr.Column(scale=3):
                chatbot = gr.Chatbot(
                    height=400,
                    label="Chatbot",
                    value=initial_history,
                )
                with gr.Row():
                    textbox = gr.Textbox(
                        placeholder="What do you do next?",
                        container=False,
                        scale=7,
                    )
                    submit_btn = gr.Button(
                        "Submit", variant="primary", scale=1
                    )
                with gr.Row():
                    retry_btn = gr.Button(
                        "🔄 Retry", size="sm", scale=0, min_width=90
                    )
                    undo_btn = gr.Button(
                        "↩️ Undo", size="sm", scale=0, min_width=90
                    )
                    clear_btn = gr.Button(
                        "🗑️ Clear", size="sm", scale=0, min_width=90
                    )
                gr.Markdown("### Examples")
                example_buttons: list[tuple[gr.Button, str]] = []
                with gr.Row():
                    for example in EXAMPLE_ACTIONS:
                        example_buttons.append((gr.Button(example), example))
            with gr.Column(scale=1):
                inventory_md = gr.Markdown(
                    value=render_inventory(get_inventory())
                )

        for btn, example in example_buttons:
            btn.click(
                lambda h, m=example: submit(m, h),
                inputs=[chatbot],
                outputs=[textbox, chatbot, inventory_md],
            )
        submit_btn.click(
            submit,
            inputs=[textbox, chatbot],
            outputs=[textbox, chatbot, inventory_md],
        )
        textbox.submit(
            submit,
            inputs=[textbox, chatbot],
            outputs=[textbox, chatbot, inventory_md],
        )
        retry_btn.click(retry, inputs=[chatbot], outputs=[chatbot, inventory_md])
        undo_btn.click(undo, inputs=[chatbot], outputs=[chatbot, inventory_md])
        clear_btn.click(clear, outputs=[chatbot, inventory_md])

    demo.launch(
        share=share,
        server_name="127.0.0.1",
        theme=gr.themes.Origin(),
        js=FORCE_LIGHT_JS,
        allowed_paths=["."],
    )
