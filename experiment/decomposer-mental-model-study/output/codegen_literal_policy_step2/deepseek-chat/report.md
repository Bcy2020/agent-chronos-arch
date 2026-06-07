# Step2 Literal Policy Experiment Report

**Model**: `deepseek-v4-flash`
**Timestamp**: 2026-06-06T20:30:32.817255

## Goal and Scope

Test whether a prompt-only change to Step2 parent codegen can distinguish
allowed PRD/branch-conditioned literals from forbidden hardcoded runtime facts.

## Exact Prompt Delta

The following VALUE ORIGIN RULES were injected into Stage 3 of the implementation prompt
and a LITERAL POLICY check was added to the verify prompt:

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

## Full Case List

| Case | Type | Target Invariant | Expected |
|------|------|-----------------|----------|
| P1 | Positive | literal_policy | accept |
| P2 | Positive | literal_policy | accept |
| P3 | Positive | dataflow_conformance | accept |
| N1 | Negative | runtime_fact_hardcode | reject |
| N2 | Negative | runtime_fact_hardcode | reject |
| N3 | Negative | runtime_fact_hardcode | reject |
| N4 | Negative | child_coverage | reject |
| N5 | Negative | tree_structure | reject |

## Self-Audit Summary

Self-audit was run before any LLM call for every case.
If a positive case failed audit, the LLM call was skipped.

| Case | Passed | Checks Failed |
|------|--------|---------------|
| P1 | PASS | none |
| P2 | PASS | none |
| P3 | PASS | none |
| N1 | PASS | none |
| N2 | PASS | none |
| N3 | PASS | none |
| N4 | PASS | none |
| N5 | PASS | none |

## Aggregate Metrics

| Metric | Value |
|--------|-------|
| Total cases | 8 |
| Positive cases | 3 |
| Positive passed | 1 |
| Positive failed | 2 |
| Negative cases | 5 |
| Negative passed (correctly rejected) | 5 |
| Negative failed (incorrectly accepted) | 0 |

## Literal-Policy Confusion Matrix

| | Accepted | Rejected |
|---|---|---|
| Allowed literal | 1 | 2 |
| Runtime literal | 0 | 5 |

## Per-Case Verdict Table

| Case | Expected | Passed | Category | Generate | Verify | Reason |
|------|----------|--------|----------|----------|--------|--------|
| P1 | accept | FAIL | false_rejection_allowed_literal | ok | cannot_compose | cannot_satisfy_parent_output |
| P2 | accept | FAIL | false_rejection_allowed_literal | generate | cannot_compose | CANNOT_COMPOSE: cannot_satisfy_parent_output |
| P3 | accept | PASS | valid_acceptance_for_positive | ok | ok |  |
| N1 | reject | PASS | valid_rejection_for_negative | ok | cannot_compose | cannot_satisfy_parent_output |
| N2 | reject | PASS | valid_rejection_for_negative | ok | cannot_compose | missing_child_capability |
| N3 | reject | PASS | valid_rejection_for_negative | ok | cannot_compose | missing_child_capability |
| N4 | reject | PASS | valid_rejection_for_negative | ok | cannot_compose | missing_child_capability |
| N5 | reject | PASS | valid_rejection_for_negative | cannot_compose | N/A | CANNOT_COMPOSE: missing_child_capability |

## Static Analysis Summary

### P1

- Defines parent function: True
- Children called: ['ParseInput', 'PlaceOrder', 'CancelOrder', 'TrackOrder']
- Allowed literals detected: ['Unsupported command', 'success']
- Has branch logic: True

### P3

- Defines parent function: True
- Children called: ['ParseInput', 'PlaceOrder', 'CancelOrder', 'TrackOrder', 'FormatResult']
- Allowed literals detected: ['formatted']
- Has branch logic: True

### N1

- Defines parent function: True
- Children called: ['ParseInput', 'ProcessPayment']
- Forbidden literals detected: ['ORDER-001']
- Allowed literals detected: ['success']
- Has branch logic: False

### N2

- Defines parent function: True
- Children called: ['ParseInput']
- Children MISSING: ['CalculateTotal']
- Forbidden literals detected: ['0.0']
- Has branch logic: False

### N3

- Defines parent function: True
- Children called: ['ParseRequest']
- Children MISSING: ['FetchOrderStatus']
- Forbidden literals detected: ['delivered']
- Allowed literals detected: ['status']
- Has branch logic: False

### N4

- Defines parent function: True
- Children called: ['ParseInput']
- Forbidden literals detected: ['Payment failed']
- Allowed literals detected: ['Payment failed']
- Has branch logic: False

### N5

- Defines parent function: False
- Children called: []
- Children MISSING: ['PlaceOrder', 'CancelOrder', 'RouteCommand']
- Has branch logic: False

## Interpretation

**Result: PARTIAL PASS / FAIL** — see details below.


## Claims and Limitations

Prompt-level value-origin discipline is a pragmatic next-MVP migration candidate.
Schema-level output value provenance remains a possible future improvement if
real runs expose more ambiguous value-origin failures.

## Compliance Statements

- **MVP not modified**: No files under `mvp/` were touched.
- **hot.md not modified**: `hot.md` was not modified.
- **No prompt tuning after results**: All cases were run exactly once with the same prompt patch.
- **Output directory**: `experiment/decomposer-mental-model-study/output/codegen_literal_policy_step2/<model>/`
