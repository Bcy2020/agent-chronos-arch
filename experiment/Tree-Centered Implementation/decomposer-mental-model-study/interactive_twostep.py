"""
Two-step decomposition: decompose, then self-review against ALL requirements.
No guiding — just "check and decide if correction is needed."
"""
import json
import os
from openai import OpenAI

api_key = os.getenv("DEEPSEEK_API_KEY")
client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com", timeout=180)

system_prompt = """You are a software system decomposition agent. Your task is to decompose a function block into smaller child function blocks.

CRITICAL RULES - ENFORCED:
1. EVERY CHILD MUST BE A FUNCTION, NOT A CLASS.
2. Each child must have explicit: name, purpose, inputs, outputs, and boundary
3. Preserve the parent's external interface - children's composition must match parent's inputs/outputs
4. The parent function MUST call every child directly. Do NOT create any child whose purpose would prevent the parent from also calling all other children.
5. Do NOT add extra external inputs or outputs beyond what the parent has
6. Children should be at the same abstraction level and minimally overlapping

SIGNATURE LOCKING - CHILD INTERFACES ARE BINDING CONTRACTS:
- Each child's declared inputs/outputs become a LOCKED signature that code generators MUST follow exactly
- Use precise Python types

SEMANTIC STOP CONDITIONS:
STOP DECOMPOSITION when the node is PURE FUNCTION, ATOMIC OPERATION, or MAX DEPTH REACHED.

Return ONLY valid JSON with this structure:
{
  "children": [{"name": "...", "purpose": "...", "inputs": [...], "outputs": [...], "boundary": {...}, "global_vars": [...], "requested_capabilities": [...]}],
  "decomposition_rationale": "...",
  "dataflow_edges": []
}"""

user_prompt = """Decompose the following function block:

Node Name: Expense_prd
Node Purpose: Expense Tracker - A system that allows users to add, list, update, delete, and get summary of expense records.

Inputs:
  - input: dict - The raw user input containing command and expense_data

Outputs:
  - result: dict - Response with success status, message, and data

Boundary:
  In Scope: Parse input, handle CRUD operations on expenses, compute summary
  Out of Scope: Authentication, user management

Data Sources:
  - expenses (list, read_write): In-memory list of expense records
  - next_id (dict, read_write): Auto-incrementing ID counter

Available Data Interfaces:
  - expenses.get: def get_expense(expense_id: int) -> dict | None
  - expenses.list: def list_expenses(category_filter: str = None, start_date: str = None, end_date: str = None) -> list
  - expenses.create: def create_expense(amount: float, category: str, description: str = '', date: str = None) -> dict
  - expenses.update: def update_expense(expense_id: int, amount: float = None, category: str = None, description: str = None) -> dict | None
  - expenses.delete: def delete_expense(expense_id: int) -> bool
  - expenses.exists: def expense_exists(expense_id: int) -> bool
  - next_id.get: def get_next_id() -> int
  - next_id.update: def increment_next_id() -> int

Maximum children allowed: 8
Maximum depth: 5"""

print("=" * 60)
print("STEP 1: DECOMPOSE Expense_prd")
print("=" * 60)

response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ],
    temperature=0.2,
    max_tokens=8192,
    response_format={"type": "json_object"}
)

result = json.loads(response.choices[0].message.content)
children = result.get("children", [])
rationale = result.get("decomposition_rationale", "")

print(f"\nRationale: {rationale}\n")
print(f"Children ({len(children)}):")
for i, c in enumerate(children):
    print(f"  [{i}] {c['name']}: {c.get('purpose', 'N/A')[:120]}")
    print(f"      stop={c.get('stop_decompose')}, type={c.get('node_type')}")

names = [c['name'] for c in children]
purposes = [c.get('purpose', '') for c in children]
listing = "\n".join(f"  - {n}: {p}" for n, p in zip(names, purposes))

# Store the initial decomposition
initial_decomposition = json.dumps(result, indent=2, ensure_ascii=False)

print(f"\n{'=' * 60}")
print("STEP 2: SELF-REVIEW — CHECK AGAINST ALL REQUIREMENTS")
print("=" * 60)

review_prompt = f"""Below is a decomposition you produced for Expense_prd. Now, review it against all the requirements you were given.

YOUR DECOMPOSITION:
{listing}

REQUIREMENTS TO CHECK:
1. EVERY CHILD MUST BE A FUNCTION, NOT A CLASS.
2. Each child must have explicit: name, purpose, inputs, outputs, and boundary
3. Preserve the parent's external interface — children's composition must match parent's inputs/outputs
4. The parent function MUST call every child directly. Do NOT create any child whose purpose would prevent the parent from also calling all other children.
5. Do NOT add extra external inputs or outputs beyond what the parent has
6. Children should be at the same abstraction level and minimally overlapping

For EACH requirement, state:
- PASS or FAIL (based on strict checking of your actual decomposition above)
- Your reasoning

After checking all requirements, state your final verdict:
- If ALL PASS: "VERDICT: ACCEPT"
- If any FAIL: "VERDICT: CORRECT" — and then produce a CORRECTED decomposition in the same JSON format as before."""

response2 = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": "You are a strict code reviewer. You check decompositions against requirements objectively. You do not suggest changes unless requirements are violated."},
        {"role": "user", "content": review_prompt}
    ],
    temperature=0.2,
    max_tokens=4096,
    response_format={"type": "json_object"}
)

content2 = response2.choices[0].message.content
print(f"\n{content2}")
