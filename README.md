# Anvil

An orchestrator that actually works.

Anvil is a two-tier CLI orchestrator: a capable **planner** model breaks a
request into small subtasks, a cheaper **worker** model handles each one, and
the planner synthesizes the results into a final program written to `output/`.
Every run is recorded in a local SQLite store.

## Install

```bash
git clone git@github.com:aucile/anvil.git

uv tool install .            # from the repo root — installs the global `anvil` command
```

## Setup

```bash
anvil init                   # interactive: pick a planner + worker, store any API keys
```

Config lives at `~/.config/anvil/config.toml` (created with `600` permissions —
it holds API keys). API keys are resolved environment-first, then from that file.

## Usage

```bash
anvil -o "write a script that renames files by date"   # orchestrate a request
anvil -o                                               # prompt for the request
anvil -s                                               # show recent request history
anvil -v                                               # view the current model config
anvil -c qwen                                          # add or edit the 'qwen' model
anvil --reset                                          # reset the saved model config
anvil -f                                               # erase the storage database
```

### Viewing and changing the config

```bash
anvil -v        # view: planner/worker selection, registered models, which keys are set
anvil init      # edit: re-pick the planner and worker (merges existing keys)
anvil -c <name> # edit: register or change one model's fields (model_id, provider, tier, …)
anvil --reset   # reset: delete the saved selection + keys (~/.config/anvil/config.toml)
```

`anvil -v` is read-only and shows exactly which model each role resolves to and
whether each required API key is present (env or saved). The same model can be
selected for both planner and worker — e.g. an all-local Ollama setup.

## Adding models

Anvil ships with presets (OpenAI, Anthropic, Grok, Deepseek, Qwen) surfaced by
`anvil init`. The same menu also has an **Other** option that lets you enter a
custom model's specs inline (model_id, provider, base_url, key_name, …) — the
provider must be one of `anthropic`, `openai-compatible`, or `ollama`, and
anything else is rejected. To register any other model outside of `init`, or
edit an existing one:

```bash
anvil -c <name>
```

You'll be prompted for:

| Field       | Notes                                                     |
|-------------|-----------------------------------------------------------|
| `model_id`  | the provider's model identifier (e.g. `gpt-4o-mini`)      |
| `provider`  | `anthropic`, `openai-compatible`, or `ollama`             |
| `specialty` | free-text description                                     |
| `tier`      | `planner` or `worker`                                     |
| `base_url`  | API base URL (blank for Anthropic and Ollama)             |
| `key_name`  | env var / config key holding the API key (blank for Ollama) |

Once registered, a model is eligible to be selected as the planner or worker.

## Local models with Ollama

Anvil can run a local model as the worker (recommended: **qwen**) through
[Ollama](https://ollama.com). Ollama-provider models are driven with the
`ollama` CLI directly — `ollama run <model_id> "<prompt>"` — rather than an HTTP
client, and Anvil starts the local Ollama server automatically if it isn't
already running.

### Install Ollama and pull qwen

```bash
# macOS
brew install ollama
# or download from https://ollama.com/download

ollama pull qwen2.5-coder:3b     # pull the default worker model
```

That's all the setup Ollama needs — Anvil launches the server (`ollama serve`)
on demand. To verify manually:

```bash
ollama run qwen2.5-coder:3b "print hello world in python"
```

### Point Anvil at it

`qwen` is a built-in preset and a seeded model (`qwen2.5-coder:3b`, provider
`ollama`), so selecting it in `anvil init` as the worker is enough. To use a
different local model, register it with `anvil -c <name>` using provider
`ollama` and the tag from `ollama list` as `model_id`.
