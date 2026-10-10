"""Llama Guard 3 moderation with a custom content policy.

The default `llama-guard3:1b` chat template on Ollama embeds Meta's
S1-S14 taxonomy, so sending categories through `/v1/chat/completions`
does nothing. To actually drive classification by a custom policy we
build the Llama Guard prompt by hand and hit `/api/generate` with
`raw=True`, bypassing the baked-in template.

Policy categories O1-O5 are from the DeepLearning.AI course lesson:
tame fantasy violence is allowed, sexual content is blocked,
self-harm / profanity / drug content is blocked.

Config via env vars:
    OLLAMA_BASE  Ollama HTTP base URL.
                 Default: http://localhost:11434
    GUARD_MODEL  Llama Guard model tag.
                 Default: llama-guard3:1b
"""

from __future__ import annotations

import os

import requests

OLLAMA_BASE = os.getenv("OLLAMA_BASE", "http://localhost:11434")
GENERATE_URL = f"{OLLAMA_BASE}/api/generate"
GUARD_MODEL = os.getenv("GUARD_MODEL", "llama-guard3:1b")

REFUSAL_TEXT = (
    "The game master pauses. \"That is not a path this story will take.\""
)

CONTENT_POLICY = """O1: Violence and Hate.
Should not
- Express hateful, derogatory, or demeaning sentiments against people based on sensitive personal characteristics.
- Use slurs based on personal characteristics
- Write gruesome / graphic violence.
Can
- Write tame fantasy violence
O2: Sexual Content.
Should not
- Write any somewhat sexual content that mentions sexual functions or sexual body parts.
- Write any content that would be inappropriate for kids.
Can
- Write romantic content (including kissing, flirting etc...)
O3: Self-Harm.
Should not
- Encourage people to harm themselves.
- Romanticize or condone self-harm or suicide.
- Write story depicting suicide.
O4: Profanity.
Should not
- Write with any profane language that wouldn't be appropriate for kids.
Can
- Write with kid appropriate language
O5: Regulated or Controlled Substances.
Should not
- Write stories that depicts, glorifies or encourages drug use."""

PROMPT_TEMPLATE = """<|begin_of_text|><|start_header_id|>user<|end_header_id|>

Task: Check if there is unsafe content in '{role}' messages in conversations according to our safety policy with the below categories.

<BEGIN UNSAFE CONTENT CATEGORIES>
{policy}
<END UNSAFE CONTENT CATEGORIES>

<BEGIN CONVERSATION>

{conversation}

<END CONVERSATION>

Provide your safety assessment for ONLY THE LAST {role} message in the above conversation:
- First line must read 'safe' or 'unsafe'.
- If unsafe, a second line must include a comma-separated list of violated categories.<|eot_id|><|start_header_id|>assistant<|end_header_id|>

"""

Message = dict[str, str]


def _format_conversation(messages: list[Message]) -> str:
    lines = []
    for m in messages:
        tag = "User" if m["role"] == "user" else "Agent"
        lines.append(f"{tag}: {m['content']}")
    return "\n\n".join(lines)


def moderate(messages: list[Message],
             role_to_check: str = "User") -> tuple[bool, str]:
    """Classify the last `role_to_check` turn against CONTENT_POLICY.

    `role_to_check` is "User" when checking a player input and "Agent"
    when checking the game master's reply, matching Llama Guard 3's
    prompt vocabulary.

    Returns (ok, violated_categories). Any violation = block, since the
    whole policy is intended to apply.
    """
    prompt = PROMPT_TEMPLATE.format(
        role=role_to_check,
        policy=CONTENT_POLICY,
        conversation=_format_conversation(messages),
    )
    r = requests.post(
        GENERATE_URL,
        json={
            "model": GUARD_MODEL,
            "prompt": prompt,
            "raw": True,
            "stream": False,
            "options": {"temperature": 0},
        },
        timeout=120,
    )
    r.raise_for_status()
    reply = r.json()["response"].strip()
    lines = reply.splitlines()
    if lines and lines[0].strip().lower() == "unsafe":
        categories = lines[1].strip() if len(lines) > 1 else ""
        return False, categories
    return True, ""
