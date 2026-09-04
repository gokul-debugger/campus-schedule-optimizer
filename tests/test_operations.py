from __future__ import annotations

import json
from pathlib import Path

from unischedule.io import university_from_dict
from unischedule.operations import (
    StaffAbsence,
    coverage_plan_records,
    eligible_substitutes,
    find_coverage_needs,
    propose_coverage_assignments,
    update_staff_availability,
    validate_coverage_assignments,
)
from unischedule.scheduler import UniversityScheduler

DEMO_PATH = Path(__file__).resolve().parents[1] / "examples" / "demo_university.json"


def scheduled_demo():
    data = json.loads(DEMO_PATH.read_text(encoding="utf-8"))
    university = university_from_dict(data)
    result = UniversityScheduler(university).solve()
    assert result.success
    return data, university, result


def test_update_staff_availability_is_non_mutating() -> None:
    data, _, _ = scheduled_demo()

    updated = update_staff_availability(data, "CS-P01", ["MON-1", "TUE-1"])

    assert "available_slot_ids" not in data["staff"][0]
    assert updated["staff"][0]["available_slot_ids"] == ["MON-1", "TUE-1"]


def test_absence_creates_need_and_filters_substitutes() -> None:
    _, university, result = scheduled_demo()
    meeting = next(
        item
        for item in result.meetings
        if item.section_id == "CS102-A" and item.occurrence == 2
    )
    absence = StaffAbsence("leave-1", "CS-P01", meeting.slot_ids)

    needs = find_coverage_needs(university, result, (absence,))
    need = next(item for item in needs if item.section_id == "CS102-A")
    candidates = eligible_substitutes(university, result, need, (absence,))

    assert need.absent_staff_id == "CS-P01"
    assert candidates == ("CS-P02",)


def test_coverage_proposal_is_complete_and_valid() -> None:
    _, university, result = scheduled_demo()
    meeting = next(
        item
        for item in result.meetings
        if item.section_id == "CS102-A" and item.occurrence == 2
    )
    absence = StaffAbsence("leave-1", "CS-P01", meeting.slot_ids)
    needs = find_coverage_needs(university, result, (absence,))

    assignments = propose_coverage_assignments(
        university,
        result,
        needs,
        (absence,),
    )

    assert assignments
    assert validate_coverage_assignments(
        university,
        result,
        needs,
        (absence,),
        assignments,
    ) == []
    records = coverage_plan_records(university, needs, assignments)
    assert records[0]["substitute"] == "Prof. Daniel Lee"
    assert records[0]["status"] == "Covered"


def test_uncovered_need_is_reported() -> None:
    _, university, result = scheduled_demo()
    meeting = next(
        item
        for item in result.meetings
        if item.section_id == "AI101-A" and item.occurrence == 1
    )
    absence = StaffAbsence("leave-1", "AI-P01", meeting.slot_ids)
    needs = find_coverage_needs(university, result, (absence,))

    assignments = propose_coverage_assignments(
        university,
        result,
        needs,
        (absence,),
    )

    assert assignments == {}
    violations = validate_coverage_assignments(
        university,
        result,
        needs,
        (absence,),
        assignments,
    )
    assert violations == ["No substitute is assigned for AI101-A:1:AI-P01."]
