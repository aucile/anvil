# AUTHOR: IAN SAVINO
# DATE: 2026

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from dotenv import load_dotenv

from anvil import config, providers, storage

load_dotenv()

OUTPUT_DIR = Path("output")


def _pick_model(tier: str) -> dict:
    """Pick a model for a role, honoring the saved planner/worker selection.

    The configured model is fetched by name directly, so the same model can
    serve as both planner and worker (e.g. a fully local Ollama setup) and the
    stored `tier` column no longer has to match the requested role.
    """
    preferred = (
        config.get_planner_model() if tier == "planner"
        else config.get_worker_model()
    )
    if preferred:
        model = storage.get_model(preferred)
        if model:
            return model

    models = storage.get_models(tier)
    if not models:
        raise SystemExit(f"Error: no '{tier}' model registered in the models table.")
    return models[0]


def extract_json(text: str) -> dict:
    """Strip markdown fences and parse JSON from a model response."""
    # Remove ```json ... ``` or ``` ... ``` wrappers if present
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text.strip())
    return json.loads(text)


def run_subtask(subtask: str, worker: dict, worker_client) -> str:
    """Dispatch a subtask to a worker model."""
    return providers.complete(
        worker,
        worker_client,
        messages=[{"role": "user", "content": subtask}],
    )


def orchestrate(request_text: str) -> str:
    planner = _pick_model("planner")
    worker = _pick_model("worker")
    planner_client = providers.get_client(planner)
    worker_client = providers.get_client(worker)

    print(f"\nPlanner ({planner['name']}) receives the request...")
    print(f'  "{request_text}"')

    # Step 1: Planner decomposes the request into subtasks
    plan_text = providers.complete(
        planner,
        planner_client,
        max_tokens=500,
        system=(
            "You are a planner model that delegates work to smaller worker models. "
            "Break the user's request into 2-4 concrete, independent subtasks "
            "that a worker can handle on their own. "
            'Respond ONLY with valid JSON: {"subtasks": ["task1", "task2"]}'
        ),
        messages=[{"role": "user", "content": request_text}]
    )

    plan = extract_json(plan_text)
    subtasks = plan["subtasks"]
    print(f"\nPlanner produced {len(subtasks)} subtask(s):")
    for i, subtask in enumerate(subtasks, 1):
        print(f"  [{i}] {subtask}")

    # Step 2: Worker models handle the subtasks in parallel
    results = {}
    print(f"\nWorker ({worker['name']}) runs {len(subtasks)} subtask(s) in parallel...")
    with ThreadPoolExecutor(max_workers=len(subtasks)) as pool:
        futures = {
            pool.submit(run_subtask, subtask, worker, worker_client): i
            for i, subtask in enumerate(subtasks, 1)
        }
        for future in as_completed(futures):
            i = futures[future]
            results[f"subtask_{i}"] = future.result()
            print(f"    ...subtask {i} complete.")

    # Step 3: Planner synthesizes the final answer
    print(f"\nPlanner synthesizes the results into a final answer...")
    final_answer = providers.complete(
        planner,
        planner_client,
        max_tokens=5000,
        system=(
            "You are the planner model. Your workers have returned with their results. "
            "Weave their findings together into a single, complete Python program. "
            "You MUST wrap all code in a fenced code block that opens with ```python and closes with ```. "
            "Never leave a code block unclosed. Do not split code across multiple blocks."
        ),
        messages=[{
            "role": "user",
            "content": (
                f"Original request: {request_text}\n\n"
                f"Worker results:\n{json.dumps(results, indent=2)}\n\n"
                "Synthesize these into a final answer."
            )
        }]
    )

    request_id = storage.save_request(
        request_text=request_text,
        subtasks=subtasks,
        results=results,
        final_answer=final_answer,
        model=worker["name"],
    )
    print(f"\nRequest #{request_id} recorded in storage ({storage.DB_PATH})")

    # Extract only the code block(s) from the answer
    code_blocks = re.findall(r"```python?\s*\n(.*?)```", final_answer, re.DOTALL)
    code = "\n\n".join(block.strip() for block in code_blocks)
    if not code:
        # Fallback: store the raw answer as a comment if no code block was found
        code = "\n".join(f"# {line}" for line in final_answer.splitlines())

    # Write the code to the output directory
    OUTPUT_DIR.mkdir(exist_ok=True)
    slug = re.sub(r"[^\w]+", "_", request_text[:50]).strip("_").lower()
    output_path = OUTPUT_DIR / f"request_{request_id}_{slug}.py"
    output_path.write_text(
        f"# Request #{request_id}: {request_text}\n"
        f"# Completed with {len(subtasks)} subtask(s)\n\n"
        f"{code}\n",
        encoding="utf-8",
    )
    print(f"Output written -> {output_path}\n")

    return final_answer
