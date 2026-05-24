"""
Step 2 (Codegen Verify) mental model test — interactive, parallel.

For each of the 10 step2_cases (5 routing + 5 non-routing):
  1. Send the code for verification (same prompt as code_generator Step 2)
  2. Record the verdict (ok / cannot_compose) and which checks passed/failed
  3. Neutral follow-up questions (no leading, no right/wrong hints):
     - What specific issues did you find?
     - How would you suggest fixing the decomposition?
     - Are there any children whose names don't appear in the code?
  4. Optional: ask LLM to propose a corrected decomposition

Each case is independent and runs in parallel.
Max concurrency: CHRONOS_MAX_CONCURRENCY env var (default 4).

Env vars (CHRONOS_xxx, fallback to DEEPSEEK_xxx):
  CHRONOS_API_KEY            - API key
  CHRONOS_BASE_URL           - API base URL
  CHRONOS_MODEL              - model name
  CHRONOS_MAX_CONCURRENCY    - max parallel cases (default 4)

Usage:
    python test_step2_mind.py
    python test_step2_mind.py --case 0
    python test_step2_mind.py --cases 0,1,2
    python test_step2_mind.py --type routing      # only routing cases
    python test_step2_mind.py --type non_routing   # only non-routing cases
"""
import json
import os
import sys
import time
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "test_data"))

from openai import OpenAI
from step2_cases import get_cases, get_routing_cases, get_non_routing_cases


# -----------------------------------------------------------------------
# Config from env
# -----------------------------------------------------------------------
def _env(key, default=""):
    return os.getenv(key) or os.getenv(f"DEEPSEEK_{key.removeprefix('CHRONOS_')}") or default


BASE_URL = _env("CHRONOS_BASE_URL", "https://api.deepseek.com")
API_KEY = _env("CHRONOS_API_KEY")
MODEL = _env("CHRONOS_MODEL", "deepseek-chat")
MAX_CONCURRENCY = int(os.getenv("CHRONOS_MAX_CONCURRENCY", "4"))
TEMPERATURE = float(os.getenv("CHRONOS_TEMPERATURE", "0.3"))
MAX_TOKENS = int(os.getenv("CHRONOS_MAX_TOKENS", "4096"))

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output", "step2_mind", MODEL)


# -----------------------------------------------------------------------
# LLM caller with logging
# -----------------------------------------------------------------------
class LLMLogger:
    def __init__(self, log_dir):
        self.log_dir = log_dir
        self.call_counter = 0
        os.makedirs(log_dir, exist_ok=True)

    def chat(self, messages, max_tokens=None, system_label="", json_mode=False):
        self.call_counter += 1
        call_id = self.call_counter
        max_tokens = max_tokens or MAX_TOKENS

        req = {
            "call_id": call_id,
            "label": system_label,
            "timestamp": time.time(),
            "messages": messages,
            "max_tokens": max_tokens,
            "json_mode": json_mode,
        }
        with open(os.path.join(self.log_dir, f"{call_id:04d}_request.json"), "w", encoding="utf-8") as f:
            json.dump(req, f, indent=2, ensure_ascii=False)

        client = OpenAI(api_key=API_KEY, base_url=BASE_URL, timeout=120)
        start = time.time()
        try:
            kwargs = dict(
                model=MODEL,
                messages=messages,
                temperature=TEMPERATURE,
                max_tokens=max_tokens,
            )
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            resp = client.chat.completions.create(**kwargs)
            text = resp.choices[0].message.content
        except Exception as e:
            elapsed = time.time() - start
            err_resp = {"call_id": call_id, "elapsed": round(elapsed, 2), "error": str(e)}
            with open(os.path.join(self.log_dir, f"{call_id:04d}_response.json"), "w", encoding="utf-8") as f:
                json.dump(err_resp, f, indent=2, ensure_ascii=False)
            raise
        elapsed = time.time() - start

        resp_data = {"call_id": call_id, "elapsed": round(elapsed, 2), "response": text}
        with open(os.path.join(self.log_dir, f"{call_id:04d}_response.json"), "w", encoding="utf-8") as f:
            json.dump(resp_data, f, indent=2, ensure_ascii=False)

        return text


