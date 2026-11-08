"""Phase 3: degree-audit rules engine.

History records come from Phase 2: {course_code, term, credits_earned, status}
Plan records come from Phase 2:    {course_code, term}
Catalog records come from Phase 1: {course_code, title, credits, prerequisites, cross_listed}

Rules (from the Phase 3 spec):
* course codes compare after upper-casing and removing spaces/hyphens
* terms are <yy><season>, season order W < SP < S < F
* every prerequisite of a planned course needs a Completed history entry
  in a strictly earlier term, else MISSING_PREREQUISITE (grouped by term)
* planning a course cross-listed with a Completed course is a CROSS_LIST_CONFLICT
* total_earned counts each completed course once; non-completed attempts give 0
* graduation target is 120 credits
"""

import re

GRADUATION_TARGET = 120
SEASON_ORDER = {"W": 0, "SP": 1, "S": 2, "F": 3}
SEASON_WORDS = {
    "WINTER": "W",
    "SPRING": "SP",
    "SUMMER": "S",
    "FALL": "F",
    "AUTUMN": "F",
    "FA": "F",
    "SU": "S",
    "WI": "W",
}


def normalize_code(code):
    """'COSC 3506', 'COSC-3506', 'cosc3506' -> 'COSC3506'."""
    return re.sub(r"[^A-Z0-9]", "", str(code or "").upper())


def display_code(code):
    """'cosc 3506' -> 'COSC-3506' (spec output style)."""
    norm = normalize_code(code)
    match = re.fullmatch(r"([A-Z]+)(\d+[A-Z]?)", norm)
    return f"{match.group(1)}-{match.group(2)}" if match else norm


def normalize_term(term):
    """'26F', '26 f', '2026F', 'Fall 2026' -> '26F'."""
    text = re.sub(r"[\s\-_]", "", str(term or "").upper())
    match = re.fullmatch(r"(?:\d{2})?(\d{2})(SP|W|S|F)", text)
    if match:
        return match.group(1) + match.group(2)
    year = re.search(r"\d{4}|\d{2}", text)
    for word, season in SEASON_WORDS.items():
        if word in text and year:
            return year.group(0)[-2:] + season
    return text


def term_key(term):
    """Sort key: 23F < 24W < 24F < 26SP < 26S < 26F. Unknown terms sort last."""
    norm = normalize_term(term)
    match = re.fullmatch(r"(\d{2})(SP|W|S|F)", norm)
    if not match:
        return (9999, 9, norm)
    return (int(match.group(1)), SEASON_ORDER[match.group(2)], norm)


def is_completed(record):
    return str(record.get("status", "")).strip().lower() == "completed"


def to_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number


def tidy(number):
    number = round(float(number), 2)
    return int(number) if number.is_integer() else number


def lookup(catalog, code):
    return catalog.get(normalize_code(code))


def earned_by_course(history):
    """One credit value per course: the best completed attempt. A retake or a
    later pass never adds the same course twice; failures contribute 0."""
    earned = {}
    for record in history:
        if not is_completed(record):
            continue
        code = normalize_code(record.get("course_code"))
        earned[code] = max(earned.get(code, 0.0), to_number(record.get("credits_earned")))
    return earned


def cross_partners(code, catalog):
    """Courses cross-listed with `code`, checked in both directions."""
    target = normalize_code(code)
    partners = set()
    course = lookup(catalog, code)
    if course:
        partners.update(normalize_code(c) for c in course.get("cross_listed") or [])
    for key, other in catalog.items():
        if target in {normalize_code(c) for c in other.get("cross_listed") or []}:
            partners.add(key)
    partners.discard(target)
    return partners


def unique_plan(plan):
    seen, result = set(), []
    for item in plan:
        key = (normalize_code(item.get("course_code")), normalize_term(item.get("term")))
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def check_prerequisites(plan, history, catalog):
    completed = [r for r in history if is_completed(r)]
    by_term = {}
    for item in plan:
        course = lookup(catalog, item.get("course_code"))
        if not course:
            continue
        planned_at = term_key(item.get("term"))
        for prereq in course.get("prerequisites") or []:
            wanted = normalize_code(prereq)
            done_before = any(
                normalize_code(r.get("course_code")) == wanted and term_key(r.get("term")) < planned_at
                for r in completed
            )
            if not done_before:
                by_term.setdefault(normalize_term(item.get("term")), []).append(
                    {
                        "course_code": display_code(item.get("course_code")),
                        "type": "MISSING_PREREQUISITE",
                        "message": f"Missing prerequisite: {display_code(prereq)}",
                    }
                )
    return [{"term": term, "errors": by_term[term]} for term in sorted(by_term, key=term_key)]


def check_cross_listings(plan, history, catalog):
    completed = {normalize_code(r.get("course_code")) for r in history if is_completed(r)}
    violations, seen = [], set()
    for item in plan:
        planned = normalize_code(item.get("course_code"))
        for partner in sorted(cross_partners(planned, catalog)):
            if partner in completed and (planned, partner) not in seen:
                seen.add((planned, partner))
                violations.append(
                    {
                        "course_code": display_code(planned),
                        "type": "CROSS_LIST_CONFLICT",
                        "message": f"Cross-listed with completed course {display_code(partner)}",
                    }
                )
    return violations


def credit_summary(plan, history, catalog):
    earned = sum(earned_by_course(history).values())
    planned = 0.0
    for item in plan:
        course = lookup(catalog, item.get("course_code"))
        planned += to_number(course.get("credits")) if course else to_number(item.get("credits"))
    remaining = max(0.0, GRADUATION_TARGET - earned - planned)
    return {
        "total_earned": tidy(earned),
        "total_planned": tidy(planned),
        "total_remaining_for_graduation": tidy(remaining),
    }


def build_audit_report(student_id, history, plan, catalog, strict=False):
    plan = unique_plan(plan)
    timeline = check_prerequisites(plan, history, catalog)
    cross = check_cross_listings(plan, history, catalog)
    if timeline or cross:
        status = "failed" if strict else "warning"
    else:
        status = "ok"
    return {
        "student_id": str(student_id),
        "status": status,
        "timeline_validation": timeline,
        "cross_list_violations": cross,
        "credit_summary": credit_summary(plan, history, catalog),
    }
