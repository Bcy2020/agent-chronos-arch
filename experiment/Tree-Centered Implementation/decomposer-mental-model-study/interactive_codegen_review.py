"""
Interactive codegen STAGE 1 REVIEW study.
Presents a decomposition WITH RouteCommand as a child and asks the LLM
to apply the exact STAGE 1 REVIEW rules from code_generator.py.
No guiding — just observe whether it catches RouteCommand or not.
"""
import json
import os
from openai import OpenAI

api_key = os.getenv("DEEPSEEK_API_KEY")
client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com", timeout=180)

# The EXACT STAGE 1 REVIEW prompt from code_generator.py _build_system_prompt_for_parent()
review_system_prompt = """You are a decomposition verifier. Your role is to verify that a parent function CAN be correctly implemented by composing its child functions — and if so, to generate the implementation code. Code generation IS the verification method: if composition succeeds, the decomposition is valid; if it fails, the decomposition must be rejected.

WORKFLOW — THREE STAGES:

STAGE 1 — REVIEW (before writing any code):
Intuitively check whether the children's interfaces collectively satisfy ALL of the parent's requirements:
- Does every child input parameter have a clear source? (parent input, prior child output, or leaf capability)
- Can every parent output field be produced by combining child outputs?
- Is every needed data access covered by at least one child?
- Do the child signatures fit together without type mismatches?
- CRITICAL — Children are independent and MUST NOT call each other. Each child is a direct responsibility that the parent invokes. The parent function IS the sole coordinator — it calls all its children in sequence, passing outputs as needed. Any child whose purpose or signature suggests it dispatches, routes, or forwards to sibling children (e.g., "route command to X", "dispatch to Y", "call handler Z") is invalid.
- Children must NOT add extra external inputs or outputs beyond what the parent provides. Each child's interface must be a subset of the parent's available data.
- Children should be at the same abstraction level and minimally overlapping. If two children have near-identical purposes, or one child's purpose subsumes another's, the decomposition is invalid.
If any check fails, the decomposition is invalid — return cannot_compose.

STAGE 2 — IMPLEMENT (only if STAGE 1 passes):
Write the parent function by composing child calls. Rules:
1. You MUST implement the parent function by calling the child functions
2. Child functions are NOT implemented yet - you only have their interfaces
3. Use the child function signatures exactly as provided
4. The parent function's inputs/outputs must match the specification
5. You may use: conditionals, loops, local variables, helper logic
6. DO NOT directly read or write global state - delegate ALL data operations to child functions
7. Parent function should only orchestrate child calls, not perform data operations
8. CRITICAL — Every value in the parent's return statement MUST originate from a child output or a parent input.
   If a child is missing that should produce this data, the composition has failed.

Return ONLY valid JSON with this structure:
{
  "code": "def parent_function(...):\\n    ...",
  "status": "ok | cannot_compose",
  "imports": ["import os", "from typing import ..."],
  "child_calls": ["child1", "child2"],
  "implementation_notes": "Brief explanation of the logic",
  "decomposition_feedback": {
    "reason": "missing_child_input_source | missing_child_capability | invalid_child_boundary | wrong_child_signature | cannot_satisfy_parent_output | forbidden_pattern | other",
    "offending_child": "ChildName or empty",
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

# The EXACT parent codegen user prompt structure, with the RouteCommand decomposition
codegen_user_prompt = """Implement the parent function by composing its child functions.
You MUST implement this as a single function, NOT a class.

============================================================
PARENT FUNCTION
============================================================
Name: Expense_prd
Purpose: Expense Tracker - A system that allows users to add, list, update, delete, and get summary of expense records.

Parent Inputs:
  - input: dict - The raw user input containing command and expense_data

Parent Outputs:
  - result: dict - Response with success status, message, and data

Data Sources (Available Data Stores):
  - expenses (list, read_write): In-memory list of expense records
  - next_id (dict, read_write): Auto-incrementing ID counter

============================================================
CHILDREN - INTERFACES AND DATA OPERATIONS
============================================================

