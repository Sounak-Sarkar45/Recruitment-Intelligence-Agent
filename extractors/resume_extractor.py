import re
import json
from langchain_core.messages import HumanMessage
from llm_client import llm
from helpers.normalizers import normalize_experience, normalize_skills, normalize_text_field
from datetime import datetime
from typing import Dict, Any

def parse_experience_dates(text: str) -> int:
    """
    Extract and calculate total months of work experience from job history.
    Handles variations like '-' and '–' and 'Present'.
    """
    # Normalize dashes
    text = text.replace("–", "-").replace("—", "-")

    # Pattern for date ranges: (Jan 2024 - Aug 2024), (Jan 2025 - Present)
    date_pattern = re.findall(r"\((\w+\s\d{4})\s*-\s*(\w+\s\d{4}|Present)\)", text)

    total_months = 0
    current_year = datetime.now().year
    current_month = datetime.now().month

    month_map = {
        "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4,
        "May": 5, "Jun": 6, "Jul": 7, "Aug": 8,
        "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12
    }

    for start, end in date_pattern:
        # Parse start date
        sm, sy = start.split()
        sm, sy = month_map[sm[:3]], int(sy)

        # Parse end date
        if "Present" in end:
            em, ey = current_month, current_year
        else:
            em, ey = end.split()
            em, ey = month_map[em[:3]], int(ey)

        # Include both start and end month → +1
        months = (ey - sy) * 12 + (em - sm) + 1
        total_months += max(0, months)

    return total_months


def extract_resume_attributes(text: str) -> Dict[str, Any]:
    """Extract structured attributes from a resume with fixed schema."""

    # Work experience calculation
    total_months = parse_experience_dates(text)
    years = total_months // 12
    months = total_months % 12
    exp_str = f"{years} years {months} months" if years > 0 else f"{months} months"

    # LLM prompt: enforce fixed schema
    prompt = f"""
    You are an intelligent resume parser.
    Extract the following details strictly into the JSON schema given below:

    - Key Skills: return as a comma-separated string.
    - Notice Period: if not found, leave empty.
    - Location: if not found, leave empty.
    - Degrees: list with objects {{'degree', 'institute', 'duration', 'CGPA/grade'}}.
    - Courses: list with objects {{'course', 'provider'}}.
    - Interpersonal Skills: list of soft skills (leadership, teamwork, communication, confidence, etc.).
    - Awards: list of awards, honors, recognitions.

    Rules:
    - If something is not explicitly mentioned, return [] for lists or "" for strings.
    - Do NOT change the field names.
    - Do NOT omit any field.
    - Always return valid JSON in exactly this schema.

    {{
      "Key Skills": "...",
      "Notice Period": "",
      "Location": "",
      "Degrees": [],
      "Courses": [],
      "Interpersonal Skills": [],
      "Awards": [],
      "Years of Experience": "{exp_str}"
    }}

    Resume Text:
    {text}
    """

    resp = llm.invoke([HumanMessage(content=prompt)]).content.strip()

    # Force JSON validity
    match = re.search(r"\{.*\}", resp, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group())
            parsed["Years of Experience"] = exp_str  # overwrite with computed value
            return parsed
        except:
            pass

    # Fallback (if parsing fails)
    return {
        "Key Skills": "",
        "Notice Period": "",
        "Location": "",
        "Degrees": [],
        "Courses": [],
        "Interpersonal Skills": [],
        "Awards": [],
        "Years of Experience": exp_str
    }