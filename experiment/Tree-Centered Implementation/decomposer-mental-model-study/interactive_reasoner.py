"""
Decomposition with deepseek-reasoner to trace chain of thought.
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
4. Do NOT add extra external inputs or outputs beyond what the parent has
5. Children should be at the same abstraction level and minimally overlapping

SIGNATURE LOCKING - CHILD INTERFACES ARE BINDING CONTRACTS:
- Each child's declared inputs/outputs become a LOCKED signature that code generators MUST follow exactly
- Use precise Python types

SEMANTIC STOP CONDITIONS:
STOP DECOMPOSITION when the node is PURE FUNCTION, ATOMIC OPERATION, or MAX DEPTH REACHED.

Return ONLY valid JSON with this structure:
{
  "children": [{"name": "...", "purpose": "...", ...}],
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
print("DECOMPOSE with reasoner (chain-of-thought)")
print("=" * 60)

response = client.chat.completions.create(
    model="deepseek-reasoner",
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ],
    temperature=0.2,
    max_tokens=8192
)

# Print reasoning/chain of thought
reasoning = response.choices[0].message.reasoning_content
if reasoning:
    print(f"\n{'=' * 60}")
    print("CHAIN OF THOUGHT")
    print(f"{'=' * 60}")
    print(reasoning)

# Print final answer
content = response.choices[0].message.content
print(f"\n{'=' * 60}")
print("DECOMPOSITION RESULT")
print(f"{'=' * 60}")
print(content[:3000])

# Parse and display children
try:
    result = json.loads(content)
    children = result.get("children", [])
    rationale = result.get("decomposition_rationale", "")
    print(f"\nRationale: {rationale}\n")
    print(f"Children ({len(children)}):")
    for i, c in enumerate(children):
        print(f"  [{i}] {c['name']}: {c.get('purpose', 'N/A')[:100]}")
except:
    print("(Could not parse JSON)")
