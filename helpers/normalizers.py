import re

def normalize_experience(exp: str) -> str:
    if not exp:
        return ""
    exp = exp.replace("–", "-").replace("—", "-").strip()
    if "year" not in exp.lower():
        exp = exp + " years"
    return exp

def normalize_skills(skills: str) -> str:
    if not skills:
        return ""
    skills_list = [s.strip() for s in re.split(r"[;,]", skills) if s.strip()]
    seen, normalized = set(), []
    for s in skills_list:
        low = s.lower()
        if low not in seen:
            seen.add(low)
            normalized.append(s)
    return ", ".join(normalized)

def normalize_text_field(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
