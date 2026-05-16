# CodeGenerator Formal Test Report (MVP-0.4.3)

## Overview

**Framework:** 10 test cases (3 correct + 7 wrong) × 3 runs × 2 sessions = 60 executions.
**Model:** deepseek-chat (temperature=0.0)
**Mechanism:** Two-step verification (Step 1: REVIEW+IMPLEMENT → Step 2: VERIFY self-review)
**Date:** 2026-05-16
**Files:** 4 runs saved as `formal_results_*.json` in this directory.

---

## 1. Aggregate Statistics

| Metric | Session 1 | Session 2 | **Total** |
|--------|-----------|-----------|-----------|
| Total executions | 30 | 30 | **60** |
| PASS | 27 | 29 | **56** |
| FAIL | 3 | 1 | **4** |
| **Pass rate** | 90.0% | 96.7% | **93.3%** |

| By category | Count | Pass rate |
|-------------|-------|-----------|
| Correct cases should accept (C1-C3) | 15/18 | 83.3% |
| Wrong cases should reject (W1-W7) | 41/42 | 97.6% |
| **Overall** | **56/60** | **93.3%** |

---

## 2. Generated Code Quality Analysis

### C1 — DeployApplication (Sequential Pipeline)

**Code (when passed, 3/6 runs):**
```python
def DeployApplication(build_id: str, target_env: str) -> dict:
    if not ValidateEnvironment(target_env):
        return {"status": "failed", "endpoint": ""}
    migration_result = RunMigrations(target_env)
    if migration_result.get("status") != "success":
        return {"status": "failed", "endpoint": ""}
    restart_result = RestartServices(target_env)
    if restart_result.get("status") != "success":
        return {"status": "failed", "endpoint": ""}
    verify_result = VerifyDeployment(target_env)
    if verify_result.get("status") != "success":
        return {"status": "failed", "endpoint": ""}
    return {"status": "success", "endpoint": f"https://{target_env}.example.com"}
```

**Rating: Good+.** Clean sequential orchestration with proper error handling at each step and early returns. The endpoint URL is correctly computed from the `target_env` parent input.

**Issue:** 3/6 runs falsely rejected by Step 1, which classified `f"https://{target_env}.example.com"` as a "hardcoded literal" rather than a legitimate computation from parent input. Step 2 (verifier) never falsely rejected C1.

### C2 — ProcessRefund (Conditional Branching)

**Code (passed 6/6 runs):**
```python
def ProcessRefund(transaction_id: str, amount: float) -> dict:
    transaction = GetTransaction(transaction_id)
    if not ValidateRefundEligibility(transaction, amount):
        return {"status": "failed", "reference": None}
    refund_result = IssueRefund(transaction, amount)
    user_id = transaction.get("user_id")
    NotifyUser(user_id, f"Refund of {amount} processed...")
    return {"status": "success", "reference": refund_result.get("reference")}
```

**Rating: Excellent.** Consistently correct conditional logic across all 6 runs. Clean data flow: GetTransaction → ValidateRefundEligibility → conditional branch → IssueRefund → NotifyUser. Zero false rejections.

### C3 — AnalyzeRepository (Fan-out Fan-in)

**Code (passed 6/6 runs):**
```python
def AnalyzeRepository(repo_url: str) -> dict:
    repo_path = CloneRepository(repo_url)
    line_count = CountLines(repo_path)
    dependencies = AnalyzeDependencies(repo_path)
    secrets = DetectSecrets(repo_path)
    report = GenerateReport(line_count, dependencies, secrets)
    return report
```

**Rating: Excellent+.** Near-identical code across all 6 runs. Perfect fan-out/fan-in pattern: all three parallel child outputs flow into GenerateReport, and the final result is delegated directly to the reporting child. The most consistent and reliable test case.

---

## 3. Wrong-Case Rejection Quality

