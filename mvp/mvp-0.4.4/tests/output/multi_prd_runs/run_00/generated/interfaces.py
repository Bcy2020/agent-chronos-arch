"""
Auto-generated interface layer code from InterfacePlan.
This layer is the ONLY layer allowed to directly access global variables.
"""

import datetime


# === Resource: users ===

def get_user(user_id: int) -> dict | None:
    return users.get(user_id)

def list_users() -> list[dict]:
    return list(users.values())

def create_user(user: dict) -> dict:
    user_id = user['user_id']
    users[user_id] = user
    return user

def update_user(user_id: int, updates: dict) -> dict | None:
    if user_id not in users:
        return None
    user = users[user_id]
    user.update(updates)
    return user

def delete_user(user_id: int) -> bool:
    if user_id in users:
        del users[user_id]
        return True
    return False

def user_exists(user_id: int) -> bool:
    return user_id in users

# === Resource: products ===

def get_product(product_id: int) -> dict | None:
    return products.get(product_id)

def list_products() -> list[dict]:
    return list(products.values())

def create_product(product: dict) -> dict:
    products[product['product_id']] = product
    return product

def update_product(product_id: int, updates: dict) -> dict | None:
    if product_id not in products:
        return None
    product = products[product_id]
    product.update(updates)
    return product

def delete_product(product_id: int) -> bool:
    if product_id in products:
        del products[product_id]
        return True
    return False

def product_exists(product_id: int) -> bool:
    return product_id in products

# === Resource: orders ===

def get_order(order_id: int) -> dict | None:
    return orders.get(order_id)

def list_orders(user_id: int = None, status: str = None) -> list[dict]:
    result = []
    for order in orders.values():
        if user_id is not None and order.get('user_id') != user_id:
            continue
        if status is not None and order.get('status') != status:
            continue
        result.append(order)
    return result

def create_order(order: dict) -> dict:
    order_id = order.get('order_id')
    if order_id is None:
        order_id = max(orders.keys(), default=0) + 1
        order['order_id'] = order_id
    orders[order_id] = order
    return order

def update_order(order_id: int, updates: dict) -> dict | None:
    if order_id not in orders:
        return None
    orders[order_id].update(updates)
    return orders[order_id]

def delete_order(order_id: int) -> bool:
    if order_id in orders:
        del orders[order_id]
        return True
    return False

def order_exists(order_id: int) -> bool:
    return order_id in orders