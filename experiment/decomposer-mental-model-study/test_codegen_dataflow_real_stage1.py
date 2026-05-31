"""
Codegen Dataflow Real Stage1 Subexperiment (Adapter Patch Rerun)

Tests dataflow-aware parent codegen using real Stage1 outputs from Exp01,
with adapter patches for: domain parent I/O, parent-local dataflow,
conditional dispatch, internal leaf access exclusion, name sanitization.

Do NOT modify mvp/mvp-0.4.4/. This is experiment-only.

Output: output/codegen_dataflow_real_stage1_adapter_patch/<model>/
"""
import json
import os
import sys
import re
import time
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "mvp", "mvp-0.4.4"))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from models import Node, DataflowEdge
from config import Config
from api_client import APIClient
from code_generator_dataflow import DataflowAwareCodeGenerator
from real_stage1_codegen_adapter import RealStage1Adapter


# ============================================================================
# Candidate Definitions (scoped for this rerun)
# ============================================================================

POSITIVE_CANDIDATES = [
    "Order/trial_02",
    "Chat/trial_02",
]

NEGATIVE_CANDIDATES = [
    "Chat/trial_00",
]

STAGE1_BASE = os.path.join(
    os.path.dirname(__file__), "output",
    "multistage_exp01_stage1_routing", "deepseek-v4-flash"
)


# ============================================================================
# Failure Categories
# ============================================================================

FAILURE_CATEGORIES = {
    "audit_failure": "Candidate failed Phase A audit",
    "adapter_conversion_failure": "Adapter conversion produced invalid interface (validation error)",
    "codegen_self_check_failure": "Codegen accepted but self-check found violations",
    "verifier_failure": "Verifier produced contradictory or incorrect verdict",
    "valid_rejection_for_negative": "Negative case correctly rejected by codegen or verifier",
    "valid_acceptance_for_positive": "Positive case correctly accepted with parent-mediated code",
}


# ============================================================================
# Verdict Reconciliation (strict)
# ============================================================================

def reconcile_verdict(
    case_name: str,
    case_type: str,
    generate_status: str,
    generate_errors: List[str],
    verify_parsed: Dict,
    code_analysis: Dict,
    elapsed: float,
    validation_errors: List[str],
) -> Dict:
    """Build a strict verdict with failure category classification."""
    verdict = {
        "case": case_name,
        "type": case_type,
        "elapsed": elapsed,
        "validation_errors": validation_errors,
    }

    # Check adapter conversion failure first
    if validation_errors:
        verdict["generate_status"] = "skipped"
        verdict["passed"] = False
        verdict["failure_category"] = "adapter_conversion_failure"
        verdict["reason"] = f"Adapter validation failed: {validation_errors}"
        return verdict

    if case_type == "positive":
        verdict["generate_status"] = generate_status

        if generate_status == "cannot_compose":
            verdict["verify_status"] = "N/A"
            verdict["passed"] = False
            verdict["failure_category"] = "codegen_self_check_failure"
            verdict["reason"] = f"Codegen rejected: {generate_errors}"
            return verdict

        # Code was generated — check verify + static analysis
        verify_status = verify_parsed.get("status", "ok")
        checks = verify_parsed.get("checks", {})
        failed_checks = verify_parsed.get("decomposition_feedback", {}).get("failed_checks", [])
        feedback = verify_parsed.get("decomposition_feedback", {})

        verdict["verify_status"] = verify_status
        verdict["verify_checks"] = checks
        verdict["code_analysis"] = code_analysis

        violations = []

        if failed_checks:
            violations.append(f"failed_checks non-empty: {failed_checks}")
        for check_name, check_val in checks.items():
            if isinstance(check_val, dict) and check_val.get("passed") is False:
                violations.append(f"{check_name}.passed=false")
        if code_analysis.get("child_calls_missing"):
            violations.append(f"static: missing child calls {code_analysis['child_calls_missing']}")
        if code_analysis.get("uses_wrong_source"):
            violations.append("static: uses wrong dataflow source")
        if verify_status == "cannot_compose":
            violations.append(f"verifier rejected: {feedback.get('reason', '')}")

        if violations:
            verdict["passed"] = False
            verdict["failure_category"] = "codegen_self_check_failure"
            verdict["violations"] = violations
            verdict["reason"] = "; ".join(violations)
        else:
            verdict["passed"] = True
            verdict["failure_category"] = "valid_acceptance_for_positive"
            verdict["reason"] = ""

    else:  # negative
        verdict["generate_status"] = generate_status

        if generate_status == "cannot_compose":
            verdict["passed"] = True
            verdict["failure_category"] = "valid_rejection_for_negative"
            verdict["reason"] = f"Correctly rejected: {generate_errors}"
            return verdict

        # Codegen accepted negative — check if verify catches it
        verify_status = verify_parsed.get("status", "ok")
        checks = verify_parsed.get("checks", {})
        failed_checks = verify_parsed.get("decomposition_feedback", {}).get("failed_checks", [])
        feedback = verify_parsed.get("decomposition_feedback", {})

        verdict["verify_status"] = verify_status
        verdict["verify_checks"] = checks
        verdict["code_analysis"] = code_analysis

        violations = []
        if failed_checks:
            violations.append(f"failed_checks non-empty: {failed_checks}")
        for check_name, check_val in checks.items():
            if isinstance(check_val, dict) and check_val.get("passed") is False:
                violations.append(f"{check_name}.passed=false")
        if code_analysis.get("child_calls_missing"):
            violations.append(f"static: missing child calls {code_analysis['child_calls_missing']}")
        if verify_status == "cannot_compose":
            violations.append(f"verifier rejected: {feedback.get('reason', '')}")

        if violations:
            verdict["passed"] = True
            verdict["failure_category"] = "valid_rejection_for_negative"
            verdict["reason"] = f"Correctly caught: {'; '.join(violations)}"
        else:
            verdict["passed"] = False
            verdict["failure_category"] = "verifier_failure"
            verdict["reason"] = "Negative incorrectly accepted — codegen and verifier both accepted"

    return verdict


