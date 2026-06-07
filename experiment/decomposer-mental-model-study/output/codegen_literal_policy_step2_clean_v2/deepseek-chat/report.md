# Step2 Literal Policy Experiment — Clean Rerun

**Model**: `deepseek-chat`
**Timestamp**: 2026-06-06T23:25:25

## Background

The first run (2026-06-06) was downgraded to INCONCLUSIVE by Codex review.
See `hot.md` Step2 Literal Policy section and `STEP2_LITERAL_POLICY_CLEAN_RERUN_GUIDE.md`.

## Goal

Answer a cleaner question: Given decomposition fixtures that already satisfy
tree structure, signatures, parent output coverage, dataflow, and child coverage,
can a prompt-only Step2 literal policy accept PRD/branch literals while rejecting
runtime facts?

## Prompt Delta

Same as first run. VALUE ORIGIN RULES injected into Stage 3 implementation prompt
and LITERAL POLICY check added to verify prompt. Additionally, verify prompt now
includes PRD/SubPRD/acceptance context and declared literal expectations.

```text
VALUE ORIGIN RULES FOR HARDCODED LITERALS:

You may use hardcoded literals only when the value is a PRD-defined constant,
an output-schema label, or a branch-conditioned fallback value directly entailed
by the current control-flow branch.

Allowed literals:
- fixed output keys such as "success", "message", "data"
- PRD-defined status strings, error messages, enum labels, or error codes
- branch-conditioned constants such as success=False for invalid input or
  "Unsupported command" for an unsupported-command branch
- empty containers only when the PRD or branch semantics permit an empty result

Forbidden literals:
- runtime facts such as ids, timestamps, counts, prices, inventory, payment
  results, order status, user records, messages, appointments, build logs, or
  any data that depends on parent input, child output, global state, or external
  systems
- any literal that substitutes for a child output
- any literal that hides a missing child capability or failed child call

Before returning a literal, classify it:
- PRD_LITERAL: fixed by PRD or output schema
- BRANCH_LITERAL: fixed by the current branch condition
- DYNAMIC_VALUE: must come from parent input, child output, computation, or data
  access

DYNAMIC_VALUE must never be hardcoded.


5. LITERAL POLICY — Trace every literal value in every return statement and classify it:
   - PRD_LITERAL: The value is explicitly fixed by the PRD, SubPRD, or output schema
     (e.g., fixed output keys like "success", "message"; PRD-defined status strings,
     error codes, enum labels).
   - BRANCH_LITERAL: The value is a fallback constant directly entailed by the current
     control-flow branch condition (e.g., success=False when the input is invalid,
     "Unsupported command" when the command is not in the supported set, empty list when
     the PRD says "return empty if no records found" AND the code already called the
     relevant child to determine emptiness).
   - DYNAMIC_VALUE: The value depends on runtime data — parent input, child output,
     computation, global state, or external system. DYNAMIC_VALUE literals are FORBIDDEN.

   A literal is FORBIDDEN if:
   - It represents a runtime fact (id, timestamp, count, price, inventory, payment
     result, order status, user record, message, appointment, build log, etc.)
   - It substitutes for a child function's output (e.g., returning total=0.0 when
     CalculateTotal child exists and should be called)
   - It hides a missing child capability (e.g., returning an error message for a
     payment path when no payment child exists)
   - It is a DYNAMIC_VALUE masquerading as a branch literal (e.g., returning
     status="delivered" under an order-status branch when the status must come from
     a child call)

   If ANY forbidden literal is found, return status="cannot_compose" with reason
   "return_value_origin" and list the forbidden literals.
```

## Case List

| Case | Type | Mode | Target | Expected | Expected Reason |
|------|------|------|--------|----------|-----------------|
| P1 | accept | positive | literal_policy | accept |  |
| P2 | accept | positive | literal_policy | accept |  |
| P3 | accept | positive | dataflow_conformance | accept |  |
| N1 | reject | verifier_only | return_value_origin | reject | return_value_origin |
| N2a | reject | verifier_only | return_value_origin | reject | return_value_origin |
| N2b | accept | full_generate | child_coverage | accept |  |
| N3a | reject | verifier_only | return_value_origin | reject | return_value_origin |
| N3b | accept | full_generate | child_coverage | accept |  |
| N4 | reject | verifier_only | child_coverage | reject | missing_child_capability |
| N5 | reject | full_generate | tree_structure | reject | tree_structure_violation |

## Self-Audit Summary

Self-audit ran before any LLM call. Checks include parent output coverage,
dataflow field existence, literal prd_basis, and reason declarations.

