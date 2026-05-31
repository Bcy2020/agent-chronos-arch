# Exp03: Shallow Pipeline Regression Report

Model: `deepseek-v4-flash`
Cases: OrderSystem, ChatApp, PatientPortal, BuildSystem, DataPipeline
Trials per condition per case: 3
Conditions: single_stage_baseline, single_stage_notraditional, three_stage

## Results Matrix (Condition x Metric)

| Condition | Trials | routing | child_count_violation | missing_field | dangling_input | global_var_subset_violation | global_var_union_gap | cannot_compose | parse_error |
|-----------|--------|---|---|---|---|---|---|---|---|
| single_stage_baseline | 15 | 14/15 | 3/15 | 0/15 | 10/15 | 0/15 | 6/15 | 15/15 | 0/15 |
| single_stage_notraditional | 15 | 4/15 | 0/15 | 1/15 | 9/15 | 0/15 | 6/15 | 15/15 | 0/15 |
| three_stage | 15 | 3/15 | 2/15 | 0/15 | 14/15 | 0/15 | 11/15 | 13/15 | 0/15 |

## Per-Case Breakdown

### BuildSystem

| Condition | Routing | CC Viol | Missing | Dangling | GV Subset | GV Gap | Compose |
|-----------|---------|---------|---------|----------|-----------|--------|---------|
| single_stage_baseline | 3/3 | 1/3 | 0/3 | 3/3 | 0/3 | 1/3 | 3/3 |
| single_stage_notraditional | 1/3 | 0/3 | 0/3 | 2/3 | 0/3 | 1/3 | 3/3 |
| three_stage | 1/3 | 0/3 | 0/3 | 2/3 | 0/3 | 3/3 | 3/3 |

### ChatApp

| Condition | Routing | CC Viol | Missing | Dangling | GV Subset | GV Gap | Compose |
|-----------|---------|---------|---------|----------|-----------|--------|---------|
| single_stage_baseline | 3/3 | 0/3 | 0/3 | 1/3 | 0/3 | 0/3 | 3/3 |
| single_stage_notraditional | 0/3 | 0/3 | 0/3 | 3/3 | 0/3 | 0/3 | 3/3 |
| three_stage | 0/3 | 0/3 | 0/3 | 3/3 | 0/3 | 0/3 | 2/3 |

### DataPipeline

| Condition | Routing | CC Viol | Missing | Dangling | GV Subset | GV Gap | Compose |
|-----------|---------|---------|---------|----------|-----------|--------|---------|
| single_stage_baseline | 2/3 | 0/3 | 0/3 | 3/3 | 0/3 | 2/3 | 3/3 |
| single_stage_notraditional | 0/3 | 0/3 | 0/3 | 1/3 | 0/3 | 2/3 | 3/3 |
| three_stage | 0/3 | 0/3 | 0/3 | 3/3 | 0/3 | 3/3 | 2/3 |

### OrderSystem

| Condition | Routing | CC Viol | Missing | Dangling | GV Subset | GV Gap | Compose |
|-----------|---------|---------|---------|----------|-----------|--------|---------|
| single_stage_baseline | 3/3 | 2/3 | 0/3 | 2/3 | 0/3 | 0/3 | 3/3 |
| single_stage_notraditional | 3/3 | 0/3 | 1/3 | 1/3 | 0/3 | 0/3 | 3/3 |
| three_stage | 2/3 | 2/3 | 0/3 | 3/3 | 0/3 | 2/3 | 3/3 |

### PatientPortal

| Condition | Routing | CC Viol | Missing | Dangling | GV Subset | GV Gap | Compose |
|-----------|---------|---------|---------|----------|-----------|--------|---------|
| single_stage_baseline | 3/3 | 0/3 | 0/3 | 1/3 | 0/3 | 3/3 | 3/3 |
| single_stage_notraditional | 0/3 | 0/3 | 0/3 | 2/3 | 0/3 | 3/3 | 3/3 |
| three_stage | 0/3 | 0/3 | 0/3 | 3/3 | 0/3 | 3/3 | 3/3 |

## Top Failure Reasons

- cannot_compose: 43 occurrences
- dangling_inputs: 33 occurrences
- global_var_union_gap: 23 occurrences
- routing: 21 occurrences
- child_count_violation: 5 occurrences
- missing_required_fields: 1 occurrences

## Representative Failures

- **single_stage_baseline/BuildSystem/trial_00**: routing=True, compose=True, gv_gap=0, dangling=10
- **single_stage_baseline/BuildSystem/trial_01**: routing=True, compose=True, gv_gap=0, dangling=6
- **single_stage_baseline/BuildSystem/trial_02**: routing=True, compose=True, gv_gap=1, dangling=10
- **single_stage_baseline/ChatApp/trial_00**: routing=True, compose=True, gv_gap=0, dangling=6
- **single_stage_baseline/ChatApp/trial_01**: routing=True, compose=True, gv_gap=0, dangling=0

## Verdict

- Baseline routing: 14/15
- Notraditional routing: 4/15
- Three-stage routing: 3/15

- GV union gap: notraditional=8, three_stage=12
- Dangling inputs: notraditional=33, three_stage=81
- Cannot compose: notraditional=15, three_stage=13

- **Verdict: PASS**
