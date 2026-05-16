"""
Test the UPDATED Step 2 VERIFY prompt against RouteCommand decomposition.
Presents a generated parent function that uses RouteCommand (not directly calling handlers).
The verify step should catch this with the new CHILD COVERAGE + CROSS-SIBLING DISPATCHER checks.
"""
import json
import os
from openai import OpenAI

api_key = os.getenv("DEEPSEEK_API_KEY")
client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com", timeout=180)

# The UPDATED verify prompt (from _build_system_prompt_for_parent_verify)
verify_system_prompt = """You are a decomposition verifier. Your role is to verify that a parent function's generated code correctly composes its child functions. If the code violates any composition rules, the decomposition must be rejected.

VERIFICATION CHECKS — examine the code carefully. Now that the code is available, you can perform CONCRETE traceability checks on the actual function calls:

1. RETURN VALUE ORIGIN — Trace every value in every return statement. Each business value must originate from a child function's output or a parent function's input. Acceptable origins include:
   - A variable assigned from a child call: rows = RunQuery(...)
   - A field extracted from a child result: user_id = transaction["user_id"]
   - A parent input parameter: amount, service, etc.
   - A computation from parent inputs: len(content), quantity * 2

   A return value that is a literal (None, True, False, a quoted string, a number, an empty list [], an empty dict {}) is a VIOLATION if it represents data that should come from a child.

2. CHILD COVERAGE — Every child function must appear as a DIRECT CALL in the generated code. Trace each child name in the code (e.g., look for "ChildName("). If a child is NOT called directly by the parent — meaning it is missing from the code, or is only called indirectly through another child — that is a VIOLATION. "Indirect coverage" (e.g., ChildA internally calls ChildB) does NOT satisfy this rule. Every child must be directly invoked by the parent function's own code.

3. DIRECT ACCESS — The code must NOT directly read or write any global variable or data source. All data operations must go through child function calls.

4. CROSS-SIBLING DISPATCHER — Examine each child's purpose and the generated code together. If any child's purpose or behavior suggests it dispatches, routes, or forwards to sibling children (e.g., "route command to the appropriate handler", "dispatch to X", "call handler Y"), the decomposition is invalid. Specifically:
   - Look for child names containing "Route", "Dispatch", "Coordinator", "Dispatcher"
   - Look for purposes that reference other sibling children as dispatch targets
   - Verify that the generated code does NOT contain a pattern where the parent calls only a subset of children while delegating the rest through an intermediary child
   - The parent IS the sole coordinator; every child must be directly and independently callable by the parent

If ANY check fails, return status="cannot_compose" with detailed feedback.
If ALL checks pass, return status="ok" with empty feedback.

Return ONLY valid JSON with this structure:
{
  "status": "ok | cannot_compose",
  "decomposition_feedback": {
    "reason": "missing_child_input_source | missing_child_capability | invalid_child_boundary | wrong_child_signature | cannot_satisfy_parent_output | forbidden_pattern | other",
    "offending_child": "ChildName or empty",
    "missing_inputs": [{"child": "ChildName", "param": "param_name", "why_needed": "why this input is needed", "expected_source": "parent input / previous child output / new child output"}],
    "direct_resource_accesses": [{"resource": "resource_name", "operation": "read", "why_needed": "why this resource access is needed"}],
    "suggested_fix": "Concrete suggestion for re-decomposition",
    "requires_redecomposition": true
  }
}"""

