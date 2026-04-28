# Tree-Centered Implementation

A proof-of-concept implementation of the **Tree-Centered Implementation Refinement** architecture for automated code generation through recursive decomposition.

## Project Variants

| Directory | Status | Description |
|-----------|--------|-------------|
| `mvp-schema-improved/` | **Active** | Current implementation with JsonPRD/SubPRD schemas, global state conservation, signature locking |
| `mvp-chinese/` | Tracked | Original MVP with Chinese-language decomposition support |

## Overview

This implementation validates the core concepts of the tree-centered decomposition approach:

1. **Structured PRD Schema** - Natural language PRD is converted to JsonPRD, then decomposed into SubPRDs for each node
2. **Signature Locking** - Child node function signatures are locked contracts set by the parent, enforced by AST validation
3. **Global State Conservation** - Parent nodes delegate all data operations to children; the system verifies completeness and correctness
4. **Decomposition-Verification Loop** - Each decomposition is validated through composition before proceeding; failures trigger re-decomposition or code regeneration depending on error type

## Architecture

### Key Components

| File | Purpose |
|------|---------|
| `main.py` | CLI entry point, root node construction from JsonPRD |
| `prd_converter.py` | NL → JsonPRD conversion (LLM-based), cached to `.chronos/prd.json` |
| `models.py` | Data models: JsonPRD, SubPRD, Node, contracts, state operations |
| `decomposer.py` | LLM-based node decomposition with signature locking |
| `code_generator.py` | LLM-based code generation with signature enforcement |
| `validator.py` | AST validation, signature checking, child usage verification, state conservation |
| `tree_builder.py` | Recursive tree construction with per-node tight loop |
| `api_client.py` | OpenAI-compatible API client |
| `config.py` | Configuration with env var support |

### Per-Node Tight Loop

```
[tree_builder._process_parent_node]
     │
     ├─ ① Decompose (LLM) → children with locked signatures
     │     Fail: retry decomposition
     │
     ├─ ② Conservation Check → verify parent state ops = Σ(child state ops)
     │     Fail: clear children → re-decompose
     │
     ├─ ③ Code Generation (LLM) → Python code using child interfaces
     │     Fail: retry code generation
     │
     ├─ ④ AST Validation → syntax + signature + child usage
     │     ├─ "Child functions not used": clear children → re-decompose
     │     └─ Other errors (signature, syntax): retry code generation
     │
     └─ Max retries exhausted → mark needs_human_intervention
```

## Features

### Schema Improvements (vs. original MVP)

| Feature | Description |
|---------|-------------|
| **JsonPRD** | Structured PRD with metadata, functional requirements, global state sources, I/O spec |
| **SubPRD** | Per-node task specification with traceability, constraints, acceptance criteria |
| **PRD Converter** | LLM-based NL → JsonPRD conversion, cached for reproducibility |
| **Global State Sources** | Formal declaration of all shared data stores (type, schema, initial state) |
| **State Operations** | Per-node declaration of read/write/delete operations on global state |

### Validation

| Validation | Method | Trigger |
|------------|--------|---------|
| **AST Correctness** | `ast.parse()` | Syntax validity of generated code |
| **Signature Match** | `validate_signature()` | Parameter names, types, return type match node declaration |
| **Child Usage** | `check_child_usage()` | Parent code calls all declared child functions |
| **State Conservation** | `check_conservation()` | Parent state ops ⊆ Σ(child state ops): completeness, correctness |
| **Interface Preservation** | Input/output matching | Parent I/O matches SubPRD specification |

### Signature Locking

Child signatures are **locked at decomposition time**. The decomposer LLM declares each child's exact input/output types; the code generator LLM must follow them precisely. The validator checks:

- Function name matches node name
- Parameter names match declaration
- Parameter types match declaration (via type annotations)
- Return type matches declaration

Signature validation errors trigger **code regeneration** (not re-decomposition), since they indicate code quality issues with the same interface.

### Global State Conservation

The State Conservation Law: a parent node's global operations must equal the **union** of all its children's operations.

Three checks:

1. **Completeness** - Every child state op references a source defined in parent's SubPRD
2. **Correctness** - Every parent state op is covered by at least one child
3. **Atomicity** - (Relaxed) Each source is operated on by at least one child

Conservation violations trigger **re-decomposition**, since they indicate flawed interface design.

## Installation

```bash
# Navigate to the active implementation
cd experiment/Tree-Centered\ Implementation/mvp-schema-improved

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate
# Activate (Linux/Mac)
source venv/bin/activate

# Install dependencies
pip install openai python-dotenv
```

## Configuration

Create a `.env` file:

```
DEEPSEEK_API_KEY=your_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
```

## Usage

### Basic

```bash
python main.py --input test_prd.md --output ./output
```

### CLI Options

| Option | Default | Description |
|--------|---------|-------------|
| `--input`, `-i` | Required | PRD input file path |
| `--output`, `-o` | `output` | Output directory |
| `--max-depth` | 3 | Maximum decomposition depth |
| `--max-children` | 4 | Maximum children per node |
| `--temperature`, `-t` | 0.3 | LLM temperature |
| `--model` | `deepseek-chat` | LLM model name |
| `--verbose`, `-v` | False | Enable verbose output |

### Output Structure

```
output/
├── assessment_report.md           # Full validation assessment
├── decomposition_tree.json        # Complete tree with all metadata
├── .chronos/
│   └── prd.json                   # Cached JsonPRD
└── nodes/
    ├── root_PersonalTaskManager.py       # Root node
    ├── root_0_ParseCommand.py            # Level 1 node
    ├── root_0_0_ValidateCommandType.py   # Level 2 node (leaf)
    └── ...                               # All generated nodes
```

## Related Documentation

- [Tree-Centered Implementation Refinement](../../docs/Tree-Centered%20Implementation%20Refinement.md) - Full architecture specification
- [Tree-Centered Implementation Refinement (中文)](../../docs/Tree-Centered%20Implementation%20Refinement-zh.md) - 中文版架构文档
