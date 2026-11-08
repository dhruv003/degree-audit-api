import pytest
from fastapi.testclient import TestClient

import main

SID = "770001"


@pytest.fixture
def client():
    main.COURSES.clear()
    main.students.clear()
    return TestClient(main.app)


def upload_catalog(client, html):
    return client.post("/api/v1/admin/catalog/import", files={"file": ("c.html", html, "text/html")})


def upload_transcript(client, html, sid=SID):
    return client.post(f"/api/v1/students/{sid}/history/import", files={"file": ("t.html", html, "text/html")})


def test_root_and_health(client):
    assert client.get("/").status_code == 200
    assert client.get("/health").json() == {"status": "ok"}


def test_phase1_catalog(client, catalog_html):
    r = upload_catalog(client, catalog_html)
    assert r.status_code == 200
    assert r.json() == {"message": "Catalog imported successfully", "courses_imported": 5}
    for code in ("COSC3506", "cosc-3506", "COSC 3506"):
        assert client.get(f"/api/v1/catalog/courses/{code}").json()["cross_listed"] == ["ITEC 3506"]
    assert client.get("/api/v1/catalog/courses/NOPE9999").status_code == 404
    assert upload_catalog(client, "<p>no table</p>").status_code == 400
    latin = client.post("/api/v1/admin/catalog/import", files={"file": ("c.html", b"\xff\xfe<p></p>", "text/html")})
    assert latin.status_code == 400


def test_phase2_history_plan_profile(client, transcript_html):
    r = upload_transcript(client, transcript_html)
    assert r.status_code == 201
    assert r.json() == {"status": "success", "past_courses_imported": 33}

    body = {"planned_courses": [{"course_code": "COSC-4426", "term": "26F"}]}
    assert client.post(f"/api/v1/students/{SID}/plan", json=body).json()["planned_courses_saved"] == 1
    assert client.put(f"/api/v1/students/{SID}/plan", json=body).json()["status"] == "success"

    profile = client.get(f"/api/v1/students/{SID}/profile").json()
    assert profile["student_id"] == SID
    assert len(profile["history"]) == 33
    assert profile["plan"] == body["planned_courses"]

    new_history = {"history": [{"course_code": "COSC-2006", "term": "24W", "credits_earned": 3, "status": "Completed"}]}
    assert client.put(f"/api/v1/students/{SID}/history", json=new_history).status_code == 200
    assert len(client.get(f"/api/v1/students/{SID}/profile").json()["history"]) == 1

    assert client.delete(f"/api/v1/students/{SID}/plan").json() == {"status": "success"}
    assert client.delete(f"/api/v1/students/{SID}/history").json() == {"status": "success"}


def test_phase2_unknown_student_and_bad_body(client):
    body = {"planned_courses": [{"course_code": "COSC-4426", "term": "26F"}]}
    assert client.post("/api/v1/students/nobody/plan", json=body).status_code == 404
    assert client.get("/api/v1/students/nobody/profile").status_code == 404
    assert client.get("/api/v1/students/nobody/audit-report").status_code == 404
    upload_transcript(client, "<p>empty</p>")
    assert client.post(f"/api/v1/students/{SID}/plan", json={"wrong": []}).status_code == 422


def test_phase3_audit_report(client, grader_catalog_html, grader_transcript_html):
    upload_catalog(client, grader_catalog_html)
    upload_transcript(client, grader_transcript_html)
    client.post(
        f"/api/v1/students/{SID}/plan",
        json={
            "planned_courses": [
                {"course_code": "COSC-4426", "term": "26F"},
                {"course_code": "ITEC 3506", "term": "26F"},
                {"course_code": "cosc4086", "term": "26W"},
            ]
        },
    )
    report = client.get(f"/api/v1/students/{SID}/audit-report").json()
    assert set(report) == {"student_id", "status", "timeline_validation", "cross_list_violations", "credit_summary"}
    assert report["student_id"] == SID
    assert report["status"] == "warning"
    assert report["timeline_validation"] == [
        {
            "term": "26F",
            "errors": [
                {
                    "course_code": "COSC-4426",
                    "type": "MISSING_PREREQUISITE",
                    "message": "Missing prerequisite: COSC-3127",
                }
            ],
        }
    ]
    assert report["cross_list_violations"][0]["course_code"] == "ITEC-3506"
    assert report["credit_summary"] == {
        "total_earned": 12,
        "total_planned": 9,
        "total_remaining_for_graduation": 99,
    }
    assert client.get(f"/api/v1/students/{SID}/audit-report?strict=true").json()["status"] == "failed"
    assert client.get(f"/api/v1/students/{SID}/audit-report?strict=false").json()["status"] == "warning"


def test_phase3_ok_when_no_issues(client, grader_catalog_html, grader_transcript_html):
    upload_catalog(client, grader_catalog_html)
    upload_transcript(client, grader_transcript_html)
    report = client.get(f"/api/v1/students/{SID}/audit-report?strict=true").json()
    assert report["status"] == "ok"
    assert report["timeline_validation"] == []
    assert report["cross_list_violations"] == []
