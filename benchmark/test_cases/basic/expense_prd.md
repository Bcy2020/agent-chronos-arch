# Expense Tracker - Product Requirements Document

## Overview
A simple expense tracking system that records daily expenses. Users can add, view, update, and delete expense records. Data is stored in memory during the session.

## External Interface
通过 `track_expense(command, expense_data)` 函数调用实现费用管理操作。

```
输入: {"command": "add", "expense_data": {"amount": 50.0, "category": "food", "description": "午餐"}}
输出: {"success": true, "message": "费用记录添加成功", "data": {"expense_id": 1}}
```

## Core Features

### 1. Add Expense
- 用户可添加费用记录（金额、类别、描述、日期）
- 每条记录获得唯一ID
- 类别：food, transport, entertainment, shopping, other
- 金额必须为正数
- 日期默认为当天

### 2. List Expenses
- 用户可列出所有费用记录
- 可按类别筛选
- 可按日期范围筛选（start_date, end_date）
- 输出显示：ID、金额、类别、描述、日期

### 3. Update Expense
- 用户可修改费用记录（通过ID）
- 可修改金额、类别、描述
- 检查记录是否存在

### 4. Delete Expense
- 用户可删除费用记录（通过ID）
- 检查记录是否存在

### 5. Get Summary
- 用户可获取费用汇总统计
- 汇总方式：按类别、按日期范围
- 返回总金额和各类别金额

## Technical Constraints
- 内存存储（无持久化）
- 金额为浮点数，精确到小数点后两位
- 日期格式：YYYY-MM-DD
- Python实现

## Input/Output Format

### Input
```json
{
  "command": "add|list|update|delete|summary",
  "expense_data": {
    "amount": 金额（add/update时必填）,
    "category": "类别（add/update时必填）",
    "description": "描述（可选）",
    "date": "日期（可选，默认当天）",
    "expense_id": 记录ID（update/delete时必填）,
    "category_filter": 类别筛选（list时可选）,
    "start_date": 开始日期（list/summary时可选）,
    "end_date": 结束日期（list/summary时可选）,
    "group_by": "category|date"（summary时可选）
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

## Example Usage
```
track_expense("add", {"amount": 50.0, "category": "food", "description": "午餐"})
→ {"success": true, "message": "记录添加成功，ID=1", "data": {"expense_id": 1}}

track_expense("add", {"amount": 200.0, "category": "shopping", "description": "衣服", "date": "2024-01-15"})
→ {"success": true, "message": "记录添加成功，ID=2", "data": {"expense_id": 2}}

track_expense("list", {"category_filter": "food"})
→ {"success": true, "message": "共1条记录", "data": {"expenses": [{"id":1, "amount":50, "category":"food", ...}], "total": 50}}

track_expense("update", {"expense_id": 1, "amount": 60.0, "description": "午餐+饮料"})
→ {"success": true, "message": "记录更新成功", "data": {"expense_id": 1}}

track_expense("delete", {"expense_id": 2})
→ {"success": true, "message": "记录删除成功", "data": {"expense_id": 2}}

track_expense("summary", {"group_by": "category"})
→ {"success": true, "message": "汇总完成", "data": {"total": 60, "by_category": {"food": 60}}}
```

## Success Criteria
- 所有5种操作正确执行
- 筛选功能正确
- 汇总统计正确
- 错误处理完善（无效ID、负数金额、无效类别）
- 日期范围筛选正确