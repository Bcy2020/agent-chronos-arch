# MVP 0.4.5 — Interface Candidate Selection Fix

This MVP copies the staged decomposition and dataflow-aware codegen baseline from
`mvp-0.4.4` and fixes the capability-to-interface binding path.

Main change in this version:

- `requested_capabilities` are treated as resource operation budgets, not
  concrete `InterfacePlan.interface_id` values.
- Capability allocation resolves those budgets into candidate interfaces.
- Leaf codegen first asks the LLM to select concrete interfaces from candidates,
  then generates code with only the selected interface definitions.
- This version does not auto-expand parent permissions and does not fully solve
  defensive overreach; it only prevents exact-name interface matching failures.

Status date: 2026-06-07  
Active branch: `codex/experiment-guidance`

## Carried Forward from MVP 0.4.4 / 0.4.5 Baseline

## Position in the Architecture

Agent Chronos 2.0 is tree-centered: software construction is organized around recursive decomposition, local implementation, validation feedback, and redecomposition. This MVP keeps the 0.4.3 feedback-loop foundation and adds staged decomposition plus stronger codegen/dataflow contracts.

Core loop:

```text
PRD / Requirement
  -> PRD Converter
  -> Interface Planner
  -> Interface CodeGen
  -> TreeBuilder
  -> Decomposer Stage 1 / 2 / 3
  -> CodeGenerator
  -> Validator
  -> feedback / redecomposition
```

The important invariant remains: the parent is the only orchestrator of its direct children. Children must not implicitly coordinate siblings.

## What Changed from 0.4.3

### MVP 0.4.4: Three-Stage Decomposer

File: `decomposer.py`

The decomposer now supports staged decomposition:

| Stage | Responsibility | Main contract |
|-------|----------------|---------------|
| Stage 1 | Structure only | child name, purpose, behavior, boundary, semantic inputs/outputs, composition role |
| Stage 2 | Interfaces | inputs, outputs, signature, call inputs, internal leaf accesses, dataflow edges |
| Stage 3 | Resources and constraints | global vars, data operations, constraints, conservation notes |

New orchestration methods:

- `decompose_staged()` for first-time staged decomposition.
- `decompose_staged_with_history()` for redecomposition with prior failure context.
- `_merge_staged_outputs()` to merge Stage 1/2/3 output into Node children.
- `_build_children_from_parsed()` as shared child construction logic.
- `_format_previous_errors()` to feed previous validation failures into redecomposition.

Stage 1 also has a child-count retry loop: if the model exceeds the child limit, the system retries Stage 1 before entering Stage 2/3.

### MVP 0.4.4: TreeBuilder Integration

File: `tree_builder.py`

TreeBuilder now routes decomposition through the staged path:

- Initial decomposition uses `decompose_staged()`.
- Redecomposition uses `decompose_staged_with_history()`.
- Failure context is converted into `previous_errors` via `_build_decompose_context_from_failure()`.
- `interface_plan` is passed through the constructor instead of a setter.

### MVP 0.4.5: Dataflow-Aware Codegen

File: `code_generator.py`

Codegen now treats structured `dataflow_edges` as authoritative composition evidence.

Main prompt changes:

- Stage 1 review is reframed as tree-structure review.
- Sibling independence and parent-as-orchestrator are explicit constraints.
- Dataflow Edge Conformance is added as a required codegen/verify step.
- Natural-language rationale is downgraded to supplementary evidence.
- Child input/output source and consumer metadata is rendered into the prompt.
- New failure categories include `tree_structure_violation` and `dataflow_conformance_failure`.

### MVP 0.4.5: Validator Updates

File: `validator.py`

Validator changes include:

- Conservation check is now correctness-oriented: child operations must be within parent authority; child union no longer has to fully cover parent operations.
- Parent operation scope is checked: a child must not request broader access than its parent.
- Obsolete non-leaf global state checks were removed.
- `validate_no_direct_resource_access()` was rewritten to be scope-aware and statement-order-sensitive.

The direct-resource validator now distinguishes local variables from actual parent resource access. For example, `orders = ListOrders(...)` is allowed as a child-return local binding, while unbound `orders`, `orders[order_id]`, or passing unbound `orders` to a child remains invalid.

## Current Validation Evidence

### Unit-Level Evidence

| Area | Test file | Result |
|------|-----------|--------|
| staged decomposer merge/prompt/integration | `tests/test_decomposer_staged.py` | 20 tests pass in the recorded migration |
| direct resource access validator | `tests/test_direct_resource_access_validator.py` | included in 23-test validator pass |
| provenance validator regression | `tests/test_provenance_validator.py` | included in 23-test validator pass |

### PRD Full Pipeline Evidence

`tests/test_prd_full_pipeline.py` exercises:

```text
PRD -> InterfacePlan -> interface code -> tree decomposition -> codegen -> validation
```

Recorded evidence from `hot.md`:

