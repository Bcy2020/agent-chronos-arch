"""
Auto-generated interface layer code from InterfacePlan.
This layer is the ONLY layer allowed to directly access global variables.
"""

import datetime


# === Resource: expenses ===

def get_expense(expense_id: int) -> dict | None:
    return expenses.get(expense_id)

def list_expenses(category: str = None, start_date: str = None, end_date: str = None) -> list:
    result = []
    for expense in expenses.values():
        if category is not None and expense['category'] != category:
            continue
        if start_date is not None and expense['date'] < start_date:
            continue
        if end_date is not None and expense['date'] > end_date:
            continue
        result.append(expense)
    return result

def create_expense(expense: dict) -> int:
    new_id = max(expenses.keys()) + 1 if expenses else 1
    expense['id'] = new_id
    expenses[new_id] = expense
    return new_id

def update_expense(expense_id: int, updates: dict) -> bool:
    if expense_id not in expenses:
        return False
    expense = expenses[expense_id]
    for key, value in updates.items():
        if key in expense:
            expense[key] = value
    return True

def delete_expense(expense_id: int) -> bool:
    if expense_id not in expenses:
        return False
    del expenses[expense_id]
    return True

def expense_exists(expense_id: int) -> bool:
    return expense_id in expenses

# === Resource: next_id ===

def get_next_id() -> int:
    return next_id

def increment_next_id() -> int:
    global next_id
    next_id += 1
    return next_id