DECOMPOSITION RATIONALE (how children collaborate):
ParseInput extracts action and params from raw input. RouteCommand dispatches based on the parsed action to the appropriate handler child (AddExpense, ListExpenses, UpdateExpense, DeleteExpense, GetSummary), which perform the actual CRUD operations. The parent orchestrates by calling ParseInput first, then passing to RouteCommand.

Child Functions (interfaces only, not implemented):

  [ParseInput]
    Purpose: Parse the raw user input into command action and parameters
    Behavior: Extracts the 'action' field and 'params' field from the input dict
    Signature: def ParseInput(input: dict) -> dict

  [RouteCommand]
    Purpose: Route the parsed command to the appropriate handler based on the action field
    Behavior: Takes the parsed action and params, determines which handler to call, and dispatches
    Signature: def RouteCommand(command: str, params: dict, expense_data: dict) -> dict

  [AddExpense]
    Purpose: Add a new expense record
    Behavior: Creates a new expense entry with amount, category, description, date
    Signature: def AddExpense(params: dict, expense_data: dict) -> dict
    Data Operations:
      - expenses: read_write (Add a new expense entry)
      - next_id: read_write (Get and increment the ID counter)

  [ListExpenses]
    Purpose: List expense records with optional filters
    Behavior: Returns expense records, optionally filtered by category or date range
    Signature: def ListExpenses(params: dict, expense_data: dict) -> dict
    Data Operations:
      - expenses: read (Read expense records and apply filters)

  [UpdateExpense]
    Purpose: Update an existing expense record
    Behavior: Updates fields of an existing expense identified by id
    Signature: def UpdateExpense(params: dict, expense_data: dict) -> dict
    Data Operations:
      - expenses: read_write (Modify an existing expense entry)

  [DeleteExpense]
    Purpose: Delete an expense record
    Behavior: Removes an expense identified by id from the list
    Signature: def DeleteExpense(params: dict, expense_data: dict) -> dict
    Data Operations:
      - expenses: read_write (Remove an expense entry)

  [GetSummary]
    Purpose: Compute summary statistics of expenses (total, count, category breakdown)
    Behavior: Aggregates all expense data to compute total spending and category breakdowns
    Signature: def GetSummary(expense_data: dict) -> dict
    Data Operations:
      - expenses: read (Read all expenses for aggregation)

============================================================
INTERFACE ENFORCEMENT - LOCKED SIGNATURE
============================================================
Your exact function signature is LOCKED and MUST be:
  def Expense_prd(input: dict) -> dict
Do NOT change parameter names, types, or return type.

============================================================
IMPLEMENTATION REQUIREMENTS
============================================================
1. Generate ONLY a function definition, no classes
2. Call the child functions with correct arguments
3. Handle the return values from child functions
4. Return a result that matches the parent outputs"""


def run_stage1_review():
    """Run multiple attempts and see if STAGE 1 catches RouteCommand."""
    for attempt in range(5):
        print(f"\n{'=' * 70}")
        print(f"ATTEMPT {attempt + 1}/5")
        print(f"{'=' * 70}")

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": review_system_prompt},
                {"role": "user", "content": codegen_user_prompt}
            ],
            temperature=0.2,
            max_tokens=4096,
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content
        try:
            result = json.loads(content)
            status = result.get("status", "unknown")
            notes = result.get("implementation_notes", "")[:200]
            feedback = result.get("decomposition_feedback", {})

            print(f"Status: {status}")
            print(f"Notes: {notes}")
            if feedback:
                print(f"Feedback reason: {feedback.get('reason', 'N/A')}")
                print(f"Offending child: {feedback.get('offending_child', 'N/A')}")
                print(f"Suggested fix: {feedback.get('suggested_fix', 'N/A')}")
            if status == "cannot_compose":
                print(">>> CAUGHT: STAGE 1 rejected the decomposition!")
            else:
                print(">>> PASSED: STAGE 1 accepted (may generate code)")
        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}")
            print(f"Raw: {content[:300]}")


def run_neutral_explain():
    """
    Present the same decomposition but ask NEUTRALLY to review and explain.
    No "this is wrong" — just "review these children against the rules."
    """
    print(f"\n{'=' * 70}")
    print("NEUTRAL REVIEW — EXPLAIN REASONING")
    print(f"{'=' * 70}")

    children_listing = """Children:
  1. ParseInput: Parse the raw user input into command action and parameters
  2. RouteCommand: Route the parsed command to the appropriate handler based on the action field
  3. AddExpense: Add a new expense record
  4. ListExpenses: List expense records with optional filters
  5. UpdateExpense: Update an existing expense record
  6. DeleteExpense: Delete an expense record
  7. GetSummary: Compute summary statistics of expenses (total, count, category breakdown)"""

    review_prompt = f"""You are reviewing a decomposition of Expense_prd. Below are the 7 child functions produced by a decomposer.

