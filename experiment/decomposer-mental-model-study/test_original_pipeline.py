"""
Test original pipeline's decomposer prompts with library JSON PRD.
Reproduces the exact prompts from mvp-0.4.4/decomposer.py.
"""
import json
import os
import sys
import time
import re

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from openai import OpenAI

# Config
def _env(key, default=""):
    return os.getenv(key) or os.getenv(f"DEEPSEEK_{key.removeprefix('CHRONOS_')}") or default

BASE_URL = _env("CHRONOS_BASE_URL", "https://api.deepseek.com")
API_KEY = _env("CHRONOS_API_KEY")
MODEL = _env("CHRONOS_MODEL", "deepseek-chat")
TEMPERATURE = float(os.getenv("CHRONOS_TEMPERATURE", "0.3"))

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output", "original_pipeline", MODEL)
os.makedirs(OUTPUT_DIR, exist_ok=True)


# Original pipeline's system prompt (exact copy from decomposer.py)
def build_system_prompt():
    return """You are a software system decomposition agent. Your task is to decompose a function block into smaller child function blocks.

CRITICAL RULES - ENFORCED:
1. EVERY CHILD MUST BE A FUNCTION, NOT A CLASS. Never generate class definitions for child blocks.
2. Each child must have explicit: name, purpose, inputs, outputs, and boundary
3. Preserve the parent's external interface - children's composition must match parent's inputs/outputs
4. TREE STRUCTURE (not graph): The decomposition forms a tree, not a graph. Children MUST NOT call each other (no cross-calls between siblings). The parent MUST explicitly and directly invoke all its children. A coordinator child node is ALLOWED, as long as it only coordinates work within its own subtree and never calls sibling nodes.
5. Do NOT add extra external inputs or outputs beyond what the parent has
6. Children should be at the same abstraction level and minimally overlapping

SIGNATURE LOCKING - CHILD INTERFACES ARE BINDING CONTRACTS:
- Each child's declared inputs/outputs become a LOCKED signature that code generators MUST follow exactly
- Use precise Python types: str, int, float, bool, dict, list, Optional[dict], List[str], Dict[int, str], Tuple[str, int], Any, None
- Do NOT invent unnecessary parameters - a child should only receive what it needs to do its job
- Do NOT use generic "Any" when a specific type is known - precision enables signature validation
- Example CORRECT: inputs=[{"name": "task_id", "type": "int", "description": "ID of the task to validate"}]
- Example WRONG:   inputs=[{"name": "task_id", "type": "Any", "description": "the task id"}]
- The verifier will reject code that does not match the declared signature exactly

SEMANTIC STOP CONDITIONS - Use these instead of line-count estimation:
STOP DECOMPOSITION when the node is ONE of the following types:

1. PURE FUNCTION: The node performs only mathematical transformations with no:
   - Global/state variable dependencies (except parameters)
   - I/O operations (file, network, database)
   - Side effects or state modifications
   Example: calculate_totals(prices, tax_rate) -> total

2. ATOMIC OPERATION: The node performs exactly one operation on exactly one data source:
   - Read from a single data source (database, cache, file)
   - Write to a single data source
   - Read-modify-write on a single data source
   Example: reserve_inventory(product_id, quantity) -> bool

3. MAXIMUM DEPTH REACHED: Tree has reached the configured maximum depth

DO NOT STOP if the node:
- Contains business logic, branching, or loops
- Coordinates multiple child operations
- Transforms data between multiple sources
- Contains conditional validation logic

DATAFLOW CLOSURE RULES:
1. Every child input must have an explicit source.
2. A child input source must be one of:
   - a parent input,
   - an output of an earlier sibling child,
   - a local constant/config value explicitly described,
   - data obtained inside that same leaf through requested_capabilities.
3. If a child needs data that no previous child outputs and no parent input provides, add a child before it to produce that data, or move the data access inside that child as a leaf capability.
4. Do not create child signatures with dangling parameters such as products_data unless a previous child outputs products_data.
5. Parent must not directly access global state or data interfaces — all data operations must go through child function calls.

OUTPUT FORMAT - You MUST return valid JSON with this exact structure:
{
  "children": [
    {
      "name": "ChildName",
      "purpose": "Clear description of what this child function does",
      "inputs": [{"name": "param", "type": "str", "description": "desc", "source": "where data comes from"}],
      "outputs": [{"name": "result", "type": "int", "description": "desc", "consumer": "who uses this output"}],
      "boundary": {"in_scope": ["..."], "out_of_scope": ["..."]},
      "preconditions": ["..."],
      "postconditions": ["..."],
      "behavior": "Detailed description of expected behavior - how this function transforms inputs to outputs",
      "signature": "def ChildName(param1: type1, param2: type2) -> return_type",
      "stop_decompose": false,
      "stop_reason": "",
      "node_type": "pure_function|atomic_operation",
      "data_operations": [
        {"source_name": "data_source_name", "operation_type": "read|write|read_write", "description": "what operation is performed"}
      ],
      "constraints": [{"constraint_id": "C-001", "description": "constraint description"}],
      "acceptance_criteria": [{"ac_id": "AC-001", "description": "criterion description", "verification_method": "automated_test"}],
      "global_vars": [
        {"variable": "data_store_name", "op": "read|write|read_write", "description": "what operation is needed"}
      ],
      "traceability": {"parent_requirement_ids": ["FR-001"], "derived_from": "root"},
      "requested_capabilities": ["resource.operation", "resource.operation"]
    }
  ],
  "data_sources": [
    {"name": "source_name", "category": "database|file|cache|external|memory", "access": "read|write|read_write", "data_type": "dict|list|object", "description": "description"}
  ],
  "decomposition_rationale": "CRITICAL: Explain HOW these children work together to implement the parent. Describe the interaction flow, data transformation, and how they collectively cover ALL parent responsibilities. This is required for the code generator to understand how to compose these functions.",
  "interface_preservation": {
    "parent_inputs_covered_by": {"input_name": "child_name"},
    "parent_outputs_produced_by": {"output_name": "child_name"}
  },
  "dataflow_edges": [
    {
      "from_node": "parent | ChildName",
      "from_output": "parent_input_or_child_output_name",
      "to_node": "ChildName | parent",
      "to_input": "child_input_or_parent_output_name",
      "note": "why this dataflow exists"
    }
  ]
}

CRITICAL GLOBAL VARIABLES DISTRIBUTION RULE:
The parent's "global_vars" declares which data variables the subtree operates on and what operations are needed (read/write/read_write).
You MUST distribute these global_vars among children based on their responsibilities:
- A child that performs read/write on a variable declares the corresponding "global_vars"
- Each child's global_vars MUST be a subset of the parent's global_vars
- The union of all children's global_vars MUST cover all of the parent's declared operations on each variable"""


