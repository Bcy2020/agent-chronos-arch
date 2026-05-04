# MVP-0.4.1 — Interface Layer & Resource Planning

## MVP Lineage

| Version | Theme | Key Feature |
|---------|-------|-------------|
| **MVP-0.1** | Proof of Concept | Basic tree decomposition, Chinese-only |
| **MVP-0.2.0** | Structured PRD | JsonPRD + SubPRD for information preservation |
| **MVP-0.2.1** | JSON Mode | `response_format=json_object` enforced at API level |
| **MVP-0.3.1** | Decomposition-Verification Loop | Signature locking, Parent-as-Coordinator, AttemptRecord, StateOperation system |
| **MVP-0.4.1** | **Interface Layer** | ResourceSpec/InterfaceSpec, Interface Planning, capability whitelist (current) |

---

## Version Context

MVP-0.4.1 addresses a fundamental problem exposed by MVP-0.3.1: **leaf nodes confuse internal tracking IDs with real Python variables, and have no stable interface layer to access global state**.

In MVP-0.3.1, the system proved it can decompose a PRD into a working tree, generate dozens of code files, and validate structure. But real runs showed recurring failures like:

```
Undeclared global variable: op_root_1_5_0
```

Leaf nodes see `op_root_1_5_0` (a `StateOperation.op_id` used for tracking) and treat it as a Python variable. The retry mechanism cannot fix this — the root cause is that operation IDs and raw data source names are exposed directly to the code generator prompt without an interface abstraction layer.

### Evolution from MVP-0.3.1

| Aspect | MVP-0.3.1 | MVP-0.4.1 |
|--------|-----------|------------|
| **Pre-decomposition** | JSON PRD → Tree Decomposition | JSON PRD → **Interface Planning** → Tree Decomposition |
| **Data Source Model** | `GlobalStateSource` (raw) | `ResourceSpec` (storage model, schema, invariants) |
| **Access Model** | `StateOperation` with `op_id` exposed to LLM | `InterfaceSpec` with locked function signatures |
| **Operation Granularity** | `read` / `write` only | CRUD whitelist: `get`, `list`, `create`, `update`, `delete`, `exists` |
| **Storage Model** | Not specified | Explicit whitelist: `dict`, `list`, `in_memory_table` |
| **Code Gen Prompt** | Exposes `op_id`, `source_id`, raw `global_vars` | (Phase 4) Only exposes granted `InterfaceSpec` signatures |
| **Business Logic in Interfaces** | Allowed implicitly | **Forbidden** — interfaces must be generic CRUD, not domain actions |
| **Backward Compatibility** | — | `--skip-interface-plan` flag restores 0.3.1 behavior |

### The Problem in One Sentence

> The system mixed "data source declarations" with "code-callable interfaces", forcing leaf nodes to guess data structures and access patterns — and retry cannot fix guessing.

### The Fix in One Sentence

> Insert an **Interface Planning** phase between JSON PRD and tree decomposition, where an LLM designs stable, typed, whitelisted CRUD interfaces for each data source — before any decomposition happens.

---

## Architecture

```
PRD/Requirement
    │
    ▼
PRD Converter ──► JsonPRD
    │
    ▼
Interface Planner (NEW) ──► InterfacePlan (interface_plan.json)
    │                          ├── ResourceSpec[] (storage model, schema, invariants)
    │                          └── InterfaceSpec[] (function signatures, pre/post conditions)
    │
    ▼
Root Node ──[Decomposer]──► Child Nodes ──[Decomposer]──► Grandchildren ...
    │                              │
    └──[CodeGenerator]             └──[CodeGenerator]
    │                              │
    ▼                              ▼
Generated Code              Generated Code
    │                              │
    ▼                              ▼
Validator ◄───────────────── Validator
    │
    ├── passed  ──► save & return
    └── failed  ──► retry or re-decompose
```

### Current Phase Scope (Phase 1 + 2)

This version implements **Phase 1 and Phase 2** of the interface layer fix:

- **Phase 1 ✓**: `ResourceSpec`, `InterfaceSpec`, `CapabilityGrant`, `InterfacePlan` data models added to `models.py`
- **Phase 2 ✓**: `InterfacePlanner` LLM agent generates `InterfacePlan` from `JsonPRD`, saved as `interface_plan.json`
- **Phase 3** (not yet): Generate `interfaces.py` implementation code
- **Phase 4** (not yet): Leaf code generator uses only granted interfaces
- **Phase 5** (not yet): Validator switches to interface usage validation