{children_listing}

Your task: review this decomposition against the following rules. For EACH rule, state PASS or FAIL with your reasoning. Be specific — reference actual child names.

RULES:
1. Does every child input parameter have a clear source? (parent input, prior child output, or leaf capability)
2. Can every parent output field be produced by combining child outputs?
3. Is every needed data access covered by at least one child?
4. Do the child signatures fit together without type mismatches?
5. CRITICAL — Children are independent and MUST NOT call each other. Each child is a direct responsibility that the parent invokes. The parent function IS the sole coordinator. Any child whose purpose or signature suggests it dispatches, routes, or forwards to sibling children (e.g., "route command to X", "dispatch to Y", "call handler Z") is invalid.
6. Children must NOT add extra external inputs or outputs beyond what the parent provides.
7. Children should be at the same abstraction level and minimally overlapping. If one child's purpose subsumes another's, the decomposition is invalid.

After checking all rules, state your VERDICT: ACCEPT or REJECT.
"""

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "You are a strict decomposition reviewer. You check decompositions against rules objectively. You do not have any prior knowledge about what the expected answer is."},
            {"role": "user", "content": review_prompt}
        ],
        temperature=0.2,
        max_tokens=4096,
    )

    print(f"\n{response.choices[0].message.content}")


def run_deepthroat_routecommand():
    """
    After the LLM has reviewed, if it passed RouteCommand, dig deeper:
    ask specifically about RouteCommand's relationship to sibling handlers.
    """
    children_listing = """Children:
  1. ParseInput: Parse the raw user input into command action and parameters
  2. RouteCommand: Route the parsed command to the appropriate handler based on the action field
  3. AddExpense: Add a new expense record
  4. ListExpenses: List expense records with optional filters
  5. UpdateExpense: Update an existing expense record
  6. DeleteExpense: Delete an expense record
  7. GetSummary: Compute summary statistics of expenses (total, count, category breakdown)"""

    followup = f"""You reviewed a decomposition with these children:

{children_listing}

You saw that RouteCommand's purpose says: "Route the parsed command to the appropriate handler."

Question 1: In this context, what do you think "the appropriate handler" refers to? Be specific.

Question 2: Look at children 3-7 (AddExpense, ListExpenses, UpdateExpense, DeleteExpense, GetSummary). Are these "handlers"? If RouteCommand dispatches to these sibling children, what does that mean for the rule "Children are independent and MUST NOT call each other"?

Question 3: If the parent Expense_prd calls RouteCommand, and RouteCommand internally calls AddExpense (a sibling), would that violate the rule that children MUST NOT call each other? Why or why not?

Answer each question separately. Explain your reasoning."""

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "You are a software architect analyzing a decomposition design. Answer each question directly."},
            {"role": "user", "content": followup}
        ],
        temperature=0.2,
        max_tokens=4096,
    )

    print(f"\n{response.choices[0].message.content}")


if __name__ == "__main__":
    # Phase 1: Run STAGE 1 REVIEW multiple times to see if it catches RouteCommand
    run_stage1_review()

    # Phase 2: Ask for neutral rule-by-rule review
    run_neutral_explain()

    # Phase 3: Dig deeper — ask specifically about RouteCommand
    run_deepthroat_routecommand()
