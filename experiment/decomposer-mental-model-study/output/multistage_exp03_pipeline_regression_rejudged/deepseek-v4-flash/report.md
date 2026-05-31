# Exp03 Rejudge Report

Model: `deepseek-v4-flash`

## Key Changes from Old Judge

1. `cannot_compose` renamed to `llm_composition_review_failure` (LLM reviewer, not real CodeGenerator)
2. Dangling inputs reclassified: `parent input`, `internal leaf access`, `global variable` are NOT hard dangling
3. Routing judge uses Exp01 criteria: `dataflow_sketch` is primary evidence, `behavior`/`purpose` confirm control calls
4. Resource coverage considers `global_vars` + `data_operations` + `requested_capabilities`

## Results Matrix (Condition x Metric)

| Condition | Trials | hard_routing | sibling_inv | ambiguous_df | hard_dangling | ambiguous_src | gv_subset_viol | res_coverage_gap | llm_review_fail | child_count_viol |
|-----------|--------|-------------|-------------|-------------|--------------|--------------|----------------|-----------------|----------------|-----------------|
| single_stage_baseline | 15 | 12/15 | 3/15 | 9/15 | 0 | 63 | 0 | 0 | 13/15 | 2/15 |
| single_stage_notraditional | 15 | 1/15 | 1/15 | 11/15 | 0 | 13 | 0 | 0 | 14/15 | 0/15 |
| three_stage | 15 | 0/15 | 0/15 | 0/15 | 0 | 0 | 0 | 0 | 11/15 | 0/15 |

## Old vs New Comparison

| Condition | Old routing | New hard_routing | Old dangling | New hard_dangling | Old cannot_compose | New llm_review_fail |
|-----------|------------|-----------------|-------------|-----------------|-------------------|-------------------|
| single_stage_baseline | 12/15 | 12/15 | 51 | 0 | 13/15 | 13/15 |
| single_stage_notraditional | 3/15 | 1/15 | 47 | 0 | 14/15 | 14/15 |
| three_stage | 3/15 | 0/15 | 75 | 0 | 11/15 | 11/15 |

## Verdict

- **PASS**: three_stage does not regress hard routing or hard deterministic failures vs notraditional.

Note: Since no real CodeGenerator `cannot_compose` is measured, the verdict is limited to deterministic structural checks.

## Manual Check Cases

### three_stage/OrderSystem/trial_00

- **hard_routing**: False
- **parent_mediated**: True
- **ambiguous_direct_dataflow**: False
- **router_node**: False
- Children: ParseCommand, PlaceOrder, CancelOrder, TrackOrder
- Hard dangling: 0
- Ambiguous sources: 0
- LLM review failure: True

### three_stage/DataPipeline/trial_00

- **hard_routing**: False
- **parent_mediated**: True
- **ambiguous_direct_dataflow**: False
- **router_node**: False
- Children: IngestData, TransformData, ValidateData, ExportData
- Hard dangling: 0
- Ambiguous sources: 0
- LLM review failure: True

## Per-Case Breakdown (three_stage)

| Case | hard_routing | hard_dangling | ambiguous_src | llm_review_fail |
|------|-------------|--------------|--------------|----------------|
| OrderSystem | 0/3 | 0 | 0 | 3/3 |
| ChatApp | 0/3 | 0 | 0 | 3/3 |
| PatientPortal | 0/3 | 0 | 0 | 2/3 |
| BuildSystem | 0/3 | 0 | 0 | 2/3 |
| DataPipeline | 0/3 | 0 | 0 | 1/3 |
