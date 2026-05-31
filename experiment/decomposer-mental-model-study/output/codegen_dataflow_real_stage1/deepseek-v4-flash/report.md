# Codegen Dataflow Real Stage1 Subexperiment Report

Model: `deepseek-v4-flash`
Timestamp: 2026-05-31T12:11:54.117750

## Experiment Description

Tests dataflow-aware parent codegen using real Stage1 outputs from Exp01.
Each candidate passes a second audit before entering codegen.
Verdict reconciliation does NOT trust LLM top-level status alone.

## Phase A: Audit Summary

- Total candidates audited: 5
- PASS_POSITIVE: 3
- PASS_NEGATIVE: 2
- REJECT: 0

## Phase C: Codegen Results

| Metric | Value |
|--------|-------|
| Positive cases entered | 3 |
| Positive accepted (code generated) | 0 |
| Positive rejected (cannot_compose) | 3 |
| Positive passed (all checks) | 0 |
| Negative cases entered | 2 |
| Negative correctly rejected | 2 |
| Negative incorrectly accepted | 0 |
| Verifier contradictions | 0 |
| Generated code missing child calls | 0 |
| Generated code ignoring dataflow | 0 |

## Pass Criteria

- All positive cases accepted and generate parent-mediated code
- All negative cases rejected by codegen or verifier
- No verifier contradictions (status=ok but failed checks)

## Per-Case Results

| Case | Type | Generate | Verify | Passed | Reason |
|------|------|----------|--------|--------|--------|
| Order/trial_02 | positive | cannot_compose | N/A | FAIL | Codegen rejected: ['CANNOT_COMPOSE: cannot_satisfy_parent_output'] |
| Chat/trial_02 | positive | cannot_compose | N/A | FAIL | Codegen rejected: ['CANNOT_COMPOSE: dataflow_conformance_failure'] |
| BuildSystem/trial_00 | positive | cannot_compose | N/A | FAIL | Codegen rejected: ['CANNOT_COMPOSE: dataflow_conformance_failure'] |
| Chat/trial_00 | negative | cannot_compose | N/A | PASS | Correctly rejected: ['CANNOT_COMPOSE: missing_child_capability'] |
| Order/trial_03 | negative | cannot_compose | N/A | PASS | Correctly rejected: ['CANNOT_COMPOSE: invalid_child_boundary'] |

## Per-Case Analysis

### Order/trial_02

- Type: positive
- Generate: cannot_compose
- Verify: N/A
- Passed: False
- Reason: Codegen rejected: ['CANNOT_COMPOSE: cannot_satisfy_parent_output']

### Chat/trial_02

- Type: positive
- Generate: cannot_compose
- Verify: N/A
- Passed: False
- Reason: Codegen rejected: ['CANNOT_COMPOSE: dataflow_conformance_failure']

### BuildSystem/trial_00

- Type: positive
- Generate: cannot_compose
- Verify: N/A
- Passed: False
- Reason: Codegen rejected: ['CANNOT_COMPOSE: dataflow_conformance_failure']

### Chat/trial_00

- Type: negative
- Generate: cannot_compose
- Verify: N/A
- Passed: True
- Reason: Correctly rejected: ['CANNOT_COMPOSE: missing_child_capability']

### Order/trial_03

- Type: negative
- Generate: cannot_compose
- Verify: N/A
- Passed: True
- Reason: Correctly rejected: ['CANNOT_COMPOSE: invalid_child_boundary']

## Key Findings

### Positive Cases: All 3 Rejected by Codegen Self-Check

All 3 audited PASS_POSITIVE real Stage1 samples were rejected by the codegen's own pre-generation self-check. None reached the verify step.

**Order/trial_02** — Rejected: `cannot_satisfy_parent_output`
- Root cause: Conditional dispatch (place/cancel/track) means not all branches execute.
- The codegen generated code with `if/elif/else`, and the `else` branch returned `None`.
- Self-check flagged: `return_value_origin` — `None` literal not from child output or parent input.
- The dataflow declares all 3 handler results as parent outputs, but only one is produced per invocation.
- The codegen cannot reconcile "always produce all outputs" with "only one branch executes".