# ============================================================================
# Static Analysis
# ============================================================================

def analyze_generated_code(code: str, node: Node) -> Dict:
    """Static analysis of generated code."""
    analysis = {
        "has_sibling_calls": False,
        "calls_all_children": True,
        "child_calls_found": [],
        "child_calls_missing": [],
        "uses_wrong_source": False,
    }

    child_names = [c.name for c in (node.children or [])]

    for cname in child_names:
        pattern = rf'\b{re.escape(cname)}\s*\('
        if re.search(pattern, code):
            analysis["child_calls_found"].append(cname)
        else:
            analysis["child_calls_missing"].append(cname)
            analysis["calls_all_children"] = False

    return analysis


# ============================================================================
# Case Runner
# ============================================================================

def run_case(
    gen: DataflowAwareCodeGenerator,
    case_name: str,
    case_type: str,
    node: Node,
    output_dir: str,
    validation_errors: List[str],
) -> Dict:
    """Run a single case through the full codegen pipeline."""
    safe_name = case_name.replace("/", "_")
    case_dir = os.path.join(output_dir, f"case_{safe_name}")
    os.makedirs(case_dir, exist_ok=True)

    # Save node.json and dataflow_edges.json
    with open(os.path.join(case_dir, "node.json"), "w", encoding="utf-8") as f:
        json.dump(node.to_dict(), f, indent=2, ensure_ascii=False)
    with open(os.path.join(case_dir, "dataflow_edges.json"), "w", encoding="utf-8") as f:
        json.dump([e.to_dict() for e in node.dataflow_edges], f, indent=2, ensure_ascii=False)

    # Skip LLM call if validation failed
    if validation_errors:
        verdict = reconcile_verdict(
            case_name=case_name, case_type=case_type,
            generate_status="skipped", generate_errors=[],
            verify_parsed={}, code_analysis={},
            elapsed=0, validation_errors=validation_errors,
        )
        with open(os.path.join(case_dir, "verdict.json"), "w", encoding="utf-8") as f:
            json.dump(verdict, f, indent=2, ensure_ascii=False)
        with open(os.path.join(case_dir, "generated_code.py"), "w") as f:
            f.write("# SKIPPED — adapter validation failed\n")
        return verdict

    # Step 1: Generate
    prompt_gen = gen._build_system_prompt_for_parent() + "\n\n" + gen._build_user_prompt_for_parent(node)
    with open(os.path.join(case_dir, "prompt_generate.txt"), "w", encoding="utf-8") as f:
        f.write(prompt_gen)

    print(f"  [{case_name}] Step 1: Code generation...")
    t0 = time.time()
    code, errors = gen.generate_for_parent(node)
    elapsed = time.time() - t0

    response_gen = {
        "code": code, "errors": errors, "elapsed": elapsed,
        "last_feedback": gen.last_composition_feedback.to_dict() if gen.last_composition_feedback else None,
    }
    with open(os.path.join(case_dir, "response_generate.json"), "w", encoding="utf-8") as f:
        json.dump(response_gen, f, indent=2, ensure_ascii=False)

    generate_status = "cannot_compose" if errors else "ok"
    generate_errors = errors or []

    if generate_status == "cannot_compose":
        with open(os.path.join(case_dir, "generated_code.py"), "w") as f:
            f.write("# CANNOT_COMPOSE\n")
        with open(os.path.join(case_dir, "prompt_verify.txt"), "w") as f:
            f.write("# Skipped — codegen rejected\n")
        with open(os.path.join(case_dir, "response_verify.json"), "w") as f:
            json.dump({"status": "skipped"}, f)
    else:
        with open(os.path.join(case_dir, "generated_code.py"), "w", encoding="utf-8") as f:
            f.write(code)

        # Step 2: Verify
        prompt_ver = gen._build_system_prompt_for_parent_verify() + "\n\n" + gen._build_user_prompt_for_parent_verify(node, code)
        with open(os.path.join(case_dir, "prompt_verify.txt"), "w", encoding="utf-8") as f:
            f.write(prompt_ver)

        print(f"  [{case_name}] Step 2: Verification...")
        verify_messages = [
            {"role": "system", "content": gen._build_system_prompt_for_parent_verify()},
            {"role": "user", "content": gen._build_user_prompt_for_parent_verify(node, code)},
        ]
        try:
            verify_response = gen.api_client.chat(verify_messages, max_tokens=1024)
            verify_parsed = gen._parse_response(verify_response)
        except Exception as e:
            verify_parsed = {"status": "error", "error": str(e)}

        with open(os.path.join(case_dir, "response_verify.json"), "w", encoding="utf-8") as f:
            json.dump(verify_parsed, f, indent=2, ensure_ascii=False)

    code_for_analysis = code if generate_status == "ok" else ""
    code_analysis = analyze_generated_code(code_for_analysis, node) if code_for_analysis else {}

    verify_parsed_local = verify_parsed if generate_status == "ok" else {}
    verdict = reconcile_verdict(
        case_name=case_name, case_type=case_type,
        generate_status=generate_status, generate_errors=generate_errors,
        verify_parsed=verify_parsed_local, code_analysis=code_analysis,
        elapsed=elapsed, validation_errors=validation_errors,
    )

    with open(os.path.join(case_dir, "verdict.json"), "w", encoding="utf-8") as f:
        json.dump(verdict, f, indent=2, ensure_ascii=False)

    return verdict


