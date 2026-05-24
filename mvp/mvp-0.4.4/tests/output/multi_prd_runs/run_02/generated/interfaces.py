"""
Auto-generated interface layer code from InterfacePlan.
This layer is the ONLY layer allowed to directly access global variables.
"""

import datetime


# === Resource: members ===

def get_member(member_id: int) -> dict:
    return members.get(member_id)

def list_members() -> list:
    return list(members.values())

def create_member(member: dict) -> dict:
    members[member['member_id']] = member
    return member

def update_member(member_id: int, updates: dict) -> dict:
    member = members[member_id]
    member.update(updates)
    return member

def member_exists(member_id: int) -> bool:
    return member_id in members

# === Resource: projects ===

def get_project(project_id: int) -> dict:
    return projects.get(project_id)

def list_projects() -> list:
    return list(projects.values())

def create_project(project: dict) -> dict:
    project_id = project['project_id']
    projects[project_id] = project
    return project

def update_project(project_id: int, updates: dict) -> dict:
    project = projects[project_id]
    project.update(updates)
    return project

def delete_project(project_id: int) -> None:
    del projects[project_id]

def project_exists(project_id: int) -> bool:
    return project_id in projects

# === Resource: tasks ===

def get_task(task_id: int) -> dict:
    return tasks.get(task_id)

def list_tasks(filters: dict = None) -> list:
    if filters is None:
        return list(tasks.values())
    result = []
    for task in tasks.values():
        match = True
        for key, value in filters.items():
            if key not in task or task[key] != value:
                match = False
                break
        if match:
            result.append(task)
    return result

def create_task(task: dict) -> dict:
    task_id = task['task_id']
    tasks[task_id] = task
    return task

def update_task(task_id: int, updates: dict) -> dict:
    task = tasks[task_id]
    task.update(updates)
    return task

def delete_task(task_id: int) -> None:
    del tasks[task_id]

def task_exists(task_id: int) -> bool:
    return task_id in tasks