# MVP-0.1 — Basic Tree Decomposition Prototype

## Version Description

MVP-0.1 is the most basic prototype of the Agent Chronos 2.0 tree-centered architecture. This version serves to prove the **feasibility of tree decomposition**: given a PRD document as input, output a decomposition tree with corresponding code for each node.

This is a Proof of Concept (PoC) for the entire architecture. All prompts and descriptive content use Chinese.

### Core Capabilities

- LLM-based recursive tree decomposition (depth-first traversal)
- Code generation for each node (LLM-driven)
- Basic static validation (AST syntax, interface preservation, child function usage)
- Failure-triggered re-decomposition mechanism

### Limitations

- ❌ Generated code is not runnable (no code pipeline connecting nodes)
- ❌ Global state is re-initialized on every function call
- ❌ No import management (datetime, typing, etc. are missing)
- ❌ Potential function name conflicts across branches
- ❌ No execution testing — only AST static validation

---

## File Structure

| File | Role |
|------|------|
| `main.py` | CLI entry point, parses arguments, starts build |
| `tree_builder.py` | Core controller, manages decompose → generate → validate loop |
| `decomposer.py` | LLM-driven node decomposer |
| `code_generator.py` | LLM-driven code generator |
| `validator.py` | Static validator (AST, interfaces, child function usage) |
| `models.py` | Data models (Node, Contract, ValidationResult, etc.) |
| `config.py` | Configuration (model, depth, retry counts, etc.) |
| `api_client.py` | DeepSeek API client |
| `node_schema.json` | Decomposition tree node JSON Schema definition |

---

## Usage

### Requirements

- Python 3.10+
- `openai` Python package
- DeepSeek API key (or compatible OpenAI API)

### Installation

```bash
pip install openai
```

### Set API Key

```bash
set DEEPSEEK_API_KEY=your_api_key_here
```

### Run

```bash
python main.py --input test_prd.md --output ./output
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--input` / `-i` | Required | Path to PRD input file |
| `--output` / `-o` | `output` | Output directory |
| `--name` / `-n` | Derived from filename | System name |
| `--max-depth` | `3` | Maximum decomposition depth |
| `--max-children` | `4` | Maximum children per node |
| `--max-lines` | `50` | Line threshold for leaf detection |
| `--temperature` / `-t` | `0.3` | LLM temperature |
| `--max-retries` | `3` | Max code generation retries |
| `--max-decompose-retries` | `3` | Max re-decomposition retries |
| `--model` | `deepseek-chat` | LLM model name |
| `--base-url` | `https://api.deepseek.com` | API base URL |
| `--verbose` / `-v` | No | Enable verbose output |

### Output Structure

```
output/
├── decomposition_tree.json    # Full decomposition tree (JSON)
├── build.log                  # Build log
└── nodes/                     # Generated code files
    ├── root_System.py
    ├── root_0_child_a.py
    └── ...
```

### Examples

```bash
# Basic usage
python main.py --input test_prd.md

# Custom output directory and system name
python main.py --input test_prd.md --output my_output --name MySystem

# Control decomposition depth
python main.py --input test_prd.md --max-depth 4 --max-children 6

# Tweak LLM parameters
python main.py --input test_prd.md --temperature 0.2 --max-retries 5
```

---

## Architecture Flow

```
PRD Document → main.py
    → TreeBuilder (core loop)
        → Decomposer (LLM splits node into children)
        → CodeGenerator (LLM generates code for each node)
        → Validator (static code validation)
        → Validation failed → retry or re-decompose
    → Output decomposition tree JSON + code files
```

### Core Loop

1. **Decompose** — LLM splits the current function block into sub-function blocks
2. **Generate Code** — LLM implements code for the node
3. **Validate** — AST syntax check + interface preservation + child function usage
4. **Retry / Re-decompose** — On failure, retry code generation or re-decompose

### Semantic Stopping Conditions

Decomposition stops when any of the following conditions is met:

| Condition | Description |
|-----------|-------------|
| **Pure Function** | Mathematical transformation with no side effects, I/O, or state dependencies |
| **Atomic Operation** | Single operation (read/write/update) on a single data source |
| **Max Depth** | Reached the configured maximum depth limit |

---

## Test Results

Tested with `test_prd.md` (Personal Task Manager):

| Metric | Value |
|--------|-------|
| Total Nodes | 26 |
| Leaf Nodes | 20 |
| Passed Validation | 26/26 |
| Max Depth | 3 |
| Pure Function Nodes | 16 |
| Atomic Operation Nodes | 4 |