# Original pipeline's user prompt (exact copy from decomposer.py)
def build_user_prompt_from_prd(prd_json):
    """Build user prompt from JSON PRD, mimicking the original pipeline's format."""
    lines = [
        "Decompose the following function block:",
        "",
        f"Node Name: {prd_json['metadata']['project_name']}",
        f"Node Purpose: {prd_json['metadata']['project_name']}",
        "",
        "SubPRD Context:",
    ]

    # Task Description with INPUT/OUTPUT FORMAT
    lines.append("  Task Description:")

    # Find input/output format from functional requirements
    # The library PRD has command-based input format
    input_format = None
    output_format = None
    for fr in prd_json.get('functional_requirements', []):
        if 'input' in fr.get('description', '').lower():
            pass

    # Build input format from the PRD structure
    # For library: command + book_data
    lines.append("    INPUT FORMAT:")
    lines.append("      Format: json")
    lines.append("      Description: Input is a JSON object with command and book_data fields.")
    lines.append("      Schema:")
    lines.append("        command: string (add|list|borrow|return|remove)")
    lines.append("        book_data: {'title': 'string (required for add)', 'author': 'string (required for add)', 'book_id': 'integer (required for borrow/return/remove)', 'status_filter': 'string (optional for list: available/borrowed/all)'}")
    lines.append("      Examples:")
    lines.append('        {"command": "add", "book_data": {"title": "Python编程", "author": "John"}}')
    lines.append('        {"command": "list", "book_data": {"status_filter": "all"}}')
    lines.append('        {"command": "borrow", "book_data": {"book_id": 1}}')
    lines.append('        {"command": "return", "book_data": {"book_id": 1}}')
    lines.append('        {"command": "remove", "book_data": {"book_id": 1}}')
    lines.append("")

    lines.append("    OUTPUT FORMAT:")
    lines.append("      Format: json")
    lines.append("      Description: Output is a JSON object with success, message, and data fields.")
    lines.append("      Schema:")
    lines.append("        success: boolean")
    lines.append("        message: string")
    lines.append("        data: object (varies by operation)")
    lines.append("      Examples:")
    lines.append('        {"success": true, "message": "书籍添加成功，ID=1", "data": {"book_id": 1}}')
    lines.append('        {"success": true, "message": "共1本书", "data": {"books": [{"id": 1, "title": "Python编程", "author": "John", "status": "available"}]}}')
    lines.append('        {"success": true, "message": "书籍借出成功", "data": {"book_id": 1}}')
    lines.append('        {"success": true, "message": "书籍归还成功", "data": {"book_id": 1}}')
    lines.append('        {"success": true, "message": "书籍删除成功", "data": {"book_id": 1}}')
    lines.append("")

    # Functional Requirements
    lines.append("    Functional Requirements:")
    for fr in prd_json.get('functional_requirements', []):
        lines.append(f"    [{fr['fr_id']}] {fr['title']}: {fr['description']}")
    lines.append("")

    # Constraints
    lines.append("  Constraints:")
    for nfr in prd_json.get('non_functional_requirements', []):
        lines.append(f"    - {nfr['nfr_id']}: {nfr['description']}")
    lines.append("")

    # Acceptance Criteria
    lines.append("  Acceptance Criteria:")
    for ac in prd_json.get('acceptance_criteria', []):
        lines.append(f"    - {ac['ac_id']}: {ac['description']}")
    lines.append("")

    # Inputs/Outputs
    lines.append("Inputs:")
    lines.append("  - command: str - Command to execute")
    lines.append("  - book_data: dict - Data for the command")
    lines.append("")
    lines.append("Outputs:")
    lines.append("  - result: dict - JSON with success, message, data")
    lines.append("")

    # Boundary
    lines.append("Boundary:")
    lines.append("  In Scope: Book management operations (add, list, borrow, return, remove)")
    lines.append("  Out of Scope: Authentication, persistence, UI")
    lines.append("")

    # Data Sources
    lines.append("Data Sources (AVAILABLE DATA STORES):")
    lines.append("  - books (memory, read_write): Dict mapping book_id to {title, author, status}")
    lines.append("")

    # Global Variables
    lines.append("Global Variables (MUST be DISTRIBUTED to children):")
    lines.append("  - read_write on books: Book storage dictionary")
    lines.append("  - read_write on next_id: Auto-increment ID counter")
    lines.append("")
    lines.append("  >>> Each child must declare a SUBSET of these global_vars in the 'global_vars' field. <<<")
    lines.append("  >>> Children perform actual data operations; parent orchestrates by calling children. <<<")

    return "\n".join(lines)


