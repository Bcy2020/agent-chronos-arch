"""
Auto-generated interface layer code from InterfacePlan.
This layer is the ONLY layer allowed to directly access global variables.
"""

import datetime


# === Resource: users ===

def get_user(user_id: int) -> dict | None:
    return users.get(user_id)

def list_users() -> list:
    return list(users.values())

def create_user(user: dict) -> dict:
    user_id = user['user_id']
    if user_id in users:
        raise ValueError('user_id already exists')
    users[user_id] = user
    return user

def update_user(user_id: int, updates: dict) -> dict:
    if user_id not in users:
        raise KeyError('user not found')
    users[user_id].update(updates)
    return users[user_id]

def delete_user(user_id: int) -> None:
    if user_id not in users:
        raise KeyError('user not found')
    del users[user_id]

def user_exists(user_id: int) -> bool:
    return user_id in users

# === Resource: products ===

def get_product(product_id: int) -> dict | None:
    return products.get(product_id)

def list_products(low_stock: bool = False, threshold: int = 10) -> list:
    result = list(products.values())
    if low_stock:
        result = [p for p in result if p['stock'] < threshold]
    return result

def create_product(product: dict) -> dict:
    product_id = product['product_id']
    products[product_id] = product
    return product

def update_product(product_id: int, updates: dict) -> dict:
    product = products[product_id]
    product.update(updates)
    return product

def delete_product(product_id: int) -> None:
    del products[product_id]

def product_exists(product_id: int) -> bool:
    return product_id in products

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
    order_id = order.get('order_id')
    if order_id is None:
        order_id = max(orders.keys()) + 1 if orders else 1
        order['order_id'] = order_id
    orders[order_id] = order
    return order

def update_order(order_id: int, updates: dict) -> dict:
    order = orders[order_id]
    order.update(updates)
    return order

def delete_order(order_id: int) -> None:
    del orders[order_id]

def order_exists(order_id: int) -> bool:
    return order_id in orders