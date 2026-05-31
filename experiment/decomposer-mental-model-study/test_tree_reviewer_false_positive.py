"""
[VERIFIED 2026-05-28] Experiment 5: Tree Reviewer False Positive Test
Result: 5/5 valid decompositions PASS, 0 false positives.
Output: output/tree_reviewer_v6/deepseek-chat/fp_*/

False Positive Test for Tree Structure Reviewer.

Creates valid (tree-structure-compliant) decompositions and runs them through
the reviewer to verify no false positives are flagged.

Test cases:
  1. Simple flat pipeline — no cross-sibling calls, data flow through parent
  2. Coordinator with real subtree — delegates to its own children
  3. Generic router — routes but doesn't name siblings in behavior
  4. Pure data flow — children only pass data, no sibling calls described
  5. Tool-like flat — each child is an independent tool, parent orchestrates

Usage:
    python test_tree_reviewer_false_positive.py
"""
import json
import os
import sys
import time
import re

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

sys.path.insert(0, os.path.dirname(__file__))
from test_tree_reviewer import (
    REVIEWER_SYSTEM_PROMPT, LLMLogger, parse_verdict,
    build_decomposition_summary
)

from openai import OpenAI

# -----------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------
def _env(key, default=""):
    return os.getenv(key) or os.getenv(f"DEEPSEEK_{key.removeprefix('CHRONOS_')}") or default

TEMPERATURE = float(os.getenv("CHRONOS_TEMPERATURE", "0.3"))
MAX_TOKENS = int(os.getenv("CHRONOS_MAX_TOKENS", "2048"))
MAX_CONCURRENCY = 5

MIMO_MODELS = {"mimo-v2.5", "mimo-v2-flash", "mimo-v2.5-pro", "mimo-v2-pro", "mimo-v2-omni"}
MIMO_BASE_URL = "https://api.xiaomimimo.com/v1"

model = "deepseek-chat"
base_url = _env("CHRONOS_BASE_URL", "https://api.deepseek.com")
api_key = _env("CHRONOS_API_KEY")

OUTPUT_DIR = os.path.join(
    os.path.dirname(__file__), "output", "tree_reviewer_v6"
)


# -----------------------------------------------------------------------
# Valid decompositions (should all PASS)
# -----------------------------------------------------------------------

