# MVP-0.4.3 — Architecture Feedback Loop

## What's New

MVP-0.4.3 introduces the **architecture feedback loop**: when a parent node cannot be implemented solely by composing its child functions, the system can now:

1. **Actively reject** the decomposition (`CANNOT_COMPOSE` from CodeGenerator)
2. **Passively detect** structural gaps (Validator checks for direct resource access, dangling inputs, unauthorized interface calls)
3. **Route feedback** to redecomposition (TreeBuilder clears children, passes structured diagnostics)
4. **Consume diagnostics** (Decomposer sees `composition_feedback`, `fix_summary`, and `structured_errors`)
5. **Emit dataflow edges** (Decomposer outputs explicit `dataflow_edges` in the tree)

## Files Changed from 0.4.2

| File | Change |
|------|--------|
| `models.py` | Added `DataflowEdge`, `CompositionFeedback`; extended `ValidationResult` (repair_action, fix_summary); extended `Node` (dataflow_edges, composition_feedback) |
| `code_generator.py` | Parent prompt now supports `status: "cannot_compose"` with `decomposition_feedback`; `generate_with_retry` short-circuits on CANNOT_COMPOSE |
| `tree_builder.py` | Routes CANNOT_COMPOSE to redecomposition; replaced UNUSED_CHILD-only context with generic `_build_redecompose_context`; validation failure now checks `repair_action` |
| `validator.py` | New checks: `validate_no_direct_resource_access`, `validate_leaf_interface_usage`, `validate_child_input_provenance`; adds `repair_action`/`fix_summary` to validation result; extended `should_redecompose` |
| `decomposer.py` | System prompt includes DATAFLOW CLOSURE RULES and `dataflow_edges`; `decompose()` parses `dataflow_edges`; previous diagnostics section consumes `fix_summary`, `composition_feedback`, `structured_errors` |

## Architecture (updated)

```
PRD/Requirement
    │
    ▼
PRD Converter ──► JsonPRD
    │
    ▼
Interface Planner ──► InterfacePlan
    │
    ▼
Interface CodeGen ──► generated/interfaces.py
    │
    ▼
Tree Construction (decompose → implement → validate → feedback loop)
    │
    ├── Decomposer emits children + dataflow_edges
    ├── CodeGenerator returns ok | cannot_compose with decomposition_feedback
    ├── Validator checks: signature, child usage, resource access, interface usage, input provenance
    └── On failure → TreeBuilder clears children, passes context → Decomposer retries
    │
    ▼
Decomposition Tree (with dataflow_edges, fix_summary, composition_feedback)
```

## Key Concepts

### Feedback Loop
```
Decompose → Codegen → Validate
                         │
            ┌────────────┤
            ▼            ▼
      cannot_compose   structural error (DIRECT_RESOURCE_ACCESS, CHILD_INPUT_SOURCE_MISSING, etc.)
            │            │
            └─────┬──────┘
                  ▼
          TreeBuilder clears children
                  │
                  ▼
          Decomposer receives composition_feedback / fix_summary
                  │
                  ▼
          New decomposition with improved dataflow
```

### Dataflow Closure Rules (in Decomposer Prompt)
1. Every child input must have an explicit source
2. Source must be: parent input, earlier sibling output, local constant, or leaf capability
3. If data is missing, add a producing child before the consuming child
4. No dangling parameters (e.g., `products_data` without a source)
5. Parent must not directly access global state

### Validator Checks (Phase 5)
| Check | Error Type | When Failed |
|-------|-----------|-------------|
| Parent accesses resource directly | `DIRECT_RESOURCE_ACCESS_PARENT` | Parent code references `products`, `orders`, etc. |
| Leaf calls unauthorized interface | `UNGRANTED_INTERFACE_CALL` | Leaf calls interface not in `granted_capabilities` |
| Child input has no source | `CHILD_INPUT_SOURCE_MISSING` | Child call argument is not from params, child outputs, or loop vars |
| Code uses op_root_* variables | `INTERFACE_USAGE_VIOLATION` | Legacy `op_id` references appear in generated code |

## Known Limitations

- **Provenance checker is not a full SSA**: does not track variables across function boundaries, comprehensions, or closures
- **LLM compliance varies**: the decomposer may still produce structurally invalid children even after receiving feedback (depends on model capability)
- **No automatic InterfacePlan repair**: missing capabilities trigger `needs_human_intervention` rather than auto-creation
- **no dynamic feedback to the interface planner**: if a leaf needs an unplanned interface, the error propagates upward

## Usage

```bash
cd mvp/mvp-0.4.3
python main.py --input test_prd.md --output output_test
```

## Tests

```bash
# CodeGenerator rejection tests
python tests/test_codegen_cannot_compose.py

# Provenance validator tests
python tests/test_provenance_validator.py
```