- `DIRECT_RESOURCE_ACCESS_PARENT` false positives are fixed.
- The pipeline can reach `max_depth=5`.
- Many nodes now generate code successfully.
- A later `grade_prd.md` run produced 144 total nodes, 141 nodes with generated code, and no reproduced direct-resource-access false positive.

Evidence paths called out in `hot.md`:

- `output/prd_pipeline_test/grade_prd_pipeline.log`
- `output/prd_pipeline_test/grade_prd_decomposition_tree.json`

These are evidence outputs, not temporary scratch outputs.

## Current Known Problems

### 1. Capability Allocation Name Matching

Some children request capabilities such as `products.read`, while the InterfacePlan may use a different naming shape such as combined or generated interface names. Current exact matching can reject semantically valid requests.

Observed failures include:

- `QueryProductDetails`
- `LookupPrices`

Likely direction:

- Normalize InterfacePlan capability names.
- Add prefix/semantic matching only after defining the invariant.
- Avoid one-off aliases that encode a single failing case.

### 2. Conservation Parent Permission Propagation

Some parent nodes declare only `write` while children require `read + write`. This appears in flows such as stock deduction, where reading current state before writing is legitimate.

Observed failure:

- `DeductStock`: parent has `write` on products, child needs `read + write`.

Likely direction:

- Define monotonic permission completion: child-required access may promote parent access when still within the root/interface authority.
- Keep the rule deterministic: children must not exceed the effective ancestor authority.

### 3. Global Var Auto-Propagation

Some children need global variables that the parent did not explicitly inherit.

Observed failure:

- `GenerateOrderId`: child declares a counter, parent has no corresponding `global_vars`.

Likely direction:

- Add a deterministic propagation pass from child declarations to parent resource summaries.
- Record provenance so propagated globals are not mistaken for model hallucinations.

### 4. Child Composition Non-Closure

The latest PRD review exposed a structural issue distinct from capability and conservation.

Observed path:

```text
Grade_prd / CalculateStudentAverage / ComputeWeightedAverage / ComputeTotalPossible / LookupTotalPoints
```

Invalid shape:

```text
LookupTotalPoints -> { LookupSingleTotal, IterateAndCollect }
```

`IterateAndCollect` is a sibling of `LookupSingleTotal`, but its purpose/behavior/dataflow says it calls `LookupSingleTotal`. This is not parent-mediated composition. It is an implicit sibling-to-sibling orchestration cycle.

Current validator only reports the symptom:

```text
UNUSED_CHILD: LookupSingleTotal
```

Needed structural diagnosis:

```text
NON_PARENT_MEDIATED_CHILD_COMPOSITION
```

Valid repair options:

- Parent owns the loop and directly calls `LookupSingleTotal`.
- Collapse the wrapper and atomic sibling into one child such as `LookupAllTotals`.

### 5. Verify Schema Order Is Not Fully Migrated

The Step2 schema-order experiment showed that LLM verifier JSON consistency improves when reasoning fields come before verdict fields:

- checks should generate `detail` before `passed`.
- top-level final status should be generated after checks and feedback.

Current MVP still carries schema-order risk where verdict-like fields may appear before full reasoning. This is a prompt-level migration candidate, but the experiment sample size is small.

### 6. Literal Fallback Policy Is Inconclusive

The clean_v2 literal policy experiment separated literal positives/negatives better, but it also exposed unrelated generation fallback and tree-review failures.

Current verdict:

```text
INCONCLUSIVE_GENERATION_FALLBACK_REGRESSION
```

Do not use the literal policy experiment alone as migration evidence.

## What Should Stay Versioned

The following are formal implementation or evidence artifacts and should remain commit candidates unless later reviewed otherwise:

- `tests/test_decomposer_staged.py`
- `tests/test_direct_resource_access_validator.py`
- `tests/test_full_pipeline.py`
- `tests/test_prd_full_pipeline.py`
- `output/prd_pipeline_test/grade_prd_pipeline.log`
- `output/prd_pipeline_test/grade_prd_decomposition_tree.json`
- experiment scripts under `experiment/decomposer-mental-model-study/`
- experiment output directories that are cited in `hot.md` or the experiment trajectory report

Temporary generated run output such as `output/nodes/` and ad-hoc `output/pipeline_test/` should not be treated as formal evidence by default.

## Usage

From this directory:

```bash
python main.py --input test_prd.md --output output_test
```

For PRD full-pipeline testing:

```bash
python tests/test_prd_full_pipeline.py
```

For unit-level staged decomposer and validator checks:

```bash
python -m pytest tests/test_decomposer_staged.py tests/test_direct_resource_access_validator.py tests/test_provenance_validator.py -q
```

For the real LLM leaf interface selection smoke test:

```bash
python tests/test_leaf_interface_selection_real_llm.py
```

## Current Next Work

1. Add deterministic enforcement for parent-mediated child composition.
2. Add a `LookupTotalPoints` regression fixture.
3. Validate MVP 0.4.5 interface selection in full PRD real LLM runs.
4. Define parent permission and global var propagation rules.
5. Decide whether to migrate detail-first verify schema ordering.
