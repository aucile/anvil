# AUTHOR: IAN SAVINO
# DATE: 2026

import argparse
from pathlib import Path
import sys

from anvil import storage


def read_storage(limit: int = 10):
    """Print recent request history straight from storage — no API key needed."""
    for request in storage.get_history(limit):
        print(f"\n{'='*60}")
        print(f"Request #{request['id']}  ({request['created_at']})")
        print(f"Request: {request['request_text']}")
        print(f"Subtasks:")
        for sub in request["subtasks"]:
            print(f"  [{sub['subtask_index']}] {sub['subtask_text']}")
            print(f"      {sub['model']}: {str(sub['result'])[:200]}")
        print(f"Final answer: {request['final_answer'][:300]}...")


def main():
    parser = argparse.ArgumentParser(description="construct simple instructions with a high-functioning model and pass them to a lower one")
    
    parser.add_argument("request", nargs="?", default=None, type=str, help="the request to be processed")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-o", "--orchestrate", action="store_true", help="used with request details to activate the model")
    group.add_argument("-f", "--forget", action="store_true", help="erases storage memory")
    group.add_argument("-s", "--storage", action="store_true", help="access memory of requests")

    args = parser.parse_args()

    storage.init_db()

    if args.storage:
        read_storage()
        sys.exit(0)

    if args.forget:
        db_path = Path(storage.DB_PATH)
        if db_path.exists():
            db_path.unlink()
            print("Storage has been erased.")
        else:
            print("No storage database found.")
        sys.exit(0)

    if (args.orchestrate and args.request):
        from anvil import orchestrator
        print(orchestrator.orchestrate(args.request))
    elif (args.request):
        raise SystemExit("Error: Did you mean to run the anvil with -o?")
    elif (args.orchestrate):
        from anvil import orchestrator
        print("What is your request?")
        err_request = input("Enter it here: ")
        print(orchestrator.orchestrate(err_request))

if __name__ == "__main__": main()