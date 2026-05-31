# Exp03 Conservation Prompt Rejudge Report

Model: `deepseek-v4-flash`

## Experiment Description

This experiment tests whether adding explicit global state conservation rules to the Stage 3 prompt
fixes the resource_coverage_gap regression found in the original Exp03 v2 rejudge.

**Stage 3 prompt changes:**
- Added GLOBAL STATE CONSERVATION section as a hard requirement
- Explicit instruction: union of child global_vars must cover every parent global_vars operation
- read_write coverage clarified: requires read_write on same var, OR read + write across children
- Self-check instruction: list every parent global var and confirm coverage before returning
- build_stage3_user_prompt now presents parent global_vars as a conservation ledger table

## Results Matrix (Condition x Metric)

| Condition | Trials | hard_routing | sibling_inv | ambiguous_df | stage_drift | missing_fields | hard_dangling | ambiguous_src | gv_subset_viol | res_coverage_gap | ambig_resource | llm_review_fail | child_count_viol |
|-----------|--------|-------------|-------------|-------------|------------|---------------|--------------|--------------|----------------|-----------------|---------------|----------------|-----------------|
| single_stage_baseline | 15 | 13/15 | 5/15 | 9/15 | 0/15 | 0 | 0 | 62 | 0 | 10 | 44 | 15/15 | 3/15 |
| single_stage_notraditional | 15 | 1/15 | 1/15 | 9/15 | 0/15 | 6 | 0 | 0 | 0 | 8 | 39 | 15/15 | 0/15 |
| three_stage | 15 | 2/15 | 2/15 | 3/15 | 0/15 | 0 | 0 | 8 | 0 | 15 | 51 | 13/15 | 2/15 |

## Conservation Prompt vs Original V2 Comparison

| Condition | Metric | Original V2 | Conservation | Delta |
|-----------|--------|-------------|--------------|-------|
| single_stage_baseline | hard_routing | 12 | 13 | +1 |
| single_stage_baseline | hard_dangling | 0 | 0 | 0 |
| single_stage_baseline | resource_coverage_gap | 9 | 10 | +1 |
| single_stage_baseline | stage_drift | 0 | 0 | 0 |
| single_stage_baseline | llm_review_fail | 13 | 15 | +2 |
| single_stage_notraditional | hard_routing | 1 | 1 | 0 |
| single_stage_notraditional | hard_dangling | 0 | 0 | 0 |
| single_stage_notraditional | resource_coverage_gap | 6 | 8 | +2 |
| single_stage_notraditional | stage_drift | 0 | 0 | 0 |
| single_stage_notraditional | llm_review_fail | 14 | 15 | +1 |
| three_stage | hard_routing | 0 | 2 | +2 |
| three_stage | hard_dangling | 0 | 0 | 0 |
| three_stage | resource_coverage_gap | 11 | 15 | +4 |
| three_stage | stage_drift | 0 | 0 | 0 |
| three_stage | llm_review_fail | 11 | 13 | +2 |

## Verdict

- **FAIL**: Regressions: hard_routing 2 > 1, resource_coverage_gap 15 > 8, child_count_violation 2 > 0

**This verdict is deterministic rejudge only; actual codegen composability remains unverified.**

## Manual Check Cases

### three_stage/OrderSystem/trial_00

- **Stage1 names**: ['ParseCommand', 'PlaceOrder', 'CancelOrder', 'TrackOrder']
- **Merged names**: ['ParseCommand', 'PlaceOrder', 'CancelOrder', 'TrackOrder']
- **Stage drift**: False
- **hard_routing**: False
- **parent_mediated**: True
- **ambiguous_direct_dataflow**: False
- **router_node**: False
- **Children**: ParseCommand, PlaceOrder, CancelOrder, TrackOrder
- **Hard dangling**: 0
- **Ambiguous sources**: 0
- **Resource coverage gaps**: 2
  - inventory:read_write — No child covers inventory:read_write
    Child union for 'inventory': ['write']
  - payments:read_write — No child covers payments:read_write
    Child union for 'payments': ['write']
- **Subset violations**: 0
- **LLM review failure**: True

### three_stage/OrderSystem/trial_02

- **Stage1 names**: ['PlaceOrder', 'CancelOrder', 'TrackOrder', 'ValidateItems', 'ChargePayment', 'ReserveInventory', 'CreateOrderRecord', 'SendConfirmationNotification', 'VerifyOrderExistsAndNotShipped', 'RefundPayment', 'RestoreInventory', 'UpdateOrderStatusToCancelled', 'GetOrderStatusAndDelivery']
- **Merged names**: ['PlaceOrder', 'CancelOrder', 'TrackOrder', 'ValidateItems', 'ChargePayment', 'ReserveInventory', 'CreateOrderRecord', 'SendConfirmationNotification', 'VerifyOrderExistsAndNotShipped', 'RefundPayment', 'RestoreInventory', 'UpdateOrderStatusToCancelled', 'GetOrderStatusAndDelivery']
- **Stage drift**: False
- **hard_routing**: False
- **parent_mediated**: True
- **ambiguous_direct_dataflow**: True
- **router_node**: False
- **Children**: PlaceOrder, CancelOrder, TrackOrder, ValidateItems, ChargePayment, ReserveInventory, CreateOrderRecord, SendConfirmationNotification, VerifyOrderExistsAndNotShipped, RefundPayment, RestoreInventory, UpdateOrderStatusToCancelled, GetOrderStatusAndDelivery
- **Hard dangling**: 0
- **Ambiguous sources**: 3
- **Resource coverage gaps**: 1
  - payments:read_write — No child covers payments:read_write
    Child union for 'payments': ['write']
