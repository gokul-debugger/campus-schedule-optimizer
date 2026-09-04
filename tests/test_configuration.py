from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from unischedule.configuration import configuration_from_editor, editor_rows
from unischedule.io import UniversityDataError, university_from_dict

DEMO_PATH = Path(__file__).resolve().parents[1] / "examples" / "demo_university.json"


@pytest.fixture()
def demo_data() -> dict:
    return json.loads(DEMO_PATH.read_text(encoding="utf-8"))


def test_editor_round_trip_preserves_valid_configuration(demo_data: dict) -> None:
    tables = editor_rows(demo_data)

    rebuilt = configuration_from_editor(demo_data["university"], tables)
    rebuilt_university = university_from_dict(rebuilt)
    original_university = university_from_dict(demo_data)

    assert rebuilt_university == original_university
    assert len(rebuilt_university.sections) == 14


def test_editor_accepts_comma_separated_list_values(demo_data: dict) -> None:
    tables = editor_rows(demo_data)
    tables["staff"][0]["school_ids"] = "SCS, SAI"

    rebuilt = configuration_from_editor(demo_data["university"], tables)

    assert rebuilt["staff"][0]["school_ids"] == ["SCS", "SAI"]


def test_editor_rejects_incomplete_added_rows(demo_data: dict) -> None:
    tables = editor_rows(demo_data)
    tables["schools"].append({"id": "NEW", "name": "", "code": "NEW"})

    with pytest.raises(UniversityDataError, match="School name is required"):
        configuration_from_editor(demo_data["university"], tables)


def test_editor_ignores_fully_blank_rows(demo_data: dict) -> None:
    tables = editor_rows(deepcopy(demo_data))
    tables["rooms"].append(
        {
            "id": "",
            "name": "",
            "building": "",
            "capacity": None,
            "school_id": None,
            "features": [],
        }
    )

    rebuilt = configuration_from_editor(demo_data["university"], tables)

    assert len(rebuilt["rooms"]) == len(demo_data["rooms"])
