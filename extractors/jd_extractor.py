import re, json
from langchain_core.messages import HumanMessage
from llm_client import llm
from helpers.normalizers import normalize_experience, normalize_skills, normalize_text_field
from typing import Dict

def extract_jd_attributes(text: str) -> Dict[str, str]:
    """Extract structured attributes from a job description with fixed schema."""

    prompt = f"""
    You are an intelligent job description parser.
    Extract the following details strictly into the JSON schema given below:

    - Key Skills: return ONLY technical skills (programming languages, frameworks, libraries, ML/DL algorithms, cloud tools, APIs, software platforms). 
    ❌ Do NOT include company names, soft skills, domains, business terms, responsibilities, or generic words like "cloud", "solutions", "predictive models".
    - Years of Experience: extract if explicitly mentioned, else "".
    - Notice Period: extract if mentioned, else "".
    - Location: extract if mentioned, else "".
    - Other Requirements: include certifications, domain knowledge, or industry-specific needs.

    Rules:
    - If something is not explicitly mentioned, return "".
    - Do NOT change field names.
    - Do NOT omit any field.
    - Always return valid JSON in exactly this schema.

    {{
    "Key Skills": "",
    "Years of Experience": "",
    "Notice Period": "",
    "Location": "",
    "Other Requirements": ""
    }}

    Job Description:
    {text}
    """

    resp = llm.invoke([HumanMessage(content=prompt)]).content.strip()

    # Validate and force schema
    match = re.search(r"\{.*\}", resp, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group())

            # Normalize fields for consistency
            fixed_result = {
                "Key Skills": normalize_skills(parsed.get("Key Skills", "")),
                "Years of Experience": normalize_experience(parsed.get("Years of Experience", "")),
                "Notice Period": normalize_text_field(parsed.get("Notice Period", "")),
                "Location": normalize_text_field(parsed.get("Location", "")),
                "Other Requirements": normalize_text_field(parsed.get("Other Requirements", ""))
            }
            return fixed_result
        except:
            pass

    # Fallback (safe empty schema)
    return {
        "Key Skills": "",
        "Years of Experience": "",
        "Notice Period": "",
        "Location": "",
        "Other Requirements": ""
    }