VALID_DECOMPOSITIONS = [
    {
        "name": "valid_pipeline",
        "description": "Simple flat pipeline, no cross-sibling calls",
        "decomposition": {
            "children": [
                {
                    "name": "ParseInput",
                    "purpose": "Parse and validate raw input data",
                    "behavior": "Parse the JSON input string into a structured data object. Validate required fields. Return the parsed data.",
                    "inputs": [{"name": "input", "type": "str", "description": "Raw JSON input", "source": "parent input"}],
                    "outputs": [{"name": "parsed_data", "type": "dict", "description": "Parsed data object", "consumer": "parent"}]
                },
                {
                    "name": "CalculateTotal",
                    "purpose": "Calculate total price from parsed data",
                    "behavior": "Extract price and quantity from parsed_data. Multiply to get total. Return the total.",
                    "inputs": [{"name": "parsed_data", "type": "dict", "description": "Parsed data with price and quantity", "source": "parent"}],
                    "outputs": [{"name": "total", "type": "float", "description": "Calculated total", "consumer": "parent"}]
                },
                {
                    "name": "FormatOutput",
                    "purpose": "Format result into output structure",
                    "behavior": "Take the total and format into a JSON response with success flag and message. Return the formatted output.",
                    "inputs": [{"name": "total", "type": "float", "description": "Total to format", "source": "parent"}],
                    "outputs": [{"name": "output", "type": "dict", "description": "Formatted result", "consumer": "parent output"}]
                }
            ],
            "decomposition_rationale": "Parent orchestrates: ParseInput → CalculateTotal → FormatOutput. Each child is independent, data flows through parent.",
            "dataflow_edges": [
                {"from_node": "parent", "from_output": "input", "to_node": "ParseInput", "to_input": "input", "note": "Pass raw input"},
                {"from_node": "ParseInput", "from_output": "parsed_data", "to_node": "parent", "to_input": "CalculateTotal input", "note": "Parent passes parsed data"},
                {"from_node": "parent", "from_output": "CalculateTotal result", "to_node": "FormatOutput", "to_input": "total", "note": "Parent passes total"},
                {"from_node": "FormatOutput", "from_output": "output", "to_node": "parent", "to_input": "output", "note": "Return formatted result"}
            ]
        }
    },
    {
        "name": "valid_coordinator_subtree",
        "description": "Coordinator that delegates to its OWN children (grandchildren of parent) — valid tree",
        "decomposition": {
            "children": [
                {
                    "name": "ParseInput",
                    "purpose": "Parse raw request input",
                    "behavior": "Parse the input JSON. Extract and validate fields. Return structured request.",
                    "inputs": [{"name": "input", "type": "str", "description": "Raw input", "source": "parent input"}],
                    "outputs": [{"name": "request", "type": "dict", "description": "Parsed request", "consumer": "parent"}]
                },
                {
                    "name": "ProcessRequest",
                    "purpose": "Orchestrate request processing by delegating to sub-tasks within its own subtree",
                    "behavior": "Coordinate the processing workflow: first check permissions, then execute the action, then log the result. These are sub-tasks managed within this node's own subtree.",
                    "inputs": [{"name": "request", "type": "dict", "description": "Parsed request", "source": "parent"}],
                    "outputs": [{"name": "result", "type": "dict", "description": "Processing result", "consumer": "parent"}]
                },
                {
                    "name": "FormatResponse",
                    "purpose": "Format final response",
                    "behavior": "Take the processing result and format it into a standard API response. Add status code and message.",
                    "inputs": [{"name": "result", "type": "dict", "description": "Processing result to format", "source": "parent"}],
                    "outputs": [{"name": "output", "type": "dict", "description": "Formatted response", "consumer": "parent output"}]
                }
            ],
            "decomposition_rationale": "Parent calls ParseInput, then ProcessRequest (which has its own children), then FormatResponse.",
            "dataflow_edges": [
                {"from_node": "parent", "from_output": "input", "to_node": "ParseInput", "to_input": "input", "note": ""},
                {"from_node": "ParseInput", "from_output": "request", "to_node": "parent", "to_input": "ProcessRequest input", "note": ""},
                {"from_node": "parent", "from_output": "ProcessRequest result", "to_node": "FormatResponse", "to_input": "result", "note": ""},
                {"from_node": "FormatResponse", "from_output": "output", "to_node": "parent", "to_input": "output", "note": ""}
            ]
        }
    },
    {
        "name": "valid_generic_router",
        "description": "Router with generic terms — 'dispatch', 'route' but NO sibling names in behavior",
        "decomposition": {
            "children": [
                {
                    "name": "ParseAndRoute",
                    "purpose": "Parse input and route to appropriate processing logic",
                    "behavior": "Parse the input to determine the request type. Based on the type, apply the corresponding business logic and return the result. The routing is handled internally within this function.",
                    "inputs": [{"name": "input", "type": "str", "description": "Raw input", "source": "parent input"}],
                    "outputs": [{"name": "result", "type": "dict", "description": "Processed result", "consumer": "parent output"}]
                }
            ],
            "decomposition_rationale": "Single child — ParseAndRoute encapsulates all logic internally. No sibling calls possible with only one child.",
            "dataflow_edges": [
                {"from_node": "parent", "from_output": "input", "to_node": "ParseAndRoute", "to_input": "input", "note": ""},
                {"from_node": "ParseAndRoute", "from_output": "result", "to_node": "parent", "to_input": "output", "note": ""}
            ]
        }
    },
    {
        "name": "valid_pure_dataflow",
        "description": "Data flow between siblings — parent orchestrates all passing, no child calls sibling",
        "decomposition": {
            "children": [
                {
                    "name": "FetchData",
                    "purpose": "Fetch raw data from data source",
                    "behavior": "Access the data store and retrieve records matching the query criteria. Return the raw records.",
                    "inputs": [{"name": "query", "type": "dict", "description": "Query parameters", "source": "parent input"}],
                    "outputs": [{"name": "raw_records", "type": "list", "description": "Fetched records", "consumer": "parent"}]
                },
                {
                    "name": "FilterData",
                    "purpose": "Filter and clean raw records",
                    "behavior": "Take records and apply filtering rules. Remove invalid entries. Return cleaned records.",
                    "inputs": [{"name": "raw_records", "type": "list", "description": "Raw records to filter", "source": "parent"}],
                    "outputs": [{"name": "clean_records", "type": "list", "description": "Filtered records", "consumer": "parent"}]
                },
                {
                    "name": "AggregateStats",
                    "purpose": "Compute aggregate statistics from filtered data",
                    "behavior": "Take cleaned records and compute sum, average, count, and distribution. Return the statistics.",
                    "inputs": [{"name": "clean_records", "type": "list", "description": "Cleaned records to aggregate", "source": "parent"}],
                    "outputs": [{"name": "statistics", "type": "dict", "description": "Computed statistics", "consumer": "parent output"}]
                }
            ],
            "decomposition_rationale": "Pure pipeline: FetchData → FilterData → AggregateStats. Parent passes each child's output as next child's input. No child references any sibling.",
            "dataflow_edges": [
                {"from_node": "parent", "from_output": "input", "to_node": "FetchData", "to_input": "query", "note": ""},
                {"from_node": "FetchData", "from_output": "raw_records", "to_node": "parent", "to_input": "FilterData input", "note": "Parent passes data"},
                {"from_node": "parent", "from_output": "FilterData result", "to_node": "AggregateStats", "to_input": "clean_records", "note": "Parent passes data"},
                {"from_node": "AggregateStats", "from_output": "statistics", "to_node": "parent", "to_input": "output", "note": ""}
            ]
        }
    },
    {
        "name": "valid_independent_tools",
        "description": "Completely independent tools — no cross-references at all",
        "decomposition": {
            "children": [
                {
                    "name": "GetUserInfo",
                    "purpose": "Retrieve user information by ID",
                    "behavior": "Look up user by user_id in the users store. Return user details including name, email, and role.",
                    "inputs": [{"name": "user_id", "type": "int", "description": "User ID", "source": "parent input"}],
                    "outputs": [{"name": "user_info", "type": "dict", "description": "User info object", "consumer": "parent output"}]
                },
                {
                    "name": "ListProducts",
                    "purpose": "List all available products",
                    "behavior": "Query the products store for all items. Optionally filter by category. Return product list.",
                    "inputs": [{"name": "category", "type": "str", "description": "Optional category filter", "source": "parent input"}],
                    "outputs": [{"name": "products", "type": "list", "description": "Product list", "consumer": "parent output"}]
                },
                {
                    "name": "CheckHealth",
                    "purpose": "Check system health status",
                    "behavior": "Verify that all data stores are accessible. Return health status with component states.",
                    "inputs": [],
                    "outputs": [{"name": "health_status", "type": "dict", "description": "Health check result", "consumer": "parent output"}]
                }
            ],
            "decomposition_rationale": "Three independent tools, no data flow between them. Parent calls them independently and aggregates results.",
            "dataflow_edges": [
                {"from_node": "parent", "from_output": "input", "to_node": "GetUserInfo", "to_input": "user_id", "note": ""},
                {"from_node": "parent", "from_output": "input", "to_node": "ListProducts", "to_input": "category", "note": ""},
                {"from_node": "parent", "from_output": "input", "to_node": "CheckHealth", "to_input": "", "note": ""}
            ]
        }
    },
]


