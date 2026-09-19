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
    assert len(university.student_groups) == 4
    assert len(university.sections) == 15


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


def test_student_groups_must_partition_their_cohort(demo_data: dict) -> None:
    invalid = deepcopy(demo_data)
    invalid["student_groups"][0]["size"] = 18

    with pytest.raises(UniversityDataError, match="must total its cohort size"):
        university_from_dict(invalid)


def test_section_groups_must_belong_to_listed_cohorts(demo_data: dict) -> None:
    invalid = deepcopy(demo_data)
    invalid["course_sections"][5]["student_group_ids"] = ["AI-Y3-GOV"]

    with pytest.raises(UniversityDataError, match="must represent every"):
        university_from_dict(invalid)


def test_section_cannot_repeat_a_student_group(demo_data: dict) -> None:
    invalid = deepcopy(demo_data)
    invalid["course_sections"][5]["student_group_ids"] = [
        "CS-Y3-DATA",
        "CS-Y3-DATA",
    ]

    with pytest.raises(UniversityDataError, match="repeats a student group"):
        university_from_dict(invalid)


def test_legacy_configuration_without_student_groups_still_loads(
    demo_data: dict,
) -> None:
    legacy = deepcopy(demo_data)
    legacy.pop("student_groups")
    for section in legacy["course_sections"]:
        section.pop("student_group_ids", None)

    university = university_from_dict(legacy)

    assert university.student_groups == ()
