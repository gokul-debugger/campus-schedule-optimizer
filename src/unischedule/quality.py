"""Transparent soft-objective scoring for generated timetables."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from unischedule.models import CourseSection, ScheduledMeeting, University

PREFERENCE_MISS_WEIGHT = 3
FOREIGN_ROOM_WEIGHT = 2
LATE_PERIOD_WEIGHT = 1
STAFF_DAILY_PAIR_WEIGHT = 1
COHORT_DAILY_PAIR_WEIGHT = 1


@dataclass(frozen=True, slots=True)
class DailyLoad:
    """Number of scheduled periods for one resource on one day."""

    resource_id: str
    day: str
    periods: int


@dataclass(frozen=True, slots=True)
class ScheduleQuality:
    """Independent quality measurements for a complete schedule."""

    soft_penalty: int
    preferred_meetings: int
    preference_eligible_meetings: int
    home_or_shared_room_meetings: int
    late_period_meetings: int
    total_meetings: int
    max_staff_daily_periods: int
    max_cohort_daily_periods: int
    staff_daily_loads: tuple[DailyLoad, ...]
    cohort_daily_loads: tuple[DailyLoad, ...]

    @property
    def preference_satisfaction_rate(self) -> float | None:
        """Return preferred placements as a ratio, if preferences exist."""
        if not self.preference_eligible_meetings:
            return None
        return self.preferred_meetings / self.preference_eligible_meetings

    @property
    def room_affinity_rate(self) -> float | None:
        """Return home-school or shared-room placements as a ratio."""
        if not self.total_meetings:
            return None
        return self.home_or_shared_room_meetings / self.total_meetings


def pair_cost(load: int) -> int:
    """Return the number of unordered pairs in a daily resource load."""
    return load * (load - 1) // 2


def placement_penalty(
    section: CourseSection,
    slot_ids: tuple[str, ...],
    room_school_id: str | None,
    slot_periods: dict[str, int],
    latest_period: int,
) -> int:
    """Score the static soft costs of one possible meeting placement."""
    penalty = 0
    if section.preferred_slot_ids and not set(slot_ids) <= section.preferred_slot_ids:
        penalty += PREFERENCE_MISS_WEIGHT
    if room_school_id not in {None, section.school_id}:
        penalty += FOREIGN_ROOM_WEIGHT
    if any(slot_periods[slot_id] == latest_period for slot_id in slot_ids):
        penalty += LATE_PERIOD_WEIGHT
    return penalty


def evaluate_schedule_quality(
    university: University,
    meetings: Iterable[ScheduledMeeting],
) -> ScheduleQuality:
    """Measure soft preferences and daily resource concentration independently."""
    meeting_list = tuple(meetings)
    sections = {section.id: section for section in university.sections}
    rooms = {room.id: room for room in university.rooms}
    slots = {slot.id: slot for slot in university.slots}
    slot_periods = {slot.id: slot.period for slot in university.slots}
    latest_period = max(slot_periods.values(), default=0)
    staff_loads: dict[tuple[str, str], int] = defaultdict(int)
    cohort_loads: dict[tuple[str, str], int] = defaultdict(int)
    preferred_meetings = 0
    preference_eligible_meetings = 0
    home_or_shared_room_meetings = 0
    late_period_meetings = 0
    static_penalty = 0

    for meeting in meeting_list:
        section = sections[meeting.section_id]
        room = rooms[meeting.room_id]
        day = slots[meeting.slot_ids[0]].day
        duration = len(meeting.slot_ids)

        if section.preferred_slot_ids:
            preference_eligible_meetings += 1
            if set(meeting.slot_ids) <= section.preferred_slot_ids:
                preferred_meetings += 1
        if room.school_id in {None, section.school_id}:
            home_or_shared_room_meetings += 1
        if any(slot_periods[slot_id] == latest_period for slot_id in meeting.slot_ids):
            late_period_meetings += 1

        static_penalty += placement_penalty(
            section,
            meeting.slot_ids,
            room.school_id,
            slot_periods,
            latest_period,
        )
        for instructor_id in section.instructor_ids:
            staff_loads[(instructor_id, day)] += duration
        for cohort_id in section.cohort_ids:
            cohort_loads[(cohort_id, day)] += duration

    staff_concentration = sum(pair_cost(load) for load in staff_loads.values())
    cohort_concentration = sum(pair_cost(load) for load in cohort_loads.values())
    staff_daily_loads = tuple(
        DailyLoad(resource_id, day, periods)
        for (resource_id, day), periods in sorted(staff_loads.items())
    )
    cohort_daily_loads = tuple(
        DailyLoad(resource_id, day, periods)
        for (resource_id, day), periods in sorted(cohort_loads.items())
    )

    return ScheduleQuality(
        soft_penalty=(
            static_penalty
            + STAFF_DAILY_PAIR_WEIGHT * staff_concentration
            + COHORT_DAILY_PAIR_WEIGHT * cohort_concentration
        ),
        preferred_meetings=preferred_meetings,
        preference_eligible_meetings=preference_eligible_meetings,
        home_or_shared_room_meetings=home_or_shared_room_meetings,
        late_period_meetings=late_period_meetings,
        total_meetings=len(meeting_list),
        max_staff_daily_periods=max(staff_loads.values(), default=0),
        max_cohort_daily_periods=max(cohort_loads.values(), default=0),
        staff_daily_loads=staff_daily_loads,
        cohort_daily_loads=cohort_daily_loads,
    )
