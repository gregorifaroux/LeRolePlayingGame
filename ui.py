"""Gradio chat UI for the role-playing game.

Builds the lesson's layout as a manual Blocks tree:

    [ chatbot                                      ]
    [ Retry ] [ Undo ] [ Clear ]
    [ textbox                        ] [ Submit ]
    Examples
    [ Look around ] [ Continue the story ]

Light mode is forced via a page-load JS redirect to `?__theme=light`
because Gradio 6 reads the theme mode from the URL query, not from a
CSS class.
"""

from __future__ import annotations

from typing import Callable

import gradio as gr

Message = dict[str, str]

MainLoop = Callable[[str, list[Message]], str]

EXAMPLE_ACTIONS = ["Look around", "Continue the story"]

FORCE_LIGHT_JS = """() => {
    const url = new URL(window.location.href);
    if (url.searchParams.get('__theme') !== 'light') {
        url.searchParams.set('__theme', 'light');
        window.location.replace(url.toString());
    }
}"""


def start_game(main_loop: MainLoop, opening: str,
               share: bool = False) -> None:
    """Launch the Gradio chat UI and block until it is closed.

    `opening` is pre-seeded as the first assistant message so the game
    is in-scene the moment the page loads, no "start game" prompt
    required. `Clear` resets back to the opening, not an empty chat.
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
