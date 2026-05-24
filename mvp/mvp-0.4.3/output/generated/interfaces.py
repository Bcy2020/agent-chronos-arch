"""
Auto-generated interface layer code from InterfacePlan.
This layer is the ONLY layer allowed to directly access global variables.
"""

import datetime


# === Resource: expenses ===

def get_expense(expense_id: int) -> dict:
    for expense in expenses:
        if expense['id'] == expense_id:
            return expense
    return None

def list_expenses(category: str = None, start_date: str = None, end_date: str = None) -> list:
    result = []
    for expense in expenses:
        if category is not None and expense['category'] != category:
            continue
        if start_date is not None and expense['date'] < start_date:
            continue
        if end_date is not None and expense['date'] > end_date:
            continue
        result.append(expense)
    return result

def create_expense(amount: float, category: str, description: str, date: str) -> dict:
    new_id = max((e['id'] for e in expenses), default=0) + 1
    new_expense = {
        'id': new_id,
        'amount': amount,
        'category': category,
        'description': description,
        'date': date
    }
    expenses.append(new_expense)
    return new_expense

def update_expense(expense_id: int, amount: float = None, category: str = None, description: str = None) -> dict:
    for expense in expenses:
        if expense['id'] == expense_id:
            if amount is not None:
                expense['amount'] = amount
            if category is not None:
                expense['category'] = category
            if description is not None:
                expense['description'] = description
            return expense
    return None

def delete_expense(expense_id: int) -> dict:
    for i, expense in enumerate(expenses):
        if expense['id'] == expense_id:
            deleted = expenses.pop(i)
            return deleted
    return None

def expense_exists(expense_id: int) -> bool:
    for expense in expenses:
        if expense['id'] == expense_id:
            return True
    return False

# === Resource: next_id ===

def get_next_id() -> int:
    return next_id

def increment_next_id() -> int:
    global next_id
    next_id += 1
    return next_id