from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from unischedule.io import university_from_dict
from unischedule.models import (
    Cohort,
    CourseSection,
    Room,
    School,
    StaffMember,
    StudentGroup,
    TimeSlot,
    University,
)
from unischedule.reporting import schedule_records, validate_schedule
from unischedule.scheduler import UniversityScheduler, workload_by_staff

DEMO_PATH = Path(__file__).resolve().parents[1] / "examples" / "demo_university.json"


def test_demo_schedule_is_complete_and_valid() -> None:
    university = university_from_dict(json.loads(DEMO_PATH.read_text(encoding="utf-8")))

    result = UniversityScheduler(university).solve()

    assert result.success
    assert len(result.meetings) == sum(
        section.meetings_per_week for section in university.sections
    )
    assert validate_schedule(university, result) == []
    records = schedule_records(university, result)
    assert len(records) == sum(
        section.meetings_per_week * section.duration_slots
        for section in university.sections
    )
    assert records[0]["day"] == "Monday"
    assert "Year" in records[0]["cohorts"]
    elective_record = next(
        record for record in records if record["section_id"] == "CS301-A"
    )
    assert elective_record["student_groups"] == "Data Systems Track"
    assert elective_record["learner_resource_ids"] == ("CS-Y3-DATA",)
    assert sum(workload_by_staff(result, university).values()) > 0


def test_recurring_meetings_are_spread_across_days() -> None:
    university = university_from_dict(json.loads(DEMO_PATH.read_text(encoding="utf-8")))
    result = UniversityScheduler(university).solve()
    slot_lookup = {slot.id: slot for slot in university.slots}
    days_by_section: dict[str, set[str]] = {}

    for meeting in result.meetings:
        days_by_section.setdefault(meeting.section_id, set()).add(
            slot_lookup[meeting.slot_ids[0]].day
        )

    for section in university.sections:
        assert len(days_by_section[section.id]) == section.meetings_per_week


def test_scheduler_reports_an_impossible_timetable() -> None:
    school = School(id="S1", name="School One", code="S1")
    cohort = Cohort(
        id="Y1",
        name="Year One",
        school_id="S1",
        program="BSc",
        size=20,
    )
    slot = TimeSlot(id="MON-1", day="Monday", period=1, start="09:00", end="10:00")
    staff = StaffMember(
        id="T1",
        name="Teacher",
        role="Professor",
        school_ids=("S1",),
    )
    room = Room(id="R1", name="Room", building="Main", capacity=30)
    first = CourseSection(
        id="A",
        code="A",
        title="A",
        school_id="S1",
        subject_area="Core",
        program="BSc",
        cohort_ids=("Y1",),
        instructor_ids=("T1",),
        meetings_per_week=1,
        duration_slots=1,
        expected_students=20,
    )
    second = replace(first, id="B", code="B", title="B")
    university = University(
        name="Test University",
        schools=(school,),
        cohorts=(cohort,),
        slots=(slot,),
        staff=(staff,),
        rooms=(room,),
        sections=(first, second),
    )

    result = UniversityScheduler(university).solve()

    assert not result.success
    assert result.meetings == ()
    assert result.backtracks > 0


def test_scheduler_spreads_shared_staff_work_across_days() -> None:
    school = School(id="S1", name="School One", code="S1")
    cohorts = (
        Cohort("C1", "Cohort One", "S1", "BSc", 20),
        Cohort("C2", "Cohort Two", "S1", "BSc", 20),
    )
    slots = (
        TimeSlot("MON-1", "Monday", 1, "09:00", "10:00"),
        TimeSlot("MON-2", "Monday", 2, "10:00", "11:00"),
        TimeSlot("TUE-1", "Tuesday", 1, "09:00", "10:00"),
        TimeSlot("ZZZ-3", "Friday", 3, "11:00", "12:00"),
    )
    staff = StaffMember("T1", "Teacher", "Professor", ("S1",))
    room = Room("R1", "Room", "Main", 30, "S1")
    first = CourseSection(
        id="A",
        code="A",
        title="A",
        school_id="S1",
        subject_area="Core",
        program="BSc",
        cohort_ids=("C1",),
        instructor_ids=("T1",),
        meetings_per_week=1,
        duration_slots=1,
        expected_students=20,
    )
    second = replace(
        first,
        id="B",
        code="B",
        title="B",
        cohort_ids=("C2",),
    )
    university = University(
        "Test University",
        (school,),
        cohorts,
        slots,
        (staff,),
        (room,),
        (first, second),
    )

    result = UniversityScheduler(university).solve()
    scheduled_days = {
        next(slot.day for slot in slots if slot.id == meeting.slot_ids[0])
        for meeting in result.meetings
    }

    assert result.success
    assert scheduled_days == {"Monday", "Tuesday"}


def test_disjoint_elective_groups_can_share_a_period() -> None:
    school = School("S1", "School One", "S1")
    cohort = Cohort("Y3", "Year Three", "S1", "BSc", 20)
    groups = (
        StudentGroup("Y3-A", "Track A", "Y3", 10),
        StudentGroup("Y3-B", "Track B", "Y3", 10),
    )
    slot = TimeSlot("MON-1", "Monday", 1, "09:00", "10:00")
    staff = (
        StaffMember("T1", "Teacher One", "Professor", ("S1",)),
        StaffMember("T2", "Teacher Two", "Professor", ("S1",)),
    )
    rooms = (
        Room("R1", "Room One", "Main", 20, "S1"),
        Room("R2", "Room Two", "Main", 20, "S1"),
    )
    first = CourseSection(
        id="A",
        code="A",
        title="Track A Course",
        school_id="S1",
        subject_area="Core",
        program="BSc",
        cohort_ids=("Y3",),
        instructor_ids=("T1",),
        meetings_per_week=1,
        duration_slots=1,
        expected_students=10,
        student_group_ids=("Y3-A",),
    )
    second = replace(
        first,
        id="B",
        code="B",
        title="Track B Course",
        instructor_ids=("T2",),
        student_group_ids=("Y3-B",),
    )
    university = University(
        "Test University",
        (school,),
        (cohort,),
        (slot,),
        staff,
        rooms,
        (first, second),
        groups,
    )

    result = UniversityScheduler(university).solve()

    assert result.success
    assert {meeting.slot_ids for meeting in result.meetings} == {("MON-1",)}
    assert validate_schedule(university, result) == []
