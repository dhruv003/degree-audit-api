"""Degree Audit API.

Phase 1 (catalog import) and Phase 2 (history, plan, profile) keep the same
routes, request bodies and responses as course-registration-api and
student-academic-api. Phase 3 adds the audit-report endpoint.
"""

from threading import RLock

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from pydantic import BaseModel

from audit import build_audit_report
from catalog import course_key, parse_catalog
from transcript import parse_transcript

app = FastAPI(title="Degree Audit API")

COURSES = {}
students = {}
lock = RLock()


class HistoryCourse(BaseModel):
    course_code: str
    term: str
    credits_earned: int
    status: str


class HistoryRequest(BaseModel):
    history: list[HistoryCourse]


class PlanCourse(BaseModel):
    course_code: str
    term: str


class PlanRequest(BaseModel):
    planned_courses: list[PlanCourse]


def get_student(student_id):
    if student_id not in students:
        raise HTTPException(status_code=404, detail="Student not found")
    return students[student_id]


@app.get("/")
def root():
    return {"message": "Degree Audit API is running"}


@app.get("/health")
def health():
    return {"status": "ok"}


# --------------------------------------------------------------- Phase 1


@app.post("/api/v1/admin/catalog/import")
async def import_catalog(file: UploadFile = File(...)):
    raw_file = await file.read()
    try:
        html = raw_file.decode("utf-8-sig")
    except UnicodeDecodeError:
        html = raw_file.decode("latin-1")

    parsed_courses = parse_catalog(html)
    if not parsed_courses:
        raise HTTPException(
            status_code=400,
            detail="No course records could be parsed from the uploaded HTML file.",
        )

    with lock:
        COURSES.clear()
        COURSES.update(parsed_courses)

    return {"message": "Catalog imported successfully", "courses_imported": len(COURSES)}


@app.get("/api/v1/catalog/courses/{course_code}")
def get_course(course_code: str):
    key = course_key(course_code)
    if key not in COURSES:
        raise HTTPException(status_code=404, detail="Course not found")
    return COURSES[key]


# --------------------------------------------------------------- Phase 2


@app.post("/api/v1/students/{student_id}/history/import", status_code=201)
async def import_history(student_id: str, file: UploadFile = File(...)):
    content = await file.read()
    history = parse_transcript(content.decode("utf-8-sig", errors="replace"))

    with lock:
        if student_id not in students:
            students[student_id] = {"history": [], "plan": []}
        students[student_id]["history"] = history

    return {"status": "success", "past_courses_imported": len(history)}


@app.put("/api/v1/students/{student_id}/history")
def update_history(student_id: str, body: HistoryRequest):
    with lock:
        student = get_student(student_id)
        student["history"] = [course.model_dump() for course in body.history]
    return {"status": "success", "message": "Academic history updated successfully"}


@app.delete("/api/v1/students/{student_id}/history")
def delete_history(student_id: str):
    with lock:
        get_student(student_id)["history"] = []
    return {"status": "success"}


def save_plan(student_id, body):
    with lock:
        student = get_student(student_id)
        student["plan"] = [course.model_dump() for course in body.planned_courses]
    return {"status": "success", "planned_courses_saved": len(body.planned_courses)}


@app.post("/api/v1/students/{student_id}/plan")
def create_plan(student_id: str, body: PlanRequest):
    return save_plan(student_id, body)


@app.put("/api/v1/students/{student_id}/plan")
def update_plan(student_id: str, body: PlanRequest):
    return save_plan(student_id, body)


@app.delete("/api/v1/students/{student_id}/plan")
def delete_plan(student_id: str):
    with lock:
        get_student(student_id)["plan"] = []
    return {"status": "success"}


@app.get("/api/v1/students/{student_id}/profile")
def get_profile(student_id: str):
    with lock:
        student = get_student(student_id)
        return {
            "student_id": student_id,
            "history": [course.copy() for course in student["history"]],
            "plan": [course.copy() for course in student["plan"]],
        }


# --------------------------------------------------------------- Phase 3


@app.get("/api/v1/students/{student_id}/audit-report")
def audit_report(student_id: str, strict: bool = Query(False)):
    with lock:
        student = get_student(student_id)
        history = [course.copy() for course in student["history"]]
        plan = [course.copy() for course in student["plan"]]
        catalog = dict(COURSES)
    return build_audit_report(student_id, history, plan, catalog, strict)
