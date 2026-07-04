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

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.