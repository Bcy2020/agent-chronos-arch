# MVP-0.2.0 — Json PRD & Structured Decomposition

## Version Description

MVP-0.2.0 introduces two key improvements over MVP-0.0: **Json PRD** and **SubPRD**, designed to address the loss and distortion of PRD information during decomposition across tree levels.

### Key Improvements

| Improvement | Description |
|-------------|-------------|
| **Json PRD** | Uses LLM to convert natural language PRD into structured JSON, explicitly extracting functional requirements, global state, and I/O specifications |
| **SubPRD** | Each node carries a sub-PRD containing the subset of functional requirements and global state operations relevant to that node's scope |
| **Global State Operation Tracking** | Explicitly tracks each node's global state operations (read/write/read_write) |
| **Conservation Check** | Validates that the parent's global operations are fully covered by its children |
| **Auto Derivation** | Automatically derives StateOperation from GlobalVar declarations |

### Differences from MVP-0.0

- Added `prd_converter.py` — PRD structured converter
- Added data models: `JsonPRD`, `SubPRD`, `StateOperation`, `FunctionalRequirement`
- `GlobalVar` uses `variable`/`op` fields instead of `name`/`type`/`access`
- `InputParam`/`OutputParam` now have `source`/`consumer` fields
- Validator now includes global operation conservation checking
- All descriptive content switched from Chinese to English

### Limitations

- ❌ Generated code is still not runnable (no code pipeline)
- ❌ LLM sometimes returns malformed JSON that cannot be parsed
- ❌ Information loss during decomposition is partially mitigated but not fully resolved

---

## File Structure

| File | Role |
|------|------|
| `main.py` | CLI entry point, supports Json PRD mode |
| `tree_builder.py` | Core controller, adds global operation auto-derivation and conservation check |
| `decomposer.py` | LLM node decomposer, integrates SubPRD |
| `code_generator.py` | LLM code generator |
| `validator.py` | Validator, adds global state conservation check |
| `models.py` | Data models (new: JsonPRD, SubPRD, etc.) |
| `config.py` | Configuration parameters |
| `api_client.py` | DeepSeek API client |
| `prd_converter.py` | **New** — PRD natural language → structured JSON |
| `node_schema.json` | Decomposition tree node JSON Schema |

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

On first run, the system calls the LLM to convert the PRD into a structured Json PRD, cached at `output/.chronos/prd.json`. Subsequent runs will automatically load the cached Json PRD.

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--input` / `-i` | Required | Path to PRD input file |
| `--output` / `-o` | `output` | Output directory |
| `--name` / `-n` | Derived from filename | System name |
| `--max-depth` | `3` | Maximum decomposition depth |
| `--max-children` | `4` | Maximum children per node |
| `--temperature` / `-t` | `0.3` | LLM temperature |
| `--max-retries` | `3` | Max code generation retries |
| `--max-decompose-retries` | `3` | Max re-decomposition retries |
| `--model` | `deepseek-chat` | LLM model name |
| `--verbose` / `-v` | No | Enable verbose output |

### Output Structure

```
output/
├── .chronos/
│   └── prd.json              # Cached Json PRD
├── decomposition_tree.json   # Full decomposition tree
├── build.log                 # Build log
└── nodes/                    # Generated code files
    ├── root_System.py
    └── ...
```

### Examples

```bash
# Basic usage
python main.py --input test_prd.md

# Custom depth
python main.py --input test_prd.md --max-depth 5 --max-children 4
```

---

## Architecture Flow

```
PRD Document
    │
    ▼
PRDConverter ──► Json PRD (structured) ──► cached to .chronos/prd.json
    │
    ▼
TreeBuilder (core loop)
    ├── Auto-derive global state operations
    ├── Decomposer (LLM decomposition + SubPRD assignment to children)
    ├── Global state conservation check
    ├── CodeGenerator (LLM code generation)
    └── Validator (syntax + interface + conservation)
```

### Json PRD Conversion Process

At runtime, `prd_converter.py` converts a natural language PRD into JSON containing the following structure:

- **Functional Requirements** — FR-001, FR-002...
- **Non-Functional Requirements**
- **Acceptance Criteria**
- **Technical Constraints** — storage, concurrency, UI, etc.
- **Global State Sources** — all shared data stores
- **Input/Output Spec** — format, schema, examples

### Global State Conservation

Every node's global operations follow the conservation law:

```
Parent global operations = Σ(Child global operations)
```

- All of the parent's global operations must be fully assigned to children
- No global operation may "disappear" during decomposition
- The validator checks conservation; violations trigger re-decomposition

---

## Test Results

Tested with `test_prd.md` (Personal Task Manager), output in `output-test/` directory:

| Metric | Value |
|--------|-------|
| Total Nodes | 28 |
| Passed Validation | 28/28 |
| Json PRD Functional Requirements | 4 |
| Global State Sources | 2 (tasks, next_id) |

For a detailed decomposition quality assessment, see [output-test/decomposition_quality_report.md](output-test/decomposition_quality_report.md)
