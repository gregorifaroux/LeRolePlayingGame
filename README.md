# Le Role Playing Game

A tiny text adventure. A local LLM plays game master and narrates each
beat as you type what you do next. Served over a Gradio chat UI.

Based on the DeepLearning.AI "Interactive AI Applications" lesson,
rewired to run on local Ollama instead of Together AI, with Lunevraie
as the world.

![Game intro](gameintro.png)

## Prerequisites

- macOS or Linux
- Python 3.13
- [Ollama](https://ollama.com) running on `localhost:11434`
- Model pulled: `ollama pull qwen2.5:14b`

Verify Ollama is reachable:

```
curl -s http://localhost:11434/api/tags | head -c 200
```

## Install

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -U gradio audioop-lts
```

The second line is the Python-3.13 fix:

- `-U gradio` upgrades Gradio to 6.x, which pulls fastapi/starlette/
  jinja2/huggingface_hub versions that work on 3.13. The pinned
  Gradio 4.44.1 from `requirements.txt` chains to deps that break on
  3.13 and does not expose the `Origin` theme.
- `audioop-lts` restores the `audioop` module that Python 3.13 removed
  (pydub, pulled in transitively, imports it).

## Run

```
.venv/bin/python game.py
```

The script:

1. Loads the world from `WORLD_FILE`
2. Asks Ollama to generate the opening scene (slow, 20-60s on 14b)
3. Writes the world + opening to `Lunevraie_L1_run.json`
4. Starts Gradio at http://127.0.0.1:7860

Open the URL. The opening scene is already in the chat when the page
loads, no "start game" prompt required. Type what your character does
and hit Submit (or Enter).

## UI notes

- Theme: `gr.themes.Origin()`
- Light mode is forced by redirecting to `?__theme=light` at page load
  (Gradio 6 reads the mode from the URL query, not from a CSS class)
- Layout matches the lesson's Gradio 4 ChatInterface:

```
[ chatbot                            ]
[ Retry ] [ Undo ] [ Clear ]
[ textbox              ] [ Submit ]
Examples
[ Look around ] [ Continue the story ]
```

- `Clear` resets the chat back to the opening scene, not an empty chat

## Configuration

All config is env vars with defaults:

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_URL` | `http://localhost:11434/v1/chat/completions` | Ollama OpenAI-compatible endpoint |
| `OLLAMA_MODEL` | `qwen2.5:14b` | Model tag Ollama has pulled |
| `WORLD_FILE` | `Lunevraie_L1.json` | World data file |
| `KINGDOM_NAME` | `Éclairia` | Key under `world["kingdoms"]` |
| `TOWN_NAME` | `Luciere` | Key under `kingdom["towns"]` |
| `CHARACTER_NAME` | `Alaric Éclair` | Key under `town["npcs"]` |

Swap character:

```
CHARACTER_NAME="Sylvie Vespera" TOWN_NAME="Cendres Étoilées" \
  .venv/bin/python game.py
```

## World data

`Lunevraie_L1.json` is a nested dict:

```
{
  "name": "Lunevraie",
  "description": "...",
  "kingdoms": {
    "Éclairia":   { "name": "...", "description": "...",
                    "towns": { "Luciere": { "name": "...", "npcs": {...} } } },
    "Verseau":    { ... },
    "Crépuscule": { ... }
  }
}
```

The `1. create world/` directory holds the notebook that generates
new world files.

## Files

- `game.py` — chat UI + action loop
- `helper.py` — world load/save (Together API key loader is unused here)
- `Lunevraie_L1.json` — the world
- `1. create world/` — notebook that generated the world
- `requirements.txt` — pinned to the lesson's original versions (see Install for the 3.13 fix)
- `gameintro.png` — screenshot of the opening screen
- `.venv/` — local virtualenv (gitignored)
- `Lunevraie_L1_run.json` — world + generated opening, written each run (gitignored)
