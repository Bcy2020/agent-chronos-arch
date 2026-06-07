"""
Full pipeline acceptance test for MVP 0.4.4+0.4.5.
Uses real LLM: three-stage decomposition + dataflow-aware codegen.

Usage:
    cd mvp/mvp-0.4.4
    python tests/test_full_pipeline.py --case OrderSystem --max-depth 2
"""
import json
import os
import sys
import argparse
import time
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import Config
from api_client import APIClient
from tree_builder import TreeBuilder
from decomposer import Decomposer
from code_generator import CodeGenerator
from validator import Validator
from models import Node, InputParam, OutputParam, Boundary, GlobalVar, DataSource, SubPRD


ROOT_CASES = {
    "OrderSystem": {
        "name": "ProcessOrder",
        "purpose": "Process incoming order commands: create, pay, ship, cancel, list, or get user orders",
        "inputs": [
            {"name": "command", "type": "str", "description": "Command name"},
            {"name": "payload", "type": "dict", "description": "Command payload"},
        ],
        "outputs": [
            {"name": "result", "type": "dict", "description": "Command result"},
        ],
        "global_vars": [
            {"variable": "orders", "op": "read_write", "description": "Orders store"},
            {"variable": "products", "op": "read", "description": "Product catalog"},
            {"variable": "users", "op": "read_write", "description": "User balances"},
        ],
    },
    "ChatApp": {
        "name": "ProcessChatCommand",
        "purpose": "Process chat commands: send message, get history, create channel, join channel",
        "inputs": [
            {"name": "command", "type": "str", "description": "Command name"},
            {"name": "payload", "type": "dict", "description": "Command payload"},
        ],
        "outputs": [
            {"name": "result", "type": "dict", "description": "Command result"},
        ],
        "global_vars": [
            {"variable": "channels", "op": "read_write", "description": "Chat channels"},
            {"variable": "messages", "op": "read_write", "description": "Chat messages"},
            {"variable": "users", "op": "write", "description": "User presence"},
        ],
    },
    "PatientPortal": {
        "name": "ProcessPatientRequest",
        "purpose": "Process patient portal requests: register, book appointment, get records, update profile",
        "inputs": [
            {"name": "request_type", "type": "str", "description": "Request type"},
            {"name": "request_data", "type": "dict", "description": "Request payload"},
        ],
        "outputs": [
            {"name": "result", "type": "dict", "description": "Request result"},
        ],
        "global_vars": [
            {"variable": "patients", "op": "read_write", "description": "Patient records"},
            {"variable": "appointments", "op": "read_write", "description": "Appointments"},
            {"variable": "medical_records", "op": "read", "description": "Medical records"},
        ],
    },
    "DataPipeline": {
        "name": "ProcessPipelineTask",
        "purpose": "Process data pipeline tasks: ingest, transform, validate, export data",
        "inputs": [
            {"name": "source_config", "type": "dict", "description": "Source configuration"},
            {"name": "pipeline_config", "type": "dict", "description": "Pipeline configuration"},
        ],
        "outputs": [
            {"name": "pipeline_result", "type": "dict", "description": "Pipeline execution result"},
        ],
        "global_vars": [
            {"variable": "pipeline_log", "op": "write", "description": "Pipeline execution log"},
            {"variable": "raw_data", "op": "read_write", "description": "Raw ingested data"},
            {"variable": "processed_data", "op": "read_write", "description": "Processed output data"},
        ],
    },
}


def build_root_node(case_name: str) -> Node:
    """Build a root Node from a test case definition."""
    case = ROOT_CASES[case_name]
    return Node(
        node_id="root",
        name=case["name"],
        depth=0,
        purpose=case["purpose"],
        inputs=[InputParam(**i) for i in case["inputs"]],
        outputs=[OutputParam(**o) for o in case["outputs"]],
        boundary=Boundary(in_scope=["all described functionality"], out_of_scope=["external systems"]),
        global_vars=[GlobalVar(**g) for g in case["global_vars"]],
        subprd=SubPRD(
            task_id="root",
            purpose=case["purpose"],
            description=case["purpose"],
            inputs=[InputParam(**i) for i in case["inputs"]],
            outputs=[OutputParam(**o) for o in case["outputs"]],
            boundary=Boundary(in_scope=["all described functionality"], out_of_scope=["external systems"]),
        ),
    )


def detect_routing_after_decompose(node: Node) -> list:
    """Check if any child's behavior describes calling a sibling."""
    child_names = {c.name for c in node.children}
    violations = []
    for child in node.children:
        contract = node.children_contracts.get(child.name)
        if not contract:
            continue
        behavior = (contract.behavior or "").lower()
        for sibling in child_names:
            if sibling != child.name and sibling.lower() in behavior:
                violations.append({"from": child.name, "to": sibling})
    return violations


