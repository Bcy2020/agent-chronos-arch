"""
Auto-generated interface layer code from InterfacePlan.
This layer is the ONLY layer allowed to directly access global variables.
"""

import datetime


# === Resource: students ===

def get_student(student_id: int) -> dict | None:
    return students.get(student_id)

def list_students() -> list[dict]:
    return list(students.values())

def create_student(student: dict) -> dict:
    if student['student_id'] in students:
        raise ValueError('student_id already exists')
    students[student['student_id']] = student
    return student

def student_exists(student_id: int) -> bool:
    return student_id in students

# === Resource: courses ===

def get_course(course_id: int) -> dict | None:
    return courses.get(course_id)

def list_courses() -> list[dict]:
    return list(courses.values())

def create_course(course: dict) -> dict:
    course_id = course['course_id']
    if course_id in courses:
        raise ValueError(f"Course with id {course_id} already exists")
    courses[course_id] = course
    return course

def course_exists(course_id: int) -> bool:
    return course_id in courses

# === Resource: grades ===

def get_grade(grade_id: int) -> dict | None:
    return grades.get(grade_id)

def list_grades(filters: dict = None) -> list[dict]:
    if filters is None:
        return list(grades.values())
    result = []
    for grade in grades.values():
        match = True
        for key, value in filters.items():
            if key not in grade or grade[key] != value:
                match = False
                break
        if match:
            result.append(grade)
    return result

def create_grade(grade: dict) -> dict:
    # Check preconditions: student_id exists in students, course_id exists in courses, score between 0 and 100, no duplicate (student_id, course_id)
    # Note: Preconditions involving other resources (students, courses) are not enforced here as per interface layer rules.
    # Only enforce invariants that are local to this resource.
    if not (0 <= grade.get('score', 0) <= 100):
        raise ValueError("Score must be between 0 and 100")
    for existing in grades.values():
        if existing['student_id'] == grade['student_id'] and existing['course_id'] == grade['course_id']:
            raise ValueError("Duplicate (student_id, course_id) pair")
    grade_id = max(grades.keys(), default=0) + 1
    grade['grade_id'] = grade_id
    grades[grade_id] = grade
    return grade

def update_grade(grade_id: int, updates: dict) -> dict:
    if grade_id not in grades:
        raise KeyError(f"Grade {grade_id} not found")
    grade = grades[grade_id]
    allowed_keys = {'score', 'recorded_at'}
    for key in updates:
        if key not in allowed_keys:
            raise ValueError(f"Cannot update field: {key}")
    grade.update(updates)
    return grade

def delete_grade(grade_id: int) -> None:
    if grade_id not in grades:
        raise KeyError(f"Grade {grade_id} not found")
    del grades[grade_id]

def grade_exists(grade_id: int) -> bool:
    return grade_id in grades