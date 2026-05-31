# Codegen Dataflow Parent-Mediated Experiment Report

Model: `deepseek-v4-flash`
Timestamp: 2026-05-31T11:21:05.395666

## Experiment Description

Tests whether parent codegen improves when it receives structured `dataflow_edges`
and treats them as the authoritative composition contract. Positive cases are
parent-mediated decompositions that look suspicious under traditional pattern priors
but are legal under tree structure. Negative cases should be rejected.

## Aggregate Metrics

| Metric | Value |
|--------|-------|
| Total cases | 5 |
| Positive cases | 3 |
| Positive accepted (code generated) | 1 |
| Positive producing parent-mediated code | 1 |
| Positive rejected as cannot_compose | 2 |
| Negative cases | 2 |
| Negative correctly rejected | 1 |
| Negative incorrectly accepted | 1 |
| Prompt parse errors | 0 |
| Generated code ignoring declared dataflow | 0 |
| Generated code with sibling calls | 0 |
| Generated code missing child calls | 2 |

## Pass Criteria

- All positive parent-mediated cases are accepted
- Positive generated code directly calls every required child
- Positive generated code realizes the declared dataflow source for each child input
- All negative cases are rejected
- No generated code relies on a child calling a sibling

## Per-Case Results

| Case | Type | Generate | Verify | Passed | Reason |
|------|------|----------|--------|--------|--------|
| positive_a_parser_handlers | positive | ok | ok | PASS |  |
| positive_b_route_intent | positive | cannot_compose | N/A | FAIL | Codegen rejected: ['CANNOT_COMPOSE: missing_child_capabil... |
| positive_c_validate_execute | positive | cannot_compose | N/A | FAIL | Codegen rejected: ['CANNOT_COMPOSE: missing_child_capabil... |
| negative_a_hidden_sibling_call | negative | N/A | N/A | FAIL | missing_child_capability |
| negative_b_wrong_dataflow_source | negative | N/A | N/A | PASS | dataflow_conformance_failure |

## Analysis Notes

### positive_a_parser_handlers

- Generate: ok
- Verify: ok
- Children called: ['ParseCommand', 'PlaceOrder', 'CancelOrder', 'TrackOrder', 'FormatResult']
- return_value_origin: PASS
- child_coverage: PASS
- no_direct_access: PASS
- no_cross_calls: PASS
- dataflow_conformance: PASS

### positive_b_route_intent

- Generate: cannot_compose
- Verify: N/A
- Children called: []

### positive_c_validate_execute

- Generate: cannot_compose
- Verify: N/A
- Children called: []

### negative_a_hidden_sibling_call

- Expected: cannot_compose, Actual: ok
- Expected reason: hidden_sibling_call
- Actual reason: missing_child_capability
- Children MISSING (confirming rejection): ['CreateOrder', 'CancelOrder']

### negative_b_wrong_dataflow_source

- Expected: cannot_compose, Actual: cannot_compose
- Expected reason: wrong_dataflow_source
- Actual reason: dataflow_conformance_failure
