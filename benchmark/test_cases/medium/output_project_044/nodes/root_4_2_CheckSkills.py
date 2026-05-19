def CheckSkills(task: dict, member: dict, check_skills: bool) -> bool:
    if not check_skills:
        return True
    required = set(task.get('required_skills', []))
    member_skills = set(member.get('skills', []))
    if required.issubset(member_skills):
        return True
    else:
        raise ValueError('Member does not have required skills')