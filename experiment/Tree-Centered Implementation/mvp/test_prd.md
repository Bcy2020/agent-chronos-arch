# Personal Task Manager - Product Requirements Document

## Overview
A simple command-line task management application that allows users to create, list, complete, and delete tasks. Tasks are stored in memory during the session.

## Core Features

### 1. Task Creation
- Users can create a new task with a title and optional description
- Each task gets a unique auto-incremented ID
- Tasks have a status: "pending" or "completed"
- Tasks have a creation timestamp

### 2. Task Listing
- Users can list all tasks
- Users can filter tasks by status (pending/completed/all)
- Output should show task ID, title, status, and creation time

### 3. Task Completion
- Users can mark a task as completed by its ID
- Should validate that the task exists
- Should return success/error message

### 4. Task Deletion
- Users can delete a task by its ID
- Should validate that the task exists
- Should return success/error message

## Technical Constraints
- In-memory storage (no database persistence)
- Single-user system (no authentication)
- Command-line interface
- Python implementation

## Input/Output Format

### Input
- Command: string (create, list, complete, delete)
- Task data: optional dict with title, description, task_id, status_filter

### Output
- Result: dict with success status, message, and optional data

## Example Usage
```
Input: {"command": "create", "task_data": {"title": "Buy groceries", "description": "Milk, eggs, bread"}}
Output: {"success": true, "message": "Task created with ID 1", "data": {"task_id": 1}}

Input: {"command": "list", "task_data": {"status_filter": "all"}}
Output: {"success": true, "message": "Found 1 task", "data": {"tasks": [...]}}
```

## Success Criteria
- All CRUD operations work correctly
- Error handling for invalid inputs
- Clean, readable code structure
