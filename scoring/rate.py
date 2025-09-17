from state import AgentState
from extractors.jd_extractor import extract_jd_attributes
from extractors.resume_extractor import extract_resume_attributes
from extractors.skills_matcher import llm_find_common_skills
from helpers.pdf_utils import read_pdf
from llm_client import llm
from langchain_core.messages import HumanMessage

def rate_resume(state: AgentState) -> AgentState:
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
    
    # Use similarity score as final_score
    final_score = state["similarity_score"]

    # Rating buckets
    if final_score >= 80:
        rating = "Strong Match"
    elif final_score >= 50:
        rating = "Moderate Match"
    else:
        rating = "Weak Match"

    # Extract granular scores
    attribute_scores = state["attribute_scores"]
    skills_score = attribute_scores.get("Skills Match", 0)
    experience_score = attribute_scores.get("Experience Match", 0)
    location_score = attribute_scores.get("Location Match", 0)
    notice_score = attribute_scores.get("Notice Period Match", 0)
    other_score = attribute_scores.get("Other Requirements Match", 0)

    # Scoring weights
    weights = {
        "Skills Match": 0.35,
        "Experience Match": 0.25,
        "Location Match": 0.15,
        "Notice Period Match": 0.10,
        "Other Requirements Match": 0.15,
    }

    # Prompt for LLM feedback (includes Other Requirements Match)
    comments_prompt = f"""
    You are generating a recruiter-facing candidate feedback report. Do not include a title or heading for the report itself.

    Candidate Final Score: {final_score:.2f}% ({rating})

    Detailed Attribute Scores:
    - Skills Match: {skills_score}% 
    - Experience Match: {experience_score}% 
    - Location Match: {location_score}% 
    - Notice Period Match: {notice_score}% 
    - Other Requirements Match: {other_score}%

    Skills Analysis:
    - Matched Skills: {matched_skills}
    - Missing Skills: {missing}

    Experience:
    - JD Requirement: {state['jd_summary'].get('Years of Experience', 'Not specified')}
    - Candidate Experience: {state['resume_summary'].get('Years of Experience', 'Not specified')}

    Notice Period:
    - JD Requirement: {state['jd_summary'].get('Notice Period', 'Not specified')}
    - Candidate Notice Period: {state['resume_summary'].get('Notice Period', 'Not specified')}

    Education:
    - JD Degrees Requirement: {state['jd_summary'].get('Degrees', [])}
    - Candidate Degrees: {state['resume_summary'].get('Degrees', [])}
    - Candidate Courses/Certifications: {state['resume_summary'].get('Courses', [])}

    Instructions for feedback:
    1. Write the report in **under 200 words**.
    2. Use exactly **3 sections**: **Strengths, Weaknesses, Summary**.
    3. In **Strengths**:
       - Mention if experience, location, or notice period requirements are matched.
       - Compare candidate’s degrees/certifications with the JD. If they are extra or relevant, highlight as a plus.
       - Mention matching skills explicitly and classify the skills match:
         * >80% → Good skills match
         * 50–80% → Moderate skills match
         * <50% → Poor skills match
    4. In **Weaknesses**:
       - **Crucially, only mention a weakness if its Attribute Score is less than 100%.**
       - **Do not** mention experience as a weakness if its score is 100%.
       - Focus on the specific skills that are missing, as indicated in the "Missing Skills" list.
       - Do **not** mention “other requirements” like courses or interpersonal skills here.
    5. In **Summary**:
       - Provide a concise recruiter-focused overview balancing strengths and weaknesses.
       - Avoid repetition, keep it professional and precise.
    """
    resp = llm.invoke([HumanMessage(content=comments_prompt)])

    # Save results
    state["rating"] = rating
    state["comments"] = resp.content.strip()

    # Build detailed breakdown with weighted contributions only
    breakdown = "\n===== Resume Match Breakdown =====\n"
    for attr, score in attribute_scores.items():
        weight = weights.get(attr, 0)
        weighted = round(score * weight, 2)
        breakdown += f"{attr:<25}: Total: {round(weight * 100, 2)}% → Contribution: {weighted}%\n"

    breakdown += "-----------------------------------\n"
    breakdown += f"Final Score             : {final_score:.2f}% → {rating}\n"
    breakdown += "===================================\n"

    # Add Other Requirements Breakdown (contributions to 9.75%)
    if "other_breakdown" in state:
        other_weight = weights["Other Requirements Match"]  # 0.15
        sub_max = {
            "Degrees": 3.75,
            "Courses": 3.75,
            "Interpersonal Skills": 3.75,
            "Awards": 3.75
        }
        breakdown += "\n--- Other Requirements Breakdown ---\n"
        for sub, sc in state["other_breakdown"].items():
            # Calculate contribution to the final score
            contribution = round(sc * other_weight, 2)
            breakdown += f"  {sub:<20}: Total: {sub_max[sub]}% → Contribution: {contribution}%\n"
        breakdown += "-----------------------------------\n"

    print(breakdown)  # for console / logs
    state["score_breakdown"] = breakdown.strip()  # store in state so UI/recruiter can see

    return state