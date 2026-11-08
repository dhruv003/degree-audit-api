# Degree Audit API (Individual Assignment Phase 3)

One FastAPI service with all three phases. Phase 1 and Phase 2 keep the same
routes, bodies and responses as `course-registration-api` and
`student-academic-api`; Phase 3 adds the audit engine.

## Endpoints

| Phase | Method | Path |
|---|---|---|
| 1 | POST | `/api/v1/admin/catalog/import` (multipart `file`) |
| 1 | GET | `/api/v1/catalog/courses/{course_code}` |
| 2 | POST | `/api/v1/students/{id}/history/import` (multipart `file`) |
| 2 | PUT, DELETE | `/api/v1/students/{id}/history` |
| 2 | POST, PUT, DELETE | `/api/v1/students/{id}/plan` (`{"planned_courses": [...]}`) |
| 2 | GET | `/api/v1/students/{id}/profile` |
| 3 | GET | `/api/v1/students/{id}/audit-report?strict=true\|false` |

## Audit rules

* Course codes compare after upper-casing and removing spaces/hyphens.
* Terms order as `<yy><season>` with W < SP < S < F.
* Every prerequisite of a planned course needs a Completed entry in a strictly earlier term,
  otherwise `MISSING_PREREQUISITE`, grouped by planned term in chronological order.
* Planning a course cross-listed with a completed course gives `CROSS_LIST_CONFLICT`.
* `total_earned` counts each completed course once; attempts and in-progress courses give 0.
* Graduation target: 120 credits.

## Run locally

```bash
pip install -r requirements-dev.txt
uvicorn main:app --reload
pytest --cov=. --cov-fail-under=80
python scripts/integration_test.py http://127.0.0.1:8000
```

## CI quality gate

`.github/workflows/ci.yml` runs flake8, then pytest with coverage >= 80%, then boots
the API and runs `scripts/integration_test.py` against it.
