import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
DATA = ROOT
sys.path.insert(0, str(ROOT))


@pytest.fixture
def catalog_html():
    return (DATA / "sample_catalog.html").read_text(encoding="utf-8")


@pytest.fixture
def transcript_html():
    return (DATA / "student-example.html").read_text(encoding="utf-8")


@pytest.fixture
def grader_catalog_html():
    return (DATA / "grader_like_catalog.html").read_text(encoding="utf-8")


@pytest.fixture
def grader_transcript_html():
    return (DATA / "grader_like_transcript.html").read_text(encoding="utf-8")
