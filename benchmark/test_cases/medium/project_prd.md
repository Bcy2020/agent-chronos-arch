# Project Task Manager - Product Requirements Document

## Overview
A project task management system that coordinates projects, tasks, and team members. Users can create projects, assign tasks, track progress, and manage team assignments. Data is stored in memory across three data sources.

## External Interface
通过 `manage_project(command, project_data)` 函数调用实现项目任务管理操作。

```
输入: {"command": "create_project", "project_data": {"name": "网站重构", "description": "重构公司官网", "owner_id": 1}}
输出: {"success": true, "message": "项目创建成功", "data": {"project_id": 1}}
```

## Data Sources

### 1. Members (members)
- 存储团队成员信息
- 字段：member_id, name, role（角色），skills（技能列表），availability（可用状态）
- 角色：developer, designer, tester, manager
- 状态：available, busy, offline
- 初始状态：预置6个团队成员

### 2. Projects (projects)
- 存储项目信息
- 字段：project_id, name, description, owner_id, status, created_at, deadline
- 状态：planning, active, completed, cancelled
- 初始状态：空

### 3. Tasks (tasks)
- 存储任务记录
- 字段：task_id, project_id, title, description, assignee_id, status, priority, estimated_hours, actual_hours, created_at
- 状态：todo, in_progress, review, done, blocked
- 优先级：low, medium, high, critical
- 初始状态：空

## Core Features

### 1. Create Project
- 创建新项目
- 指定项目名、描述、负责人
- 检查负责人存在
- 项目状态默认：planning
- 记录创建时间

### 2. Update Project
- 更新项目信息
- 可修改描述、负责人、状态、截止日期
- 检查项目存在
- 状态变更记录

### 3. Delete Project
- 删除项目
- 检查项目存在
- 同时删除项目下所有任务

### 4. Create Task
- 创建任务
- 指定项目、标题、描述、优先级、预估工时
- 检查项目存在且状态为planning或active
- 任务状态默认：todo
- 未分配执行者

### 5. Assign Task
- 分配任务给团队成员
- 检查任务存在且未分配或需重新分配
- 检查成员存在且状态为available
- 检查成员技能匹配任务需求（可选）
- 更新任务assignee_id
- 更新成员状态为busy

### 6. Update Task Status
- 更新任务状态
- 检查任务存在
- 状态流转：todo→in_progress→review→done
- blocked状态可随时设置
- done状态时记录实际工时

### 7. Complete Task
- 完成任务
- 检查任务状态为review
- 更新状态为done
- 记录实际工时
- 释放成员（状态变为available）

### 8. Delete Task
- 删除任务
- 检查任务存在
- 如任务已分配，释放成员

### 9. List Project Tasks
- 列出项目任务
- 可按状态筛选
- 可按优先级筛选
- 可按执行者筛选
- 显示任务详情和进度

### 10. Get Member Tasks
- 获取成员的所有任务
- 显示当前任务和历史任务
- 计算工时统计

### 11. Get Project Progress
- 获取项目进度
- 计算任务完成率
- 各状态任务数统计
- 工时对比（预估vs实际）
- 预计完成时间

### 12. Add Member
- 添加团队成员
- 检查成员ID不重复

### 13. Update Member Availability
- 更新成员可用状态
- 检查成员无进行中任务时才能设为offline

## Technical Constraints
- 内存存储（三个独立数据源）
- 任务状态流转需遵循规则
- 成员状态与任务分配需协调
- Python实现

## Input/Output Format

### Input
```json
{
  "command": "create_project|update_project|delete_project|create_task|assign_task|update_task_status|complete_task|delete_task|list_project_tasks|get_member_tasks|get_project_progress|add_member|update_member_availability",
  "project_data": {
    "name": 项目/任务名称,
    "description": 描述,
    "owner_id": 负责人ID,
    "project_id": 项目ID,
    "task_id": 任务ID,
    "assignee_id": 执行者ID,
    "member_id": 成员ID,
    "status": 状态,
    "priority": 优先级,
    "estimated_hours": 预估工时,
    "actual_hours": 实际工时,
    "deadline": 截止日期,
    "role": 角色（add_member时用）,
    "skills": 报能列表（add_member时用）,
    "availability": 可用状态,
    "status_filter": 状态筛选,
    "priority_filter": 优先级筛选,
    "assignee_filter": 执行者筛选
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

### Members
| member_id | name | role | skills | availability |
|-----------|------|------|--------|--------------|
| 1 | 张开发 | developer | [python, javascript] | available |
| 2 | 李设计 | designer | [ui, css] | available |
| 3 | 王测试 | tester | [testing, automation] | available |
| 4 | 赵前端 | developer | [javascript, react] | available |
| 5 | 陈后端 | developer | [python, database] | available |
| 6 | 刘经理 | manager | [planning, coordination] | available |

## Example Usage

```
// 创建项目
manage_project("create_project", {"name": "网站重构", "description": "重构公司官网", "owner_id": 6})
→ {"success": true, "message": "项目创建成功", "data": {"project_id": 1, "status": "planning"}}

// 激活项目
manage_project("update_project", {"project_id": 1, "status": "active", "deadline": "2024-03-01"})
→ {"success": true, "message": "项目已激活", "data": {"project_id": 1}}

// 创建任务
manage_project("create_task", {"project_id": 1, "title": "首页设计", "description": "重新设计首页UI", "priority": "high", "estimated_hours": 8})
→ {"success": true, "data": {"task_id": 1, "status": "todo"}}

// 分配任务
manage_project("assign_task", {"task_id": 1, "assignee_id": 2})
→ {"success": true, "message": "任务已分配给李设计", "data": {"task_id": 1, "assignee": "李设计", "member_status": "busy"}}

// 分配给忙碌的成员
manage_project("assign_task", {"task_id": 2, "assignee_id": 2})
→ {"success": false, "message": "成员当前不可用", "data": {"member_id": 2, "availability": "busy"}}

// 开始任务
manage_project("update_task_status", {"task_id": 1, "status": "in_progress"})
→ {"success": true, "data": {"task_id": 1, "status": "in_progress"}}

// 提交审核
manage_project("update_task_status", {"task_id": 1, "status": "review"})
→ {"success": true, "data": {"task_id": 1, "status": "review"}}

// 完成任务
manage_project("complete_task", {"task_id": 1, "actual_hours": 10})
→ {"success": true, "message": "任务完成，成员已释放", "data": {"task_id": 1, "status": "done", "member_availability": "available"}}

// 查看项目进度
manage_project("get_project_progress", {"project_id": 1})
→ {"success": true, "data": {
    "total_tasks": 5,
    "completed": 1,
    "completion_rate": 0.2,
    "by_status": {"todo": 2, "in_progress": 2, "done": 1},
    "estimated_hours": 30,
    "actual_hours": 10
}}

// 查看成员任务
manage_project("get_member_tasks", {"member_id": 2})
→ {"success": true, "data": {
    "current_tasks": [],
    "completed_tasks": [{"task_id": 1, "title": "首页设计", "actual_hours": 10}],
    "total_hours": 10
}}

// 删除项目（连带删除任务）
manage_project("delete_project", {"project_id": 1})
→ {"success": true, "message": "项目已删除，包括3个任务", "data": {"project_id": 1, "deleted_tasks": 3}}
```

## Success Criteria
- 三数据源协调查询正确
- 任务状态流转规则正确
- 成员状态与任务分配协调正确
- 项目删除连带删除任务
- 进度计算正确
- 工时统计正确
- 状态筛选正确
- 错误处理完善（无效项目/任务/成员、状态冲突）