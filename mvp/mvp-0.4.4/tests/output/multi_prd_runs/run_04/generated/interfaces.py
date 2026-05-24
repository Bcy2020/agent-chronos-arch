"""
Auto-generated interface layer code from InterfacePlan.
This layer is the ONLY layer allowed to directly access global variables.
"""

import datetime


# === Resource: students ===

def get_student(student_id: int) -> dict:
    return students.get(student_id)

def list_students(filters: dict) -> list:
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

def get_course(course_id: int) -> dict:
    return courses.get(course_id)

def list_courses(filters: dict) -> list:
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

def get_grade(grade_id: int) -> dict:
    return grades.get(grade_id)

def list_grades(filters: dict) -> list:
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
    if not (0 <= grade['score'] <= 100):
        raise ValueError('Score must be between 0 and 100')
    for g in grades.values():
        if g['student_id'] == grade['student_id'] and g['course_id'] == grade['course_id']:
            raise ValueError('Duplicate student-course pair')
    new_id = max(grades.keys()) + 1 if grades else 1
    grade['grade_id'] = new_id
    grades[new_id] = grade
    return grade

def update_grade(grade_id: int, updates: dict) -> dict:
    if grade_id not in grades:
        raise KeyError('Grade not found')
    if 'score' in updates and not (0 <= updates['score'] <= 100):
        raise ValueError('Score must be between 0 and 100')
    grades[grade_id].update(updates)
    return grades[grade_id]

def delete_grade(grade_id: int) -> None:
    if grade_id not in grades:
        raise KeyError('Grade not found')
    del grades[grade_id]

def grade_exists(grade_id: int) -> bool:
    return grade_id in grades