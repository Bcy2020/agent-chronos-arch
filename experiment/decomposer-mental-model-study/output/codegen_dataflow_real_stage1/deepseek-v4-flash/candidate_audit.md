# Candidate Audit Report

Timestamp: 2026-05-31T12:00:00
Source: `multistage_exp01_stage1_routing/deepseek-v4-flash/`

## Audit Criteria

For each candidate, inspect original `0001_response.json` and check:
1. Every declared child appears in dataflow
2. Every positive child has usable incoming and outgoing path
3. No dataflow edge implies direct sibling orchestration
4. Behavior/rationale does not say a child calls a sibling
5. Formatter/aggregator children have complete path
6. Can be converted to codegen-ready interface without inventing responsibilities

## Candidates

### Order/trial_02 — PASS_POSITIVE

- **Children**: ParseCommand, PlaceOrder, CancelOrder, TrackOrder
- **Dataflow**: 8 edges, all parent-mediated
- **Structure**: Clean conditional dispatch. ParseCommand validates input, parent routes to appropriate handler based on command.
- **Sibling calls**: None. All dataflow is parent<->child.
- **Formatter**: None.
- **Conversion**: Straightforward. No types in Stage1 — will default to `Any`/`dict`.

### Chat/trial_02 — PASS_POSITIVE

- **Children**: ParseAndValidateCommand, SendMessage, GetHistory, CreateChannel, JoinChannel, FormatResponse
- **Dataflow**: 12 edges, all parent-mediated
- **Structure**: Conditional dispatch with formatter. ParseAndValidateCommand validates, parent routes to handler, FormatResponse wraps output.
- **Sibling calls**: None.
- **Formatter**: FormatResponse receives `operation_result` from parent, returns `output` to parent. Complete path.
- **Note**: SendMessage/GetHistory/CreateChannel/JoinChannel have `internal leaf access` inputs (channels, messages stores). These are data_sources, not sibling calls.
- **Conversion**: Straightforward.

### BuildSystem/trial_00 — PASS_POSITIVE

- **Children**: ParseAndValidateInput, CheckBuildConstraint, CreateBuildRecord, RunCompilation, RunTests, PackageArtifacts, QueryBuildStatus, ListBuilds, CancelBuild, FormatOutput
- **Dataflow**: 20 edges, all parent-mediated
- **Structure**: Complex conditional dispatch with aggregator. Trigger workflow is sequential (ParseAndValidateInput -> CheckBuildConstraint -> CreateBuildRecord -> RunCompilation -> RunTests -> PackageArtifacts). Status/List/Cancel are independent paths.
- **Sibling calls**: None. All dataflow is parent<->child.
- **Aggregator**: FormatOutput receives inputs from multiple children via parent (action from ParseAndValidateInput, build_id from CreateBuildRecord|QueryBuildStatus|CancelBuild, etc.). Complete path.
- **Note**: FormatOutput input sources use `|` notation (e.g., `CreateBuildRecord | QueryBuildStatus | CancelBuild`) indicating aggregate input from parent mediation. This is NOT sibling calling.
- **Conversion**: Straightforward but large (10 children). No types in Stage1.

### Chat/trial_00 — PASS_NEGATIVE

- **Children**: ParseAndValidateInput, RouteCommand, HandleSendMessage, HandleGetHistory, HandleCreateChannel, HandleJoinChannel, FormatOutput
- **Dataflow**: 12 edges, but includes sibling orchestration
- **Structure**: Classic routing pattern. ParseAndValidateInput -> RouteCommand -> handlers -> RouteCommand -> FormatOutput.
- **Sibling calls**: EXPLICIT. RouteCommand behavior: "Use conditional logic to select which child to call based on parsed_command value". Dataflow shows RouteCommand->HandleSendMessage, RouteCommand->HandleGetHistory, RouteCommand->HandleCreateChannel, RouteCommand->HandleJoinChannel edges.
- **Handler outputs**: `HandleSendMessage.send_result.consumer = "RouteCommand"` — handler results go back to RouteCommand, not parent.
- **Failure mode**: RouteCommand orchestrates siblings directly. Parent never calls handlers.
- **Conversion**: Not possible without violating tree structure.

### Order/trial_03 — PASS_NEGATIVE

- **Children**: 12 nodes (ParseAndValidateInput, PlaceOrder, CancelOrder, TrackOrder, + 8 sub-children)
- **Dataflow**: 26 edges, includes sibling orchestration
- **Structure**: 2-level decomposition flattened to 1 level. PlaceOrder orchestrates ValidateItemsAndStock, ChargePayment, ReserveInventory, CreateOrderRecord. CancelOrder orchestrates VerifyOrderNotShipped, RefundPayment, RestoreInventory, UpdateOrderStatus.
- **Sibling calls**: EXPLICIT. PlaceOrder behavior: "Call ValidateItemsAndStock, ChargePayment, ReserveInventory, CreateOrderRecord in sequence". CancelOrder behavior: "Call VerifyOrderNotShipped, RefundPayment, RestoreInventory, UpdateOrderStatus in sequence". Dataflow shows PlaceOrder->sub-child and CancelOrder->sub-child edges.
- **Sub-child outputs**: `ValidateItemsAndStock.validation_result.consumer = "PlaceOrder"` — sub-child results go to PlaceOrder, not parent.
- **Failure mode**: Abstraction-level mixing. PlaceOrder/CancelOrder are intermediate orchestrators, not leaf children. If flattened, they become empty wrappers and parent must sequence 10+ children.
- **Conversion**: Not possible without either (a) keeping sibling calls or (b) inventing new responsibilities for PlaceOrder/CancelOrder.

## Summary

| Candidate | Type | Verdict | Key Issue |
|-----------|------|---------|-----------|
| Order/trial_02 | positive | PASS_POSITIVE | Clean, no issues |
| Chat/trial_02 | positive | PASS_POSITIVE | Clean, formatter path complete |
| BuildSystem/trial_00 | positive | PASS_POSITIVE | Complex but all parent-mediated |
| Chat/trial_00 | negative | PASS_NEGATIVE | RouteCommand explicitly routes to siblings |
| Order/trial_03 | negative | PASS_NEGATIVE | PlaceOrder/CancelOrder explicitly call sub-children |

3 positive + 2 negative candidates pass audit and enter codegen experiment.