# -----------------------------------------------------------------------
# Prompt builders — replicate code_generator Step 2 verify prompts
# -----------------------------------------------------------------------
def build_verify_system():
    """System prompt for Step 2 VERIFY — same as code_generator._build_system_prompt_for_parent_verify()."""
    return """You are a senior code reviewer examining a code submission. The code below was written by another developer. Your job is to review whether the submitted parent function correctly uses the declared child functions — and based on that, judge whether the decomposition (the set of children) is valid.

The decomposition declares a set of child functions. The parent function is supposed to call EACH child directly. Review the code carefully: if any child's name never appears as a DIRECT call in the parent code, the decomposition is INVALID — those children are not actually composed into the parent.

REVIEW CHECKLIST — examine the code and the children list together:

1. RETURN VALUE ORIGIN — Trace every value in every return statement. Each business value must originate from a child function's output or a parent function's input. Acceptable origins include:
   - A variable assigned from a child call: rows = RunQuery(...)
   - A field extracted from a child result: user_id = transaction["user_id"]
   - A parent input parameter: amount, service, etc.
   - A computation from parent inputs: len(content), quantity * 2

   A return value that is a literal (None, True, False, a quoted string, a number, an empty list [], an empty dict {}) is a VIOLATION if it represents data that should come from a child.

2. CHILD COVERAGE — Compare the children list against the actual code. EVERY child's function name must appear as a direct call site in the parent code. If child names are missing from the code (not called by the parent), that is a FAIL — the decomposition claims these children are needed but the parent doesn't use them.

3. DIRECT ACCESS — The code must NOT directly read or write any global variable or data source. All data operations must go through child function calls.

4. NO CROSS CALLS (TREE STRUCTURE) — The decomposition is a tree, not a graph. Each child should only be called by the parent. If the code shows one child calling another child, that is a tree structure violation — siblings do not call each other.

If ANY check fails, return status="cannot_compose" with detailed feedback and list which checks failed in failed_checks.
If ALL checks pass, return status="ok" with empty checks marked passed.

Return ONLY valid JSON with this structure:
{
  "status": "ok | cannot_compose",
  "checks": {
    "return_value_origin": {"passed": true, "detail": "explanation of the verdict"},
    "child_coverage": {"passed": true, "detail": "explanation of the verdict"},
    "no_direct_access": {"passed": true, "detail": "explanation of the verdict"},
    "no_cross_calls": {"passed": true, "detail": "explanation of the verdict"}
  },
  "decomposition_feedback": {
    "reason": "missing_child_input_source | missing_child_capability | invalid_child_boundary | wrong_child_signature | cannot_satisfy_parent_output | other",
    "offending_child": "ChildName or empty",
    "failed_checks": ["return_value_origin", "child_coverage"],
    "missing_inputs": [
      {
        "child": "ChildName",
        "param": "param_name",
        "why_needed": "why this input is needed",
        "expected_source": "parent input / previous child output / new child output"
      }
    ],
    "direct_resource_accesses": [
      {
        "resource": "resource_name",
        "operation": "read",
        "why_needed": "why this resource access is needed"
      }
    ],
    "suggested_fix": "Concrete suggestion for re-decomposition",
    "requires_redecomposition": true
  }
}"""


def build_verify_user(node, code):
    """User prompt for Step 2 VERIFY — same as code_generator._build_user_prompt_for_parent_verify()."""
    lines = [
        "Review the submitted code below. This code was written by another developer.",
        "",
        "=" * 60,
        "SUBMITTED PARENT FUNCTION",
        "=" * 60,
        f"Name: {node.name}",
        f"Purpose: {node.purpose}",
        "",
        "Parent Inputs:",
    ]
    for inp in node.inputs:
        lines.append(f"  - {inp.name}: {inp.type} - {inp.description}")
    lines.append("Parent Outputs:")
    for out in node.outputs:
        lines.append(f"  - {out.name}: {out.type} - {out.description}")

    if node.data_sources:
        lines.append("")
        lines.append("Data Sources:")
        for ds in node.data_sources:
            lines.append(f"  - {ds.name} ({ds.category}, {ds.access})")

    if node.global_vars:
        lines.append("")
        lines.append("Global Variables:")
        for gv in node.global_vars:
            lines.append(f"  - {gv.op} on {gv.variable}: {gv.description}")

    lines.append("")
    lines.append("=" * 60)
    lines.append("CHILDREN - INTERFACES")
    lines.append("=" * 60)
    for child in (node.children or []):
        contract = node.children_contracts.get(child.name)
        if contract:
            lines.append("")
            lines.append(f"  [{child.name}]")
            lines.append(f"    Purpose: {contract.purpose}")
            lines.append(f"    Behavior: {contract.behavior}")
            if contract.signature:
                lines.append(f"    Signature: {contract.signature}")
            if contract.data_operations:
                lines.append(f"    Data Operations:")
                for op in contract.data_operations:
                    lines.append(f"      - {op.source_name}: {op.operation_type} ({op.description})")

    lines.append("")
    lines.append("=" * 60)
    lines.append("GENERATED CODE TO VERIFY")
    lines.append("=" * 60)
    lines.append("```python")
    lines.append(code.strip())
    lines.append("```")
    lines.append("")
    lines.append("Apply the verification checklist. Return your verdict as valid JSON.")
    return "\n".join(lines)


