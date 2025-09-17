import os
import shutil
import uvicorn
import markdown   # <-- add this
from fastapi import FastAPI, UploadFile, Form, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

# Import pipeline
from main import app as workflow_app, AgentState

load_dotenv()

fastapi_app = FastAPI(title="JD-Resume Matcher API")

# Templates directory
templates = Jinja2Templates(directory="templates")
fastapi_app.mount("/static", StaticFiles(directory="static"), name="static")


# ---------- Home Page ----------
@fastapi_app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# ---------- API Endpoint ----------
@fastapi_app.post("/match")
async def match_resume(
    request: Request,
    job_description: str = Form(...),
    resume: UploadFile = None
):
    if resume is None:
        return JSONResponse(status_code=400, content={"error": "Resume PDF is required"})
    
    # Save uploaded resume temporarily
    temp_resume_path = f"temp_{resume.filename}"
    with open(temp_resume_path, "wb") as buffer:
        shutil.copyfileobj(resume.file, buffer)

    # Initialize state
    state: AgentState = {
        "job_description": job_description,
        "resume_file": temp_resume_path,
        "jd_summary": {},
        "resume_text": "",
        "resume_summary": {},
        "attribute_scores": {},
        "similarity_score": 0,
        "rating": "",
        "comments": ""
    }

    # Run pipeline
    result = workflow_app.invoke(state)

    # Convert markdown in comments to HTML
    if result.get("comments"):
        result["comments_html"] = markdown.markdown(result["comments"])
    else:
        result["comments_html"] = ""

    # Cleanup
    try:
        os.remove(temp_resume_path)
    except:
        pass

    # Render results on frontend
    return JSONResponse(content=result)
    return templates.TemplateResponse("result.html", {"request": request, "result": result})

if __name__ == "__main__":
    uvicorn.run("app:fastapi_app", host="0.0.0.0", port=8000, reload=True)