The InterfacePlan is currently generated and saved, but the tree decomposition and code generation phases do not yet consume it. This ensures backward compatibility while laying the full data foundation.

---

## Key New Concepts

### ResourceSpec

Describes a data source's technical storage model and schema — decided **before** any decomposition:

```python
@dataclass
class ResourceSpec:
    resource_id: str        # "orders"
    description: str        # "Stores all orders by order_id"
    storage_model: str      # "dict" | "list" | "in_memory_table"
    key_type: str | None    # "int"
    value_type: str | None  # "Order"
    item_schema: dict       # {"order_id": "int", "status": "str", ...}
    invariants: list[str]   # ["order_id is unique", "status must be one of pending, paid, ..."]
```

### InterfaceSpec

A locked function signature for a low-level data access operation. Never a business action:

```python
@dataclass
class InterfaceSpec:
    interface_id: str     # "orders.get_order"
    resource_id: str      # "orders"
    operation: str        # "get" | "list" | "create" | "update" | "delete" | "exists"
    function_name: str    # "get_order"
    signature: str        # "def get_order(order_id: int) -> Optional[dict]"
    description: str
    preconditions: list[str]
    postconditions: list[str]
```

### Operation Whitelist

Interfaces are restricted to these low-level operations only:

| Operation | Meaning |
|-----------|---------|
| `get` | Retrieve by ID/key |
| `list` | List/search with optional filters |
| `create` | Insert new entity |
| `update` | Modify existing entity |
| `delete` | Remove entity |
| `exists` | Check existence |

Business actions like `pay_order`, `ship_order`, `cancel_order` are **forbidden** at the interface layer. Leaf nodes compose these generic interfaces to implement business logic.

### Storage Model Whitelist

| Model | When to Use |
|-------|-------------|
| `dict` | Key-value access, entities have unique IDs |
| `list` | Sequential access, iteration, search |
| `in_memory_table` | Multi-field filtering required |

### InterfacePlan

Aggregate object containing all resources and interfaces for a project, serializable to `interface_plan.json`:

```
interface_plan.json
├── resources: [ResourceSpec, ...]
├── interfaces: [InterfaceSpec, ...]
└── created_at: ISO timestamp
```

---

## Files

| File | Role | Status |
|------|------|--------|
| `main.py` | CLI entry point | **Modified** — added `--skip-interface-plan` flag and Interface Planning phase |
| `interface_planner.py` | LLM-based Interface Planner | **New** — generates InterfacePlan from JsonPRD |
| `models.py` | Data models | **Modified** — added `ResourceSpec`, `InterfaceSpec`, `CapabilityGrant`, `InterfacePlan` |
| `tree_builder.py` | Core controller | Unchanged from 0.3.1 |
| `decomposer.py` | LLM node decomposer | Unchanged from 0.3.1 |
| `code_generator.py` | LLM code generator | Unchanged from 0.3.1 |
| `validator.py` | Static validator | Unchanged from 0.3.1 |
| `config.py` | Configuration | Unchanged from 0.3.1 |
| `api_client.py` | LLM API client | Unchanged from 0.3.1 |
| `prd_converter.py` | PRD → JsonPRD converter | Unchanged from 0.3.1 |
| `node_schema.json` | Node JSON Schema | Unchanged from 0.3.1 |

### What Changed from 0.3.1

**Added** (Phase 1):
```
models.py :: ResourceSpec       — data source technical spec
models.py :: InterfaceSpec      — locked CRUD function signature
models.py :: CapabilityGrant    — which interfaces a node may use
models.py :: InterfacePlan      — aggregate container for all resource/interface specs
```

**Added** (Phase 2):
```
interface_planner.py            — LLM agent, system prompt, schema validation
```

**Modified**:
```
main.py                         — integrated Interface Planning into main flow
```

**Output added**:
```
output_test/interface_plan.json — structured interface design
```

---

## Key Concepts (inherited from MVP-0.3.1)

### Signature Locking

When the Decomposer creates child nodes, it locks their function signatures. The CodeGenerator must follow them exactly — the Validator rejects any deviation.

### Parent-as-Coordinator

The parent node IS the coordinator. "Coordinator" child nodes are forbidden — coordination logic belongs in the parent function body.

### Global State Conservation

The union of children's global variable declarations must cover all of the parent's declarations. The Validator enforces this to prevent silent loss of state operations.

