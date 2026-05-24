# Routing Ablation - Thinking Disabled (无思考)

- Model: deepseek-v4-flash (thinking: disabled)
- Temperature: 0.3
- Trials per condition: 5
- PRDs: real pipeline English PRDs (order_real, grade_real, project_real)
- Total trials: 135

## Results Matrix

| Experiment | grade_real | order_real | project_real | Total |
|------------|--------|--------|--------|-------|
| **baseline** | 5/5 | 5/5 | 5/5 | **15/15** |
| **no_boundary** | 5/5 | 4/5 | 5/5 | **14/15** |
| **no_coordinator** | 5/5 | 5/5 | 5/5 | **15/15** |
| **no_data_sources** | 5/5 | 5/5 | 5/5 | **15/15** |
| **no_dataflow_closure** | 5/5 | 3/5 | 5/5 | **13/15** |
| **no_signature_lock** | 5/5 | 5/5 | 5/5 | **15/15** |
| **no_stop_conditions** | 5/5 | 5/5 | 5/5 | **15/15** |
| **no_subprd** | 5/5 | 2/5 | 4/5 | **11/15** |
| **specific_input** | 5/5 | 5/5 | 5/5 | **15/15** |

## Variable Impact Analysis

| Ablation | What s Removed | Rate | Delta vs Baseline |
|----------|----------------|------|-------------------|
| **baseline** | (exact real pipeline) | 100% | - |
| no_boundary | Boundary section | 93% | -7% |
| no_coordinator | Coordinator rule | 100% | +0% |
| no_data_sources | Data Sources section | 100% | +0% |
| no_dataflow_closure | DATAFLOW CLOSURE RULES | 87% | -13% |
| no_signature_lock | SIGNATURE LOCKING section | 100% | +0% |
| no_stop_conditions | SEMANTIC STOP CONDITIONS | 100% | +0% |
| no_subprd | SubPRD Context section | 73% | -27% |
| specific_input | input: Any -> command: str, order_data: dict | 100% | +0% |

## Key Findings

1. Routing is the DEFAULT behavior (baseline 100%) when thinking is disabled.
2. SubPRD Context is the only effective routing suppressor (-27%).
3. All other variables (coordinator, signature locking, stop conditions, dataflow closure,
   boundary, data sources, specific input) have negligible effect on routing.
4. The thinking-enabled experiment showed 20% baseline routing - the model reasons
   through the problem and produces clean decompositions. Thinking-disabled produces
   the raw ParseInput + RouteCommand + handler pattern consistently.
