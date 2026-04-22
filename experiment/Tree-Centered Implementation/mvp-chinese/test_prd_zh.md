# 个人任务管理器 - 产品需求文档

## 概述
一个简单的命令行任务管理应用，允许用户创建、列出、完成和删除任务。任务在会话期间存储在内存中。

## 核心功能

### 1. 任务创建
- 用户可以创建带有标题和可选描述的新任务
- 每个任务获得唯一的自增ID
- 任务状态："pending" 或 "completed"
- 任务具有创建时间戳

### 2. 任务列表
- 用户可以列出所有任务
- 用户可以按状态筛选任务（pending/completed/all）
- 输出应显示任务ID、标题、状态和创建时间

### 3. 任务完成
- 用户可以按ID将任务标记为已完成
- 应验证任务是否存在
- 应返回成功/错误消息

### 4. 任务删除
- 用户可以按ID删除任务
- 应验证任务是否存在
- 应返回成功/错误消息

## 技术约束
- 内存存储（无数据库持久化）
- 单用户系统（无身份验证）
- 命令行界面
- Python实现

## 输入/输出格式

### 输入
- Command: 字符串 (create, list, complete, delete)
- Task data: 可选字典，包含 title, description, task_id, status_filter

### 输出
- Result: 包含成功状态、消息和可选数据的字典

## 使用示例
```
输入: {"command": "create", "task_data": {"title": "Buy groceries", "description": "Milk, eggs, bread"}}
输出: {"success": true, "message": "Task created with ID 1", "data": {"task_id": 1}}

输入: {"command": "list", "task_data": {"status_filter": "all"}}
输出: {"success": true, "message": "Found 1 task", "data": {"tasks": [...]}}
```

## 成功标准
- 所有CRUD操作正确工作
- 无效输入的错误处理
- 清晰、可读的代码结构
