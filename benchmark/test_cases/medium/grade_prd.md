# Student Grade System - Product Requirements Document

## Overview
A student grade management system that coordinates students, courses, and grade records. Teachers can record grades, students can view their performance, and administrators can generate reports. Data is stored in memory across three data sources.

## External Interface
通过 `manage_grade(command, grade_data)` 函数调用实现成绩管理操作。

```
输入: {"command": "record_grade", "grade_data": {"student_id": 1, "course_id": 2, "score": 85}}
输出: {"success": true, "message": "成绩记录成功", "data": {"grade_id": 1}}
```

## Data Sources

### 1. Students (students)
- 存储学生信息
- 字段：student_id, name, class（班级），enrollment_year
- 初始状态：预置10个测试学生（2个班级）

### 2. Courses (courses)
- 存储课程信息
- 字段：course_id, name, credit（学分），teacher
- 初始状态：预置4门测试课程

### 3. Grades (grades)
- 存储成绩记录
- 字段：grade_id, student_id, course_id, score, recorded_at
- 成绩等级：A(90-100), B(80-89), C(70-79), D(60-69), F(<60)

## Core Features

### 1. Record Grade
- 教师录入学生成绩
- 检查学生存在
- 检查课程存在
- 检查成绩范围（0-100）
- 检查是否已有该学生该课程成绩（不允许重复）
- 创建成绩记录

### 2. Update Grade
- 教师修改学生成绩
- 检查成绩记录存在
- 更新分数和记录时间

### 3. Delete Grade
- 教师删除成绩记录
- 检查成绩记录存在
- 删除记录

### 4. Get Student Grades
- 获取某学生的所有成绩
- 计算平均分、总学分、GPA
- 按课程显示成绩和等级

### 5. Get Course Grades
- 获取某课程的所有学生成绩
- 计算课程平均分、最高分、最低分
- 统计各等级人数分布

### 6. List Grades by Class
- 按班级列出成绩
- 可指定课程筛选
- 计算班级平均分
- 排名显示

### 7. Get Grade Report
- 生成学生成绩报告单
- 包含：各科成绩、平均分、GPA、学分汇总
- 生成文字格式报告

### 8. Get Course Statistics
- 获取课程统计信息
- 平均分、标准差、及格率
- 各等级占比

### 9. Add Student
- 添加新学生
- 检查学号不重复

### 10. Add Course
- 添加新课程
- 检查课程号不重复

## Technical Constraints
- 内存存储（三个独立数据源）
- GPA计算：A=4.0, B=3.0, C=2.0, D=1.0, F=0
- 加权GPA = Σ(绩点 × 学分) / 总学分
- Python实现

## Input/Output Format

### Input
```json
{
  "command": "record_grade|update_grade|delete_grade|get_student_grades|get_course_grades|list_class_grades|get_grade_report|get_course_stats|add_student|add_course",
  "grade_data": {
    "student_id": 学生ID,
    "course_id": 课程ID,
    "score": 分数(0-100),
    "grade_id": 成绩记录ID,
    "class": 班级筛选,
    "name": 名称（add时用）,
    "credit": 学分（add_course时用）,
    "teacher": 教师（add_course时用）,
    "enrollment_year": 入学年份（add_student时用）
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

### Students
| student_id | name | class | enrollment_year |
|------------|------|-------|-----------------|
| 1 | 张明 | A班 | 2022 |
| 2 | 李华 | A班 | 2022 |
| 3 | 王芳 | A班 | 2022 |
| 4 | 刘强 | A班 | 2022 |
| 5 | 陈静 | A班 | 2022 |
| 6 | 赵伟 | B班 | 2022 |
| 7 | 周婷 | B班 | 2022 |
| 8 | 吴刚 | B班 | 2022 |
| 9 | 孙丽 | B班 | 2022 |
| 10 | 钱杰 | B班 | 2022 |

### Courses
| course_id | name | credit | teacher |
|-----------|------|--------|---------|
| 1 | 数学 | 4 | 王老师 |
| 2 | 英语 | 3 | 李老师 |
| 3 | 物理 | 3 | 张老师 |
| 4 | 化学 | 2 | 陈老师 |

## Example Usage

```
// 录入成绩
manage_grade("record_grade", {"student_id": 1, "course_id": 1, "score": 92})
→ {"success": true, "message": "成绩记录成功", "data": {"grade_id": 1, "letter_grade": "A"}}

// 重复录入（同一学生同一课程）
manage_grade("record_grade", {"student_id": 1, "course_id": 1, "score": 95})
→ {"success": false, "message": "该学生此课程已有成绩记录", "data": {"existing_grade_id": 1}}

// 更新成绩
manage_grade("update_grade", {"grade_id": 1, "score": 88})
→ {"success": true, "message": "成绩更新成功", "data": {"grade_id": 1, "new_letter_grade": "B"}}

// 获取学生成绩
manage_grade("get_student_grades", {"student_id": 1})
→ {"success": true, "data": {
    "grades": [{"course": "数学", "score": 88, "letter": "B", "credit": 4}],
    "average": 88,
    "total_credits": 4,
    "gpa": 3.0
}}

// 获取课程成绩分布
manage_grade("get_course_grades", {"course_id": 1})
→ {"success": true, "data": {
    "grades": [...],
    "average": 85.5,
    "max": 98,
    "min": 62,
    "distribution": {"A": 3, "B": 5, "C": 2, "D": 0, "F": 0}
}}

// 按班级查看成绩
manage_grade("list_class_grades", {"class": "A班", "course_id": 1})
→ {"success": true, "data": {
    "students": [{"student_id": 1, "name": "张明", "score": 88, "rank": 3}, ...],
    "class_average": 85.2
}}

// 生成成绩报告
manage_grade("get_grade_report", {"student_id": 1})
→ {"success": true, "data": {
    "report": "学生：张明\n班级：A班\n...\n数学：88(B)\n英语：85(B)\n平均分：86.5\nGPA：3.0\n总学分：7"
}}

// 课程统计
manage_grade("get_course_stats", {"course_id": 1})
→ {"success": true, "data": {
    "average": 85.5,
    "std_dev": 8.2,
    "pass_rate": 0.95,
    "grade_distribution": {"A": 30%, "B": 50%, "C": 15%, "F": 5%}
}}
```

## Success Criteria
- 三数据源协调查询正确
- GPA和加权计算正确
- 成绩等级转换正确
- 统计计算正确（平均分、标准差、及格率）
- 排名功能正确
- 重复录入检查正确
- 报告生成格式清晰