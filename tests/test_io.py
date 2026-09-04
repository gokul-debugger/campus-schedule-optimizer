from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from unischedule.io import UniversityDataError, university_from_dict

DEMO_PATH = Path(__file__).resolve().parents[1] / "examples" / "demo_university.json"


@pytest.fixture()
def demo_data() -> dict:
    return json.loads(DEMO_PATH.read_text(encoding="utf-8"))


def test_demo_configuration_loads(demo_data: dict) -> None:
    university = university_from_dict(demo_data)

    assert university.name == "Northstar University"
    assert len(university.schools) == 2
    assert len(university.cohorts) == 6
    assert len(university.sections) == 14


def test_unknown_instructor_is_rejected(demo_data: dict) -> None:
    invalid = deepcopy(demo_data)
    invalid["course_sections"][0]["instructor_ids"] = ["UNKNOWN"]

    with pytest.raises(UniversityDataError, match="Unknown values"):
        university_from_dict(invalid)


def test_instructor_must_be_connected_to_course_school(demo_data: dict) -> None:
    invalid = deepcopy(demo_data)
    invalid["course_sections"][0]["instructor_ids"] = ["AI-P01"]

    with pytest.raises(UniversityDataError, match="outside its school"):
        university_from_dict(invalid)


def test_section_requires_a_suitable_room(demo_data: dict) -> None:
    invalid = deepcopy(demo_data)
    invalid["course_sections"][0]["expected_students"] = 1_000

    with pytest.raises(UniversityDataError, match="no room"):
        university_from_dict(invalid)
