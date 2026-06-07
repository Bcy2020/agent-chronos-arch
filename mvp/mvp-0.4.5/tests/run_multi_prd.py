"""
Multi-PRD test runner: runs test_decomposition_flow with each PRD 5 times.
Records Step 2 CANNOT_COMPOSE rejection details for analysis.
"""
import subprocess
import sys
import os
import json
import time
import shutil

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
PRD_DIR = os.path.join(TEST_DIR, "..", "..", "..", "benchmark", "test_cases", "medium")

PRDS = ["order_prd.md", "grade_prd.md", "project_prd.md"]
TOTAL_RUNS = 5
BASE_OUTPUT_DIR = os.path.join(TEST_DIR, "output", "multi_prd_runs")


def get_step2_rejections(llm_log_dir: str) -> list:
    """Extract Step 2 VERIFY rejection details from LLM logs."""
    rejections = []
    if not os.path.exists(llm_log_dir):
        return rejections

    files = sorted(os.listdir(llm_log_dir))
    for fname in files:
        if not fname.endswith("_response.json"):
            continue
        fpath = os.path.join(llm_log_dir, fname)
        try:
            with open(fpath, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, KeyError):
            continue

        resp_text = data.get("response", "")
        try:
            resp = json.loads(resp_text)
        except json.JSONDecodeError:
            continue

        # Only Step 2 VERIFY responses have a "checks" field
        checks = resp.get("checks")
        if checks is None:
            continue
        status = resp.get("status", "ok")
        if status != "cannot_compose":
            continue

        fb = resp.get("decomposition_feedback", {})
        call_id = data.get("call_id", 0)
        rejections.append({
            "call_id": call_id,
            "reason": fb.get("reason", ""),
            "failed_checks": fb.get("failed_checks", []),
            "suggested_fix": fb.get("suggested_fix", ""),
            "checks": {k: {"passed": v.get("passed"), "detail": v.get("detail")}
                       for k, v in checks.items()},
        })
    return rejections


def run_test(prd_name: str, run_index: int) -> dict:
    prd_path = os.path.join(PRD_DIR, prd_name)
    output_dir = os.path.join(BASE_OUTPUT_DIR, f"run_{run_index:02d}")

    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)

    env = os.environ.copy()
    env["TEST_PRD_PATH"] = prd_path
    env["TEST_OUTPUT_DIR"] = output_dir

    start = time.time()
    proc = subprocess.run(
        [sys.executable, os.path.join(TEST_DIR, "test_decomposition_flow.py")],
        cwd=os.path.dirname(TEST_DIR),
        capture_output=True, text=True, timeout=300,
        env=env
    )
    elapsed = time.time() - start

    result = {
        "prd": prd_name,
        "run": run_index,
        "elapsed": round(elapsed, 1),
        "exit_code": proc.returncode,
        "success": None,
        "total_attempts": 0,
        "attempts": [],
        "cannot_compose_count": 0,
        "rejections": [],
    }

    # Read result.json
    result_path = os.path.join(output_dir, "result.json")
    if os.path.exists(result_path):
        with open(result_path, encoding="utf-8") as f:
            data = json.load(f)
            result["success"] = data.get("success")
            result["total_attempts"] = data.get("attempt_count", 0)
            result["cannot_compose_count"] = data.get("cannot_compose_count", 0)
            result["attempts"] = [
                {"stage": a["stage"], "decision": a["decision"]}
                for a in data.get("attempts", [])
            ]

    # Get Step 2 rejection details
    llm_log_dir = os.path.join(output_dir, "llm_log")
    result["rejections"] = get_step2_rejections(llm_log_dir)

    status = "PASS" if result["success"] else "FAIL"
    print(f"  [{status}] {prd_name}: {result['elapsed']}s, "
          f"attempts={result['total_attempts']}, "
          f"CC_rejections={result['cannot_compose_count']}")

    # Print rejection details
    for rej in result["rejections"]:
        print(f"    Step 2 rejection (call #{rej['call_id']}):")
        print(f"      failed_checks: {rej['failed_checks']}")
        print(f"      reason: {rej['reason']}")
        print(f"      suggested_fix: {rej['suggested_fix'][:200]}")

    return result


def main():
    os.makedirs(BASE_OUTPUT_DIR, exist_ok=True)

    schedule = []
    for i in range(TOTAL_RUNS):
        schedule.append(PRDS[i % len(PRDS)])

    print(f"Running {len(schedule)} tests, rotating through PRDs:")
    for i, prd in enumerate(schedule):
        print(f"  Run {i+1}: {prd}")
    print()

    results = []
    for i, prd in enumerate(schedule):
        print(f"--- Run {i+1}/{len(schedule)}: {prd} ---")
        result = run_test(prd, i)
        results.append(result)
        print()

    # Summary
    print("=" * 60)
    print("  FINAL SUMMARY")
    print("=" * 60)
    passed = sum(1 for r in results if r["success"])
    total = len(results)
    print(f"  Passed: {passed}/{total}")
    print()

    for r in results:
        cc_detail = ""
        if r["rejections"]:
            reasons = "; ".join(f"call#{rej['call_id']}:{rej['failed_checks']}"
                               for rej in r["rejections"])
            cc_detail = f" CC_reject={reasons}"
        print(f"  {r['prd']:20s} run {r['run']:2d}: "
              f"{'PASS' if r['success'] else 'FAIL':4s} "
              f"{r['elapsed']:5.1f}s  "
              f"attempts={r['total_attempts']}{cc_detail}")

    print()
    if passed == total:
        print("  ALL TESTS PASSED")
        return 0
    else:
        print(f"  {total - passed} TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
