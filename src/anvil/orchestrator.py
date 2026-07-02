# AUTHOR: IAN SAVINO
# DATE: 2026

import json
import re
import sys
from pathlib import Path
import anthropic
from openai import OpenAI
from dotenv import load_dotenv

from anvil import storage

load_dotenv()

claude = anthropic.Anthropic()
ollama = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")

WORKER_MODEL = "qwen2.5-coder:3b"
PLANNER_MODEL = "claude-sonnet-4-6"
OUTPUT_DIR = Path("output")


def extract_json(text: str) -> dict:
    """Strip markdown fences and parse JSON from a model response."""
    # Remove ```json ... ``` or ``` ... ``` wrappers if present
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text.strip())
    return json.loads(text)


def run_subtask(subtask: str, model: str = WORKER_MODEL) -> str:
    """Dispatch a subtask to a local worker model — fast and free."""
    response = ollama.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": subtask}]
    )
    return response.choices[0].message.content


def orchestrate(request_text: str) -> str:
    print(f"\nPlanner receives the request...")
    print(f'  "{request_text}"')

    # Step 1: Planner decomposes the request into subtasks
    plan_response = claude.messages.create(
        model=PLANNER_MODEL,
        max_tokens=500,
        system=(
            "You are a planner model that delegates work to smaller worker models. "
            "Break the user's request into 2-4 concrete, independent subtasks "
            "that a worker can handle on their own. "
            'Respond ONLY with valid JSON: {"subtasks": ["task1", "task2"]}'
        ),
        messages=[{"role": "user", "content": request_text}]
    )

    plan = extract_json(plan_response.content[0].text)
    subtasks = plan["subtasks"]
    print(f"\nPlanner produced {len(subtasks)} subtask(s):")
    for i, subtask in enumerate(subtasks, 1):
        print(f"  [{i}] {subtask}")

    # Step 2: Worker models handle each subtask
    results = {}
    for i, subtask in enumerate(subtasks, 1):
        print(f"\nWorker runs subtask {i}: {subtask[:60]}{'...' if len(subtask) > 60 else ''}")
        results[f"subtask_{i}"] = run_subtask(subtask)
        print(f"    ...subtask complete.")

    # Step 3: Planner synthesizes the final answer
    print(f"\nPlanner synthesizes the results into a final answer...")
    final = claude.messages.create(
        model=PLANNER_MODEL,
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

    final_answer = final.content[0].text

    request_id = storage.save_request(
        request_text=request_text,
        subtasks=subtasks,
        results=results,
        final_answer=final_answer,
        model="qwen",
    )
    print(f"\nRequest #{request_id} recorded in storage ({storage.DB_PATH})")

    # Extract only the code block(s) from the answer
    code_blocks = re.findall(r"```(?:python)?\s*\n(.*?)```", final_answer, re.DOTALL)
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
