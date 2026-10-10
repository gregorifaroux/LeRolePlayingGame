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
- Models pulled:
  - `ollama pull qwen2.5:14b` (game master)
  - `ollama pull llama-guard3:1b` (moderation)

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

## Safety and moderation

Every player input and every game-master reply is classified by
[Llama Guard 3](https://ai.meta.com/research/publications/llama-guard-3/)
(`llama-guard3:1b`) running locally on the same Ollama instance,
using the model's **native S1-S14 hazard taxonomy**. A short Python
blocklist in `safety.py` decides which hazards refuse the turn:

| Code | Category | Behavior |
|---|---|---|
| S3 | Sex Crimes | **Blocked** |
| S4 | Child Sexual Exploitation | **Blocked** |
| S10 | Hate | **Blocked** |
| S11 | Self-Harm | **Blocked** |
| S12 | Sexual Content | **Blocked** |
| S1 | Violent Crimes | Allowed (fantasy combat) |
| all others | — | Allowed |

Any blocked hazard hard-refuses the turn. The game master is **not**
called. The chat shows an in-character refusal with the violated
hazard appended:

> The game master pauses. "That is not a path this story will take." (violated: S11: Self-Harm)

**Why the native taxonomy**: An earlier version used the course's
custom O1-O5 content policy over `/api/generate` with `raw=True`. The
1b model has strong priors on its S1-S14 training set and misassigns
self-harm content to `S3` under a custom policy. The 8b handles
custom policies but costs 5 GB and is slower. Running the native
taxonomy with a Python blocklist keeps the 1b accurate and the
moderation decision auditable.

**Known gaps vs. the course policy**: the native taxonomy does not
cover profanity (O4) or recreational drug use (O5). If you need
those, set `GUARD_MODEL=llama-guard3:8b` after
`ollama pull llama-guard3:8b` and revive the custom-policy branch.

Per turn cost: `guard(input) + qwen(reply) + guard(output)`. The two
`llama-guard3:1b` calls add roughly 0.5-1s each on an M-series Mac.

To tune the policy, edit `BLOCKED_CATEGORIES` in `safety.py`.

## Inventory

Each session carries a mutable item inventory. The player starts with:

| Item | Count |
|---|---|
| cloth robes | 1 |
| silver moon pendant | 1 |
| spellbook | 1 |
| gold | 5 |

(Edit `STARTING_INVENTORY` in `inventory.py` to change this.)

Three touch points, all in `game.py`:

1. **Initial state** — `build_game_state()` copies `STARTING_INVENTORY` into
   `game_state["inventory"]`.
2. **GM context** — `run_action()` prepends the current inventory to the
   `world_info` block of every GM call, and the system prompt tells the GM
   *"Don't let the player use items they don't have in their inventory."*
3. **Post-reply delta** — after the GM reply passes moderation,
   `detect_inventory_changes()` makes a second LLM call in JSON mode that
   returns a list like
   `[{"name": "sword", "change_amount": 1}, {"name": "gold", "change_amount": -5}]`,
   and `update_inventory()` applies them in place and returns a summary that
   gets appended to the chatbot message:

   > You buy a sword from the merchant for 5 gold.
   > Inventory: sword +1
   > Inventory: gold -5

Entries that would drop to zero are removed. Negative changes to items the
player doesn't own are ignored.

The inventory lives in `game_state` for the lifetime of the Python process.
`Clear` in the UI resets history but not inventory; restart `game.py` to
reset both.

## Configuration

All config is env vars with defaults:

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_URL` | `http://localhost:11434/v1/chat/completions` | Ollama OpenAI-compatible endpoint (game master and moderation) |
| `OLLAMA_MODEL` | `qwen2.5:14b` | Game-master model tag Ollama has pulled |
| `GUARD_MODEL` | `llama-guard3:1b` | Llama Guard model tag for moderation |
| `INVENTORY_MODEL` | `qwen2.5:14b` | Model tag for the JSON inventory-delta extraction |
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

- `game.py` — entrypoint: config, chat client, prompts, game state, action loop, `main()`
- `safety.py` — Llama Guard 3 moderation and refusal policy
- `inventory.py` — starting inventory, item-change detection, inventory updates
- `ui.py` — Gradio Blocks layout and launch
- `helper.py` — world load/save (Together API key loader is unused here)
- `Lunevraie_L1.json` — the world
- `1. create world/` — notebook that generated the world (lesson L1)
- `2. inventory/` — notebook the inventory mechanics are ported from (lesson L4)
- `requirements.txt` — pinned to the lesson's original versions (see Install for the 3.13 fix)
- `gameintro.png` — screenshot of the opening screen
- `.venv/` — local virtualenv (gitignored)
- `Lunevraie_L1_run.json` — world + generated opening, written each run (gitignored)