| Case | Passed | Checks Failed | Uncovered Outputs |
|------|--------|---------------|-------------------|
| P1 | PASS | none | none |
| P2 | PASS | none | none |
| P3 | PASS | none | none |
| N1 | PASS | none | order_id, details |
| N2a | PASS | none | total |
| N2b | PASS | none | none |
| N3a | PASS | none | status |
| N3b | PASS | none | none |
| N4 | PASS | none | success, message |
| N5 | PASS | none | success |

## Aggregate Metrics

- **total_cases**: 10
- **migration_cases**: 9
- **literal_positive_cases**: 2
- **literal_positive_passed**: 2
- **dispatch_positive_cases**: 1
- **dispatch_positive_passed**: 0
- **full_generate_positive_control_cases**: 2
- **full_generate_positive_control_passed**: 2
- **verifier_literal_negative_cases**: 3
- **verifier_literal_negative_expected_reason**: 3
- **missing_capability_negative_cases**: 1
- **missing_capability_negative_expected_reason**: 1
- **positive_cases**: 5
- **positive_passed**: 4
- **positive_failed**: 1
- **negative_cases**: 4
- **negative_passed_expected_reason**: 4
- **negative_rejected_other_reason**: 0
- **negative_false_acceptance**: 0
- **tree_regression_cases**: 1
- **tree_regression_expected_reason**: 0
- **tree_regression_excluded_from_migration**: True
- **api_or_parse_failures**: 0
- **artifact_failures**: 0

## Grouped Verdicts

| Group | Cases | Passed / Expected-Reason | Migration Role |
|-------|-------|--------------------------|----------------|
| Literal positives | 2 | 2 passed | Must all accept |
| Parent-mediated dispatch positive | 1 | 0 passed | Must accept, but not a literal false-rejection signal |
| Full-generate positive controls | 2 | 2 passed | Must call child and cover parent output |
| Verifier-only literal negatives | 3 | 3 expected-reason rejects | Must reject with return_value_origin |
| Missing-capability negative | 1 | 1 expected-reason rejects | Must reject with missing_child_capability |
| Tree regression control | 1 | 0 expected-reason rejects | Excluded from literal migration verdict |

## Confusion Matrix

| | Accepted | Rejected (expected reason) | Rejected (other reason) |
|---|---|---|---|
| Allowed literal | 2 | 0 | N/A |
| Runtime literal | 0 | 3 | 0 |

## Per-Case Verdict Table

| Case | Expected | Passed | Category | Gen | Verify | Actual Reason | Expected Reason |
|------|----------|--------|----------|-----|--------|---------------|-----------------|
| P1 | accept | True | valid_acceptance_for_positive | ok | ok |  |  |
| P2 | accept | True | valid_acceptance_for_positive | ok | ok |  |  |
| P3 | accept | False | generation_introduced_forbidden_literal | cannot_compose | N/A | cannot_satisfy_parent_output |  |
| N1 | reject | True | valid_rejection_expected_reason | ok | cannot_compose | cannot_satisfy_parent_output | expected_reason=return_value_origin; match=failed_checks,checks.return_value_origin.passed=false |
| N2a | reject | True | valid_rejection_expected_reason | ok | cannot_compose | cannot_satisfy_parent_output | expected_reason=return_value_origin; match=failed_checks,checks.return_value_origin.passed=false |
| N2b | accept | True | valid_acceptance_for_positive | ok | N/A |  | expected_reason=; match= |
| N3a | reject | True | valid_rejection_expected_reason | ok | cannot_compose | cannot_satisfy_parent_output | expected_reason=return_value_origin; match=failed_checks,checks.return_value_origin.passed=false |
| N3b | accept | True | valid_acceptance_for_positive | ok | N/A |  | expected_reason=; match= |
| N4 | reject | True | valid_rejection_expected_reason | ok | cannot_compose | missing_child_capability | expected_reason=missing_child_capability; match=reason,semantic_missing_child |
| N5 | reject | False | false_acceptance_negative | ok | N/A |  | expected_reason=tree_structure_violation; match= |

## Reason-Match Results

- **Valid rejection with expected reason**: 4
- **Rejected by other reason**: 0
- **False acceptance**: 0

## Migration Verdict

**INCONCLUSIVE_GENERATION_FALLBACK_REGRESSION** — a no-literal parent-mediated positive did not pass; this is not counted as allowed-literal rejection.

## Claims and Limitations

This experiment uses synthetic fixtures. Real-world migration may uncover
additional value-origin ambiguities not captured here.

## Stop-Rule Compliance

- MVP not modified.
- hot.md not modified by this run (updated separately).
- No prompt tuning after results.
- Single pass.
- Output: C:\Users\Lenovo\Desktop\agent-chronos-arch\experiment\decomposer-mental-model-study\output\codegen_literal_policy_step2_clean_v2\deepseek-chat
