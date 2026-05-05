"""
Auto-generated interface layer code from InterfacePlan.
This layer is the ONLY layer allowed to directly access global variables.
"""

import datetime


# === Resource: users (dict) ===
# Stores user information keyed by user_id.

# Invariant: user_id is unique and non-negative
# Invariant: balance must be non-negative

def get_user():
    """Retrieve a user by user_id."""
    return users.get(key)

def user_exists():
    """Check if a user exists."""
    return key in users

def update_user():
    """Update user fields (e.g., balance)."""
    if key not in users:
        return None
    users[key].update(updates)
    return users[key]


# === Resource: products (dict) ===
# Stores product information keyed by product_id.

# Invariant: product_id is unique and non-negative
# Invariant: stock must be non-negative

def get_product():
    """Retrieve a product by product_id."""
    return products.get(key)

def list_products():
    """List all products, optionally filter low stock (stock < 10)."""
    return list(products.values())

def update_product():
    """Update product fields (e.g., stock)."""
    if key not in products:
        return None
    products[key].update(updates)
    return products[key]


# === Resource: orders (dict) ===
# Stores order records keyed by order_id.

# Invariant: order_id is unique and non-negative
# Invariant: status must be one of: pending, paid, shipped, completed, cancelled

def get_order():
    """Retrieve an order by order_id."""
    return orders.get(key)

def list_orders():
    """List orders with optional filters by user_id and status."""
    return list(orders.values())

def create_order():
    """Create a new order and return its order_id."""
    new_key = orders.get('_next_id', 1) if isinstance(orders, dict) and '_next_id' in orders else len(orders) + 1
    if isinstance(new_key, int) and '_next_id' not in orders:
        new_key = max(orders.keys()) + 1 if orders else 1
    orders[new_key] = item
    return orders[new_key]

def update_order():
    """Update order fields (e.g., status)."""
    if key not in orders:
        return None
    orders[key].update(updates)
    return orders[key]

def order_exists():
    """Check if an order exists."""
    return key in orders
