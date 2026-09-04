"""Constraint scheduler using MRV selection and backtracking."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from time import perf_counter

from unischedule.graph import build_conflict_graph, graph_density
from unischedule.models import CourseSection, ScheduledMeeting, University

MeetingKey = tuple[str, int]


@dataclass(frozen=True, slots=True)
class Candidate:
    slot_ids: tuple[str, ...]
    room_id: str
    penalty: int


@dataclass(frozen=True, slots=True)
class ScheduleResult:
    meetings: tuple[ScheduledMeeting, ...]
    success: bool
    elapsed_ms: float
    explored_states: int
    backtracks: int
    conflict_edges: int
    graph_density: float
    message: str


class UniversityScheduler:
    """Generate a conflict-free schedule across all university schools."""

    def __init__(self, university: University, max_states: int = 100_000):
        self.university = university
        self.max_states = max_states
        self.sections = {section.id: section for section in university.sections}
        self.staff = {member.id: member for member in university.staff}
        self.rooms = {room.id: room for room in university.rooms}
        self.slots = {slot.id: slot for slot in university.slots}
        self.graph = build_conflict_graph(university.sections)
        self._blocks = self._build_contiguous_blocks()
        self._states = 0
        self._backtracks = 0

    def solve(self) -> ScheduleResult:
        """Run constraint search and return either a complete or empty result."""
        self._states = 0
        self._backtracks = 0
        started = perf_counter()
        meetings = tuple(
            (section.id, occurrence)
            for section in self.university.sections
            for occurrence in range(1, section.meetings_per_week + 1)
        )
        assignments: dict[MeetingKey, Candidate] = {}
        solved = self._search(meetings, assignments)
        elapsed_ms = (perf_counter() - started) * 1_000
        edge_count = sum(len(neighbors) for neighbors in self.graph.values()) // 2

        if solved:
            scheduled = tuple(
                ScheduledMeeting(
                    section_id=key[0],
                    occurrence=key[1],
                    slot_ids=candidate.slot_ids,
                    room_id=candidate.room_id,
                )
                for key, candidate in sorted(assignments.items())
            )
            message = "A complete conflict-free timetable was generated."
        else:
            scheduled = ()
            message = (
                "No complete timetable was found within the search limit. "
                "Review room capacity, staff availability, and cohort conflicts."
            )

        return ScheduleResult(
            meetings=scheduled,
            success=solved,
            elapsed_ms=elapsed_ms,
            explored_states=self._states,
            backtracks=self._backtracks,
            conflict_edges=edge_count,
            graph_density=graph_density(self.graph),
            message=message,
        )

    def _search(
        self,
        meetings: tuple[MeetingKey, ...],
        assignments: dict[MeetingKey, Candidate],
    ) -> bool:
        if len(assignments) == len(meetings):
            return True
        if self._states >= self.max_states:
            return False

        unassigned = [meeting for meeting in meetings if meeting not in assignments]
        candidate_map = {
            meeting: self._candidates(meeting, assignments) for meeting in unassigned
        }
        if any(not candidates for candidates in candidate_map.values()):
            self._backtracks += 1
            return False

        meeting = min(
            unassigned,
            key=lambda item: (
                len(candidate_map[item]),
                -len(self.graph[item[0]]),
                item[0],
                item[1],
            ),
        )

        for candidate in candidate_map[meeting]:
            self._states += 1
            assignments[meeting] = candidate
            if self._search(meetings, assignments):
                return True
            del assignments[meeting]

        self._backtracks += 1
        return False

    def _candidates(
        self,
        meeting: MeetingKey,
        assignments: dict[MeetingKey, Candidate],
    ) -> list[Candidate]:
        section = self.sections[meeting[0]]
        candidates: list[Candidate] = []

        occupied_rooms: dict[str, set[str]] = defaultdict(set)
        occupied_sections: dict[str, set[str]] = defaultdict(set)
        section_days: set[str] = set()

        for assigned_key, assigned in assignments.items():
            assigned_section_id = assigned_key[0]
            for slot_id in assigned.slot_ids:
                occupied_rooms[slot_id].add(assigned.room_id)
                occupied_sections[slot_id].add(assigned_section_id)
            if assigned_section_id == section.id:
                section_days.add(self.slots[assigned.slot_ids[0]].day)

        suitable_rooms = [
            room
            for room in self.university.rooms
            if room.capacity >= section.expected_students
            and section.required_room_features <= room.features
        ]

        for block in self._blocks.get(section.duration_slots, ()):
            block_set = set(block)
            day = self.slots[block[0]].day
            if day in section_days:
                continue
            if block_set & section.unavailable_slot_ids:
                continue
            if not self._staff_available(section, block_set):
                continue
            if self._has_academic_conflict(section, block_set, occupied_sections):
                continue

            for room in suitable_rooms:
                if any(room.id in occupied_rooms[slot_id] for slot_id in block):
                    continue
                penalty = self._candidate_penalty(section, block, room.school_id)
                candidates.append(Candidate(block, room.id, penalty))

        return sorted(
            candidates,
            key=lambda item: (item.penalty, item.slot_ids, item.room_id),
        )

    def _staff_available(self, section: CourseSection, block: set[str]) -> bool:
        for instructor_id in section.instructor_ids:
            availability = self.staff[instructor_id].available_slot_ids
            if availability and not block <= availability:
                return False
        return True

    def _has_academic_conflict(
        self,
        section: CourseSection,
        block: set[str],
        occupied_sections: dict[str, set[str]],
    ) -> bool:
        conflicting_sections = self.graph[section.id] | {section.id}
        return any(
            occupied_sections[slot_id] & conflicting_sections for slot_id in block
        )

    def _candidate_penalty(
        self,
        section: CourseSection,
        block: tuple[str, ...],
        room_school_id: str | None,
    ) -> int:
        penalty = 0
        if section.preferred_slot_ids and not set(block) <= section.preferred_slot_ids:
            penalty += 3
        if room_school_id not in {None, section.school_id}:
            penalty += 2
        start_period = self.slots[block[0]].period
        if start_period == max(slot.period for slot in self.university.slots):
            penalty += 1
        return penalty

    def _build_contiguous_blocks(self) -> dict[int, tuple[tuple[str, ...], ...]]:
        by_day: dict[str, list] = defaultdict(list)
        for slot in self.university.slots:
            by_day[slot.day].append(slot)

        durations = {section.duration_slots for section in self.university.sections}
        blocks: dict[int, list[tuple[str, ...]]] = defaultdict(list)
        for day_slots in by_day.values():
            ordered = sorted(day_slots, key=lambda slot: slot.period)
            for duration in durations:
                for index in range(len(ordered) - duration + 1):
                    window = ordered[index : index + duration]
                    periods = [slot.period for slot in window]
                    if periods == list(range(periods[0], periods[0] + duration)):
                        blocks[duration].append(tuple(slot.id for slot in window))
        return {duration: tuple(values) for duration, values in blocks.items()}


def workload_by_staff(
    result: ScheduleResult,
    university: University,
) -> dict[str, int]:
    """Count scheduled teaching periods for each staff member."""
    sections = {section.id: section for section in university.sections}
    workload: Counter[str] = Counter()
    for meeting in result.meetings:
        section = sections[meeting.section_id]
        for instructor_id in section.instructor_ids:
            workload[instructor_id] += len(meeting.slot_ids)
    return dict(workload)
