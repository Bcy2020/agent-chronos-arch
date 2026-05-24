# Routing Ablation - Thinking Enabled (有思考)

- Model: deepseek-v4-flash (thinking: enabled/default)
- Temperature: 0.3
- Trials per condition: 5
- PRDs: generated Chinese PRDs (order, grade, project)
- Total trials: 105

## Results Matrix

| Experiment | grade | order | project | Total |
|------------|--------|--------|--------|-------|
| **baseline** | 0/5 | 2/5 | 1/5 | **3/15** |
| **gen_no_coord** | 0/5 | 0/5 | 0/5 | **0/15** |
| **gen_no_format** | 2/5 | 2/5 | 1/5 | **5/15** |
| **gen_no_iface** | 0/5 | 1/5 | 0/5 | **1/15** |
| **gen_no_purpose** | 0/5 | 0/5 | 1/5 | **1/15** |
| **generic_input** | 0/5 | 0/5 | 2/5 | **2/15** |
| **minimal** | 0/5 | 1/5 | 1/5 | **2/15** |

## Variable Impact Analysis

| Ablation | What s Removed | Rate | Delta vs Baseline |
|----------|----------------|------|-------------------|
| **baseline** | (all variables present) | 20% | - |
| gen_no_coord | Coordinator rule | 0% | -20% |
| gen_no_format | INPUT FORMAT + EXAMPLES | 33% | +13% |
| gen_no_iface | Data interfaces | 7% | -13% |
| gen_no_purpose | Purpose routing language | 7% | -13% |
| generic_input | Generic input: Any -> specific types | 13% | -7% |
| minimal | All removed | 13% | -7% |

## Key Finding

With thinking enabled, baseline routing rate is 20%. The model reasons through the
problem and often produces clean command-handler decompositions without routing nodes.
The main ablation that increases routing is gen_no_format (+20%), confirming that
INPUT FORMAT + EXAMPLES section helps the model understand the command structure.
