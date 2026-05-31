"""
[VERIFIED 2026-05-28] Experiment 6: Step 2 Codegen Tree Structure Review
Result: codegen correctly rejected Chat_00 routing (cannot_compose, 4 sibling_invisibility violations).
Output: output/chat00_codegen_test/deepseek-v4-flash/

Test Chat_00 decomposition with codegen to see if Phase 2 detects routing violation.
"""
import json
import os
import sys
import time

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

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output", "chat00_codegen_test", MODEL)
os.makedirs(OUTPUT_DIR, exist_ok=True)


# Load Chat_00 Phase 1 result
chat00_path = os.path.join(os.path.dirname(__file__), "output", "notraditional_moredomains", "deepseek-v4-flash", "Chat_00", "0001_response.json")
with open(chat00_path, encoding='utf-8') as f:
    chat00_data = json.load(f)

phase1_response = json.loads(chat00_data['response'])
children_phase1 = phase1_response['children']
dataflow_edges = phase1_response['dataflow_edges']

print(f"Chat_00 Phase 1 result:")
print(f"  Children: {[c['name'] for c in children_phase1]}")
print(f"  Dataflow edges: {len(dataflow_edges)}")


# Build Phase 2 system prompt (from code_generator.py)
system_prompt = """You are a decomposition verifier. Your role is to verify that a parent function CAN be correctly implemented by composing its child functions -- and if so, to generate the implementation code. Code generation IS the verification method: if composition succeeds, the decomposition is valid; if it fails, the decomposition must be rejected.

WORKFLOW -- THREE STAGES:

STAGE 1 -- TREE STRUCTURE REVIEW (before writing any code):

First, verify the decomposition satisfies tree structure constraints. These are non-negotiable structural rules:

TREE STRUCTURE RULES:
1. **Child independence**: Each child node is an independent function. A child must NOT call, reference, or depend on any sibling node.
2. **Sibling invisibility**: Children operate at the same level and have no knowledge of each other. The decomposition tree ensures that sibling nodes are isolated -- they cannot invoke each other's functions.
3. **Parent as sole orchestrator**: The parent node is the ONLY node that directly calls its children. The parent coordinates the workflow by invoking children in sequence or conditionally.
4. **Data flow goes through parent**: Data flow edges represent LOGICAL dependencies -- the parent takes one child's output and passes it as input to another child. This is the normal pattern of parent orchestration and is NOT a violation. What IS forbidden is a child directly calling or invoking a sibling function.

TRUST THE STRUCTURE, NOT THE DESCRIPTION:
The tree structure is the authoritative representation of relationships. Base your verification on structural facts, not on how nodes describe themselves.
- Tree visualization is ground truth: All nodes at the same depth under the same parent ARE siblings. This is a structural fact that overrides any ambiguous wording in behavior descriptions.
- Behavior text naming siblings explicitly IS a violation: If a node's behavior says "calls CreateOrder" and CreateOrder is a sibling, that is a clear violation.
- Behavior text with ambiguous wording that implies sibling calling IS also a violation: If a node's behavior says "calls the handler child" but the tree shows all handlers as siblings at the same depth, the structure proves these handlers are NOT its children -- the description is misleading, and what it describes IS sibling calling.
- Input source / output consumer fields are NOT evidence of direct calls: These show logical data flow that the parent resolves by passing data between children. Do not flag them.
- Generic processing terms are not violations: Words like "parse", "validate", "process", "calculate", "return result" without referencing specific sibling functions are normal single-node behavior.

DO NOT TRUST THE DECOMPOSER'S DESCRIPTION:
The decomposer may describe a node as "coordinating" or "routing" -- these are red flags. If a node's behavior describes calling or invoking other sibling nodes, that IS a violation regardless of how the decomposer frames it. The decomposer's narrative does not override structural reality.

DO NOT TRUST TRADITIONAL SOFTWARE ENGINEERING PATTERNS:
Common patterns like "Command Pattern", "Strategy Pattern", "Dispatcher", "Router", "Controller" are NOT valid in a tree decomposition. These patterns assume sibling-to-sibling communication, which violates tree structure. Do not accept a decomposition simply because it resembles familiar software architecture -- tree decomposition has its own rules that override conventional patterns.

If any tree structure check fails, the decomposition is invalid -- return cannot_compose with reason "tree_structure_violation".

STAGE 2 -- INTERFACE REVIEW (only if STAGE 1 passes):
Check whether the children's interfaces collectively satisfy ALL of the parent's requirements:
- Does every child input parameter have a clear source? (parent input, prior child output, or leaf capability)
- Can every parent output field be produced by combining child outputs?
- Is every needed data access covered by at least one child?
- Do the child signatures fit together without type mismatches?
If any check fails, the decomposition is invalid -- return cannot_compose.

STAGE 3 -- IMPLEMENT (only if STAGE 1 and STAGE 2 pass):
Write the parent function by composing child calls. Rules:
1. You MUST implement the parent function by calling the child functions
2. Child functions are NOT implemented yet - you only have their interfaces
3. Use the child function signatures exactly as provided
4. The parent function's inputs/outputs must match the specification
5. You may use: conditionals, loops, local variables, helper logic
6. DO NOT directly read or write global state - delegate ALL data operations to child functions
7. Parent function should only orchestrate child calls, not perform data operations
8. CRITICAL -- Every value in the parent's return statement MUST originate from a child output or a parent input.
   If a child is missing that should produce this data, the composition has failed.

SIGNATURE ENFORCEMENT - YOUR FUNCTION SIGNATURE IS LOCKED:
- Your function's parameter names, types, and return type are specified and non-negotiable
- The signature shown in the user prompt is the EXACT contract the caller expects
- Do NOT add, remove, or rename parameters
- Do NOT change parameter types or return type
- The verifier strictly checks signature compliance

DATA SOURCE OPERATIONS:
- Each child has declared data_operations that specify which data source it operates on
- The parent must NOT directly access any data source - only children can do that
- If you need to read/write data, ensure a child is responsible for it

The code you generate will be validated:
- It must be syntactically correct Python
- It must use the child function interfaces correctly
- It must NOT directly read/write any data source (only through child calls)
- It must preserve the parent's input/output contract

Return ONLY valid JSON with this structure:
{
  "code": "def parent_function(...): ...",
  "status": "ok | cannot_compose",
  "imports": ["import os", "from typing import ..."],
  "child_calls": ["child1", "child2"],
  "implementation_notes": "Brief explanation of the logic",
  "decomposition_feedback": {
    "reason": "tree_structure_violation | missing_child_input_source | missing_child_capability | invalid_child_boundary | wrong_child_signature | cannot_satisfy_parent_output | other",
    "offending_child": "ChildName or empty",
    "violations": [
      {
        "from_node": "name of node that violates",
        "to_node": "name of node being called/referenced",
        "rule": "which rule is violated",
        "details": "why this is a violation"
      }
    ],
    "missing_inputs": [
      {
        "child": "ChildName",
        "param": "param_name",
        "why_needed": "why this input is needed",
        "expected_source": "parent input / previous child output / new child output"
      }
    ],
    "direct_resource_accesses": [
      {
        "resource": "resource_name",
        "operation": "read",
        "why_needed": "why this resource access is needed"
      }
    ],
    "suggested_fix": "Concrete suggestion for re-decomposition",
    "requires_redecomposition": true
  }
}"""