def build_verify_user_prompt(code: str) -> str:
    """Build the verification prompt with children list + generated code."""
    lines = [
        "Verify the generated parent function code below.",
        "",
        "=" * 60,
        "PARENT FUNCTION",
        "=" * 60,
        "Name: Expense_prd",
        "Purpose: Expense Tracker - A system that allows users to add, list, update, delete, and get summary of expense records.",
        "",
        "Parent Inputs:",
        "  - input: dict - The raw user input containing command and expense_data",
        "Parent Outputs:",
        "  - result: dict - Response with success status, message, and data",
        "",
        "Data Sources:",
        "  - expenses (list, read_write)",
        "  - next_id (dict, read_write)",
        "",
        "=" * 60,
        "CHILDREN - INTERFACES",
        "=" * 60,
        "",
        "  [ParseInput]",
        "    Purpose: Parse the raw user input into command action and parameters",
        "    Behavior: Extracts the 'action' field and 'params' field from the input dict",
        "    Signature: def ParseInput(input: dict) -> dict",
        "",
        "  [RouteCommand]",
        "    Purpose: Route the parsed command to the appropriate handler based on the action field",
        "    Behavior: Takes the parsed action and params, determines which handler to call, and dispatches",
        "    Signature: def RouteCommand(command: str, params: dict, expense_data: dict) -> dict",
        "",
        "  [AddExpense]",
        "    Purpose: Add a new expense record",
        "    Behavior: Creates a new expense entry with amount, category, description, date",
        "    Signature: def AddExpense(params: dict, expense_data: dict) -> dict",
        "    Data Operations:",
        "      - expenses: read_write (Add a new expense entry)",
        "      - next_id: read_write (Get and increment the ID counter)",
        "",
        "  [ListExpenses]",
        "    Purpose: List expense records with optional filters",
        "    Behavior: Returns expense records, optionally filtered by category or date range",
        "    Signature: def ListExpenses(params: dict, expense_data: dict) -> dict",
        "    Data Operations:",
        "      - expenses: read (Read expense records and apply filters)",
        "",
        "  [UpdateExpense]",
        "    Purpose: Update an existing expense record",
        "    Behavior: Updates fields of an existing expense identified by id",
        "    Signature: def UpdateExpense(params: dict, expense_data: dict) -> dict",
        "    Data Operations:",
        "      - expenses: read_write (Modify an existing expense entry)",
        "",
        "  [DeleteExpense]",
        "    Purpose: Delete an expense record",
        "    Behavior: Removes an expense identified by id from the list",
        "    Signature: def DeleteExpense(params: dict, expense_data: dict) -> dict",
        "    Data Operations:",
        "      - expenses: read_write (Remove an expense entry)",
        "",
        "  [GetSummary]",
        "    Purpose: Compute summary statistics of expenses (total, count, category breakdown)",
        "    Behavior: Aggregates all expense data to compute total spending and category breakdowns",
        "    Signature: def GetSummary(expense_data: dict) -> dict",
        "    Data Operations:",
        "      - expenses: read (Read all expenses for aggregation)",
        "",
        "=" * 60,
        "GENERATED CODE TO VERIFY",
        "=" * 60,
        "```python",
        code.strip(),
        "```",
        "",
        "Apply the verification checklist. Return your verdict as valid JSON."
    ]
    return "\n".join(lines)


# Code that uses RouteCommand — does NOT directly call handlers
code_with_routecommand = """def Expense_prd(input: dict) -> dict:
    parsed = ParseInput(input)
    command = parsed.get('command')
    params = parsed.get('params')
    expense_data = input.get('expense_data', {})
    result = RouteCommand(command, params, expense_data)
    return result"""

# Code that directly calls ALL children (correct pattern)
code_correct = """def Expense_prd(input: dict) -> dict:
    parsed = ParseInput(input)
    command = parsed.get('command')
    params = parsed.get('params')
    expense_data = input.get('expense_data', {})

    if command == 'add':
        result = AddExpense(params, expense_data)
    elif command == 'list':
        result = ListExpenses(params, expense_data)
    elif command == 'update':
        result = UpdateExpense(params, expense_data)
    elif command == 'delete':
        result = DeleteExpense(params, expense_data)
    elif command == 'summary':
        result = GetSummary(expense_data)
    else:
        result = {'success': False, 'error': f'Unknown command: {command}'}

    return result"""


def test_verify(code: str, label: str):
    """Run a single verify test."""
    print(f"\n{'=' * 70}")
    print(f"TEST: {label}")
    print(f"{'=' * 70}")
    print(f"Code:\n{code}\n")

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": verify_system_prompt},
            {"role": "user", "content": build_verify_user_prompt(code)}
        ],
        temperature=0.2,
        max_tokens=2048,
        response_format={"type": "json_object"}
    )

    content = response.choices[0].message.content
    try:
        result = json.loads(content)
        status = result.get("status", "unknown")
        feedback = result.get("decomposition_feedback", {})

        print(f"Status: {status}")
        if feedback:
            print(f"Reason: {feedback.get('reason', 'N/A')}")
            print(f"Offending child: {feedback.get('offending_child', 'N/A')}")
            print(f"Suggested fix: {feedback.get('suggested_fix', 'N/A')}")
        if status == "cannot_compose":
            print(">>> REJECTED — verify step caught the issue!")
        else:
            print(">>> PASSED — verify step let it through (missed)")
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        print(f"Raw: {content[:500]}")


if __name__ == "__main__":
    # Test 1: RouteCommand pattern (should be REJECTED)
    test_verify(code_with_routecommand, "RouteCommand (should reject)")

    # Test 2: Correct pattern (should PASS)
    test_verify(code_correct, "Correct dispatch (should pass)")

    # Test 3-5: RouteCommand pattern repeated to check consistency
    for i in range(3):
        test_verify(code_with_routecommand, f"RouteCommand repeat {i+2}/4")
