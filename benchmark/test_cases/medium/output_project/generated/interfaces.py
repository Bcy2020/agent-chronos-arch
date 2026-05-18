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
    member_id = member['member_id']
    members[member_id] = member
    return member

def update_member(member_id: int, updates: dict) -> dict:
    member = members[member_id]
    member.update(updates)
    return member

def delete_member(member_id: int) -> None:
    del members[member_id]

def member_exists(member_id: int) -> bool:
    return member_id in members

# === Resource: projects ===

def get_project(project_id: int) -> dict:
    return projects.get(project_id)

def list_projects() -> list:
    return list(projects.values())

def create_project(project: dict) -> dict:
    new_id = max(projects.keys()) + 1 if projects else 1
    project['project_id'] = new_id
    projects[new_id] = project
    return project

def update_project(project_id: int, updates: dict) -> dict:
    if project_id not in projects:
        return None
    projects[project_id].update(updates)
    return projects[project_id]

def delete_project(project_id: int) -> None:
    if project_id in projects:
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
            if key in task and task[key] != value:
                match = False
                break
        if match:
            result.append(task)
    return result

def create_task(task: dict) -> dict:
    new_id = max(tasks.keys()) + 1 if tasks else 1
    task['task_id'] = new_id
    tasks[new_id] = task
    return task

def update_task(task_id: int, updates: dict) -> dict:
    if task_id not in tasks:
        return None
    tasks[task_id].update(updates)
    return tasks[task_id]

def delete_task(task_id: int) -> None:
    if task_id in tasks:
        del tasks[task_id]

def task_exists(task_id: int) -> bool:
    return task_id in tasks