# -----------------------------------------------------------------------
# Run reviews
# -----------------------------------------------------------------------
def run_review(test_case, replicate_idx, logger):
    """Run a single review on a valid decomposition."""
    decomposition = test_case["decomposition"]
    children = decomposition.get("children", [])
    name = test_case["name"]

    summary = build_decomposition_summary(decomposition)

    review_messages = [
        {"role": "system", "content": REVIEWER_SYSTEM_PROMPT},
        {"role": "user", "content": (
            "Please review the following decomposition for compliance with tree structure constraints.\n\n"
            + summary +
            "\n\nDoes this decomposition satisfy tree structure rules? "
            "Output your verdict as JSON: {\"verdict\": \"PASS\" or \"FAIL\", ...}"
        )},
    ]

    response = logger.chat(review_messages)
    verdict, violations, reasoning, recommendation = parse_verdict(response)

    return {
        "test_name": name,
        "description": test_case["description"],
        "replicate": replicate_idx,
        "n_children": len(children),
        "child_names": [c.get("name", "") for c in children],
        "verdict": verdict,
        "violations": violations,
        "reasoning": reasoning[:500] if reasoning else "",
        "recommendation": recommendation[:500] if recommendation else "",
        "raw_response": response,
    }


def main():
    global api_key, base_url, model

    if not api_key:
        print("ERROR: Set CHRONOS_API_KEY (or DEEPSEEK_API_KEY)")
        return 1

    print(f"Model: {model}")
    print(f"API: {base_url}")
    print(f"Test cases: {len(VALID_DECOMPOSITIONS)}")
    print(f"Replicates per case: 2")
    print()

    # Run reviews
    all_results = []
    for test_case in VALID_DECOMPOSITIONS:
        for rep in range(2):
            log_dir = os.path.join(OUTPUT_DIR, model, f"fp_{test_case['name']}")
            os.makedirs(log_dir, exist_ok=True)
            logger = LLMLogger(log_dir, api_key, base_url, model)

            t0 = time.time()
            try:
                result = run_review(test_case, rep, logger)
                result["elapsed"] = round(time.time() - t0, 1)
                all_results.append(result)

                verdict = result["verdict"]
                n_violations = len(result.get("violations", []))
                fp_mark = " <-- FALSE POSITIVE?" if verdict == "FAIL" else " [OK]"
                print(f"  [{test_case['name']}/rep_{rep:02d}] {verdict} ({n_violations} violations){fp_mark}")
            except Exception as e:
                print(f"  [{test_case['name']}/rep_{rep:02d}] ERROR: {e}")
                all_results.append({"test_name": test_case['name'], "error": str(e)})

    # Report
    print(f"\n{'='*60}")
    print(f"  FALSE POSITIVE TEST RESULTS")
    print(f"{'='*60}")
    print()

    false_positives = 0
    for r in all_results:
        verdict = r.get("verdict", "ERROR")
        name = r["test_name"]
        desc = r.get("description", "")
        violations = r.get("violations", [])
        n_v = len(violations)
        is_fp = verdict == "FAIL"

        status = "<-- FALSE POSITIVE" if is_fp else "[OK] CORRECTLY PASSED"
        if is_fp:
            false_positives += 1

        print(f"  {name}/rep_{r['replicate']:02d}: {verdict} — {status}")
        print(f"    {desc}")
        if n_v > 0:
            for v in violations:
                if isinstance(v, dict):
                    print(f"    Violation: {v.get('from_node','')} → {v.get('to_node','')}: {v.get('details','')[:200]}")
                else:
                    print(f"    Violation: {v}")
            print(f"    Reasoning: {r.get('reasoning', '')[:300]}")
        print()

    total = len(all_results)
    pass_count = total - false_positives
    print(f"  Total: {total}")
    print(f"  Correctly PASSED: {pass_count}/{total}")
    print(f"  False positives: {false_positives}/{total}")
    print(f"{'='*60}")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
