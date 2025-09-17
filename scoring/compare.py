from state import AgentState
from helpers.pdf_utils import read_pdf
from extractors.jd_extractor import extract_jd_attributes
from extractors.resume_extractor import extract_resume_attributes
from extractors.skills_matcher import llm_find_common_skills
from helpers.fuzzy import fuzzy_match
from llm_client import llm

def parse_and_compare(state: AgentState) -> AgentState:
    jd = state["job_description"]

    # Summarize JD
    jd_summary = extract_jd_attributes(jd)
    state["jd_summary"] = jd_summary

    # Extract text from PDF
    resume_text = read_pdf(state["resume_file"])
    state["resume_text"] = resume_text

    # Summarize Resume
    resume_summary = extract_resume_attributes(resume_text)
    state["resume_summary"] = resume_summary

    # --- Calculate Attribute Scores ---
    attribute_scores = {}

    # 1. Skills Match
    jd_skills_raw = [s.strip() for s in jd_summary.get("Key Skills", "").split(',') if s.strip()]
    resume_skills_raw = [s.strip() for s in resume_summary.get("Key Skills", "").split(',') if s.strip()]

    # Use original case for LLM
    matched_skills = llm_find_common_skills(llm, jd_skills_raw, resume_skills_raw)
    
    print('Job Description Skills: ',jd_skills_raw)
    print('Resume Skills: ',resume_skills_raw)
    print('Common skills between job description and resume: ',matched_skills)
    missing=list(set(jd_skills_raw)-set(matched_skills))
    print('Missing skills between job description and resume: ',missing)
    
    # Save to state so other functions can use them
    state["matched_skills"] = matched_skills
    state["missing_skills"] = missing

    # For scoring → normalize to lowercase
    jd_skills = [s.lower() for s in jd_skills_raw]
    matched_lower = {s.lower() for s in matched_skills}

    if jd_skills:
        skills_score = (len(matched_lower) / len(jd_skills)) * 100
    else:
        skills_score = 100

    attribute_scores["Skills Match"] = round(skills_score, 2)
    state["matched_skills"] = matched_skills

    # 2. Experience Match % (tolerant scoring)
    jd_exp_str = str(jd_summary.get("Years of Experience", "0")).replace('+', '').strip()
    resume_exp_str = str(resume_summary.get("Years of Experience", "0")).replace('+', '').strip()

    def extract_years(exp_str: str) -> float:
        nums = [int(x) for x in exp_str.split() if x.isdigit()]
        if "-" in exp_str:  # handle "2-4 years"
            parts = exp_str.replace("years", "").replace("year", "").split("-")
            try:
                nums = [int(p.strip()) for p in parts if p.strip().isdigit()]
            except:
                nums = []
        if len(nums) == 2:
            return sum(nums) / 2  # take average for a range
        return nums[0] if nums else 0

    jd_years = extract_years(jd_exp_str)
    resume_years = extract_years(resume_exp_str)

    if jd_years == 0 and resume_years > 0:
        exp_score = 100  # JD didn’t specify
    elif resume_years == 0:
        exp_score = 0  # resume missing -> penalize
    elif resume_years >= jd_years:
        exp_score = 100
    else:
        exp_score = (resume_years / jd_years) * 100

    attribute_scores["Experience Match"] = round(exp_score, 2)

    # 3. Location Match %
    jd_loc = jd_summary.get("Location", "").strip().lower()
    resume_loc = resume_summary.get("Location", "").strip().lower()

    if "remote" in jd_loc:
        loc_score = 100
    elif not resume_loc:  # resume missing location -> penalty only if JD needs a specific city
        loc_score = 0
    elif "remote" in resume_loc:
        loc_score = 100
    else:
        jd_locs = [l.strip() for l in jd_loc.split(",")]
        if any(l in resume_loc or resume_loc in l for l in jd_locs if l):
            loc_score = 100
        elif jd_loc and resume_loc and jd_loc != resume_loc:
            loc_score = 50
        else:
            loc_score = 0
    attribute_scores["Location Match"] = loc_score

    # 4. Notice Period Match %
    jd_notice_str = str(jd_summary.get("Notice Period", "30")).strip()
    resume_notice_str = str(resume_summary.get("Notice Period", "30")).strip()

    try:
        jd_notice = int(''.join(filter(str.isdigit, jd_notice_str)))
    except:
        jd_notice = float('inf')

    try:
        resume_notice = int(''.join(filter(str.isdigit, resume_notice_str)))
    except:
        resume_notice = float('inf')

    if resume_notice == float('inf'):  # missing in resume
        notice_score = 100  # ignore if missing
    else:
        notice_score = 100 if resume_notice <= jd_notice else 0
    attribute_scores["Notice Period Match"] = notice_score

    # 5. Other Requirements (semantic / fuzzy matching)
    jd_degrees = [d.strip().lower() for d in jd_summary.get("Degrees", [])]
    jd_courses = [c.strip().lower() for c in jd_summary.get("Courses", [])]
    jd_interpersonal_skills = [s.strip().lower() for s in jd_summary.get("Interpersonal Skills", [])]
    jd_awards = [a.strip().lower() for a in jd_summary.get("Awards", [])]

    def get_list_of_strings(summary_key, default_value=[]):
        items = resume_summary.get(summary_key, default_value)
        if all(isinstance(item, dict) for item in items):
            # Extract degree or course name from dictionaries
            return [item.get("degree", item.get("course", "")).strip().lower() for item in items]
        return [str(item).strip().lower() for item in items]

    resume_degrees = get_list_of_strings("Degrees")
    resume_courses = get_list_of_strings("Courses")
    resume_interpersonal_skills = get_list_of_strings("Interpersonal Skills")
    resume_awards = get_list_of_strings("Awards")

    other_total_score = 0
    other_breakdown = {}  # Store sub-scores
    matched_other_requirements = []

    # Score Degrees
    degrees_score = 0
    if jd_degrees:
        match_found = False
        for jd_d in jd_degrees:
            if any(fuzzy_match(jd_d, resume_d) for resume_d in resume_degrees):
                degrees_score = 25  # Directly relevant
                match_found = True
                matched_other_requirements.append(jd_d)
                break
        if not match_found and resume_degrees:
            degrees_score = 15  # Partially relevant
    elif resume_degrees:
        degrees_score = 25  # JD didn't specify, but resume has it
    other_total_score += degrees_score
    other_breakdown["Degrees"] = degrees_score

    # Score Courses
    courses_score = 0
    if jd_courses:
        match_found = False
        for jd_c in jd_courses:
            if any(fuzzy_match(jd_c, resume_c) for resume_c in resume_courses):
                courses_score = 25  # Directly relevant
                match_found = True
                matched_other_requirements.append(jd_c)
                break
        if not match_found and resume_courses:
            courses_score = 15  # Partially relevant
    elif resume_courses:
        courses_score = 25  # JD didn't specify, but resume has it
    other_total_score += courses_score
    other_breakdown["Courses"] = courses_score

    # Score Interpersonal Skills
    interpersonal_skills_score = 0
    if jd_interpersonal_skills:
        match_count = 0
        for jd_s in jd_interpersonal_skills:
            if any(fuzzy_match(jd_s, resume_s) for resume_s in resume_interpersonal_skills):
                match_count += 1
                matched_other_requirements.append(jd_s)
        if match_count == len(jd_interpersonal_skills):
            interpersonal_skills_score = 25  # All skills matched
        elif match_count > 0:
            interpersonal_skills_score = 15  # Some skills matched
    elif resume_interpersonal_skills:
        interpersonal_skills_score = 25  # JD didn't specify, but resume has some (changed to 25 for consistency)
    other_total_score += interpersonal_skills_score
    other_breakdown["Interpersonal Skills"] = interpersonal_skills_score

    # Score Awards
    awards_score = 0
    if jd_awards:
        match_found = False
        for jd_a in jd_awards:
            if any(fuzzy_match(jd_a, resume_a) for resume_a in resume_awards):
                awards_score = 25  # Directly relevant
                match_found = True
                matched_other_requirements.append(jd_a)
                break
        if not match_found and resume_awards:
            awards_score = 15  # Partially relevant
    elif resume_awards:
        awards_score = 25  # JD didn't specify, but resume has some (changed to 25 for consistency)
    other_total_score += awards_score
    other_breakdown["Awards"] = awards_score

    attribute_scores["Other Requirements Match"] = round(other_total_score, 2)
    state["matched_other_requirements"] = list(set(matched_other_requirements))
    state["other_breakdown"] = other_breakdown  # Store the breakdown

    # --- Final Score (weighted average) ---
    weights = {
        "Skills Match": 0.35,
        "Experience Match": 0.25,
        "Location Match": 0.15,
        "Other Requirements Match": 0.15,
        "Notice Period Match": 0.10
    }

    weighted_score = 0
    for attr, score in attribute_scores.items():
        weight = weights.get(attr, 0)
        weighted_score += score * weight

    state["attribute_scores"] = attribute_scores
    state["similarity_score"] = round(weighted_score, 2)

    return state