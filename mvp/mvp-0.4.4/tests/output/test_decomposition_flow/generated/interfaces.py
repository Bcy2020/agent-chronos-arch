"""
Auto-generated interface layer code from InterfacePlan.
This layer is the ONLY layer allowed to directly access global variables.
"""

import datetime


# === Resource: users ===

def get_user(user_id: int) -> dict | None:
    return users.get(user_id)

def user_exists(user_id: int) -> bool:
    return user_id in users

def update_user(user_id: int, updates: dict) -> dict:
    user = users[user_id]
    user.update(updates)
    return user

# === Resource: products ===

def get_product(product_id: int) -> dict | None:
    return products.get(product_id)

def list_products(low_stock: bool = False, threshold: int = 10) -> list:
    result = []
    for product in products.values():
        if low_stock:
            if product['stock'] < threshold:
                result.append(product)
        else:
            result.append(product)
    return result

def update_product(product_id: int, updates: dict) -> dict:
    product = products[product_id]
    product.update(updates)
    return product

# === Resource: orders ===

def get_order(order_id: int) -> dict | None:
    return orders.get(order_id)

def list_orders(user_id: int = None, status: str = None) -> list:
    result = []
    for order in orders.values():
        if user_id is not None and order.get('user_id') != user_id:
            continue
        if status is not None and order.get('status') != status:
            continue
        result.append(order)
    return result

def create_order(order: dict) -> dict:
    order_id = order['order_id']
    orders[order_id] = order
    return order

def update_order(order_id: int, updates: dict) -> dict:
    order = orders[order_id]
    order.update(updates)
    return order

def order_exists(order_id: int) -> bool:
    return order_id in orders