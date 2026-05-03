# MVP-0.3.1 — Tree-Centered Decomposition-Verification Architecture

## Version Context

MVP-0.3.1 is the most complete version in the current MVP series, introducing several key architectural improvements over its predecessors.

### Evolution from MVP-0.2.1

| Aspect | MVP-0.2.x | MVP-0.3 |
|--------|-----------|---------|
| **Coordination** | Allowed coordinator child nodes | **Parent-as-Coordinator** — coordinator child nodes prohibited; coordination logic belongs to the parent |
| **Interface Constraints** | Basic interface matching | **Signature Locking** — child function signatures are precisely saved and must be strictly followed during code generation |
| **Validation Granularity** | Syntax + interface + conservation | Syntax + signature + child function usage + global variables + structured error classification |
| **Failure Handling** | Basic retry | **Context Continuity** — AttemptRecord history + snapshot saving + structured diagnostic feedback |
| **Global State** | GlobalVar declarations | StateOperation system + auto-derivation + conservation verification |
| **Loading** | None | **Partial** — `load_tree()` available in TreeBuilder layer, but `--load` CLI parameter not yet wired |

### Key Improvements

1. **Parent-as-Coordinator** — Eliminates ambiguous coordinator child nodes, simplifying decomposition and code generation
2. **Signature Locking** — Signatures locked during decomposition become binding contracts that the code generator must precisely follow
3. **Context Continuity** — Full AttemptRecord history and snapshot mechanism, allowing the LLM to see complete failure context during retries
4. **Structured ValidationError** — Precise error-type-based decisions, replacing fragile string matching

---

A tree-centered multi-agent software construction system. The system recursively decomposes a function specification into a tree of leaf functions, generates code for each node, and validates correctness at every level — all driven by LLM agents with structured prompts and JSON schemas.

## Architecture

```
PRD/Requirement
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

### Core Loop

For each node in the tree:

1. **Decompose** — LLM splits a function into child sub-functions (if not a leaf)
2. **Code Generate** — LLM implements the function, calling children by their locked signatures
3. **Validate** — Static analysis checks: signature match, child usage, global variable conservation, syntax
4. **Retry or Re-decompose** — On failure, either retry code generation (with validation feedback) or re-decompose (with full context from previous attempt)

## Files

| File | Role |
|------|------|
| `main.py` | CLI entry point. Reads PRD, builds tree, saves output |
| `tree_builder.py` | **Core controller**. Manages the decompose → generate → validate loop per node, with retry/re-decompose logic |
| `decomposer.py` | LLM-based decomposer. Splits a parent node into children with locked interfaces |
| `code_generator.py` | LLM-based code generator. Implements leaf functions or parent coordination code |
| `validator.py` | Static validator. Checks signatures, child function usage, global variable conservation, syntax |
| `models.py` | All data classes: Node, ValidationResult, AttemptRecord, ChildContract, etc. |
| `config.py` | Configuration: model, max depth, retry counts, temperature |
| `api_client.py` | LLM API client (DeepSeek-compatible) |
| `prd_converter.py` | Converts raw PRD text into JsonPRD structure |
| `node_schema.json` | JSON Schema for the decomposition tree node format |

## Key Concepts

### Signature Locking

When the Decomposer creates child nodes, it also locks their function signatures (name, parameters, types, return type). The CodeGenerator **must** follow these signatures exactly — the Validator will reject any deviation. This ensures composability: parent code that calls children by their locked signatures can trust the interface will match.

### Parent-as-Coordinator

The parent node IS the coordinator. It directly calls its children to orchestrate behavior. The Decomposer is explicitly forbidden from creating "coordinator", "router", or "aggregator" child nodes — coordination logic belongs in the parent function body.

### Global State Conservation

If a parent declares it operates on global variables, the union of all children's global variable declarations must cover all of the parent's operations. The Validator enforces this to prevent silent loss of global state operations during decomposition.

### Context Continuity (P0)

When a node fails validation and needs retry or re-decomposition, the system preserves the full context of what happened:

- **AttemptRecord** — Every attempt (decompose, codegen, validate) is recorded in `node.attempt_history[]`
- **Snapshot before clear** — Before clearing children for re-decomposition, the system saves children names, contracts, rationale, and generated code
- **Rich feedback to LLM** — On re-decomposition, the Decomposer receives not just error strings but structured diagnostic context: which children were unused, what code was generated, what the previous rationale was, and what the Validator found

## Usage

```bash
# Set API key (DeepSeek-compatible API)
set DEEPSEEK_API_KEY=your_key_here

# Build from Markdown PRD
python main.py --input path/to/prd.md --output ./output

# Build with custom parameters
python main.py --input prd.md --output ./out --max-depth 4 --temperature 0.2

# Note: Loading existing tree via CLI is not yet implemented.
# To load programmatically, use TreeBuilder.load_tree():
```

### Output

```
output/
├── decomposition_tree.json    # Full tree with all nodes
├── build.log                  # Processing log
└── nodes/                     # Generated code files
    ├── root_System.py
    ├── 0_0_child_a.py
    └── ...
```

## Configuration

All settings in `config.py`, overridable via constructor or environment variables:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `model` | `deepseek-chat` | LLM model |
| `temperature` | `0.3` | LLM temperature |
| `max_depth` | `3` | Maximum decomposition depth |
| `max_children` | `4` | Maximum children per node |
| `max_retries` | `3` | Code generation retries |
| `max_decompose_retries` | `3` | Re-decomposition retries |
| `max_lines_threshold` | `50` | Leaf detection threshold |

## Development

The system uses only the Python standard library plus an HTTP client for LLM API calls. No heavy frameworks, no orchestration engines — the "tree-centered" design means the data structure itself drives the control flow.

### Adding a new validation rule

1. Add the check method in `validator.py`
2. Call it from `validate()` and append errors
3. Add a classification in `_classify_error()` for structured error reporting
4. Optionally update `should_redecompose()` if the new error type should trigger re-decomposition

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| Parent is coordinator | Eliminates coordinator child conflict; simplifies decomposition and code generation |
| Structured ValidationError | Enables precise error-type-based decisions instead of fragile string matching |
| AttemptRecord history | Preserves evidence chain across retries; enables future diagnosis and repair patterns |
| Rich re-decomposition context | LLM can see exactly what it did before and what went wrong, enabling targeted fixes |
| Signature locking | Prevents interface drift between decomposition and code generation phases |
