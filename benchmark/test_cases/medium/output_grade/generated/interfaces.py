"""
Auto-generated interface layer code from InterfacePlan.
This layer is the ONLY layer allowed to directly access global variables.
"""

import datetime


# === Resource: students ===

def get_student(student_id: int) -> dict | None:
    return students.get(student_id)

def list_students(filters: dict = None) -> list:
    if filters is None:
        return list(students.values())
    result = []
    for student in students.values():
        match = True
        for key, value in filters.items():
            if key not in student or student[key] != value:
                match = False
                break
        if match:
            result.append(student)
    return result

def create_student(student: dict) -> dict:
    student_id = student['student_id']
    if student_id in students:
        raise ValueError(f"Student with id {student_id} already exists")
    students[student_id] = student
    return student

def student_exists(student_id: int) -> bool:
    return student_id in students

# === Resource: courses ===

def get_course(course_id: int) -> dict | None:
    return courses.get(course_id)

def list_courses(filters: dict = None) -> list:
    if filters is None:
        return list(courses.values())
    result = []
    for course in courses.values():
        match = True
        for key, value in filters.items():
            if key not in course or course[key] != value:
                match = False
                break
        if match:
            result.append(course)
    return result

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

def list_grades(filters: dict = None) -> list:
    if filters is None:
        return list(grades.values())
    result = []
    for g in grades.values():
        match = True
        for key, value in filters.items():
            if key not in g or g[key] != value:
                match = False
                break
        if match:
            result.append(g)
    return result

def create_grade(grade: dict) -> dict:
    # Check preconditions
    if not (0 <= grade['score'] <= 100):
        raise ValueError("Score must be between 0 and 100")
    # Check duplicate (student_id, course_id)
    for g in grades.values():
        if g['student_id'] == grade['student_id'] and g['course_id'] == grade['course_id']:
            raise ValueError("Duplicate grade for student and course")
    # Generate new grade_id
    new_id = max(grades.keys(), default=0) + 1
    grade['grade_id'] = new_id
    grades[new_id] = grade
    return grade

def update_grade(grade_id: int, updates: dict) -> dict:
    if grade_id not in grades:
        raise KeyError(f"Grade {grade_id} not found")
    grade = grades[grade_id]
    # Only allow updating score and recorded_at
    allowed_keys = {'score', 'recorded_at'}
    for key in updates:
        if key not in allowed_keys:
            raise ValueError(f"Cannot update field: {key}")
    grade.update(updates)
    return grade

def delete_grade(grade_id: int) -> bool:
    if grade_id not in grades:
        raise KeyError(f"Grade {grade_id} not found")
    del grades[grade_id]
    return True

def grade_exists(grade_id: int) -> bool:
    return grade_id in grades