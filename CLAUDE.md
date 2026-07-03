# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Anvil is a two-tier CLI orchestrator: a capable **planner** model decomposes a request into subtasks, a cheaper **worker** model executes each one, and the planner synthesizes the results into a Python program written to `output/`. Runs are persisted to a user-level SQLite database.

Note: this repo lives inside `~/forge/`, whose own `CLAUDE.md` describes the *predecessor* project (`orchestrator.py` / `grimoire` / wizard-themed names). None of that applies here — anvil is a separate git repo with its own plain naming (planner/worker, requests/subtasks, `storage.db`).

## Setup & commands

The venv is `.venv/` at the repo root, with anvil installed editable. There is no test suite, linter, or build step.

```bash
source .venv/bin/activate
pip install -e .                 # (already done in .venv; needed for a fresh venv)
uv tool install .                # alternative: install the global `anvil` command

anvil init                       # interactive setup: pick planner + worker, store API keys
anvil -o "<request>"             # orchestrate a request end-to-end
anvil -s                         # print recent request history
anvil -v                         # view current model config (read-only)
anvil -c <name>                  # register or edit one model
anvil --reset                    # delete ~/.config/anvil/config.toml
anvil -f                         # erase the storage database
```

Runtime requirements: an API key for the planner (e.g. `ANTHROPIC_API_KEY`, resolved environment-first then from config.toml), and Ollama installed for a local worker (`ollama pull qwen2.5-coder:3b` is the seeded default; anvil starts `ollama serve` itself if needed).

## Architecture

All logic is in `src/anvil/` (five modules). `build/` and `src/anvil.egg-info/` are stale packaging artifacts — never edit them.

**State is split across two stores**, and this shapes everything:
- **Model definitions** (name, model_id, provider, tier, base_url, key_name) live in the SQLite `models` table (`storage.py`).
- **Role selection** (`planner_model` / `worker_model` names) and **saved API keys** live in `~/.config/anvil/config.toml` (`config.py`, written with 600 perms via a hand-rolled TOML renderer — string/list values only).

**`anvil.py`** — argparse CLI and entry point (`anvil = anvil.anvil:main`). Holds the `PRESETS` list shown by `anvil init`. `anvil init` is a special-cased *positional argument*, not a flag. `orchestrator` is imported lazily only when `-o` runs, so config/history commands work without provider SDks or keys.

**`orchestrator.py`** — `orchestrate(request_text)` runs three passes: (1) planner returns JSON subtasks (`extract_json` strips markdown fences), (2) worker runs each subtask sequentially, (3) planner synthesizes a fenced Python program. The request is saved via `storage.save_request()` first so the DB id becomes the output filename id, then code blocks are regex-extracted to `output/request_<id>_<slug>.py`. `OUTPUT_DIR` is **cwd-relative** — the installed command writes `output/` wherever it is run.

**`providers.py`** — dispatch on the model row's `provider` field:
- `anthropic` → `anthropic.Anthropic` client
- `ollama` → no HTTP client at all; drives the `ollama run <model_id> "<prompt>"` CLI via subprocess and auto-starts `ollama serve` if the server isn't up
- anything else → OpenAI-compatible `OpenAI(base_url=...)` client

`get_client()` returns the client (or `None` for ollama); `complete()` normalizes system prompt + messages across all three shapes.

**`storage.py`** — SQLite at `~/.local/share/anvil/storage.db` (override with `ANVIL_STORAGE_DB`; deliberately *not* cwd-relative so the installed command uses one DB). `init_db()` creates `models`/`requests`/`subtasks`, runs in-place column migrations, and seeds two models: `claude` (planner) and `qwen` (worker). `get_connection()` is a context manager that enables foreign keys and auto-commits.

**Model resolution** (`orchestrator._pick_model`): the name saved in config.toml is looked up directly in the `models` table, ignoring the row's `tier` column — so the same model can serve both roles (all-local setup). Only when no selection is saved does it fall back to the first row with a matching `tier`.

**Duplication to maintain:** the `PRESETS` list in `anvil.py` and the seed rows in `storage.init_db()` overlap (e.g. `qwen`). Adding or changing a default model usually means updating both.
