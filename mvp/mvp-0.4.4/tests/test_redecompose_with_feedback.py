"""
Test: Decomposer redecomposition with correct CANNOT_COMPOSE feedback.

Simulates the scenario where Step 2 correctly rejects a two-level decomposition
(ParseInput + ExecuteCommand + 5 handlers) and suggests flat dispatch.
Tests whether the decomposer produces a correct flat decomposition.

All LLM inputs/outputs are saved to tests/output/test_redecompose_with_feedback/llm_log/.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from api_client import APIClient
from decomposer import Decomposer
from models import Node, InputParam, OutputParam, Boundary, GlobalVar, CompositionFeedback, FailureContext


OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output", "test_redecompose_with_feedback")
LLM_LOG_DIR = os.path.join(OUTPUT_DIR, "llm_log")
os.makedirs(LLM_LOG_DIR, exist_ok=True)


class LoggingAPIClient(APIClient):
    def __init__(self, config, log_dir):
        super().__init__(config)
        self.log_dir = log_dir
        self.call_counter = 0
        os.makedirs(log_dir, exist_ok=True)

    def chat(self, messages, temperature=None, max_tokens=4096):
        self.call_counter += 1
        call_id = self.call_counter

        req = {
            "call_id": call_id,
            "timestamp": time.time(),
            "messages": messages,
            "max_tokens": max_tokens,
        }
        with open(os.path.join(self.log_dir, f"{call_id:04d}_request.json"), "w", encoding="utf-8") as f:
            json.dump(req, f, indent=2, ensure_ascii=False)

        print(f"  [LLM #{call_id}] ...")
        start = time.time()
        response_text = super().chat(messages, temperature, max_tokens)
        elapsed = time.time() - start

        resp = {"call_id": call_id, "elapsed": round(elapsed, 2), "response": response_text}
        with open(os.path.join(self.log_dir, f"{call_id:04d}_response.json"), "w", encoding="utf-8") as f:
            json.dump(resp, f, indent=2, ensure_ascii=False)

        print(f"    done ({elapsed:.1f}s)")
        return response_text


def make_library_root() -> Node:
    """Create a Library_prd root node (same as what PRD converter produces)."""
    root = Node(
        node_id="root_Library_prd",
        name="Library_prd",
        purpose="Simple Book Library: supports add, list, borrow, return, remove books. "
                "Input is JSON with 'command' field and 'book_data' object.",
        depth=0,
        inputs=[InputParam(name="input", type="Any", description="System input")],
        outputs=[OutputParam(name="output", type="Any", description="System output")],
        boundary=Boundary(),
        global_vars=[
            GlobalVar(variable="books", op="read_write", description="Stores all books with book_id as key."),
            GlobalVar(variable="next_id", op="read_write", description="Counter for generating unique book IDs."),
        ],
    )
    return root


def run_test():
    print("=" * 70)
    print("  TEST: Decomposer redecomposition with CANNOT_COMPOSE feedback")
    print("=" * 70)

    cfg = Config(
        api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        temperature=0.2,
        max_depth=3,
        max_children=10,
        max_retries=3,
        max_decompose_retries=3,
        output_dir=OUTPUT_DIR,
    )

    if not cfg.api_key:
        print("ERROR: DEEPSEEK_API_KEY not set")
        return 1

    api_client = LoggingAPIClient(cfg, LLM_LOG_DIR)
    decomposer = Decomposer(cfg, api_client)

    # ---------------------------------------------------------------
    # Step 1: First decomposition (no feedback)
    # ---------------------------------------------------------------
    print("\n--- Step 1: First decomposition ---")
    root = make_library_root()
    node, errors = decomposer.decompose(root)

    if errors:
        print(f"  ERROR: First decomposition failed: {errors}")
        return 1

    child_names = [c.name for c in node.children]
    print(f"  Children ({len(node.children)}): {child_names}")

    # Check if it's the problematic two-level pattern
    has_execute_command = "ExecuteCommand" in child_names
    has_flat_handlers = any(name in child_names for name in ["AddBook", "ListBooks", "BorrowBook", "ReturnBook", "RemoveBook"])

    if has_execute_command and has_flat_handlers:
        print("  Detected: two-level pattern (ExecuteCommand + handlers)")
    elif has_flat_handlers and not has_execute_command:
        print("  Detected: flat dispatch pattern (correct!)")
    else:
        print(f"  Detected: other pattern: {child_names}")

    # ---------------------------------------------------------------
    # Step 2: Simulate CANNOT_COMPOSE rejection + correct suggestion
    # ---------------------------------------------------------------
    print("\n--- Step 2: Build multi-turn messages with CANNOT_COMPOSE feedback ---")

    # Simulate what Step 2 would produce if it correctly rejected
    feedback = CompositionFeedback(
        status="cannot_compose",
        reason="invalid_child_boundary",
        failed_checks=["child_coverage"],
        suggested_fix=(
            "The parent must directly call each business handler. "
            "ExecuteCommand is acting as a router that internally calls AddBook, ListBooks, etc., "
            "but in a tree decomposition the parent is the sole coordinator. "
            "Remove ExecuteCommand and have the parent directly call: "
            "ParseInput to get command and book_data, then use if/elif to dispatch to "
            "AddBook(book_data), ListBooks(book_data), BorrowBook(book_data), ReturnBook(book_data), RemoveBook(book_data)."
        ),
        checks={
            "child_coverage": {
                "passed": False,
                "detail": "Children AddBook, ListBooks, BorrowBook, ReturnBook, RemoveBook are not directly called by the parent. "
                          "ExecuteCommand calls them internally, which violates the tree structure rule: "
                          "parent must be the sole coordinator, children must not call each other."
            }
        }
    )

    # Save to last_failure for the message builder
    node.last_failure = FailureContext(
        stage="codegen",
        errors=["CANNOT_COMPOSE: invalid_child_boundary"],
        structured_errors=[],
        children_snapshot=[c.name for c in node.children],
        decomposition_rationale=node.decomposition_rationale,
        composition_feedback=feedback,
    )

    # Build messages the same way tree_builder does
    from tree_builder import TreeBuilder
    builder = TreeBuilder(cfg, api_client=api_client)
    messages = builder._build_decompose_messages(node, retry_count=1)

    print(f"  Messages: {len(messages)}")
    for i, m in enumerate(messages):
        role = m["role"]
        preview = m["content"][:120].replace("\n", " ")
        print(f"    [{i}] {role}: {preview}...")

    # ---------------------------------------------------------------
    # Step 3: Call decomposer with multi-turn messages
    # ---------------------------------------------------------------
    print("\n--- Step 3: Decompose with feedback ---")

    # Clear children to simulate redecomposition
    node.children = []
    node.children_contracts = {}

    node2, errors2 = decomposer.decompose_with_messages(node, messages)

    if errors2:
        print(f"  ERROR: Redecomposition failed: {errors2}")
        return 1

    child_names2 = [c.name for c in node2.children]
    print(f"  Children ({len(node2.children)}): {child_names2}")

    has_execute_command2 = "ExecuteCommand" in child_names2
    has_flat_handlers2 = any(name in child_names2 for name in ["AddBook", "ListBooks", "BorrowBook", "ReturnBook", "RemoveBook"])

    if has_execute_command2 and has_flat_handlers2:
        print("  Result: STILL two-level pattern (ExecuteCommand + handlers)")
        print("  FAIL: Decomposer did not fix the structure despite correct feedback")
        verdict = "FAIL"
    elif has_flat_handlers2 and not has_execute_command2:
        print("  Result: flat dispatch pattern (correct!)")
        print("  PASS: Decomposer correctly removed ExecuteCommand and uses flat dispatch")
        verdict = "PASS"
    else:
        print(f"  Result: other pattern: {child_names2}")
        verdict = "UNKNOWN"

    # Check if ParseInput is still there (should be)
    if "ParseInput" in child_names2:
        print("  ParseInput: present (correct)")
    else:
        print("  ParseInput: missing (decomposition may be incomplete)")

    # ---------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------
    print("\n" + "=" * 70)
    print(f"  VERDICT: {verdict}")
    print(f"  LLM calls: {api_client.call_counter}")
    print(f"  LLM logs: {LLM_LOG_DIR}")
    print("=" * 70)

    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(run_test())