- **Subset violations**: 0
- **LLM review failure**: True

### three_stage/ChatApp/trial_02

- **Stage1 names**: ['ValidateAndPrepareSend', 'StoreMessage', 'UpdateUserLastSeen', 'NotifyChannelMembers', 'RetrieveMessageHistory', 'CreateChannel', 'JoinChannel']
- **Merged names**: ['ValidateAndPrepareSend', 'StoreMessage', 'UpdateUserLastSeen', 'NotifyChannelMembers', 'RetrieveMessageHistory', 'CreateChannel', 'JoinChannel']
- **Stage drift**: False
- **hard_routing**: False
- **parent_mediated**: True
- **ambiguous_direct_dataflow**: False
- **router_node**: False
- **Children**: ValidateAndPrepareSend, StoreMessage, UpdateUserLastSeen, NotifyChannelMembers, RetrieveMessageHistory, CreateChannel, JoinChannel
- **Hard dangling**: 0
- **Ambiguous sources**: 0
- **Resource coverage gaps**: 1
  - users:read — No child covers users:read
    Child union for 'users': ['write']
- **Subset violations**: 0
- **LLM review failure**: True

### three_stage/BuildSystem/trial_02

- **Stage1 names**: ['ValidateBuildRequest', 'RouteAction', 'TriggerBuild', 'CheckBuildStatus', 'ListBuildHistory', 'CancelBuild']
- **Merged names**: ['ValidateBuildRequest', 'RouteAction', 'TriggerBuild', 'CheckBuildStatus', 'ListBuildHistory', 'CancelBuild']
- **Stage drift**: False
- **hard_routing**: True
- **parent_mediated**: True
- **ambiguous_direct_dataflow**: False
- **router_node**: True
- **Router nodes**: ['RouteAction']
- **Hard routing calls**: [{'from': 'RouteAction', 'to': 'TriggerBuild'}, {'from': 'RouteAction', 'to': 'CheckBuildStatus'}, {'from': 'RouteAction', 'to': 'ListBuildHistory'}, {'from': 'RouteAction', 'to': 'CancelBuild'}]
- **Children**: ValidateBuildRequest, RouteAction, TriggerBuild, CheckBuildStatus, ListBuildHistory, CancelBuild
- **Hard dangling**: 0
- **Ambiguous sources**: 4
- **Resource coverage gaps**: 1
  - artifacts:read_write — No child covers artifacts:read_write
    Child union for 'artifacts': ['write']
- **Subset violations**: 0
- **LLM review failure**: True

### three_stage/DataPipeline/trial_00

- **Stage1 names**: ['IngestData', 'TransformData', 'ValidateData', 'ExportData']
- **Merged names**: ['IngestData', 'TransformData', 'ValidateData', 'ExportData']
- **Stage drift**: False
- **hard_routing**: False
- **parent_mediated**: True
- **ambiguous_direct_dataflow**: False
- **router_node**: False
- **Children**: IngestData, TransformData, ValidateData, ExportData
- **Hard dangling**: 0
- **Ambiguous sources**: 0
- **Resource coverage gaps**: 1
  - pipeline_log:read_write — No child covers pipeline_log:read_write
    Child union for 'pipeline_log': ['write']
- **Subset violations**: 0
- **LLM review failure**: False

### three_stage/DataPipeline/trial_02

- **Stage1 names**: ['IngestData', 'TransformData', 'ValidateData', 'ExportData']
- **Merged names**: ['IngestData', 'TransformData', 'ValidateData', 'ExportData']
- **Stage drift**: False
- **hard_routing**: False
- **parent_mediated**: True
- **ambiguous_direct_dataflow**: False
- **router_node**: False
- **Children**: IngestData, TransformData, ValidateData, ExportData
- **Hard dangling**: 0
- **Ambiguous sources**: 0
- **Resource coverage gaps**: 1
  - pipeline_log:read_write — No child covers pipeline_log:read_write
    Child union for 'pipeline_log': ['write']
- **Subset violations**: 0
- **LLM review failure**: True

## Per-Case Breakdown (three_stage)

| Case | hard_routing | stage_drift | hard_dangling | ambig_src | res_gap | subset_viol | llm_review_fail | child_count_viol |
|------|-------------|------------|--------------|----------|---------|------------|----------------|-----------------|
| OrderSystem | 0/3 | 0/3 | 0 | 3 | 3 | 0 | 3/3 | 2/3 |
| ChatApp | 0/3 | 0/3 | 0 | 0 | 3 | 0 | 2/3 | 0/3 |
| PatientPortal | 1/3 | 0/3 | 0 | 1 | 3 | 0 | 3/3 | 0/3 |
| BuildSystem | 1/3 | 0/3 | 0 | 4 | 3 | 0 | 3/3 | 0/3 |
| DataPipeline | 0/3 | 0/3 | 0 | 0 | 3 | 0 | 2/3 | 0/3 |
