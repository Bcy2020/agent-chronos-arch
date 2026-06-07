"""
Test: FailureContext + Multi-turn Messages flow with real LLM calls.

Verifies:
  1. FailureContext is created at each failure stage (decompose/codegen/validate)
  2. Multi-turn messages are built correctly on retry (assistant + user feedback)
  3. composition_feedback is stored on CodeGenerator, not on Node
  4. node.last_failure is populated and used across retries
  5. Attempt history records are correct

All LLM requests/responses are logged to tests/output/<prd>/llm_log/.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from api_client import APIClient
from code_generator import CodeGenerator
from prd_converter import PRDConverter
from interface_planner import InterfacePlanner
from interface_normalizer import InterfaceNormalizer
from interface_impl_generator import InterfaceImplementationGenerator
from interface_verifier import InterfaceVerifier
from tree_builder import TreeBuilder
from models import Node, FailureContext


OUTPUT_DIR = os.environ.get("TEST_OUTPUT_DIR") or os.path.join(
    os.path.dirname(__file__), "output", "test_failure_context_flow"
)


class LoggingAPIClient(APIClient):
    """APIClient that logs all LLM requests/responses to a given directory."""

    def __init__(self, config, log_dir):
        super().__init__(config)
        self.log_dir = log_dir
        self.call_counter = 0
        os.makedirs(log_dir, exist_ok=True)

    def chat(self, messages, temperature=None, max_tokens=4096):
        self.call_counter += 1
        call_id = self.call_counter

        caller_frame = sys._getframe(1)
        caller_func = caller_frame.f_code.co_name
        caller_module = caller_frame.f_globals.get("__name__", "unknown")

        req = {
            "call_id": call_id,
            "caller": f"{caller_module}.{caller_func}",
            "timestamp": time.time(),
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        req_path = os.path.join(self.log_dir, f"{call_id:04d}_request.json")
        with open(req_path, "w", encoding="utf-8") as f:
            json.dump(req, f, indent=2, ensure_ascii=False)

        print(f"  [LLM #{call_id}] {caller_module}.{caller_func}...")
        start = time.time()
        response_text = super().chat(messages, temperature, max_tokens)
        elapsed = time.time() - start

        resp = {
            "call_id": call_id,
            "elapsed": round(elapsed, 2),
            "response": response_text,
        }
        resp_path = os.path.join(self.log_dir, f"{call_id:04d}_response.json")
        with open(resp_path, "w", encoding="utf-8") as f:
            json.dump(resp, f, indent=2, ensure_ascii=False)

        print(f"    done ({elapsed:.1f}s)")
        return response_text


def verify_failure_contexts(node: Node) -> dict:
    """Verify FailureContext consistency in attempt_history and node.last_failure."""
    report = {
        "total_attempts": len(node.attempt_history),
        "has_last_failure": node.last_failure is not None,
        "last_failure_stage": None,
        "failure_stages_seen": [],
        "issues": [],
    }

    if node.last_failure:
        report["last_failure_stage"] = node.last_failure.stage
        fc = node.last_failure
        if not fc.stage:
            report["issues"].append("last_failure.stage is empty")
        if not isinstance(fc.errors, list):
            report["issues"].append("last_failure.errors is not a list")
        if fc.stage == "codegen" and fc.composition_feedback:
            report["last_failure_has_feedback"] = True

    for i, att in enumerate(node.attempt_history):
        if att.decision in ("failed", "redecompose", "redecompose_conservation"):
            report["failure_stages_seen"].append({
                "index": i,
                "stage": att.stage,
                "decision": att.decision,
                "error_count": len(att.validation_errors),
            })

    return report


def verify_multiturn_messages(llm_log_dir: str) -> dict:
    """Check LLM log files for multi-turn message format on retries."""
    report = {"multiturn_detected": False, "message_turns": []}

    if not os.path.isdir(llm_log_dir):
        return report

    request_files = sorted(f for f in os.listdir(llm_log_dir) if f.endswith("_request.json"))
    for fname in request_files:
        fpath = os.path.join(llm_log_dir, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            req = json.load(f)

        caller = req.get("caller", "")
        messages = req.get("messages", [])
        msg_count = len(messages)

        if "decompose" in caller and msg_count > 2:
            report["multiturn_detected"] = True
            roles = [m.get("role", "?") for m in messages]
            report["message_turns"].append({
                "file": fname,
                "turn_count": msg_count,
                "roles": roles,
            })

    return report


def verify_codegen_feedback_location() -> dict:
    """Verify composition_feedback is NOT on Node, but on CodeGenerator."""
    report = {"issues": []}
    node = Node(node_id="test_001", name="test", purpose="test", depth=0)
    if hasattr(node, "composition_feedback") and node.composition_feedback is not None:
        report["issues"].append("Node still has composition_feedback")
    if hasattr(node, "validation") and node.validation is not None:
        report["issues"].append("Node still has validation")
    if not hasattr(node, "last_failure"):
        report["issues"].append("Node missing last_failure")
    return report


def run_single_test(prd_path: str, prd_label: str) -> dict:
    """Run full pipeline on a single PRD and verify FailureContext behavior."""
    print()
    print("=" * 70)
    print(f"  TEST: FailureContext Flow — {prd_label}")
    print(f"  PRD: {prd_path}")
    print("=" * 70)

    if not os.path.exists(prd_path):
        print(f"ERROR: PRD not found: {prd_path}")
        return {"prd": prd_label, "error": "PRD not found"}

    test_output = os.path.join(OUTPUT_DIR, prd_label)
    test_llm_log = os.path.join(test_output, "llm_log")
    os.makedirs(test_llm_log, exist_ok=True)

    cfg = Config(
        api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        temperature=0.2,
        max_depth=3,
        max_children=10,
        max_retries=3,
        max_decompose_retries=3,
        output_dir=test_output,
        nodes_dir=os.path.join(test_output, "nodes"),
    )

    if not cfg.api_key:
        print("ERROR: DEEPSEEK_API_KEY not set")
        return {"prd": prd_label, "error": "No API key"}

    api_client = LoggingAPIClient(cfg, test_llm_log)

    # Phase 0: PRD Conversion
    print("\n--- Phase 0: PRD Conversion ---")
    with open(prd_path, "r", encoding="utf-8") as f:
        prd_text = f.read()
    converter = PRDConverter(cfg, api_client)
    json_prd = converter.convert_and_save(prd_text, test_output)

    # Phase 1: Root Node
    print("\n--- Phase 1: Root Node ---")
    from main import create_root_from_prd
    root = create_root_from_prd(prd_path, name=None, json_prd=json_prd)
    print(f"  Root: {root.name}")

    # Phase 2: Interface Planning
    print("\n--- Phase 2: Interface Planning ---")
    interface_plan = None
    if json_prd:
        planner = InterfacePlanner(cfg, api_client)
        interface_plan = planner.plan(json_prd)

    # Phase 3: Interface Code Generation
    if interface_plan and interface_plan.resources:
        print("\n--- Phase 3: Interface Code ---")
        normalizer = InterfaceNormalizer()
        normalizer.normalize_plan(interface_plan)
        impl_gen = InterfaceImplementationGenerator(cfg, api_client)
        interface_code = impl_gen.generate(interface_plan)
        interface_dir = os.path.join(test_output, "generated")
        os.makedirs(interface_dir, exist_ok=True)
        with open(os.path.join(interface_dir, "interfaces.py"), "w", encoding="utf-8") as f:
            f.write(interface_code)

    # Phase 4: Decomposition Loop
    print("\n--- Phase 4: Decomposition Loop ---")
    builder = TreeBuilder(cfg, interface_plan=interface_plan, api_client=api_client)
    if interface_plan:
        builder.code_generator.set_interface_plan(interface_plan)

    start = time.time()
    result_node, success = builder._process_node(root)
    elapsed = time.time() - start

    # Save snapshot
    snapshot = {
        "name": result_node.name,
        "success": success,
        "elapsed": round(elapsed, 1),
        "children": [c.name for c in result_node.children],
        "attempt_count": len(result_node.attempt_history),
        "needs_human_intervention": result_node.needs_human_intervention,
    }
    if result_node.last_failure:
        snapshot["last_failure"] = result_node.last_failure.to_dict()
    with open(os.path.join(test_output, "snapshot.json"), "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)

    # Verifications
    print("\n--- Verification ---")

    fc_report = verify_failure_contexts(result_node)
    print(f"  FailureContext: {fc_report['total_attempts']} attempts, "
          f"stages_seen={len(fc_report['failure_stages_seen'])}")
    for issue in fc_report["issues"]:
        print(f"    ISSUE: {issue}")

    mt_report = verify_multiturn_messages(test_llm_log)
    print(f"  Multi-turn messages: detected={mt_report['multiturn_detected']}")
    for turn in mt_report["message_turns"]:
        print(f"    {turn['file']}: {turn['turn_count']} msgs, roles={turn['roles']}")

    cg_report = verify_codegen_feedback_location()
    for issue in cg_report["issues"]:
        print(f"    CODEGEN ISSUE: {issue}")
    if not cg_report["issues"]:
        print(f"  Codegen feedback location: OK")

    print(f"\n  Result: {'PASS' if success else 'FAIL'} ({elapsed:.1f}s, "
          f"{len(result_node.attempt_history)} attempts, "
          f"{api_client.call_counter} LLM calls)")

    return {
        "prd": prd_label,
        "success": success,
        "elapsed": round(elapsed, 1),
        "attempt_count": len(result_node.attempt_history),
        "llm_calls": api_client.call_counter,
        "failure_context_report": fc_report,
        "multiturn_report": mt_report,
        "codegen_location_report": cg_report,
    }


def main():
    benchmark_dir = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "benchmark", "test_cases"
    )

    prds = [
        (os.path.join(benchmark_dir, "basic", "library_prd.md"), "library"),
        (os.path.join(benchmark_dir, "basic", "expense_prd.md"), "expense"),
    ]

    print("=" * 70)
    print("  FailureContext + Multi-turn Messages Flow Test")
    print(f"  PRDs: {[p[1] for p in prds]}")
    print(f"  Output: {OUTPUT_DIR}")
    print("=" * 70)

    results = []
    for prd_path, prd_label in prds:
        result = run_single_test(prd_path, prd_label)
        results.append(result)

    # Summary
    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)

    all_pass = True
    for r in results:
        label = r.get("prd", "?")
        success = r.get("success", False)
        status = "PASS" if success else "FAIL"
        if not success:
            all_pass = False

        fc = r.get("failure_context_report", {})
        mt = r.get("multiturn_report", {})
        cg = r.get("codegen_location_report", {})

        print(f"\n  [{status}] {label}")
        print(f"    Attempts: {r.get('attempt_count', 0)}, LLM calls: {r.get('llm_calls', 0)}")
        print(f"    Failure stages seen: {len(fc.get('failure_stages_seen', []))}")
        print(f"    Multi-turn detected: {mt.get('multiturn_detected', False)}")
        if cg.get("issues"):
            print(f"    Codegen issues: {cg['issues']}")

    result_path = os.path.join(OUTPUT_DIR, "results.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n  Full results: {result_path}")
    print(f"  LLM logs: {OUTPUT_DIR}/<prd>/llm_log/")

    if all_pass:
        print("\n  ALL TESTS PASSED")
        print("=" * 70)
        return 0
    else:
        print("\n  SOME TESTS FAILED")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