| Case | Rejection Rate | Rejection Reason | Assessment |
|------|---------------|-----------------|------------|
| W1 (missing badge_id) | 6/6 | `missing_child_input_source` | Stable, precise |
| W2 (no data-reading child) | 6/6 | `invalid_child_boundary` | Stable, precise |
| W3 (missing api_key) | 6/6 | `missing_child_input_source` | Stable, precise |
| W4 (5 output fields, 1 source) | 6/6 | `cannot_satisfy_parent_output` | Stable, precise |
| W5 (orphan fields) | 5/6 | `cannot_satisfy_parent_output` | 1 missed detection |
| W6 (missing merge child) | 6/6 | `cannot_satisfy_parent_output` | Stable, precise |
| W7 (missing inventory write) | 6/6 | `missing_child_capability` | Stable, precise |

**W5 Miss Analysis:** In 1/6 runs, the LLM generated code using `datetime.now().isoformat()` for `published_at` and hardcoded `"published"` for `status`. Step 2 verifier failed to catch the hardcoded literal.

**Feedback Quality:** All rejections include detailed, actionable `composition_feedback` with `offending_child`, `missing_inputs` lists, `why_needed` explanations, and concrete `suggested_fix`. All set `requires_redecomposition: true` appropriately.

---

## 4. Failure Mode Classification

| Type | Occurrences | Rate | Impact |
|------|------------|------|--------|
| **False positive** (should accept, was rejected) | 3 | 5.0% | C1 rejected by Step 1 — LLM misclassifies parent-input computation as "hardcoded". Not systematic. |
| **False negative** (should reject, was accepted) | 1 | 1.7% | W5 — Step 2 verifier missed hardcoded `status` literal. |
| **API/parse errors** | 0 | 0.0% | None. |

### False Positive Detail: C1 endpoint

The LLM's Step 1 prompt says every return value must come from child output or parent input. The code generates `f"https://{target_env}.example.com"` where `target_env` IS a parent input, but the LLM treats the entire formatted string as a "literal." This is a rule-application inconsistency specific to Step 1 of the deepseek-chat model.

### False Negative Detail: W5

```
published_at = datetime.now().isoformat()
word_count = len(content.split())
return {"article_id": ..., "published_at": published_at, "reviewer": ..., "status": "published", "word_count": word_count}
```

- `word_count = len(content.split())` — acceptable computation from parent input `content`
- `published_at = datetime.now().isoformat()` — marginal (system call, not parent input computation)
- `status = "published"` — clear literal violation, missed by Step 2

---

## 5. Code Quality Scores

| Dimension | C1 | C2 | C3 | Average |
|-----------|----|----|----|---------|
| Correctness (child composition) | ★★★★☆ | ★★★★★ | ★★★★★ | 4.7/5 |
| Consistency across runs | ★★★☆☆ | ★★★★★ | ★★★★★ | 4.3/5 |
| Error handling | ★★★★☆ | ★★★★☆ | ★★★☆☆ | 3.7/5 |
| Code style / readability | ★★★★☆ | ★★★★★ | ★★★★★ | 4.7/5 |
| Data flow integrity | ★★★★☆ | ★★★★★ | ★★★★★ | 4.7/5 |
| **Composite** | **3.8/5** | **4.8/5** | **4.8/5** | **4.5/5** |

---

## 6. Recommendations

1. **Fix C1 false positives:** Step 1 prompt should explicitly allow context-aware string formatting (e.g., `f"https://{target_env}.example.com"`). Currently it says "every value must originate from child output or parent input," but the LLM treats the formatted string as opaque rather than tracing `target_env` back to a parent input.

2. **Fix W5-class misses:** Step 2 verifier should add a check for system calls (`datetime.now()`, `time.time()`, `os.urandom()`, etc.) in return value computation — these are neither child outputs nor parent input computations.

3. **Standardize code style:** Add prompt guidance for consistent docstrings and error handling. C3 currently has no error handling at all; C1 has good per-step error handling.

4. **Long-term: majority voting for Step 1 rejection:** C1's 3/6 false rejection rate is LLM randomness on identical prompts. Run Step 1 3 times and accept if ≥2 pass. This would eliminate the dominant failure mode.

---

## Summary

The two-step verification mechanism achieves **93.3% (56/60) overall pass rate** with **97.6% (41/42) wrong-case rejection rate**. Generated code quality is solid: correct cases produce clean, readable Python composition code, with C2 and C3 demonstrating excellent consistency and correctness. Primary remaining issues are Step 1's conditional false positives on C1 (3/6 runs) and one Step 2 missed detection on W5.
