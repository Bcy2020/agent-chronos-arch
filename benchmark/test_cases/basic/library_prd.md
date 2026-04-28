# Simple Book Library - Product Requirements Document

## Overview
A simple book library management system that tracks books and their borrow status. Books are stored in memory during the session.

## External Interface
通过 `manage_library(command, book_data)` 函数调用实现图书馆管理操作。

```
输入: {"command": "add", "book_data": {"title": "书名", "author": "作者"}}
输出: {"success": true, "message": "书籍添加成功", "data": {"book_id": 1}}
```

## Core Features

### 1. Add Book
- 用户可添加新书（书名、作者）
- 每本书获得唯一ID
- 书籍状态默认为 "available"

### 2. List Books
- 用户可列出所有书籍
- 可按状态筛选（available/borrowed/all）
- 输出显示：ID、书名、作者、状态

### 3. Borrow Book
- 用户可借阅书籍（通过ID）
- 检查书籍是否存在且可借
- 状态从 "available" 变为 "borrowed"

### 4. Return Book
- 用户可归还书籍（通过ID）
- 检查书籍是否存在且已借出
- 状态从 "borrowed" 变为 "available"

### 5. Remove Book
- 用户可删除书籍（通过ID）
- 检查书籍是否存在
- 已借出的书不能删除

## Technical Constraints
- 内存存储（无持久化）
- 单用户系统
- Python实现

## Input/Output Format

### Input
```json
{
  "command": "add|list|borrow|return|remove",
  "book_data": {
    "title": "书名（add时必填）",
    "author": "作者（add时必填）",
    "book_id": "书籍ID（其他操作必填）",
    "status_filter": "筛选状态（list时可选）"
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
manage_library("add", {"title": "Python编程", "author": "John"})
→ {"success": true, "message": "书籍添加成功，ID=1", "data": {"book_id": 1}}

manage_library("list", {"status_filter": "all"})
→ {"success": true, "message": "共1本书", "data": {"books": [{"id":1, "title":"...", "author":"...", "status":"available"}]}}

manage_library("borrow", {"book_id": 1})
→ {"success": true, "message": "书籍借出成功", "data": {"book_id": 1}}

manage_library("return", {"book_id": 1})
→ {"success": true, "message": "书籍归还成功", "data": {"book_id": 1}}

manage_library("remove", {"book_id": 1})
→ {"success": true, "message": "书籍删除成功", "data": {"book_id": 1}}
```

## Success Criteria
- 所有5种操作正确执行
- 状态转换正确
- 错误处理完善（书籍不存在、重复借阅等）
- 约束条件满足（已借书籍不能删除）