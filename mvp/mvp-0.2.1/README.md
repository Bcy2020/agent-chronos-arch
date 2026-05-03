# MVP-0.2.1 — JSON Output Mode Enforcement

## Version Description

MVP-0.2.1 has **identical code structure** to MVP-0.2.0, with a single change in `api_client.py`: adding `response_format={"type": "json_object"}` to LLM calls.

### Key Improvement

| Improvement | Description |
|-------------|-------------|
| **JSON Output Enforcement** | Forces the LLM to always return valid JSON via API parameter, fundamentally solving JSON parsing failures |

This change is small but significant. In MVP-0.2.0, the LLM occasionally returned non-JSON responses (interspersed with explanatory text, Markdown code block markers, etc.), causing parsing failures in `PRDConverter` and `Decomposer`. By enabling JSON mode at the API level, the LLM's output is guaranteed to be valid JSON.

### Difference from MVP-0.2.0

The only code change is in `api_client.py`:

```python
# MVP-0.2.0
response = self.client.chat.completions.create(
    model=self.config.model,
    messages=messages,
    temperature=temp,
    max_tokens=max_tokens
)

# MVP-0.2.1
response = self.client.chat.completions.create(
    model=self.config.model,
    messages=messages,
    temperature=temp,
    max_tokens=max_tokens,
    response_format={"type": "json_object"}  # ← New
)
```

> **Note**: `response_format={"type": "json_object"}` requires support from the underlying LLM model. Newer DeepSeek and OpenAI models both support this parameter.

### Limitations

- ❌ Generated code is still not runnable (no code pipeline)
- ❌ JSON mode may not be supported or may behave differently on some models

---

## File Structure

Identical to MVP-0.2.0:

| File | Role |
|------|------|
| `main.py` | CLI entry point |
| `tree_builder.py` | Core controller |
| `decomposer.py` | LLM node decomposer |
| `code_generator.py` | LLM code generator |
| `validator.py` | Validator |
| `models.py` | Data models |
| `config.py` | Configuration parameters |
| `api_client.py` | **Modified** — enables JSON output mode |
| `prd_converter.py` | PRD structured converter |
| `node_schema.json` | Node JSON Schema |

---

## Usage

### Requirements

- Python 3.10+
- `openai` Python package
- DeepSeek API key (must support JSON output mode)

### Installation & Run

```bash
pip install openai
set DEEPSEEK_API_KEY=your_api_key_here
python main.py --input test_prd.md --output ./output
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--input` / `-i` | Required | Path to PRD input file |
| `--output` / `-o` | `output` | Output directory |
| `--max-depth` | `3` | Maximum decomposition depth |
| `--max-children` | `4` | Maximum children per node |
| `--temperature` / `-t` | `0.3` | LLM temperature |
| `--max-retries` | `3` | Max code generation retries |
| `--max-decompose-retries` | `3` | Max re-decomposition retries |
| `--model` | `deepseek-chat` | LLM model name |

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

---

## Architecture Flow

```
PRD Document
    │
    ▼
PRDConverter ──► Json PRD (JSON mode enforced) ──► .chronos/prd.json
    │
    ▼
TreeBuilder (core loop)
    ├── Auto-derive global state operations
    ├── Decomposer (LLM decomposition, JSON mode enforced)
    ├── Global state conservation check
    ├── CodeGenerator (LLM code generation, JSON mode enforced)
    └── Validator (syntax + interface + conservation)
```

### Impact of JSON Mode

With `response_format={"type": "json_object"}` enabled:

- `PRDConverter` PRD→JSON conversion no longer fails due to parsing exceptions
- `Decomposer` decomposition result JSON parsing is more stable
- `CodeGenerator` code generation results are always well-formed JSON
- Overall pipeline is more reliable, with fewer silent failures caused by parsing errors