def main():
    if not API_KEY:
        print("ERROR: Set CHRONOS_API_KEY (or DEEPSEEK_API_KEY)")
        return 1

    print(f"API: {BASE_URL}")
    print(f"Model: {MODEL}")

    # Load library JSON PRD
    prd_path = os.path.join(os.path.dirname(__file__), "..", "..", "mvp", "mvp-0.4.4", "tests", "output", "test_failure_context_flow", "library", ".chronos", "prd.json")
    with open(prd_path, encoding='utf-8') as f:
        prd_json = json.load(f)

    print(f"PRD: {prd_json['metadata']['project_name']}")

    # Build prompts
    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt_from_prd(prd_json)

    # Save prompts
    with open(os.path.join(OUTPUT_DIR, "system_prompt.txt"), "w", encoding="utf-8") as f:
        f.write(system_prompt)
    with open(os.path.join(OUTPUT_DIR, "user_prompt.txt"), "w", encoding="utf-8") as f:
        f.write(user_prompt)

    print(f"\nSystem prompt: {len(system_prompt)} chars")
    print(f"User prompt: {len(user_prompt)} chars")

    # Call LLM
    print(f"\nCalling LLM...")
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL, timeout=120)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    # Save request
    with open(os.path.join(OUTPUT_DIR, "request.json"), "w", encoding="utf-8") as f:
        json.dump({"messages": messages, "model": MODEL, "temperature": TEMPERATURE}, f, indent=2, ensure_ascii=False)

    start = time.time()
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=TEMPERATURE,
            max_tokens=16384,
            response_format={"type": "json_object"},
        )
        response_text = resp.choices[0].message.content
    except Exception as e:
        print(f"ERROR: {e}")
        return 1
    elapsed = time.time() - start

    # Save response
    with open(os.path.join(OUTPUT_DIR, "response.json"), "w", encoding="utf-8") as f:
        json.dump({"response": response_text, "elapsed": round(elapsed, 2)}, f, indent=2, ensure_ascii=False)

    print(f"Response: {len(response_text)} chars, {elapsed:.1f}s")

    # Parse response
    try:
        parsed = json.loads(response_text)
    except json.JSONDecodeError:
        # Try to extract JSON
        m = re.search(r'\{.*\}', response_text, re.DOTALL)
        if m:
            try:
                parsed = json.loads(m.group())
            except:
                print("Failed to parse JSON")
                print(response_text[:1000])
                return 1
        else:
            print("No JSON found in response")
            print(response_text[:1000])
            return 1

    # Analyze children
    children = parsed.get('children', [])
    print(f"\nChildren: {len(children)}")
    for c in children:
        name = c.get('name', '')
        purpose = c.get('purpose', '')
        behavior = c.get('behavior', '')
        print(f"\n  {name}:")
        print(f"    purpose: {purpose[:100]}")
        print(f"    behavior: {behavior[:150]}")

        # Check for routing pattern
        combined = (purpose + ' ' + behavior).lower()
        if any(kw in combined for kw in ['calls the', 'call the', 'invoke', 'dispatch', 'route', 'coordinate', 'handler']):
            print(f"    ** ROUTING PATTERN DETECTED **")

    # Save parsed result
    with open(os.path.join(OUTPUT_DIR, "parsed.json"), "w", encoding="utf-8") as f:
        json.dump(parsed, f, indent=2, ensure_ascii=False)

    print(f"\nOutput: {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
