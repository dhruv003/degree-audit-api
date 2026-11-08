"""Phase 2: transcript parsing (unchanged from student-academic-api)."""

import re

from bs4 import BeautifulSoup


def parse_credits(value):
    try:
        number = float(value.strip())
        if number.is_integer():
            return int(number)
    except (ValueError, OverflowError):
        pass
    return 0


def grade_rank(value):
    value = value.strip().upper()

    if re.fullmatch(r"\d+(\.\d+)?%?", value):
        return 2

    if value in {"", "P", "PASS", "-", "—"}:
        return 0

    return 1


def parse_transcript(html):
    soup = BeautifulSoup(html, "html.parser")
    found = {}

    for table in soup.find_all("table"):
        rows = table.find_all("tr")

        if not rows:
            continue

        header_index = None
        columns = None

        for index, row in enumerate(rows):
            cells = row.find_all(["th", "td"], recursive=False)
            labels = [
                cell.get_text(" ", strip=True).lower()
                for cell in cells
            ]

            required = ["status", "course", "grade", "term", "credits"]

            if all(label in labels for label in required):
                columns = {
                    name: labels.index(name)
                    for name in required
                }
                header_index = index
                break

        if columns is None:
            continue

        for row in rows[header_index + 1:]:
            cells = row.find_all(["td", "th"], recursive=False)

            if len(cells) <= max(columns.values()):
                continue

            def cell(name):
                return cells[columns[name]].get_text(" ", strip=True)

            status = cell("status")
            course_code = cell("course")
            grade = cell("grade")
            term = cell("term")
            credits = parse_credits(cell("credits"))

            if status not in {"Completed", "In-Progress", "Attempted"}:
                continue

            if not term or not course_code:
                continue

            record = {
                "course_code": course_code,
                "term": term,
                "credits_earned": credits,
                "status": status,
            }

            key = (course_code, term)
            priority = (grade_rank(grade), credits)

            if key not in found or priority > found[key][0]:
                found[key] = (priority, record)

    return [entry[1] for entry in found.values()]
