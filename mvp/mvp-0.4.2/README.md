# MVP-0.4.2 — Interface Layer (Phases 3 + 4)

## MVP Lineage

| Version | Theme | Key Feature |
|---------|-------|-------------|
| **MVP-0.1** | Proof of Concept | Basic tree decomposition, Chinese-only |
| **MVP-0.2.0** | Structured PRD | JsonPRD + SubPRD for information preservation |
| **MVP-0.2.1** | JSON Mode | `response_format=json_object` enforced at API level |
| **MVP-0.3.1** | Decomposition-Verification Loop | Signature locking, Parent-as-Coordinator, AttemptRecord, StateOperation system |
| **MVP-0.4.1** | Interface Layer (Phase 1+2) | ResourceSpec/InterfaceSpec, Interface Planning, capability whitelist |
| **MVP-0.4.2** | **Interface Layer (Phase 3+4)** | Interface CodeGen, Capability Allocation, interface-based leaf prompts |

---

## Version Context

MVP-0.4.2 implements **Phase 3 and Phase 4** of the interface layer fix, building on the data models and planner from MVP-0.4.1:

- **Phase 3 ✓**: `InterfaceCodeGenerator` generates `output_test/generated/interfaces.py` from `InterfacePlan`, with storage-model-specific templates (dict/list operations) and `ast.parse` syntax validation.
- **Phase 4 ✓**: Leaf nodes declare `requested_capabilities` during decomposition; `CapabilityAllocator` grants or fails them against the `InterfacePlan`; `CodeGenerator` uses a new interface-based prompt (no `global`, no `op_id`, no `source_id`) when `granted_capabilities` are present.

---

## Architecture (updated)

```
PRD/Requirement
    │
    ▼
PRD Converter ──► JsonPRD
    │
    ▼
Interface Planner (Phase 2) ──► InterfacePlan (interface_plan.json)
    │
    ▼
Interface CodeGen (Phase 3, NEW) ──► generated/interfaces.py
    │
    ▼
Root Node ──[Decomposer]──► Child Nodes ──[Decomposer]──► Grandchildren ...
    │                              │
    │              [CapabilityAllocator] (Phase 4, NEW)
    │              grants interfaces to leaves with requested_capabilities
    │                              │
    └──[CodeGenerator]             └──[CodeGenerator]
    │         ↑                    │         ↑
    │   interface-based prompt     │   (unchanged if no granted_capabilities)
    │   (no global, no op_id)      │
    ▼                              ▼
Generated Code              Generated Code
    │                              │
    ▼                              ▼
Validator ◄───────────────── Validator
    │
    ├── passed  ──► save & return
    └── failed  ──► retry or re-decompose
```

### Current Phase Scope (Phase 1 + 2 + 3 + 4)

This version implements **Phase 1 through Phase 4** of the interface layer fix:

- **Phase 1 ✓**: `ResourceSpec`, `InterfaceSpec`, `CapabilityGrant`, `InterfacePlan` data models added to `models.py`
- **Phase 2 ✓**: `InterfacePlanner` LLM agent generates `InterfacePlan` from `JsonPRD`, saved as `interface_plan.json`
- **Phase 3 ✓**: `InterfaceCodeGenerator` generates `interfaces.py` from `InterfacePlan` with storage-model templates, validated with `ast.parse`
- **Phase 4 ✓**: Leaf nodes declare `requested_capabilities`; `CapabilityAllocator` grants/fails; `CodeGenerator` uses interface-based leaf prompt when granted
- **Phase 5** (not yet): Validator switches to interface usage validation

---

## Key New Concepts (Phase 3)

### InterfaceCodeGenerator

Generates a standalone `interfaces.py` file from `InterfacePlan`. Each `InterfaceSpec` becomes a function with storage-model-specific implementation:

| Storage Model | Operations | Implementation Pattern |
|---------------|-----------|----------------------|
| `dict` | get/list/create/update/delete/exists | Direct dict operations via global variable |
| `list` | get/list/create/update/delete/exists | Iteration with key field matching |
| `in_memory_table` | (same as dict) | Uses dict-based patterns |

The generated code:
- Is the ONLY layer allowed to access global variables directly
- Is validated with `ast.parse` for syntactic correctness
- Is saved to `output_test/generated/interfaces.py`

## Key New Concepts (Phase 4)

### CapabilityAllocator

After decomposition and conservation check pass but before parent codegen, each leaf child with `requested_capabilities` is checked against the `InterfacePlan`:

- Interface exists in plan → `CapabilityGrant` with granted interface IDs
- Interface does not exist → allocation fails, node marked `needs_human_intervention`

### Interface-Based Leaf Prompt

When a leaf node has `granted_capabilities`, the `CodeGenerator` uses a new prompt template that:
- Shows only the granted interface functions (signature + description)
- Forbids `global` keyword declarations
- Forbids `op_root_*` or `source_id` references
- Tells the LLM to call interfaces as normal function calls (they are imported externally)

---

## Files

| File | Role | Status |
|------|------|--------|
| `main.py` | CLI entry point | **Modified** — added `--skip-interface-codegen` flag, Interface CodeGen phase, passes InterfacePlan to TreeBuilder |
| `interface_codegen.py` | Interface code generator | **New (Phase 3)** — generates `interfaces.py` from InterfacePlan |
| `interface_planner.py` | LLM-based Interface Planner | Unchanged from 0.4.1 |
| `models.py` | Data models | **Modified** — `Node` adds `requested_capabilities` and `granted_capabilities` fields |
| `capability_allocator.py` | Capability allocator | **New (Phase 4)** — matches `requested_capabilities` against InterfacePlan |
| `tree_builder.py` | Core controller | **Modified** — integrates CapabilityAllocator, passes InterfacePlan to Decomposer and CodeGenerator |
| `decomposer.py` | LLM node decomposer | **Modified** — adds `requested_capabilities` to leaf output format, injects available interfaces into prompt |
| `code_generator.py` | LLM code generator | **Modified** — adds interface-based leaf prompt with granted interfaces |
| `validator.py` | Static validator | Unchanged from 0.4.1 (Phase 5 pending) |
| `config.py` | Configuration | Unchanged from 0.3.1 |
| `api_client.py` | LLM API client | Unchanged from 0.3.1 |
| `prd_converter.py` | PRD → JsonPRD converter | Unchanged from 0.3.1 |
| `node_schema.json` | Node JSON Schema | Unchanged from 0.3.1 |

