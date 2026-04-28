# Order Management System - Product Requirements Document

## Overview
An order management system that coordinates users, products, and orders. Users can create orders, track order status, and manage inventory. Data is stored in memory across three data sources.

## External Interface
通过 `manage_order(command, order_data)` 函数调用实现订单管理操作。

```
输入: {"command": "create_order", "order_data": {"user_id": 1, "items": [{"product_id": 1, "quantity": 2}]}}
输出: {"success": true, "message": "订单创建成功", "data": {"order_id": 1, "total_price": 199.8}}
```

## Data Sources

### 1. Users (users)
- 存储用户信息
- 字段：user_id, name, email, balance（账户余额）
- 初始状态：预置3个测试用户

### 2. Products (products)
- 存储商品信息和库存
- 字段：product_id, name, price, stock（库存数量）
- 初始状态：预置5个测试商品

### 3. Orders (orders)
- 存储订单记录
- 字段：order_id, user_id, items（商品列表），total_price, status, created_at
- 状态：pending, paid, shipped, completed, cancelled

## Core Features

### 1. Create Order
- 用户创建订单（指定用户ID和商品列表）
- 检查用户是否存在
- 检查商品库存是否充足
- 计算订单总价
- 扣减商品库存
- 创建订单记录（状态：pending）

### 2. Pay Order
- 用户支付订单（从用户余额扣款）
- 检查订单存在且状态为pending
- 检查用户余额充足
- 扣减用户余额
- 更新订单状态为paid

### 3. Ship Order
- 订单发货
- 检查订单存在且状态为paid
- 更新订单状态为shipped

### 4. Complete Order
- 订单完成
- 检查订单存在且状态为shipped
- 更新订单状态为completed

### 5. Cancel Order
- 订单取消
- 检查订单存在且状态为pending或paid
- 恢复商品库存
- 如已支付，退还用户余额
- 更新订单状态为cancelled

### 6. List Orders
- 列出订单
- 可按用户筛选
- 可按状态筛选
- 显示订单详情：商品列表、总价、状态、时间

### 7. Get User Orders
- 获取某用户的所有订单
- 计算用户订单总额、各状态订单数

### 8. List Products
- 列出商品
- 显示商品信息和当前库存
- 可筛选库存不足的商品

## Technical Constraints
- 内存存储（三个独立数据源）
- 数据源之间需要协调操作
- 余额和库存必须保证一致性
- Python实现

## Input/Output Format

### Input
```json
{
  "command": "create_order|pay_order|ship_order|complete_order|cancel_order|list_orders|get_user_orders|list_products",
  "order_data": {
    "user_id": 用户ID,
    "order_id": 订单ID,
    "items": [{"product_id": 商品ID, "quantity": 数量}],
    "status_filter": 状态筛选,
    "user_filter": 用户筛选,
    "low_stock": 是否筛选低库存
  }
}
```

### Output
```json
{
  "success": true/false,
  "message": "操作结果消息",
  "data": {"返回数据"}
}
```

## Initial Data

### Users
| user_id | name | email | balance |
|---------|------|-------|---------|
| 1 | 张三 | zhang@test.com | 500.0 |
| 2 | 李四 | li@test.com | 300.0 |
| 3 | 王五 | wang@test.com | 100.0 |

### Products
| product_id | name | price | stock |
|------------|------|-------|-------|
| 1 | 手机 | 999.0 | 10 |
| 2 | 耳机 | 99.9 | 20 |
| 3 | 充电器 | 49.9 | 50 |
| 4 | 数据线 | 19.9 | 100 |
| 5 | 手机壳 | 29.9 | 30 |

## Example Usage

```
// 创建订单
manage_order("create_order", {"user_id": 1, "items": [{"product_id": 2, "quantity": 2}]})
→ {"success": true, "message": "订单创建成功", "data": {"order_id": 1, "total_price": 199.8}}

// 支付订单
manage_order("pay_order", {"order_id": 1})
→ {"success": true, "message": "支付成功，余额扣减199.8", "data": {"order_id": 1, "new_balance": 300.2}}

// 库存不足时创建订单
manage_order("create_order", {"user_id": 1, "items": [{"product_id": 1, "quantity": 15}]})
→ {"success": false, "message": "商品库存不足", "data": {"product_id": 1, "available": 10, "requested": 15}}

// 余额不足时支付
manage_order("pay_order", {"order_id": 2})  // 假设订单总价300
→ {"success": false, "message": "用户余额不足", "data": {"user_id": 3, "balance": 100, "required": 300}}

// 取消订单（恢复库存和余额）
manage_order("cancel_order", {"order_id": 1})
→ {"success": true, "message": "订单取消成功，库存和余额已恢复", "data": {"order_id": 1}}

// 获取用户订单统计
manage_order("get_user_orders", {"user_id": 1})
→ {"success": true, "data": {"orders": [...], "total_spent": 199.8, "pending": 0, "paid": 0, "completed": 1}}

// 查看低库存商品
manage_order("list_products", {"low_stock": true})
→ {"success": true, "data": {"products": [{"product_id": 1, "name": "手机", "stock": 10}]}}
```

## Success Criteria
- 三数据源协调操作正确
- 库存扣减和恢复一致性
- 余额扣减和退还一致性
- 订单状态流转正确（pending→paid→shipped→completed）
- 取消订单正确恢复资源
- 错误处理完善（库存不足、余额不足、无效订单）