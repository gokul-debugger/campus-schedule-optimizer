from __future__ import annotations

from unischedule.models import (
    Cohort,
    CourseSection,
    Room,
    ScheduledMeeting,
    School,
    StaffMember,
    TimeSlot,
    University,
)
from unischedule.quality import evaluate_schedule_quality


def test_schedule_quality_reports_each_soft_objective() -> None:
    school = School(id="S1", name="School One", code="S1")
    cohort = Cohort("C1", "Cohort One", "S1", "BSc", 20)
    staff = StaffMember("T1", "Teacher", "Professor", ("S1",))
    slots = (
        TimeSlot("MON-1", "Monday", 1, "09:00", "10:00"),
        TimeSlot("MON-2", "Monday", 2, "10:00", "11:00"),
    )
    rooms = (
        Room("HOME", "Home Room", "Main", 30, "S1"),
        Room("AWAY", "Away Room", "Other", 30, "S2"),
    )
    section = CourseSection(
        id="A",
        code="A",
        title="Course A",
        school_id="S1",
        subject_area="Core",
        program="BSc",
        cohort_ids=("C1",),
        instructor_ids=("T1",),
        meetings_per_week=2,
        duration_slots=1,
        expected_students=20,
        preferred_slot_ids=frozenset({"MON-1"}),
    )
    university = University(
        "Test University",
        (school,),
        (cohort,),
        slots,
        (staff,),
        rooms,
        (section,),
    )
    meetings = (
        ScheduledMeeting("A", 1, ("MON-1",), "HOME"),
        ScheduledMeeting("A", 2, ("MON-2",), "AWAY"),
    )

    quality = evaluate_schedule_quality(university, meetings)

    assert quality.soft_penalty == 8
    assert quality.preference_satisfaction_rate == 0.5
    assert quality.room_affinity_rate == 0.5
    assert quality.late_period_meetings == 1
    assert quality.max_staff_daily_periods == 2
    assert quality.max_cohort_daily_periods == 2
    assert quality.staff_daily_loads[0].periods == 2


def test_quality_handles_an_empty_schedule() -> None:
    university = University("Empty", (), (), (), (), (), ())

    quality = evaluate_schedule_quality(university, ())

    assert quality.soft_penalty == 0
    assert quality.preference_satisfaction_rate is None
    assert quality.room_affinity_rate is None
    assert quality.max_staff_daily_periods == 0