def run_pipeline(case_name: str, max_depth: int = 2, max_children: int = 6):
    """Run the full decomposition pipeline on a root node."""
    config = Config(max_depth=max_depth, max_children=max_children, max_decompose_retries=2, max_retries=2)
    api_client = APIClient(config)

    # Quick connection check
    try:
        ok = api_client.test_connection()
        if not ok:
            print("API connection failed — check DEEPSEEK_API_KEY")
            return None
        print(f"API connection OK. Model: {config.model}")
    except Exception as e:
        print(f"API connection error: {e}")
        return None

    root = build_root_node(case_name)
    print(f"\n{'='*60}")
    print(f"FULL PIPELINE TEST: {case_name} ({root.name})")
    print(f"Max depth: {max_depth}, Max children: {max_children}")
    print(f"{'='*60}")

    builder = TreeBuilder(config=config, api_client=api_client)
    start = time.time()

    root = builder.build_tree(root)
    success = not root.needs_human_intervention

    elapsed = time.time() - start
    print(f"\n{'='*60}")
    print(f"PIPELINE RESULT")
    print(f"{'='*60}")
    print(f"Success: {success}")
    print(f"Elapsed: {elapsed:.0f}s")
    print(f"Node: {root.name} (depth={root.depth})")

    # Collect tree stats
    all_nodes = []

    def collect(n):
        all_nodes.append(n)
        for c in (n.children or []):
            collect(c)

    collect(root)
    parent_nodes = [n for n in all_nodes if n.children]
    leaf_nodes = [n for n in all_nodes if not n.children]
    success_nodes = [n for n in parent_nodes if n.code]

    print(f"Total nodes: {len(all_nodes)} ({len(parent_nodes)} parents, {len(leaf_nodes)} leaves)")
    print(f"Parent nodes with code: {len(success_nodes)}/{len(parent_nodes)}")
    print(f"Nodes needing human intervention: {sum(1 for n in all_nodes if n.needs_human_intervention)}")

    # Check routing
    routing_count = 0
    for n in parent_nodes:
        violations = detect_routing_after_decompose(n)
        if violations:
            routing_count += 1
            print(f"  ROUTING in {n.name}: {violations}")

    print(f"Routing violations: {routing_count}/{len(parent_nodes)} parent nodes")
    if len(parent_nodes) > 0:
        routing_rate = routing_count / len(parent_nodes) * 100
        print(f"Routing rate: {routing_rate:.0f}%")
        verdict = "PASS" if routing_rate < 10 else "FAIL"
        print(f"Verdict: {verdict} (threshold: <10%)")
    else:
        verdict = "INCONCLUSIVE (no parent nodes)"

    # Save tree
    out_dir = os.path.join(config.output_dir, "pipeline_test")
    os.makedirs(out_dir, exist_ok=True)
    tree_path = os.path.join(out_dir, f"{case_name}_tree.json")
    try:
        with open(tree_path, "w", encoding="utf-8") as f:
            json.dump(root.to_dict(), f, indent=2, ensure_ascii=False, default=str)
        print(f"Tree saved: {tree_path}")
    except Exception as e:
        print(f"Tree save error: {e}")

    return {
        "case": case_name,
        "success": success,
        "elapsed": elapsed,
        "total_nodes": len(all_nodes),
        "parent_nodes": len(parent_nodes),
        "leaf_nodes": len(leaf_nodes),
        "routing_violations": routing_count,
        "routing_rate": routing_count / len(parent_nodes) * 100 if parent_nodes else 0,
        "verdict": verdict,
        "needs_human": sum(1 for n in all_nodes if n.needs_human_intervention),
    }


def main():
    parser = argparse.ArgumentParser(description="Full pipeline acceptance test")
    parser.add_argument("--case", type=str, default="OrderSystem",
                        choices=list(ROOT_CASES.keys()),
                        help="Test case to run")
    parser.add_argument("--max-depth", type=int, default=2)
    parser.add_argument("--max-children", type=int, default=6)
    parser.add_argument("--all", action="store_true", help="Run all cases")
    args = parser.parse_args()

    if args.all:
        results = []
        for case_name in ROOT_CASES:
            r = run_pipeline(case_name, args.max_depth, args.max_children)
            if r:
                results.append(r)
            time.sleep(2)  # Rate limiting

        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        passed = sum(1 for r in results if r.get("verdict") == "PASS")
        print(f"Passed: {passed}/{len(results)}")
        for r in results:
            print(f"  {r['case']}: routing={r['routing_rate']:.0f}% ({r['routing_violations']}/{r['parent_nodes']}), "
                  f"verdict={r['verdict']}, nodes={r['total_nodes']}, time={r['elapsed']:.0f}s")
    else:
        run_pipeline(args.case, args.max_depth, args.max_children)


if __name__ == "__main__":
    main()
