"""
Interactive decomposition debug: let LLM decompose, then neutrally ask about its design.
No leading questions — just "explain your design."
"""
import json
import os
from openai import OpenAI

api_key = os.getenv("DEEPSEEK_API_KEY")
client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com", timeout=120)

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

OUTPUT FORMAT - You MUST return valid JSON with this exact structure:
{
  "children": [...],
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
Maximum depth: 5
Return ONLY the JSON response."""

print("=" * 60)
print("DECOMPOSE Expense_prd")
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
    print(f"  [{i}] {c['name']}: {c['purpose'][:100]}")
    print(f"      stop={c.get('stop_decompose')}, type={c.get('node_type')}")

print(f"\n{'=' * 60}")
print("EXPLAIN YOUR DESIGN")
print("=" * 60)

names = [c['name'] for c in children]
purposes = [c['purpose'] for c in children]
listing = "\n".join(f"  - {n}: {p}" for n, p in zip(names, purposes))

followup = f"""You decomposed Expense_prd into these children:

{listing}

Please explain your design decisions:

1. Walk through how the parent function Expense_prd implements its functionality by using these children. What does the parent's code look like?

2. For each child, what is its relationship to the other children? Does it use any other child's output? Does it call any other child?

3. If the parent calls one child, does that affect whether it calls other children? Explain how the children work together."""

response2 = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": "You are a software architect explaining your design decisions in plain text."},
        {"role": "user", "content": followup}
    ],
    temperature=0.2,
    max_tokens=4096
)

print(f"\n{response2.choices[0].message.content}")

print(f"\n{'=' * 60}")
print("RULE-BY-RULE SELF-ASSESSMENT")
print("=" * 60)

followup3 = f"""You decomposed Expense_prd into these children:

{listing}

Now, go through each rule in the system prompt (the one you received for decomposition) one by one and explain how YOUR ACTUAL decomposition above addresses that rule.

The rules were:

1. EVERY CHILD MUST BE A FUNCTION, NOT A CLASS.
2. Each child must have explicit: name, purpose, inputs, outputs, and boundary
3. Preserve the parent's external interface - children's composition must match parent's inputs/outputs
4. Do NOT add extra external inputs or outputs beyond what the parent has
5. Children should be at the same abstraction level and minimally overlapping

For EACH rule, answer:
- Does your decomposition satisfy this rule? Why or why not?
- How did you think about this rule when designing the decomposition?

Go through them in order (1→5), one at a time. Be specific. Reference the actual child names from the listing above."""

response3 = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": "You are a software architect explaining your design decisions in plain text. Be precise and thorough."},
        {"role": "user", "content": followup3}
    ],
    temperature=0.2,
    max_tokens=4096
)

print(f"\n{response3.choices[0].message.content}")
