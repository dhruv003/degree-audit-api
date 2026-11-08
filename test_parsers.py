from catalog import course_key, extract_course_codes, parse_catalog, parse_credits
from transcript import grade_rank, parse_transcript
from transcript import parse_credits as transcript_credits


def test_phase1_catalog_parser(catalog_html):
    courses = parse_catalog(catalog_html)
    assert len(courses) == 5
    assert courses["COSC3506"]["prerequisites"] == ["COSC 2007"]
    assert courses["COSC3506"]["cross_listed"] == ["ITEC 3506"]
    assert courses["COSC2006"]["prerequisites"] == []
    assert courses["COSC2006"]["credits"] == 3


def test_phase1_helpers():
    assert course_key("cosc-3506") == course_key("COSC 3506") == "COSC3506"
    assert extract_course_codes("COSC 2007, MATH-1057 and cosc 2007") == ["COSC 2007", "MATH-1057"]
    assert parse_credits("3 credits") == 3
    assert parse_credits("1.5") == 1.5
    assert parse_credits("none") is None
    assert parse_catalog("<table><tr><th>Foo</th></tr></table><table></table>") == {}


def test_phase1_catalog_skips_self_cross_listing():
    html = """<table><tr><th>Code</th><th>Title</th><th>Cross Listed</th></tr>
    <tr><td>COSC 3506</td><td>SE</td><td>COSC 3506, ITEC 3506</td></tr>
    <tr><td></td><td>blank</td><td></td></tr><tr><th>x</th></tr></table>"""
    assert parse_catalog(html)["COSC3506"]["cross_listed"] == ["ITEC 3506"]


def test_phase2_parser_on_ellucian_sample(transcript_html):
    history = parse_transcript(transcript_html)
    assert len(history) == 33
    completed = [h for h in history if h["status"] == "Completed"]
    # Matches "81 credits completed" on the student's own progress page.
    assert sum(h["credits_earned"] for h in completed) == 81
    statuses = {h["status"] for h in history}
    assert statuses == {"Completed", "In-Progress", "Attempted"}


def test_phase2_parser_keeps_best_row_per_course_and_term(grader_transcript_html):
    history = parse_transcript(grader_transcript_html)
    rows = {(h["course_code"], h["term"]): h for h in history}
    assert rows[("COSC-2007", "24F")]["credits_earned"] == 3  # graded row beats the 0-credit lab
    assert rows[("COSC-2006", "23F")]["status"] == "Attempted"
    assert ("COSC-4426", "27W") not in rows  # planned rows are not history


def test_phase2_helpers():
    assert transcript_credits("3") == 3
    assert transcript_credits("2.5") == 0
    assert transcript_credits("x") == 0
    assert grade_rank("85") == 2
    assert grade_rank("P") == 0
    assert grade_rank("B+") == 1