# ============================================================================
# Report Generation
# ============================================================================

def generate_report(results: List[Dict], audit_data: Dict, notes_data: Dict, output_dir: str) -> Dict:
    """Generate report.md and results.json with failure category breakdown."""
    positive = [r for r in results if r["type"] == "positive"]
    negative = [r for r in results if r["type"] == "negative"]

    # Count by failure category
    category_counts = {}
    for r in results:
        cat = r.get("failure_category", "unknown")
        category_counts[cat] = category_counts.get(cat, 0) + 1

    summary = {
        "total_cases": len(results),
        "positive_cases": len(positive),
        "positive_accepted": sum(1 for r in positive if r.get("failure_category") == "valid_acceptance_for_positive"),
        "positive_rejected": sum(1 for r in positive if r.get("failure_category") != "valid_acceptance_for_positive"),
        "negative_cases": len(negative),
        "negative_correctly_rejected": sum(1 for r in negative if r.get("passed")),
        "negative_incorrectly_accepted": sum(1 for r in negative if not r.get("passed")),
        "failure_category_counts": category_counts,
    }

    results_json = {
        "experiment": "codegen_dataflow_real_stage1_adapter_patch",
        "model": os.environ.get("CHRONOS_MODEL", "deepseek-v4-flash"),
        "timestamp": datetime.now().isoformat(),
        "summary": summary,
        "trials": results,
    }

    with open(os.path.join(output_dir, "results.json"), "w", encoding="utf-8") as f:
        json.dump(results_json, f, indent=2, ensure_ascii=False)

    lines = [
        "# Codegen Dataflow Real Stage1 Adapter Patch Report",
        "",
        f"Model: `{results_json['model']}`",
        f"Timestamp: {results_json['timestamp']}",
        "",
        "## Changes from Previous Run",
        "",
        "1. Parent I/O: domain contract (input/output) instead of inferred from dataflow edges",
        "2. Parent-local dataflow: child->parent outputs are internal variables, not external outputs",
        "3. Conditional dispatch: unified `operation_result` variable, not all handler outputs required",
        "4. Internal leaf access: excluded from child signatures",
        "5. Name sanitization: all interface names validated as Python identifiers",
        "6. Comma-separated fields: split into separate edges",
        "",
        "## Failure Category Breakdown",
        "",
        "| Category | Count | Description |",
        "|----------|-------|-------------|",
    ]
    for cat, count in sorted(category_counts.items()):
        desc = FAILURE_CATEGORIES.get(cat, "Unknown")
        lines.append(f"| {cat} | {count} | {desc} |")

    lines.extend([
        "",
        "## Results",
        "",
        "| Case | Type | Category | Passed | Reason |",
        "|------|------|----------|--------|--------|",
    ])

    for r in results:
        case = r["case"]
        ctype = r["type"]
        cat = r.get("failure_category", "unknown")
        passed = "PASS" if r.get("passed") else "FAIL"
        reason = r.get("reason", "")
        if len(reason) > 80:
            reason = reason[:77] + "..."
        lines.append(f"| {case} | {ctype} | {cat} | {passed} | {reason} |")

    lines.extend(["", "## Per-Case Details", ""])
    for r in results:
        lines.append(f"### {r['case']}")
        lines.append("")
        lines.append(f"- Type: {r['type']}")
        lines.append(f"- Failure category: {r.get('failure_category', 'N/A')}")
        lines.append(f"- Generate: {r.get('generate_status', 'N/A')}")
        lines.append(f"- Verify: {r.get('verify_status', 'N/A')}")
        lines.append(f"- Passed: {r.get('passed')}")
        lines.append(f"- Reason: {r.get('reason', 'ok')}")

        ve = r.get("validation_errors", [])
        if ve:
            lines.append(f"- Validation errors: {ve}")

        ca = r.get("code_analysis", {})
        if ca:
            if ca.get("child_calls_missing"):
                lines.append(f"- Children MISSING: {ca['child_calls_missing']}")
            lines.append(f"- Children called: {ca.get('child_calls_found', [])}")

        checks = r.get("verify_checks", {})
        if checks:
            for cn, cv in checks.items():
                if isinstance(cv, dict):
                    lines.append(f"- {cn}: {'PASS' if cv.get('passed') else 'FAIL'}")

        violations = r.get("violations", [])
        if violations:
            lines.append(f"- Violations: {violations}")
        lines.append("")

    # Conversion notes
    lines.extend(["## Conversion Notes", ""])
    for case_name, notes in notes_data.items():
        lines.append(f"### {case_name}")
        lines.append("")
        for note in notes.get("conversion_notes", []):
            lines.append(f"- {note}")
        lines.append("")

    with open(os.path.join(output_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return summary


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Codegen Dataflow Real Stage1 Adapter Patch")
    parser.add_argument("--model", default="deepseek-v4-flash", help="Model name")
    args = parser.parse_args()

    os.environ["CHRONOS_MODEL"] = args.model

    output_dir = os.path.join(os.path.dirname(__file__), "output", "codegen_dataflow_real_stage1_adapter_patch", args.model)
    os.makedirs(output_dir, exist_ok=True)

    # Load previous audit data
    audit_path = os.path.join(
        os.path.dirname(__file__), "output",
        "codegen_dataflow_real_stage1", "deepseek-v4-flash", "candidate_audit.json"
    )
    with open(audit_path, "r", encoding="utf-8") as f:
        audit_data = json.load(f)

    config = Config.from_env()
    api_client = APIClient(config)
    gen = DataflowAwareCodeGenerator(config, api_client)
    adapter = RealStage1Adapter()

    print(f"Model: {args.model}")
    print(f"Output: {output_dir}")
    print(f"Rerun scope: {POSITIVE_CANDIDATES + NEGATIVE_CANDIDATES}")
    print()

    results = []
    notes_data = {}

    # Positive cases
    print("=" * 60)
    print("POSITIVE CASES")
    print("=" * 60)
    for case_name in POSITIVE_CANDIDATES:
        response_path = os.path.join(STAGE1_BASE, case_name, "0001_response.json")
        if not os.path.exists(response_path):
            print(f"  [{case_name}] SKIP — not found")
            continue

        print(f"  [{case_name}] Converting...")
        node, notes = adapter.convert(response_path, case_name)
        notes_data[case_name] = notes
        validation_errors = notes.get("validation_errors", [])

        # Save artifacts
        safe_name = case_name.replace("/", "_")
        case_dir = os.path.join(output_dir, f"case_{safe_name}")
        os.makedirs(case_dir, exist_ok=True)
        with open(os.path.join(case_dir, "original_stage1_response.json"), "w", encoding="utf-8") as f:
            with open(response_path, "r", encoding="utf-8") as src:
                f.write(src.read())
        with open(os.path.join(case_dir, "conversion_notes.json"), "w", encoding="utf-8") as f:
            json.dump(notes, f, indent=2, ensure_ascii=False)

        verdict = run_case(gen, case_name, "positive", node, output_dir, validation_errors)
        results.append(verdict)
        status = "PASS" if verdict["passed"] else "FAIL"
        print(f"  -> [{verdict.get('failure_category', 'unknown')}] {status}: {verdict.get('reason', 'ok')}")

    # Negative cases
    print()
    print("=" * 60)
    print("NEGATIVE CASES")
    print("=" * 60)
    for case_name in NEGATIVE_CANDIDATES:
        response_path = os.path.join(STAGE1_BASE, case_name, "0001_response.json")
        if not os.path.exists(response_path):
            print(f"  [{case_name}] SKIP — not found")
            continue

        print(f"  [{case_name}] Converting...")
        node, notes = adapter.convert(response_path, case_name)
        notes_data[case_name] = notes
        validation_errors = notes.get("validation_errors", [])

        safe_name = case_name.replace("/", "_")
        case_dir = os.path.join(output_dir, f"case_{safe_name}")
        os.makedirs(case_dir, exist_ok=True)
        with open(os.path.join(case_dir, "original_stage1_response.json"), "w", encoding="utf-8") as f:
            with open(response_path, "r", encoding="utf-8") as src:
                f.write(src.read())
        with open(os.path.join(case_dir, "conversion_notes.json"), "w", encoding="utf-8") as f:
            json.dump(notes, f, indent=2, ensure_ascii=False)

        verdict = run_case(gen, case_name, "negative", node, output_dir, validation_errors)
        results.append(verdict)
        status = "PASS" if verdict["passed"] else "FAIL"
        print(f"  -> [{verdict.get('failure_category', 'unknown')}] {status}: {verdict.get('reason', 'ok')}")

    # Report
    print()
    print("=" * 60)
    print("GENERATING REPORT")
    print("=" * 60)
    summary = generate_report(results, audit_data, notes_data, output_dir)

    print(f"\nSummary:")
    print(f"  Total: {summary['total_cases']}")
    print(f"  Positive accepted: {summary['positive_accepted']}/{summary['positive_cases']}")
    print(f"  Negative rejected: {summary['negative_correctly_rejected']}/{summary['negative_cases']}")
    print(f"  Failure categories: {summary['failure_category_counts']}")
    print(f"\nOutput: {output_dir}")


if __name__ == "__main__":
    main()