**Chat/trial_02** — Rejected: `dataflow_conformance_failure`
- Root cause: Stage1 `internal leaf access` inputs (channels, messages) were passed to codegen as child parameters.
- The adapter normalized `source: "internal leaf access"` as regular inputs, so the codegen prompt listed them as parameters to pass.
- The codegen tried to pass `channels` and `messages` from parent to children, but these are NOT parent inputs — children access them internally.
- Self-check flagged: `no_direct_access` + `dataflow_conformance_failure` — parent directly accessing data stores.

**BuildSystem/trial_00** — Rejected: `dataflow_conformance_failure`
- Root cause: FormatOutput receives aggregate inputs from multiple children (build_id from CreateBuildRecord|QueryBuildStatus|CancelBuild, etc.).
- In conditional branches where only one path executes, non-executed branch outputs are `None` literals.
- Self-check flagged: `return_value_origin` (literals) + `dataflow_conformance` (some FormatOutput inputs are None, not from declared sources).

### Negative Cases: Both Correctly Rejected

**Chat/trial_00** — Correctly rejected: `missing_child_capability`
- RouteCommand behavior says "select which child to call" — sibling orchestration.
- Codegen detected that HandleSendMessage, HandleGetHistory, etc. would not be directly called by parent.
- Failed checks: `child_coverage`, `dataflow_conformance`.

**Order/trial_03** — Correctly rejected: `invalid_child_boundary`
- PlaceOrder behavior says "Call ValidateItemsAndStock, ChargePayment, ..." — sibling orchestration.
- Codegen detected that sub-children (ValidateItemsAndStock, etc.) would not be directly called by parent.
- Suggested fix: either make sub-children direct children of parent, or treat PlaceOrder/CancelOrder as atomic.

### Verifier Contradictions: 0

No verifier contradictions occurred because no case reached the verify step (all positives rejected at codegen, all negatives rejected at codegen).

### Does This Support Another Experiment?

The results reveal two systematic gaps in the Stage1-to-codegen conversion, not in the codegen itself:

1. **Conditional dispatch output problem**: Stage1 declares all handler outputs as parent outputs, but conditional execution means only one is produced per invocation. The codegen's "always produce all outputs" rule conflicts with conditional dispatch.

2. **`internal leaf access` handling**: Stage1 marks data store inputs as "internal leaf access", but the adapter passes them as regular child parameters. The codegen then tries to pass them from parent, violating the no-direct-access rule.

Both are adapter/conversion issues, not codegen capability issues. The codegen's self-check correctly identified the problems.

## Conversion Notes

### Order/trial_02


### Chat/trial_02


### BuildSystem/trial_00

-   CheckBuildConstraint: source 'ParseAndValidateInput' references another node -> 'parent (from ParseAndValidateInput)'
-   CheckBuildConstraint: source 'ParseAndValidateInput' references another node -> 'parent (from ParseAndValidateInput)'
-   CreateBuildRecord: source 'ParseAndValidateInput' references another node -> 'parent (from ParseAndValidateInput)'
-   CreateBuildRecord: source 'ParseAndValidateInput' references another node -> 'parent (from ParseAndValidateInput)'
-   CreateBuildRecord: source 'ParseAndValidateInput' references another node -> 'parent (from ParseAndValidateInput)'
-   RunCompilation: source 'CreateBuildRecord' references another node -> 'parent (from CreateBuildRecord)'
-   RunCompilation: source 'ParseAndValidateInput' references another node -> 'parent (from ParseAndValidateInput)'
-   RunTests: source 'CreateBuildRecord' references another node -> 'parent (from CreateBuildRecord)'
-   RunTests: source 'ParseAndValidateInput' references another node -> 'parent (from ParseAndValidateInput)'
-   PackageArtifacts: source 'CreateBuildRecord' references another node -> 'parent (from CreateBuildRecord)'
-   PackageArtifacts: source 'ParseAndValidateInput' references another node -> 'parent (from ParseAndValidateInput)'
-   QueryBuildStatus: source 'ParseAndValidateInput' references another node -> 'parent (from ParseAndValidateInput)'
-   ListBuilds: source 'ParseAndValidateInput' references another node -> 'parent (from ParseAndValidateInput)'
-   ListBuilds: source 'ParseAndValidateInput' references another node -> 'parent (from ParseAndValidateInput)'
-   ListBuilds: source 'ParseAndValidateInput' references another node -> 'parent (from ParseAndValidateInput)'
-   CancelBuild: source 'ParseAndValidateInput' references another node -> 'parent (from ParseAndValidateInput)'
-   FormatOutput: source 'ParseAndValidateInput' references another node -> 'parent (from ParseAndValidateInput)'
-   FormatOutput: source 'QueryBuildStatus' references another node -> 'parent (from QueryBuildStatus)'
-   FormatOutput: source 'ListBuilds' references another node -> 'parent (from ListBuilds)'

