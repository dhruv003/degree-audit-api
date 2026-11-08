import pytest

from audit import (
    build_audit_report,
    cross_partners,
    display_code,
    normalize_code,
    normalize_term,
    term_key,
    to_number,
    unique_plan,
)
from catalog import parse_catalog
from transcript import parse_transcript


@pytest.fixture
def catalog(grader_catalog_html):
    return parse_catalog(grader_catalog_html)


@pytest.fixture
def history(grader_transcript_html):
    return parse_transcript(grader_transcript_html)


def plan(*pairs):
    return [{"course_code": code, "term": term} for code, term in pairs]


@pytest.mark.parametrize("raw", ["COSC 3506", "COSC-3506", "cosc3506", " cosc - 3506 "])
def test_code_normalization(raw):
    assert normalize_code(raw) == "COSC3506"
    assert display_code(raw) == "COSC-3506"


def test_display_code_fallback():
    assert display_code("XYZ") == "XYZ"


@pytest.mark.parametrize(
    "raw,expected",
    [("26F", "26F"), ("26sp", "26SP"), ("2026F", "26F"), ("Fall 2026", "26F"), ("Winter 2027", "27W"), ("?", "?")],
)
def test_term_normalization(raw, expected):
    assert normalize_term(raw) == expected


def test_term_order_matches_spec():
    terms = ["26F", "24F", "26SP", "23F", "24W", "26S", "26W"]
    assert sorted(terms, key=term_key) == ["23F", "24W", "24F", "26W", "26SP", "26S", "26F"]
    assert term_key("???") > term_key("99F")


def test_missing_prerequisite(catalog, history):
    report = build_audit_report("770001", history, plan(("COSC-4426", "26F")), catalog)
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


def test_prerequisite_must_be_in_strictly_earlier_term(catalog, history):
    # COSC-2007 completed in 24F: planning a course that needs it in 24F fails, 24F+ passes.
    same_term = build_audit_report("1", history, plan(("COSC-3127", "24F")), catalog)
    assert same_term["timeline_validation"][0]["term"] == "24F"
    later = build_audit_report("1", history, plan(("COSC-3127", "25W")), catalog)
    assert later["timeline_validation"] == []


def test_failed_attempt_does_not_satisfy_prerequisite(catalog, history):
    # COSC-2006 failed in 23F, passed in 24W; planning COSC-2007 in 24W is still too early.
    report = build_audit_report("1", history, plan(("COSC 2007", "24W")), catalog)
    assert report["timeline_validation"][0]["errors"][0]["message"] == "Missing prerequisite: COSC-2006"


def test_multiple_prereqs_and_chronological_order(catalog, history):
    report = build_audit_report(
        "1",
        history,
        plan(("COSC-4426", "27F"), ("COSC-4426", "26SP"), ("COSC-4086", "24F"), ("COSC-4086", "26F")),
        catalog,
    )
    assert [t["term"] for t in report["timeline_validation"]] == ["24F", "26SP", "27F"]
    first = report["timeline_validation"][0]["errors"]
    assert {e["message"] for e in first} == {"Missing prerequisite: COSC-2007", "Missing prerequisite: MATH-1057"}


def test_cross_list_violation(catalog, history):
    report = build_audit_report("1", history, plan(("itec 3506", "26F")), catalog)
    assert report["cross_list_violations"] == [
        {
            "course_code": "ITEC-3506",
            "type": "CROSS_LIST_CONFLICT",
            "message": "Cross-listed with completed course COSC-3506",
        }
    ]


def test_cross_list_is_symmetric(catalog):
    catalog["ITEC3506"]["cross_listed"] = []
    assert cross_partners("ITEC-3506", catalog) == {"COSC3506"}


def test_retake_not_double_counted(catalog, history):
    summary = build_audit_report("1", history, [], catalog)["credit_summary"]
    # COSC-2006 once + COSC-2007 + COSC-3506 + MATH-1057; attempt and in-progress = 0
    assert summary["total_earned"] == 12


def test_retake_counted_once_even_if_passed_twice(catalog):
    history = [
        {"course_code": "COSC-2006", "term": "23F", "credits_earned": 3, "status": "Completed"},
        {"course_code": "COSC 2006", "term": "24W", "credits_earned": 3, "status": "Completed"},
    ]
    assert build_audit_report("1", history, [], catalog)["credit_summary"]["total_earned"] == 3


def test_credit_summary(catalog, history):
    report = build_audit_report(
        "1",
        history,
        plan(("COSC-4426", "26F"), ("ITEC-3506", "26F"), ("ITEC 3506", "26F"), ("PHIL-1000", "27W")),
        catalog,
    )
    assert report["credit_summary"] == {
        "total_earned": 12,
        "total_planned": 6,
        "total_remaining_for_graduation": 102,
    }


def test_remaining_never_negative(catalog):
    history = [
        {"course_code": f"COSC-{1000 + i}", "term": "23F", "credits_earned": 3, "status": "Completed"}
        for i in range(45)
    ]
    summary = build_audit_report("1", history, [], catalog)["credit_summary"]
    assert summary["total_earned"] == 135
    assert summary["total_remaining_for_graduation"] == 0


def test_strict_and_ok_status(catalog, history):
    assert build_audit_report("1", history, plan(("COSC-4426", "26F")), catalog, strict=True)["status"] == "failed"
    assert build_audit_report("1", history, plan(("MATH-1057", "27W")), catalog, strict=True)["status"] == "ok"


def test_helpers():
    assert unique_plan(plan(("COSC 1", "26F"), ("COSC-1", "26f"))) == plan(("COSC 1", "26F"))
    assert to_number(None) == 0.0
    assert to_number("1.5") == 1.5
