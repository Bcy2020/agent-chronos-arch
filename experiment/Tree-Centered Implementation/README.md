# Tree-Centered Implementation

A proof-of-concept implementation of the **Tree-Centered Implementation Refinement** architecture for automated code generation through recursive decomposition.

## Overview

This MVP validates the core concepts of the decomposition-based code generation approach:

1. **Semantic Stop Conditions** - Decomposition stops when nodes become pure functions or atomic operations, not based on arbitrary line counts
2. **Global State Conservation** - Parent nodes delegate all data operations to children, ensuring traceable state mutations
3. **Decomposition-Verification Loop** - Each decomposition is validated through composition before proceeding

## Achievements (MVP 1.0)

### Core Features Implemented

| Feature | Status | Description |
|---------|--------|-------------|
| Semantic Stop Conditions | ✅ Complete | Decomposition stops based on node type (Pure Function / Atomic Operation) instead of line count |
| Data Source Declaration | ✅ Complete | Each node declares its data operations with source name, operation type, and description |
| Decomposition Rationale | ✅ Complete | LLM-generated explanation of how children work together to implement parent |
| Function-only Generation | ✅ Complete | All child nodes are functions, not classes |
| Child Usage Validation | ✅ Complete | Parent code must use all declared child functions |
| Re-decomposition Loop | ✅ Complete | Automatic re-decomposition when validation fails |
| Interface Preservation | ✅ Complete | Parent inputs/outputs must match specification |

### Test Results

```
Personal Task Manager PRD:
├── Total nodes: 26
├── Leaf nodes: 20
├── Passed validations: 26/26
└── Max depth: 3

Stop condition distribution:
├── Pure Function: 16 nodes
└── Atomic Operation: 4 nodes
```

## Current Issues

### High Priority

| Issue | Impact | Description |
|-------|--------|-------------|
| **Global State Reset** | Runtime Failure | `tasks` and `next_id` are re-initialized on every function call, losing data between calls |
| **next_id Update Loss** | Functional Bug | `generate_task_id()` returns updated `next_id` but it's not persisted back to caller |
| **Missing Imports** | Runtime Failure | `datetime` and typing imports are used but not declared in generated code |

### Medium Priority

| Issue | Impact | Description |
|-------|--------|-------------|
| **Function Name Conflicts** | Potential Override | Same function names appear in different branches (e.g., `validate_task_exists` in complete and delete handlers) |
| **Type Annotations** | Incomplete | Some generated code uses types without proper imports |
| **State Management** | Architecture Gap | No unified state management across the application |

### Low Priority

| Issue | Impact | Description |
|-------|--------|-------------|
| **No Execution Testing** | Validation Gap | Code is validated via AST but not actually executed |
| **No Error Handling** | Robustness | Generated code lacks comprehensive error handling |
| **No Cross-cutting Concerns** | Architecture Gap | Logging, caching, authentication not addressed |

## Roadmap to 2.0

### Phase 1: Auto-Assembly Module

**Goal**: Automatically combine generated node files into a runnable application

- [ ] Import management - collect and deduplicate all required imports
- [ ] State manager class - replace module-level globals with a `TaskStore` class
- [ ] Function namespace resolution - resolve naming conflicts
- [ ] Entry point generation - create main CLI or API entry

### Phase 2: Execution Testing

**Goal**: Validate not just syntax but runtime behavior

- [ ] Unit test generation for each leaf node
- [ ] Integration test generation for parent nodes
- [ ] Mock framework integration for data sources
- [ ] Test execution and feedback loop

### Phase 3: Enhanced Validation

**Goal**: Catch more issues at decomposition time

- [ ] Global state conservation verification
- [ ] Data operation type checking
- [ ] Contract compatibility verification between parent and children
- [ ] Cycle detection in data dependencies

### Phase 4: Cross-cutting Concerns

**Goal**: Address non-functional requirements

- [ ] Logging injection
- [ ] Error handling patterns
- [ ] Retry mechanisms for external services
- [ ] Basic caching strategies

## Architecture

```
PRD Input → Decomposer (LLM) → Node Tree → Code Generator (LLM) → Python Files
                ↑                      ↓
                └── Validation ← AST Check + Child Usage Check
```

### Key Components

| File | Purpose |
|------|---------|
| `main.py` | CLI entry point with configuration options |
| `decomposer.py` | LLM-based node decomposition with semantic stop conditions |
| `code_generator.py` | LLM-based code generation for parent and leaf nodes |
| `validator.py` | AST validation and child function usage verification |
| `models.py` | Data structures for nodes, contracts, and data sources |
| `tree_builder.py` | Recursive tree construction with depth-first traversal |

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/agent-chronos-arch.git
cd agent-chronos-arch/experiment/Tree-Centered\ Implementation/mvp

# Install dependencies
pip install openai python-dotenv
```

## Configuration

Create a `.env` file in the project root:

```
DEEPSEEK_API_KEY=your_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
```

## Usage

### Basic Usage

```bash
python main.py --input test_prd.md
python main.py --input test_prd.md --output my_output --name MySystem
python main.py --input prd.txt --max-depth 4 --max-children 6
python main.py --input prd.txt --temperature 0.2 --max-retries 5
```

### CLI Options

| Option | Default | Description |
|--------|---------|-------------|
| `--input`, `-i` | Required | Path to PRD input file |
| `--output`, `-o` | `output` | Output directory for generated files |
| `--name`, `-n` | Derived from input | System name for the root node |
| `--max-depth` | 3 | Maximum decomposition depth |
| `--max-children` | 4 | Maximum children per node |
| `--max-lines` | 50 | Lines threshold for semantic stopping |
| `--temperature`, `-t` | 0.3 | LLM temperature |
| `--max-retries` | 3 | Maximum API retries |
| `--max-decompose-retries` | 3 | Maximum decomposition retries on failure |
| `--api-key` | Env var | DeepSeek API key |
| `--base-url` | `https://api.deepseek.com` | API base URL |
| `--model` | `deepseek-chat` | Model name |
| `--timeout` | 120 | API timeout in seconds |
| `--verbose`, `-v` | False | Enable verbose output |

## Output Structure

```
output/
├── personaltaskmanager_decomposition_tree.json   # Complete tree with all node metadata
└── nodes/
    ├── root_PersonalTaskManager.py      # Root node
    ├── root_0_handle_create_task.py     # Level 1 node
    ├── root_0_0_validate_task_data.py   # Level 2 node
    └── ...                              # Leaf nodes
```

## Node Types

The system identifies three node types for stop conditions:

| Type | Description | Example |
|------|-------------|---------|
| **Pure Function** | No side effects, deterministic | `calculate_totals()`, `validate_input()` |
| **Atomic Operation** | Single operation on single data source | `store_task()`, `read_config()` |
| **Coordination** | Orchestrates multiple children | `handle_create_task()` |

## Validation

The system validates:

1. **AST Correctness** - Generated code must be syntactically valid Python
2. **Child Usage** - Parent nodes must use all declared child functions
3. **Interface Preservation** - Parent inputs/outputs match the specification

If validation fails, the system automatically re-decomposes with error feedback.

## Related Documentation

- [Tree-Centered Implementation Refinement](../../docs/Tree-Centered%20Implementation%20Refinement.md) - Full architecture specification
- [Chinese Version](../../docs/Tree-Centered%20Implementation%20Refinement-zh.md) - 中文版架构文档

## License

MIT License
