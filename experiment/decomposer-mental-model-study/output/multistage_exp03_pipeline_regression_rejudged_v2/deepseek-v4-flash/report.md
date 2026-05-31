# Exp03 Rejudge V2 Report

Model: `deepseek-v4-flash`

## Key Changes from V1

1. **Dangling input source-of-truth**: three_stage uses `merged_node.json` `inputs` field, not `stage1.json` `semantic_inputs`
2. **Resource coverage**: uses parent globals/data_sources from `test_data/decomposer_cases.py`
3. **Child count**: uses case-specific `expected_children_range`, not generic (2, 10)
4. **Stage drift**: compares stage1 child names with merged child names
5. **Missing required fields**: checks field completeness for each condition
6. **Resource normalization**: conservative normalization (orders_db -> orders, etc.)
7. **Stricter source classification**: `global variable` and `internal leaf access` require matching resource declarations

**IMPORTANT**: This is deterministic rejudge only. No real CodeGenerator composability is measured.

## Results Matrix (Condition x Metric)

| Condition | Trials | hard_routing | sibling_inv | ambiguous_df | stage_drift | missing_fields | hard_dangling | ambiguous_src | gv_subset_viol | res_coverage_gap | ambig_resource | llm_review_fail | child_count_viol |
|-----------|--------|-------------|-------------|-------------|------------|---------------|--------------|--------------|----------------|-----------------|---------------|----------------|-----------------|
| single_stage_baseline | 15 | 12/15 | 3/15 | 9/15 | 0/15 | 0 | 0 | 48 | 0 | 9 | 44 | 13/15 | 2/15 |
| single_stage_notraditional | 15 | 1/15 | 1/15 | 11/15 | 0/15 | 0 | 0 | 7 | 0 | 6 | 47 | 14/15 | 3/15 |
| three_stage | 15 | 0/15 | 0/15 | 0/15 | 0/15 | 0 | 0 | 0 | 0 | 11 | 78 | 11/15 | 1/15 |

## Old vs V1 vs V2 Comparison

| Condition | Metric | Old Judge | V1 Judge | V2 Judge |
|-----------|--------|-----------|----------|----------|
| single_stage_baseline | routing | 12/15 | - | 12/15 |
| single_stage_baseline | hard_dangling | 51 | - | 0 |
| single_stage_baseline | resource_coverage_gap | - | - | 9 |
| single_stage_baseline | stage_drift | - | - | 0/15 |
| single_stage_baseline | llm_review_fail | 13/15 | - | 13/15 |
| single_stage_notraditional | routing | 3/15 | - | 1/15 |
| single_stage_notraditional | hard_dangling | 47 | - | 0 |
| single_stage_notraditional | resource_coverage_gap | - | - | 6 |
| single_stage_notraditional | stage_drift | - | - | 0/15 |
| single_stage_notraditional | llm_review_fail | 14/15 | - | 14/15 |
| three_stage | routing | 3/15 | - | 0/15 |
| three_stage | hard_dangling | 75 | - | 0 |
| three_stage | resource_coverage_gap | - | - | 11 |
| three_stage | stage_drift | - | - | 0/15 |
| three_stage | llm_review_fail | 11/15 | - | 11/15 |

## Verdict

- **FAIL**: Regressions: resource_coverage_gap 11 > 6

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
- **Resource coverage gaps**: 0
- **Subset violations**: 0
- **LLM review failure**: True
- **Missing fields**: 0

### three_stage/OrderSystem/trial_02

- **Stage1 names**: ['ParseCommand', 'ValidateOrderData', 'PlaceOrder', 'CancelOrder', 'TrackOrder', 'FormatResult']
- **Merged names**: ['ParseCommand', 'ValidateOrderData', 'PlaceOrder', 'CancelOrder', 'TrackOrder', 'FormatResult']
- **Stage drift**: False
- **hard_routing**: False
- **parent_mediated**: True
- **ambiguous_direct_dataflow**: False
- **router_node**: False
- **Children**: ParseCommand, ValidateOrderData, PlaceOrder, CancelOrder, TrackOrder, FormatResult
- **Hard dangling**: 0
- **Ambiguous sources**: 0
- **Resource coverage gaps**: 0
- **Subset violations**: 0
- **LLM review failure**: True
- **Missing fields**: 0

### three_stage/ChatApp/trial_02

- **Stage1 names**: ['ValidateCommand', 'SendMessage', 'GetHistory', 'CreateChannel', 'JoinChannel']
- **Merged names**: ['ValidateCommand', 'SendMessage', 'GetHistory', 'CreateChannel', 'JoinChannel']
- **Stage drift**: False
- **hard_routing**: False
- **parent_mediated**: True
- **ambiguous_direct_dataflow**: False
- **router_node**: False
- **Children**: ValidateCommand, SendMessage, GetHistory, CreateChannel, JoinChannel
- **Hard dangling**: 0
- **Ambiguous sources**: 0
- **Resource coverage gaps**: 0
- **Subset violations**: 0
- **LLM review failure**: True
- **Missing fields**: 0

### three_stage/BuildSystem/trial_02

- **Stage1 names**: ['ParseBuildRequest', 'CheckConcurrentBuild', 'CreateBuildRecord', 'ExecuteBuildSteps', 'StoreArtifacts', 'GetBuildStatus', 'ListBuilds', 'CancelBuild', 'FormatBuildResult']
- **Merged names**: ['ParseBuildRequest', 'CheckConcurrentBuild', 'CreateBuildRecord', 'ExecuteBuildSteps', 'StoreArtifacts', 'GetBuildStatus', 'ListBuilds', 'CancelBuild', 'FormatBuildResult']
- **Stage drift**: False
- **hard_routing**: False
- **parent_mediated**: True
- **ambiguous_direct_dataflow**: False
- **router_node**: False
- **Children**: ParseBuildRequest, CheckConcurrentBuild, CreateBuildRecord, ExecuteBuildSteps, StoreArtifacts, GetBuildStatus, ListBuilds, CancelBuild, FormatBuildResult
- **Hard dangling**: 0
- **Ambiguous sources**: 0
- **Resource coverage gaps**: 1
  - artifacts:read_write — No child covers artifacts:read_write
- **Subset violations**: 0
- **LLM review failure**: True
- **Missing fields**: 0

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
- **Subset violations**: 0
- **LLM review failure**: True
- **Missing fields**: 0

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
- **Subset violations**: 0
- **LLM review failure**: False
- **Missing fields**: 0

## Per-Case Breakdown (three_stage)

| Case | hard_routing | stage_drift | hard_dangling | ambig_src | res_gap | subset_viol | llm_review_fail | child_count_viol |
|------|-------------|------------|--------------|----------|---------|------------|----------------|-----------------|
| OrderSystem | 0/3 | 0/3 | 0 | 0 | 0 | 0 | 3/3 | 0/3 |
| ChatApp | 0/3 | 0/3 | 0 | 0 | 1 | 0 | 3/3 | 0/3 |
| PatientPortal | 0/3 | 0/3 | 0 | 0 | 4 | 0 | 2/3 | 0/3 |
| BuildSystem | 0/3 | 0/3 | 0 | 0 | 3 | 0 | 2/3 | 1/3 |
| DataPipeline | 0/3 | 0/3 | 0 | 0 | 3 | 0 | 1/3 | 0/3 |
