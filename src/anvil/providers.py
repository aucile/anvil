# AUTHOR: IAN SAVINO
# DATE: 2026

import shutil
import subprocess
import time
import urllib.request

import anthropic
from openai import OpenAI

from anvil import config

OLLAMA_HOST = "http://localhost:11434"


def _ollama_server_up() -> bool:
    """True if a local Ollama server is already answering."""
    try:
        with urllib.request.urlopen(f"{OLLAMA_HOST}/api/tags", timeout=1):
            return True
    except Exception:
        return False


def ensure_ollama_server():
    """Make sure a local Ollama server is running, starting one if needed."""
    if shutil.which("ollama") is None:
        raise SystemExit(
            "Error: the 'ollama' command was not found. Install Ollama and pull "
            "the model first — see the README (Local models with Ollama)."
        )
    if _ollama_server_up():
        return
    print("Starting local Ollama server...")
    subprocess.Popen(
        ["ollama", "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(20):
        if _ollama_server_up():
            return
        time.sleep(0.5)
    raise SystemExit("Error: started 'ollama serve' but it never became ready.")


def _ollama_complete(model_row: dict, messages: list[dict],
                     system: str | None) -> str:
    """Drive a local model through `ollama run MODEL "PROMPT"` and return stdout."""
    parts = [system] if system else []
    parts.extend(m["content"] for m in messages)
    prompt = "\n\n".join(parts)

    result = subprocess.run(
        ["ollama", "run", model_row["model_id"], prompt],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(
            f"Error: `ollama run {model_row['model_id']}` failed:\n"
            f"{result.stderr.strip()}"
        )
    return result.stdout.strip()


def get_client(model_row: dict):
    """Given a row from the models table, return a ready-to-use client.

    Anthropic models get an `anthropic.Anthropic` client. Ollama models are
    driven through the `ollama` CLI and need no client, so this ensures the
    local server is up and returns None. Everything else is treated as
    OpenAI-compatible (OpenAI, vLLM, Grok, etc.).
    """
    if model_row["provider"] == "ollama":
        ensure_ollama_server()
        return None

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
    """Run a chat completion against any client type and return the text."""
    if model_row["provider"] == "ollama":
        return _ollama_complete(model_row, messages, system)

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
