# Codegen Dataflow Real Stage1 Adapter Patch Report

Model: `deepseek-v4-flash`
Timestamp: 2026-05-31T12:57:41.311218

## Changes from Previous Run

1. Parent I/O: domain contract (input/output) instead of inferred from dataflow edges
2. Parent-local dataflow: child->parent outputs are internal variables, not external outputs
3. Conditional dispatch: unified `operation_result` variable, not all handler outputs required
4. Internal leaf access: excluded from child signatures
5. Name sanitization: all interface names validated as Python identifiers
6. Comma-separated fields: split into separate edges

## Failure Category Breakdown

| Category | Count | Description |
|----------|-------|-------------|
| codegen_self_check_failure | 1 | Codegen accepted but self-check found violations |
| valid_acceptance_for_positive | 1 | Positive case correctly accepted with parent-mediated code |
| valid_rejection_for_negative | 1 | Negative case correctly rejected by codegen or verifier |

## Results

| Case | Type | Category | Passed | Reason |
|------|------|----------|--------|--------|
| Order/trial_02 | positive | codegen_self_check_failure | FAIL | failed_checks non-empty: ['return_value_origin']; return_value_origin.passed=... |
| Chat/trial_02 | positive | valid_acceptance_for_positive | PASS |  |
| Chat/trial_00 | negative | valid_rejection_for_negative | PASS | Correctly rejected: ['CANNOT_COMPOSE: missing_child_capability'] |

## Per-Case Details

### Order/trial_02

- Type: positive
- Failure category: codegen_self_check_failure
- Generate: ok
- Verify: cannot_compose
- Passed: False
- Reason: failed_checks non-empty: ['return_value_origin']; return_value_origin.passed=false; verifier rejected: cannot_satisfy_parent_output
- Children called: ['ParseCommand', 'PlaceOrder', 'CancelOrder', 'TrackOrder']
- return_value_origin: FAIL
- child_coverage: PASS
- no_direct_access: PASS
- no_cross_calls: PASS
- dataflow_conformance: PASS
- Violations: ["failed_checks non-empty: ['return_value_origin']", 'return_value_origin.passed=false', 'verifier rejected: cannot_satisfy_parent_output']

### Chat/trial_02

- Type: positive
- Failure category: valid_acceptance_for_positive
- Generate: ok
- Verify: ok
- Passed: True
- Reason: 
- Children called: ['ParseAndValidateCommand', 'SendMessage', 'GetHistory', 'CreateChannel', 'JoinChannel', 'FormatResponse']
- return_value_origin: PASS
- child_coverage: PASS
- no_direct_access: PASS
- no_cross_calls: PASS
- dataflow_conformance: PASS

### Chat/trial_00

- Type: negative
- Failure category: valid_rejection_for_negative
- Generate: cannot_compose
- Verify: N/A
- Passed: True
- Reason: Correctly rejected: ['CANNOT_COMPOSE: missing_child_capability']

## Conversion Notes

### Order/trial_02

-   Detected conditional dispatch pattern
-   PlaceOrder: source 'parent input via ParseCommand' -> 'parent (mediates from parent input via ParseCommand)'
-   CancelOrder: source 'parent input via ParseCommand' -> 'parent (mediates from parent input via ParseCommand)'
-   TrackOrder: source 'parent input via ParseCommand' -> 'parent (mediates from parent input via ParseCommand)'

### Chat/trial_02

-   Detected conditional dispatch pattern
-   Detected formatter/aggregator: FormatResponse
-   SendMessage: excluded 'channels' (internal leaf access — child accesses internally)
-   SendMessage: excluded 'messages' (internal leaf access — child accesses internally)
-   GetHistory: excluded 'messages' (internal leaf access — child accesses internally)
-   CreateChannel: excluded 'channels' (internal leaf access — child accesses internally)
-   JoinChannel: excluded 'channels' (internal leaf access — child accesses internally)
-   dataflow edge: skipped non-identifier field 'operation_result or error' (from=parent, to=FormatResponse)

### Chat/trial_00

-   Detected conditional dispatch pattern
-   Detected formatter/aggregator: FormatOutput
-   RouteCommand: source 'ParseAndValidateInput' -> 'parent (mediates from ParseAndValidateInput)'
-   RouteCommand: source 'ParseAndValidateInput' -> 'parent (mediates from ParseAndValidateInput)'
-   HandleSendMessage: source 'ParseAndValidateInput' -> 'parent (mediates from ParseAndValidateInput)'
-   HandleSendMessage: excluded 'channels' (internal leaf access — child accesses internally)
-   HandleSendMessage: excluded 'messages' (internal leaf access — child accesses internally)
-   HandleSendMessage: consumer 'RouteCommand' -> 'parent (mediates to RouteCommand)'
-   HandleGetHistory: source 'ParseAndValidateInput' -> 'parent (mediates from ParseAndValidateInput)'
-   HandleGetHistory: excluded 'messages' (internal leaf access — child accesses internally)
-   HandleGetHistory: consumer 'RouteCommand' -> 'parent (mediates to RouteCommand)'
-   HandleCreateChannel: source 'ParseAndValidateInput' -> 'parent (mediates from ParseAndValidateInput)'
-   HandleCreateChannel: excluded 'channels' (internal leaf access — child accesses internally)
-   HandleCreateChannel: consumer 'RouteCommand' -> 'parent (mediates to RouteCommand)'
-   HandleJoinChannel: source 'ParseAndValidateInput' -> 'parent (mediates from ParseAndValidateInput)'
-   HandleJoinChannel: excluded 'channels' (internal leaf access — child accesses internally)
-   HandleJoinChannel: consumer 'RouteCommand' -> 'parent (mediates to RouteCommand)'
-   FormatOutput: source 'RouteCommand' -> 'parent (mediates from RouteCommand)'
