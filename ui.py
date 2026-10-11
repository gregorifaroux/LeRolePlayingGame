"""Gradio chat UI for the role-playing game.

Three-column Blocks layout:

    [ Lunevraie.png ] |                     🔄 ↩️ 🗑️ | [ character/inventory ]
    [               ] | [ chatbot                   ] | [                     ]
    [               ] | [ textbox      ] [ Submit ] | [                     ]
    [               ] | Look around · Continue      | [                     ]

Chatbot header (label and share/copy/delete icons) is hidden; Retry /
Undo / Clear sit above the chatbot where the icons used to be.
Examples are rendered as compact text-only link buttons under the
input. Theme follows the browser / OS preference.
"""

from __future__ import annotations

from typing import Callable

import gradio as gr

Message = dict[str, str]

MainLoop = Callable[[str, list[Message]], str]
InventoryGetter = Callable[[], dict[str, int]]
StateGetter = Callable[[], dict]

CLASS_ICONS: dict[str, str] = {
    "Mage": "🪄",
    "Warrior": "⚔️",
    "Healer": "🌿",
}

EXAMPLE_ACTIONS = ["Look around", "Continue the story"]

SIDEBAR_CSS = """
.sidebar-md hr {
    margin: 0.25rem 0 !important;
    border: none;
    border-top: 1px solid var(--border-color-primary, #e5e7eb);
}
.sidebar-md h2, .sidebar-md h3 {
    margin-top: 0.25rem !important;
    margin-bottom: 0.25rem !important;
}
.sidebar-md p {
    margin: 0.25rem 0 !important;
}
.example-link {
    flex: 0 0 auto !important;
    width: auto !important;
    min-width: 0 !important;
}
.chat-bare .label-wrap,
.chat-bare label,
.chat-bare > .top-panel,
.chat-bare .icon-button-wrapper,
.chat-bare button[aria-label*="hare"],
.chat-bare button[aria-label*="opy"],
.chat-bare button[aria-label*="elete"],
.chat-bare button[aria-label*="lear"] {
    display: none !important;
}
.chat-toolbar {
    display: flex !important;
    justify-content: flex-end !important;
    gap: 0.25rem !important;
    margin-bottom: -0.5rem !important;
}
.chat-toolbar button {
    padding: 0.25rem 0.5rem !important;
}
.example-link button {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    color: var(--link-text-color, #4f46e5) !important;
    text-decoration: underline;
    padding: 0 0.75rem !important;
    min-width: 0 !important;
    width: auto !important;
    white-space: nowrap !important;
    font-weight: normal !important;
}
.example-link button:hover {
    color: var(--link-text-color-hover, #818cf8) !important;
}
"""


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
        return f"### Inventory{_HR}_Empty_"
    items = "\n".join(
        f"{icon_for(name)} **{name}** × {count}  "
        for name, count in inventory.items()
    )
    return f"### Inventory{_HR}{items}"


_HR = '\n\n<hr style="margin:4px 0; border:0; border-top:1px solid #d0d0d0;">\n\n'


def render_character(state: dict) -> str:
    """Render the name/class/level/XP header for the right column."""
    name = state.get("name", "")
    cls = state.get("class", "Mage")
    level = state.get("level", 1)
    xp = state.get("xp", 0)
    icon = CLASS_ICONS.get(cls, "✨")
    header = f"## {name}{_HR}" if name else ""
    return (
        header
        + f"### {icon} {cls}"
        + _HR
        + f"**Level** {level}  \n"
        + f"**XP** {xp}"
        + _HR
    )


def render_sidebar(state: dict) -> str:
    """Render the full right-column panel (character header + inventory)."""
    return render_character(state) + "\n\n" + render_inventory(
        state.get("inventory", {})
    )


def start_game(main_loop: MainLoop, opening: str,
               get_state: StateGetter, share: bool = False) -> None:
    """Launch the Gradio chat UI and block until it is closed.

    `opening` is pre-seeded as the first assistant message so the game
    is in-scene the moment the page loads, no "start game" prompt
    required. `Clear` resets back to the opening, not an empty chat.

    `get_state` returns the live game_state dict so the right column
    (class / level / XP header, then inventory) can refresh after
    every turn, retry, or clear.
    """
    initial_history: list[Message] = [
        {"role": "assistant", "content": opening},
    ]

    def submit(message: str,
               history: list[Message]) -> tuple[str, list[Message], str]:
        if not message:
            return "", history, render_sidebar(get_state())
        assistant_msg = main_loop(message, history)
        new_history = history + [
            {"role": "user", "content": message},
            {"role": "assistant", "content": assistant_msg},
        ]
        return "", new_history, render_sidebar(get_state())

    def retry(history: list[Message]) -> tuple[list[Message], str]:
        """Regenerate the assistant reply to the last user message."""
        if not history:
            return history, render_sidebar(get_state())
        if history[-1]["role"] == "assistant":
            history = history[:-1]
        if not history or history[-1]["role"] != "user":
            return history, render_sidebar(get_state())
        last_user = history[-1]["content"]
        prior = history[:-1]
        assistant_msg = main_loop(last_user, prior)
        new_history = prior + [
            {"role": "user", "content": last_user},
            {"role": "assistant", "content": assistant_msg},
        ]
        return new_history, render_sidebar(get_state())

    def undo(history: list[Message]) -> tuple[list[Message], str]:
        """Drop the last user/assistant exchange."""
        new = list(history)
        while new and new[-1]["role"] == "assistant":
            new.pop()
        while new and new[-1]["role"] == "user":
            new.pop()
        return new, render_sidebar(get_state())

    def clear() -> tuple[list[Message], str]:
        return list(initial_history), render_sidebar(get_state())

    with gr.Blocks(title="AI RPG, Lunevraie") as demo:
        with gr.Row():
            with gr.Column(scale=2):
                gr.Image(
                    value="Lunevraie.png",
                    show_label=False,
                    container=False,
                    interactive=False,
                    buttons=[],
                )
            with gr.Column(scale=3):
                with gr.Row(elem_classes=["chat-toolbar"]):
                    retry_btn = gr.Button(
                        "🔄 Retry", size="sm", scale=0, min_width=90
                    )
                    undo_btn = gr.Button(
                        "↩️ Undo", size="sm", scale=0, min_width=90
                    )
                    clear_btn = gr.Button(
                        "🗑️ Clear", size="sm", scale=0, min_width=90
                    )
                chatbot = gr.Chatbot(
                    height=500,
                    show_label=False,
                    value=initial_history,
                    elem_classes=["chat-bare"],
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
                example_buttons: list[tuple[gr.Button, str]] = []
                with gr.Row(equal_height=True):
                    for example in EXAMPLE_ACTIONS:
                        example_buttons.append((
                            gr.Button(
                                example,
                                size="sm",
                                elem_classes=["example-link"],
                            ),
                            example,
                        ))
            with gr.Column(scale=2):
                inventory_md = gr.Markdown(
                    value=render_sidebar(get_state()),
                    elem_classes=["sidebar-md"],
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
        css=SIDEBAR_CSS,
        allowed_paths=["."],
    )
