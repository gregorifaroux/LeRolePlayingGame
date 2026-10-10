# Le Role Playing Game

A tiny text adventure. A local LLM plays game master and narrates each
beat as you type what you do next. Served over a Gradio chat UI.

Based on the DeepLearning.AI "Interactive AI Applications" lesson,
rewired to run on local Ollama instead of Together AI, with Lunevraie
as the world.

## Prerequisites

- macOS or Linux
- Python 3.13 (a venv is already in `.venv`)
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
.venv/bin/pip install audioop-lts "huggingface_hub<1.0" "jinja2<3.1.6" \
                     "starlette<0.40" "fastapi<0.115"
```

The second line is needed because `requirements.txt` is pinned to
Python 3.10 era deps and we run on 3.13. The pins fix:

- `audioop` is gone from Python 3.13 (pydub needs it, `audioop-lts` restores it)
- `huggingface_hub` 1.x removed `HfFolder` (gradio 4.44.1 imports it)
- `jinja2` 3.1.6 changed the cache-key API gradio uses
- `starlette` 1.x changed `TemplateResponse(name, context)` signature,
  which gradio 4.44.1 calls the old way

## Run

```
.venv/bin/python game.py
```

The script:

1. Loads the world from `WORLD_FILE`
2. Asks Ollama to generate the opening scene (slow, 20-60s on 14b)
3. Writes the world + opening to `Lunevraie_L1_run.json`
4. Starts Gradio at http://127.0.0.1:7860

In the UI, type `start game` first to see the opening, then describe
what your character does.

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
- `helper.py` — world load/save and (unused here) Together API key loader
- `Lunevraie_L1.json` — the world
- `1. create world/` — notebook that generated the world
- `requirements.txt` — pinned to the lesson's original versions
- `.venv/` — local virtualenv (gitignored)
- `Lunevraie_L1_run.json` — world + generated opening, written each run (gitignored)