def build_interview_questions(node, code, verdict_data):
    """Neutral follow-up questions — no leading, no right/wrong hints."""
    status = verdict_data.get("status", "unknown")
    checks = verdict_data.get("checks", {})

    questions = [
        {
            "role": "user",
            "content": (
                "请详细说明你在验证过程中发现的具体问题。"
                "哪些检查项没有通过？为什么？"
            ),
        },
        {
            "role": "user",
            "content": (
                "请列出所有在代码中没有被父函数直接调用的子节点名称。"
                "对于每个未被调用的子节点，你认为原因是什么？"
            ),
        },
        {
            "role": "user",
            "content": (
                "如果你认为这个分解存在问题，请提出具体的修复建议。"
                "应该如何重新分解才能解决这些问题？"
            ),
        },
        {
            "role": "user",
            "content": (
                "在这个分解中，是否存在某个子节点承担了过多职责？"
                "如果有，它应该被拆分为哪些更小的子节点？"
            ),
        },
    ]
    return questions


# -----------------------------------------------------------------------
# Test runner
# -----------------------------------------------------------------------
def run_case(case_index, case):
    """Run Step 2 verify + interview for a single case."""
    node = case["node"]
    code = case["code"]
    error_type = case["error_type"]
    label = f"{case_index:02d}_{error_type}_{node.name}"
    log_dir = os.path.join(OUTPUT_DIR, "llm_log", label)
    logger = LLMLogger(log_dir)

    print(f"  [{label}] Start (Step 2 verify + interview)")

    t0 = time.time()

    # Step 1: Verify
    verify_messages = [
        {"role": "system", "content": build_verify_system()},
        {"role": "user", "content": build_verify_user(node, code)},
    ]

    verify_response = logger.chat(verify_messages, system_label="verify", json_mode=True)

    # Parse verdict
    try:
        verdict_data = json.loads(verify_response)
    except json.JSONDecodeError:
        import re
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", verify_response, re.DOTALL)
        if m:
            verdict_data = json.loads(m.group(1))
        else:
            verdict_data = {"error": "Failed to parse JSON", "raw": verify_response[:500]}

    verdict = verdict_data.get("status", "unknown")
    checks = verdict_data.get("checks", {})
    feedback = verdict_data.get("decomposition_feedback", {})

    # Step 2: Interview (multi-turn)
    interview_messages = [
        {"role": "system", "content": (
            "你是一个代码审查员。你刚刚完成了一次代码验证。"
            "接下来会有人就你的验证结果提出问题。请如实回答，说明你的判断依据和推理过程。"
        )},
        {"role": "assistant", "content": (
            f"验证结果：{verdict}\n\n"
            f"检查项：\n"
            + "\n".join(
                f"- {k}: {'通过' if v.get('passed') else '未通过'} — {v.get('detail', '')}"
                for k, v in checks.items()
            )
            + (f"\n\n反馈：{json.dumps(feedback, ensure_ascii=False, indent=2)}" if feedback else "")
        )},
    ]

    questions = build_interview_questions(node, code, verdict_data)
    interview_responses = []

    for q in questions:
        interview_messages.append(q)
        resp = logger.chat(interview_messages, system_label="interview")
        interview_messages.append({"role": "assistant", "content": resp})
        interview_responses.append({"question": q["content"], "answer": resp})

    total_elapsed = time.time() - t0

    # Build report
    report = {
        "case_index": case_index,
        "name": node.name,
        "error_type": error_type,
        "description": case["description"],
        "expected_verdict": case["expected_verdict"],
        "actual_verdict": verdict,
        "verdict_match": verdict == case["expected_verdict"],
        "elapsed": round(total_elapsed, 1),
        "llm_calls": logger.call_counter,
        "checks": {
            k: {"passed": v.get("passed"), "detail": v.get("detail", "")}
            for k, v in checks.items()
        } if isinstance(checks, dict) else {},
        "feedback": feedback,
        "interview": interview_responses,
        "tags": case["tags"],
    }

    with open(os.path.join(log_dir, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    match_str = "MATCH" if report["verdict_match"] else "MISMATCH"
    print(f"  [{label}] Done ({total_elapsed:.1f}s, {logger.call_counter} calls, "
          f"expected={case['expected_verdict']}, actual={verdict}, {match_str})")

    return report


# -----------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Step 2 mental model test")
    parser.add_argument("--case", type=int, help="Run single case by index")
    parser.add_argument("--cases", type=str, help="Run selected cases (comma-separated)")
    parser.add_argument("--type", type=str, choices=["routing", "non_routing", "all"], default="all",
                        help="routing=R1-R5, non_routing=N6-N10, all=both (default)")
    args = parser.parse_args()

    if not API_KEY:
        print("ERROR: Set CHRONOS_API_KEY (or DEEPSEEK_API_KEY)")
        return 1

    print(f"API: {BASE_URL}")
    print(f"Model: {MODEL}")
    print(f"Max concurrency: {MAX_CONCURRENCY}")

    # Select cases
    if args.type == "routing":
        all_cases = get_routing_cases()
    elif args.type == "non_routing":
        all_cases = get_non_routing_cases()
    else:
        all_cases = get_cases()

    if args.case is not None:
        # Map global index to filtered list
        full_cases = get_cases()
        target = full_cases[args.case]
        all_cases = [target]
        indices = [args.case]
    elif args.cases:
        indices = [int(x) for x in args.cases.split(",")]
        full_cases = get_cases()
        all_cases = [full_cases[i] for i in indices]
    else:
        indices = list(range(len(all_cases)))

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Re-index for parallel execution
    tasks = list(enumerate(all_cases))

    print(f"\nRunning {len(tasks)} cases with concurrency {MAX_CONCURRENCY}...\n")

    # Execute in parallel
    results = []
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as pool:
        futures = {}
        for i, case in tasks:
            actual_index = indices[i] if args.cases or args.case is not None else i
            f = pool.submit(run_case, actual_index, case)
            futures[f] = (actual_index, case["node"].name)

        for f in as_completed(futures):
            idx, name = futures[f]
            try:
                report = f.result()
                results.append(report)
            except Exception as e:
                print(f"  [ERROR] {idx:02d}_{name}: {e}")
                results.append({"case_index": idx, "name": name, "error": str(e)})

    # Save combined results
    results_path = os.path.join(OUTPUT_DIR, "results.json")
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)

    # Summary
    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")

    routing_match = 0
    routing_total = 0
    non_routing_match = 0
    non_routing_total = 0

    for r in sorted(results, key=lambda x: x.get("case_index", 0)):
        name = r.get("name", "?")
        error_type = r.get("error_type", "?")
        if "error" in r:
            print(f"  [{error_type}] {name}: ERROR — {r['error']}")
        else:
            expected = r.get("expected_verdict", "?")
            actual = r.get("actual_verdict", "?")
            match = r.get("verdict_match", False)
            match_str = "OK" if match else "FAIL"
            failed_checks = [k for k, v in r.get("checks", {}).items() if not v.get("passed")]

            print(f"  [{error_type}] {name}: expected={expected}, actual={actual} [{match_str}]"
                  + (f"  failed: {', '.join(failed_checks)}" if failed_checks else ""))

            if error_type == "routing":
                routing_total += 1
                routing_match += int(match)
            else:
                non_routing_total += 1
                non_routing_match += int(match)

    print(f"\n  Routing cases:     {routing_match}/{routing_total} matched")
    print(f"  Non-routing cases: {non_routing_match}/{non_routing_total} matched")
    print(f"  Total:             {routing_match + non_routing_match}/{routing_total + non_routing_total} matched")

    print(f"\n  Results: {results_path}")
    print(f"  LLM logs: {OUTPUT_DIR}/llm_log/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
