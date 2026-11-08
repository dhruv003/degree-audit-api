"""Phase 1: course catalog parsing (unchanged from course-registration-api)."""

import re
from typing import Any

from bs4 import BeautifulSoup


def clean_text(value: str) -> str:
    """Remove extra spaces and line breaks."""
    return " ".join(value.replace("\xa0", " ").split())


def course_key(value: str) -> str:
    """
    Make course-code lookup flexible.

    COSC 3506
    COSC3506
    COSC-3506

    all become the same internal lookup key.
    """
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def normalize_header(value: str) -> str:
    """Make HTML table headings easier to compare."""
    value = clean_text(value).lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return value.strip()


HEADER_ALIASES = {
    "course_code": {
        "course code",
        "code",
        "course",
        "course number",
        "catalog number",
        "catalogue number",
    },
    "title": {
        "title",
        "course title",
        "course name",
        "name",
    },
    "credits": {
        "credits",
        "credit",
        "credit hours",
        "credit hour",
        "units",
        "unit",
    },
    "prerequisites": {
        "prerequisite",
        "prerequisites",
        "prereq",
        "prereqs",
        "pre requisite",
        "pre requisites",
    },
    "cross_listed": {
        "cross listed",
        "cross listed courses",
        "cross listing",
        "cross listings",
        "crosslisted",
        "crosslisted courses",
    },
}


def get_header_name(value: str):
    """Convert a table heading into one of our standard field names."""
    normalized = normalize_header(value)

    for field_name, aliases in HEADER_ALIASES.items():
        if normalized in aliases:
            return field_name

    return None


COURSE_PATTERN = re.compile(
    r"\b[A-Za-z]{2,10}\s*(?:-\s*)?\d{3,4}[A-Za-z]?\b"
)


def extract_course_codes(value: str) -> list[str]:
    """Extract course codes from prerequisite/cross-listing text."""
    results = []

    for match in COURSE_PATTERN.finditer(value):
        code = clean_text(match.group(0)).upper()

        if code not in results:
            results.append(code)

    return results


def parse_credits(value: str):
    """Convert a credit value such as '3 credits' into 3."""
    match = re.search(r"\d+(?:\.\d+)?", value)

    if not match:
        return None

    number = float(match.group(0))

    if number.is_integer():
        return int(number)

    return number


def parse_catalog(html: str) -> dict[str, dict[str, Any]]:
    """Read course records from HTML tables."""

    soup = BeautifulSoup(html, "html.parser")

    parsed_courses: dict[str, dict[str, Any]] = {}

    # Look through every table rather than assuming one particular table.
    for table in soup.find_all("table"):

        rows = table.find_all("tr")

        if not rows:
            continue

        header_row_index = None
        column_map: dict[int, str] = {}

        # Search the first few rows for recognizable column headings.
        for row_index, row in enumerate(rows[:5]):

            cells = row.find_all(["th", "td"])

            possible_map: dict[int, str] = {}

            for column_index, cell in enumerate(cells):

                field_name = get_header_name(
                    cell.get_text(" ", strip=True)
                )

                if field_name:
                    possible_map[column_index] = field_name

            # A useful course table should at least identify course code
            # and title.
            if (
                "course_code" in possible_map.values()
                and "title" in possible_map.values()
            ):
                header_row_index = row_index
                column_map = possible_map
                break

        # If this table does not look like a course table, skip it.
        if header_row_index is None:
            continue

        # Process every data row after the detected heading.
        for row in rows[header_row_index + 1:]:

            cells = row.find_all("td")

            if not cells:
                continue

            record = {
                "course_code": "",
                "title": "",
                "credits": "",
                "prerequisites": "",
                "cross_listed": "",
            }

            for column_index, field_name in column_map.items():

                if column_index < len(cells):
                    record[field_name] = clean_text(
                        cells[column_index].get_text(" ", strip=True)
                    )

            course_code = record["course_code"]

            if not course_code:
                continue

            title = record["title"]

            prerequisites = extract_course_codes(
                record["prerequisites"]
            )

            cross_listed = extract_course_codes(
                record["cross_listed"]
            )

            # Do not list the course itself as cross-listed with itself.
            cross_listed = [
                code
                for code in cross_listed
                if course_key(code) != course_key(course_code)
            ]

            course = {
                "course_code": course_code,
                "title": title,
                "credits": parse_credits(record["credits"]),
                "prerequisites": prerequisites,
                "cross_listed": cross_listed,
            }

            parsed_courses[course_key(course_code)] = course

    return parsed_courses
