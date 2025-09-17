import json
from langchain_core.messages import HumanMessage
from llm_client import llm
from helpers.fuzzy import fuzzy_match
from langchain_core.prompts import ChatPromptTemplate
import regex as re

def llm_find_common_skills(llm, jd_skills: list, resume_skills: list) -> list:
    """
    Find JD skills that match resume skills using LLM semantic reasoning.
    Returns only JD skills that have a valid match in the resume.
    """

    if not jd_skills or not resume_skills:
        return []

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", """You are an expert recruiter.
        Your task is to identify which skills from the Job Description are represented in the Resume.

        A Job Description skill is a match if the resume skill is:
        - The exact same skill.
        - An acronym or full form (e.g., 'LLM' ↔ 'Large Language Model').
        - A synonym, equivalent term, or related technology.
        - A broader category or a sub-skill.

        ❌ Do not match unrelated skills (e.g., 'Java' ≠ 'JavaScript').
        ✅ Only return JD skills that matched. No resume skills in the output.

        Output strictly as a JSON list of JD skills.
        """),
        ("human", f"""
        Job Description Skills:
        {jd_skills}

        Resume Skills:
        {resume_skills}

        Output:
        """)
    ])

    try:
        response = llm.invoke(prompt_template.format_messages())
        text = response.content.strip()

        if not isinstance(text, str):
            print(f"LLM response content is not a string. Type: {type(text)}")
            return []

        match = re.search(r"```json\n(.*?)\n```", text, re.DOTALL)
        if match:
            json_text = match.group(1).strip()
        else:
            match = re.search(r"\[.*\]", text, re.DOTALL)
            if match:
                json_text = match.group(0).strip()
            else:
                print("Could not find a JSON list in the LLM's response.")
                return []

        matched_skills = json.loads(json_text)

        if not isinstance(matched_skills, list):
            print("Parsed JSON is not a list.")
            return []

        # Validate against original JD skills to prevent hallucinations
        validated_skills = [
            skill for skill in matched_skills
            if isinstance(skill, str) and fuzzy_match(skill, jd_skills)
        ]

        return list(set(validated_skills))

    except (json.JSONDecodeError, IndexError, AttributeError) as e:
        print(f"Error parsing LLM response or during validation: {e}")
        print(f"Original LLM response text:\n{text}")
        return []