### Context Continuity

When a node fails validation, the system preserves full context: AttemptRecord history, child snapshots, generated code, and structured diagnostics — enabling the LLM to make targeted fixes on retry.

---

## Usage

### Requirements

- Python 3.10+
- `openai` Python package
- DeepSeek API key (or any OpenAI-compatible API)

### Installation

```bash
cd mvp\mvp-0.4.1
pip install openai
set DEEPSEEK_API_KEY=your_api_key_here
```

### Run with Interface Planning (full 0.4.1 flow)

```bash
python main.py --input test_prd.md --output output_test
```

Output:
```
output_test/
├── .chronos/prd.json              # JsonPRD (from PRDConverter)
├── interface_plan.json            # NEW: InterfacePlan (from Interface Planner)
├── order_prd_decomposition_tree.json  # Decomposition tree
└── nodes/                         # Generated code files
```

### Run without Interface Planning (0.3.1 backward-compatible flow)

```bash
python main.py --input test_prd.md --output output_test --skip-interface-plan
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
| **`--skip-interface-plan`** | Off | **Skip Interface Planning (0.3.1 mode)** |

---

## Design Decisions

### Why add Interface Planning as a separate phase, not part of decomposition?

Because interface design should happen **once** per project, not per node. If each subtree designs its own view of `orders`, different branches produce incompatible conventions. A centralized pre-decomposition phase ensures all nodes share the same interface contract.

### Why whitelist CRUD operations and forbid business actions?

Business actions (`pay_order`, `ship_order`) are what leaf nodes should implement using interfaces. If interfaces already contain business logic, the decomposition tree collapses — there is nothing left for leaves to do. CRUD-only interfaces force a clean separation: interfaces provide data access, leaves provide business logic.

### Why `--skip-interface-plan` exists?

So that MVP-0.3.1 behavior can be reproduced at any time for comparison. This is critical during the transition — if 0.4.1 introduces a regression in tree decomposition, the user can isolate whether the interface planner caused it.

### Why store InterfacePlan as a separate file from the decomposition tree?

Because the InterfacePlan has a different lifecycle: it is generated once at project start and shared across all nodes. Embedding it in the tree would couple interface design to tree structure, making it harder to reuse interfaces across different decompositions of the same project.

---

## What's Next (Future Phases)

| Phase | What | Status |
|-------|------|--------|
| **1** | InterfacePlan data models | ✅ Done |
| **2** | LLM Interface Planner | ✅ Done |
| **3** | Generate interface implementation code (`interfaces.py`) | ❌ |
| **4** | Leaf code generator uses only granted interfaces | ❌ |
| **5** | Validator switches to interface usage validation + fix summary | ❌ |

When all 5 phases are complete, the leaf code generator will receive only:

```
Function to implement:
def UpdateOrderStatus(order_id: int) -> bool

Granted interfaces:
- get_order(order_id: int) -> Optional[dict]
- update_order(order_id: int, patch: dict) -> bool

Rules:
- Use only the granted interfaces.
- Do not declare or access global variables.
- Do not use operation ids.
- Do not invent new resource access functions.
```

And the generated leaf code will be:

```python
def UpdateOrderStatus(order_id: int) -> bool:
    order = get_order(order_id)
    if order is None:
        return False
    return update_order(order_id, {"status": "paid"})
```

Instead of the current (failing) pattern:

```python
def UpdateOrderStatus(order_id: int) -> bool:
    global op_root_1_5_0  # ← BUG: operation ID used as variable
    orders = op_root_1_5_0
    ...
```

---

## Design Decisions (inherited from MVP-0.3.1)

| Decision | Rationale |
|----------|-----------|
| Parent is coordinator | Eliminates coordinator child conflict; simplifies decomposition and code generation |
| Structured ValidationError | Enables precise error-type-based decisions instead of fragile string matching |
| AttemptRecord history | Preserves evidence chain across retries; enables future diagnosis and repair patterns |
| Rich re-decomposition context | LLM can see exactly what it did before and what went wrong |
| Signature locking | Prevents interface drift between decomposition and code generation phases |
| **Interface Planning as separate phase** | Interface design is a project-level concern, not per-node — prevents incompatible conventions across subtrees |
| **CRUD-only operation whitelist** | Forbids business actions at interface layer — leaves must implement business logic, not delegate it |
| **Separate InterfacePlan file** | Different lifecycle from tree decomposition — enables reuse across different decompositions |
