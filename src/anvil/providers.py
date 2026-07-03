# AUTHOR: IAN SAVINO
# DATE: 2026

import anthropic
from openai import OpenAI

from anvil import config


def get_client(model_row: dict):
    """Given a row from the models table, return a ready-to-use client.

    Anthropic models get an `anthropic.Anthropic` client; everything else
    is treated as OpenAI-compatible (Ollama, OpenAI, vLLM, etc.).
    """
    key_name = model_row.get("key_name")
    api_key = config.get_api_key(key_name)
    base_url = model_row.get("base_url")

    if key_name and not api_key:
        raise SystemExit(
            f"Error: model '{model_row['name']}' needs {key_name}, but it isn't "
            f"set in the environment or saved config — run `anvil init`."
        )

    if model_row["provider"] == "anthropic":
        return anthropic.Anthropic(api_key=api_key, base_url=base_url)

    return OpenAI(base_url=base_url, api_key=api_key or "not-needed")


def complete(model_row: dict, client, messages: list[dict],
             system: str | None = None, max_tokens: int = 5000) -> str:
    """Run a chat completion against either client type and return the text."""
    if model_row["provider"] == "anthropic":
        response = client.messages.create(
            model=model_row["model_id"],
            max_tokens=max_tokens,
            system=system or anthropic.NOT_GIVEN,
            messages=messages,
        )
        return response.content[0].text

    if system:
        messages = [{"role": "system", "content": system}, *messages]
    response = client.chat.completions.create(
        model=model_row["model_id"],
        messages=messages,
    )
    return response.choices[0].message.content
