"""API integration test against a running server (CI boots one locally).

Usage:
    python scripts/integration_test.py http://127.0.0.1:8000
"""

import sys
import time
from pathlib import Path

import requests

DATA = Path(__file__).resolve().parent
SID = "770001"


def wait_for(base, timeout=90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if requests.get(f"{base}/health", timeout=10).ok:
                return
        except requests.RequestException:
            pass
        time.sleep(2)
    raise SystemExit(f"Server at {base} did not start")


def upload(url, path):
    with open(path, "rb") as fh:
        return requests.post(url, files={"file": (path.name, fh, "text/html")}, timeout=60)


def main(base):
    base = base.rstrip("/")
    api = f"{base}/api/v1"
    wait_for(base)
    results = []

    def check(name, condition, detail=""):
        results.append(bool(condition))
        print(f"{'PASS' if condition else 'FAIL'}  {name}  {detail}")

    r = upload(f"{api}/admin/catalog/import", DATA / "grader_like_catalog.html")
    check("Phase 1 catalog import", r.status_code == 200, r.text)
    r = requests.get(f"{api}/catalog/courses/cosc-3506", timeout=30)
    check("Phase 1 course lookup", r.ok and r.json()["cross_listed"] == ["ITEC 3506"])

    r = upload(f"{api}/students/{SID}/history/import", DATA / "grader_like_transcript.html")
    check("Phase 2 history import", r.status_code == 201, r.text)
    plan = {
        "planned_courses": [
            {"course_code": "COSC-4426", "term": "26F"},
            {"course_code": "ITEC 3506", "term": "26F"},
            {"course_code": "cosc4086", "term": "26W"},
        ]
    }
    r = requests.post(f"{api}/students/{SID}/plan", json=plan, timeout=30)
    check("Phase 2 plan", r.ok, r.text)
    check("Phase 2 profile", requests.get(f"{api}/students/{SID}/profile", timeout=30).ok)

    report = requests.get(f"{api}/students/{SID}/audit-report", timeout=30).json()
    keys = {"student_id", "status", "timeline_validation", "cross_list_violations", "credit_summary"}
    check("A. audit schema", keys <= set(report))
    check("A. default status warning", report.get("status") == "warning")
    strict = requests.get(f"{api}/students/{SID}/audit-report?strict=true", timeout=30).json()
    check("A. strict=true -> failed", strict.get("status") == "failed")
    errors = [e for t in report.get("timeline_validation", []) for e in t["errors"]]
    check(
        "B. missing prerequisite",
        any(e["course_code"] == "COSC-4426" and e["type"] == "MISSING_PREREQUISITE" for e in errors),
    )
    check(
        "C. cross-list violation",
        any(v["course_code"] == "ITEC-3506" for v in report.get("cross_list_violations", [])),
    )
    summary = report.get("credit_summary", {})
    check("D. retake not double counted", summary.get("total_earned") == 12, str(summary))
    check("E. total_planned", summary.get("total_planned") == 9)
    check("E. remaining for graduation", summary.get("total_remaining_for_graduation") == 99)

    r = upload(f"{api}/students/5123456/history/import", DATA / "student-example.html")
    check("Sample Ellucian transcript import", r.status_code == 201, r.text)
    sample = requests.get(f"{api}/students/5123456/audit-report", timeout=30).json()
    check("Sample transcript earned credits = 81", sample["credit_summary"]["total_earned"] == 81)

    print(f"\n{sum(results)}/{len(results)} checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"))