# Build user prompt with Chat_00's children
def build_user_prompt(children, dataflow_edges):
    lines = [
        "Verify and implement the following parent function by composing its children.",
        "",
        "Parent Function: ChatApp",
        "Purpose: Handle real-time messaging operations",
        "",
        "Inputs:",
        "  - command: str - Command to execute (send/history/create_channel/join)",
        "  - message_data: dict - JSON with content, channel_id, user_id, channel_name fields",
        "",
        "Outputs:",
        "  - result: dict - JSON with success, data, and message fields",
        "",
        "Children:",
    ]

    for child in children:
        lines.append(f"  - {child['name']}: {child['purpose']}")
        lines.append(f"    Behavior: {child['behavior']}")
        lines.append(f"    Signature: def {child['name']}(message_data: dict) -> dict")
        lines.append("")

    lines.append("Dataflow Edges:")
    for edge in dataflow_edges:
        lines.append(f"  {edge['from_node']}:{edge['from_output']} -> {edge['to_node']}:{edge['to_input']} ({edge['note']})")

    lines.append("")
    lines.append("Available Data Stores:")
    lines.append("  - messages (memory, read_write): Stores messages keyed by message_id.")
    lines.append("  - channels (memory, read_write): Stores channel info keyed by channel_id.")

    return "\n".join(lines)


user_prompt = build_user_prompt(children_phase1, dataflow_edges)

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
    sys.exit(1)
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
    import re
    m = re.search(r'\{.*\}', response_text, re.DOTALL)
    if m:
        try:
            parsed = json.loads(m.group())
        except:
            print("Failed to parse JSON")
            print(response_text[:1000])
            sys.exit(1)
    else:
        print("No JSON found in response")
        print(response_text[:1000])
        sys.exit(1)

# Analyze result
print(f"\n{'='*60}")
print(f"CODEGEN RESULT")
print(f"{'='*60}")
print(f"Status: {parsed.get('status', 'unknown')}")
print(f"Child calls: {parsed.get('child_calls', [])}")
print(f"Implementation notes: {parsed.get('implementation_notes', 'N/A')}")

if parsed.get('status') == 'cannot_compose':
    print(f"\n** CANNOT_COMPOSE - Decomposition rejected **")
    feedback = parsed.get('decomposition_feedback', {})
    print(f"Reason: {feedback.get('reason', 'N/A')}")
    print(f"Offending child: {feedback.get('offending_child', 'N/A')}")
    print(f"Suggested fix: {feedback.get('suggested_fix', 'N/A')}")
else:
    print(f"\n** OK - Decomposition accepted **")
    code = parsed.get('code', '')
    print(f"\nGenerated code:")
    print(code[:500] if len(code) > 500 else code)

# Save parsed result
with open(os.path.join(OUTPUT_DIR, "parsed.json"), "w", encoding="utf-8") as f:
    json.dump(parsed, f, indent=2, ensure_ascii=False)

print(f"\nOutput: {OUTPUT_DIR}")