### Chat/trial_00

-   RouteCommand: source 'ParseAndValidateInput' references another node -> 'parent (from ParseAndValidateInput)'
-   RouteCommand: source 'ParseAndValidateInput' references another node -> 'parent (from ParseAndValidateInput)'
-   HandleSendMessage: source 'ParseAndValidateInput' references another node -> 'parent (from ParseAndValidateInput)'
-   HandleSendMessage: consumer 'RouteCommand' references another node -> 'parent (mediated from RouteCommand)'
-   HandleGetHistory: source 'ParseAndValidateInput' references another node -> 'parent (from ParseAndValidateInput)'
-   HandleGetHistory: consumer 'RouteCommand' references another node -> 'parent (mediated from RouteCommand)'
-   HandleCreateChannel: source 'ParseAndValidateInput' references another node -> 'parent (from ParseAndValidateInput)'
-   HandleCreateChannel: consumer 'RouteCommand' references another node -> 'parent (mediated from RouteCommand)'
-   HandleJoinChannel: source 'ParseAndValidateInput' references another node -> 'parent (from ParseAndValidateInput)'
-   HandleJoinChannel: consumer 'RouteCommand' references another node -> 'parent (mediated from RouteCommand)'
-   FormatOutput: source 'RouteCommand' references another node -> 'parent (from RouteCommand)'

### Order/trial_03

-   PlaceOrder: source 'ParseAndValidateInput' references another node -> 'parent (from ParseAndValidateInput)'
-   CancelOrder: source 'ParseAndValidateInput' references another node -> 'parent (from ParseAndValidateInput)'
-   TrackOrder: source 'ParseAndValidateInput' references another node -> 'parent (from ParseAndValidateInput)'
-   ValidateItemsAndStock: source 'PlaceOrder' references another node -> 'parent (from PlaceOrder)'
-   ValidateItemsAndStock: consumer 'PlaceOrder' references another node -> 'parent (mediated from PlaceOrder)'
-   ChargePayment: source 'PlaceOrder' references another node -> 'parent (from PlaceOrder)'
-   ChargePayment: source 'PlaceOrder' references another node -> 'parent (from PlaceOrder)'
-   ChargePayment: consumer 'PlaceOrder' references another node -> 'parent (mediated from PlaceOrder)'
-   ReserveInventory: source 'PlaceOrder' references another node -> 'parent (from PlaceOrder)'
-   ReserveInventory: consumer 'PlaceOrder' references another node -> 'parent (mediated from PlaceOrder)'
-   CreateOrderRecord: source 'PlaceOrder' references another node -> 'parent (from PlaceOrder)'
-   CreateOrderRecord: source 'PlaceOrder' references another node -> 'parent (from PlaceOrder)'
-   CreateOrderRecord: consumer 'PlaceOrder' references another node -> 'parent (mediated from PlaceOrder)'
-   VerifyOrderNotShipped: source 'CancelOrder' references another node -> 'parent (from CancelOrder)'
-   VerifyOrderNotShipped: consumer 'CancelOrder' references another node -> 'parent (mediated from CancelOrder)'
-   RefundPayment: source 'CancelOrder' references another node -> 'parent (from CancelOrder)'
-   RefundPayment: consumer 'CancelOrder' references another node -> 'parent (mediated from CancelOrder)'
-   RestoreInventory: source 'CancelOrder' references another node -> 'parent (from CancelOrder)'
-   RestoreInventory: consumer 'CancelOrder' references another node -> 'parent (mediated from CancelOrder)'
-   UpdateOrderStatus: source 'CancelOrder' references another node -> 'parent (from CancelOrder)'
-   UpdateOrderStatus: consumer 'CancelOrder' references another node -> 'parent (mediated from CancelOrder)'
