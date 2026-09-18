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


def coverage_case(university, result, *, has_candidates: bool):
    for meeting in result.meetings:
        section = next(
            item for item in university.sections if item.id == meeting.section_id
        )
        for staff_id in section.instructor_ids:
            absence = StaffAbsence("leave-1", staff_id, meeting.slot_ids)
            needs = find_coverage_needs(university, result, (absence,))
            need = next(
                item
                for item in needs
                if item.section_id == meeting.section_id
                and item.occurrence == meeting.occurrence
                and item.absent_staff_id == staff_id
            )
            candidates = eligible_substitutes(
                university,
                result,
                need,
                (absence,),
            )
            if bool(candidates) is has_candidates:
                return absence, needs, need, candidates
    raise AssertionError("The demonstration needs both covered and uncovered cases")


def test_update_staff_availability_is_non_mutating() -> None:
    data, _, _ = scheduled_demo()

    updated = update_staff_availability(data, "CS-P01", ["MON-1", "TUE-1"])

    assert "available_slot_ids" not in data["staff"][0]
    assert updated["staff"][0]["available_slot_ids"] == ["MON-1", "TUE-1"]


def test_absence_creates_need_and_filters_substitutes() -> None:
    _, university, result = scheduled_demo()
    absence, _, need, candidates = coverage_case(
        university,
        result,
        has_candidates=True,
    )

    assert need.absent_staff_id == absence.staff_id
    assert candidates
    assert need.absent_staff_id not in candidates


def test_coverage_proposal_is_complete_and_valid() -> None:
    _, university, result = scheduled_demo()
    absence, needs, need, candidates = coverage_case(
        university,
        result,
        has_candidates=True,
    )

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
    assert assignments[need.id] in candidates
    assert next(row for row in records if row["status"] == "Covered")


def test_uncovered_need_is_reported() -> None:
    _, university, result = scheduled_demo()
    absence, needs, need, candidates = coverage_case(
        university,
        result,
        has_candidates=False,
    )

    assignments = propose_coverage_assignments(
        university,
        result,
        needs,
        (absence,),
    )

    assert candidates == ()
    assert assignments == {}
    violations = validate_coverage_assignments(
        university,
        result,
        needs,
        (absence,),
        assignments,
    )
    assert violations == [f"No substitute is assigned for {need.id}."]