### What Changed from 0.4.1

**New** (Phase 3):
```
interface_codegen.py            — generates interfaces.py from InterfacePlan with storage-model templates
```

**New** (Phase 4):
```
capability_allocator.py         — matches requested_capabilities against InterfacePlan, grants or fails
```

**Modified**:
```
models.py                       — Node dataclass: +requested_capabilities, +granted_capabilities
                                 to_dict/from_dict updated for both new fields
decomposer.py                   — leaf output JSON includes "requested_capabilities" field
                                 system prompt shows available interfaces when InterfacePlan available
                                 _create_child_node() extracts requested_capabilities
                                 decompose() accepts optional interface_plan_summary
code_generator.py               — new _build_system_prompt_for_leaf_with_interfaces()
                                 new _build_user_prompt_for_leaf_with_interfaces()
                                 generate_for_leaf() routes to interface prompt when granted_capabilities exist
                                 set_interface_plan() populates _interface_map
tree_builder.py                 — __init__ accepts InterfacePlan, creates CapabilityAllocator
                                 _allocate_capabilities() grants interfaces to leaf children
                                 _process_parent_node() calls allocation after conservation check
                                 passes interface_plan_summary to decomposer
main.py                         — added --skip-interface-codegen flag
                                 Interface CodeGen phase after InterfacePlan generation
                                 TreeBuilder(config, interface_plan=interface_plan)
```

---

## Usage

### Requirements

- Python 3.10+
- `openai` Python package
- DeepSeek API key (or any OpenAI-compatible API)

### Installation

```bash
cd mvp\mvp-0.4.2
pip install openai
set DEEPSEEK_API_KEY=your_api_key_here
```

### Run with full 0.4.2 flow (Interface Planning + CodeGen + Capability Allocation)

```bash
python main.py --input test_prd.md --output output_test
```

Output:
```
output_test/
├── .chronos/prd.json                      # JsonPRD (from PRDConverter)
├── interface_plan.json                    # InterfacePlan (from Interface Planner)
├── generated/interfaces.py                # NEW: Generated interface code (Phase 3)
├── order_prd_decomposition_tree.json      # Decomposition tree
└── nodes/                                 # Generated code files
```

### Run without Interface Planning (0.3.1 backward-compatible)

```bash
python main.py --input test_prd.md --output output_test --skip-interface-plan
```

### Run with Interface Planning but skip CodeGen

```bash
python main.py --input test_prd.md --output output_test --skip-interface-codegen
```

### Custom Parameters

```bash
python main.py --input prd.md --output ./out ^
    --max-depth 4 --temperature 0.2 ^
    --skip-interface-plan
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--input` / `-i` | Required | Path to PRD input file |
| `--output` / `-o` | `output` | Output directory |
| `--name` / `-n` | Derived from filename | System name |
| `--max-depth` | `3` | Maximum decomposition depth |
| `--max-children` | `4` | Maximum children per node |
| `--max-lines` | `50` | Lines threshold for leaf detection |
| `--temperature` / `-t` | `0.3` | LLM temperature |
| `--max-retries` | `3` | Max code generation retries |
| `--max-decompose-retries` | `3` | Max re-decomposition retries |
| `--model` | `deepseek-chat` | LLM model |
| `--skip-prd-convert` | Off | Skip JSON PRD conversion |
| `--skip-interface-plan` | Off | Skip Interface Planning (0.3.1 mode) |
| **`--skip-interface-codegen`** | Off | **Skip Interface Code Generation (Phase 3)** |

---

## Design Decisions

### Why generate `interfaces.py` as a standalone file?

Because the interface layer has a single responsibility: provide stable data access. It should be importable, testable, and regeneratable independently of the decomposition tree. Placing interface code in a standalone file also makes it visible for manual inspection and debugging.

### Why allow direct global variable access only in the interface layer?

Because the interface layer is the **only** part of the system where the storage model (dict/list/in_memory_table) is explicitly known. Leaf nodes should not care about storage details — they call `get_order(id)` and get a result. The interface layer bridges the gap between "global variable" and "function call."

### Why Capability Allocation after decomposition but before codegen?

Because allocation requires knowing which children exist and their data access needs. Decomposition produces these needs (`requested_capabilities`), and codegen consumes the grants (`granted_capabilities`). The allocation step is a pure mapping — it does not call the LLM.

### Why not auto-create missing interfaces in CapabilityAllocator?

The interface plan is meant to be comprehensive and pre-decided. If a leaf needs an interface that was not planned, it means the InterfacePlan was incomplete. Auto-creation would hide this gap and produce inconsistent interfaces across subtrees. A hard failure signals the user to revise the plan.

---

## What's Next (Future Phases)

| Phase | What | Status |
|-------|------|--------|
| **1** | InterfacePlan data models | ✅ Done |
| **2** | LLM Interface Planner | ✅ Done |
| **3** | Generate interface implementation code (`interfaces.py`) | ✅ Done |
| **4** | Leaf code generator uses only granted interfaces | ✅ Done |
| **5** | Validator switches to interface usage validation + fix summary | ❌ |
