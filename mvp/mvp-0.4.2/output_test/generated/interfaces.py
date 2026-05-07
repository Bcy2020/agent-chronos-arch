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

def update_user(user_id: int, updates: dict) -> dict:
    user = users[user_id]
    user.update(updates)
    return user

def delete_user(user_id: int) -> None:
    del users[user_id]

def user_exists(user_id: int) -> bool:
    return user_id in users

# === Resource: products ===

def get_product(product_id: int) -> dict | None:
    return products.get(product_id)

def list_products() -> list[dict]:
    return list(products.values())

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

def list_orders(filters: dict = None) -> list[dict]:
    if filters is None:
        return list(orders.values())
    result = []
    for order in orders.values():
        match = True
        for key, value in filters.items():
            if key not in order or order[key] != value:
                match = False
                break
        if match:
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

def delete_order(order_id: int) -> None:
    del orders[order_id]

def order_exists(order_id: int) -> bool:
    return order_id in orders