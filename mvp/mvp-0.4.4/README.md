# MVP-0.4.4 — Architecture Feedback Loop: Leaf Rejection & Parent Redecomposition

## What's New

MVP-0.4.4 completes the **architecture feedback loop** by closing the gap between leaf-level capability rejection and parent-level redecomposition. The full chain is now operational:

1. **Leaf actively rejects** at code generation time when granted capabilities are insufficient (`status: "insufficient_capabilities"`)
2. **Leaf diagnoses** the gap via `composition_feedback.missing_interfaces` (which interfaces are missing and why)
3. **Parent decides** based on resource ownership:
   - **Owns the resource** (resource name in `global_vars`) → clears children, redecomposes with failure context
   - **Missing the resource** (resource not in `global_vars`) → marks `needs_human_intervention`, propagates upward
4. **Resource name normalization** (`_interface_prefix_map`) eliminates LLM singular/plural inconsistencies between resource IDs and interface prefixes

This version also fixes two propagation gaps inherited from MVP-0.4.3:
- **Fix A**: Decomposer prompt key mismatch (`error_type` → `error_types`; removed dead `unused_children`/`actual_calls` branches)
- **Fix B**: Child validation failure status now propagates upward to parent

## Files Changed from 0.4.3

| File | Change |
|------|--------|
| `code_generator.py` | Leaf prompt split into TWO STAGES (capability coverage review → implement); outputs `status: "insufficient_capabilities"` + `capability_gap_feedback`; `generate_with_retry` short-circuits on INSUFFICIENT_CAPABILITIES |
| `tree_builder.py` | `_build_tree_recursive()` rewritten as `while True` loop with redecomposition counter; `_build_interface_prefix_map()` for resource name normalization; `_process_parent_node()` condition updated to pass `composition_feedback` to decomposer |
| `decomposer.py` | **Fix A**: `error_type` → `error_types`; removed dead keys |
| `README.md` | New version documentation |

## Key Concepts

### Leaf Rejection Flow (TWO STAGES)

```
CodeGenerator.generate_for_leaf(node)
  │
  ├── STAGE 1: Capability Coverage Review
  │   Prompt: "Review the granted_capabilities. Do you have ALL interfaces needed?"
  │   LLM output: status: "ok" | "insufficient_capabilities"
  │   If insufficient → sets composition_feedback.missing_interfaces + returns error
  │
  └── STAGE 2: Implement (only if STAGE 1 passed)
      Prompt: "Implement the function using only the granted interfaces"
      LLM output: status: "ok" with code
```

### Parent Decision Flow

```
_build_tree_recursive(parent)
  → for each child: _build_tree_recursive(child)
    → leaf rejects: INSUFFICIENT_CAPABILITIES, composition_feedback set

  → parent inspects missing_interfaces:
    ├── Resource IN parent.global_vars:
    │     → PARENT_HAS_RESOURCE_BUT_MISSING_ALLOCATION
    │     → Save snapshot, clear children, continue loop
    │     → Decomposer receives failure context → produces better decomposition
    │
    └── Resource NOT in parent.global_vars:
          → PARENT_MISSING_RESOURCE
          → Log diagnosis, fall through
          → Parent marked needs_human_intervention
```

### Resource Name Normalization

Interface IDs use plural prefixes (e.g., `products.get`), but LLM output may reference the singular `resource_id` (e.g., `product`). The `_interface_prefix_map` maps `resource_id → interface_prefix`:

```
"product" → "products"  // resource_id → interface prefix
"products" → "products" // idempotent passthrough
```

## Known Limitations

- **Parent without resource produces no structured summary**: when a parent lacks the resource in `global_vars`, it correctly marks `needs_human_intervention` but does not generate a centralized diagnostic report. The root cause information is embedded in `composition_feedback` and log lines but not aggregated into a human-readable summary.
- **LLM compliance varies**: the decomposer may still produce structurally invalid children even after receiving feedback (depends on model capability).
- **No automatic InterfacePlan repair**: missing capabilities beyond the current plan still trigger `needs_human_intervention` rather than auto-extension of the plan.
- **Provenance checker is not a full SSA**: does not track variables across function boundaries, comprehensions, or closures.
- **Max retries exhausted has no summary**: after `max_decompose_retries` failed redecomposition attempts, the node is marked `needs_human_intervention` but no aggregated failure report is produced.

## Usage

```bash
cd mvp/mvp-0.4.4
python main.py --input test_prd.md --output output_test
```

## Tests

```bash
# Formal test suite: 5 cases × 3 runs = 15 executions (100% pass)
python tests/test_formal_leaf_rejection.py

# E2E redecomposition: parent-has-resource → redecompose, parent-missing → propagate
python tests/test_e2e_redecompose.py
```

## MVP Tier

**Tier: MVP-0.x** — Feasibility of tree decomposition with architecture feedback loop.
The generated code is not yet connected by a code pipeline and cannot be executed.
