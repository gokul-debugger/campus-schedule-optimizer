"""Resolve the learner resources represented by each course section."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping

from unischedule.models import CourseSection, StudentGroup


def groups_by_cohort(
    student_groups: tuple[StudentGroup, ...],
) -> dict[str, tuple[str, ...]]:
    """Index student-group IDs by their parent cohort."""
    grouped: dict[str, list[str]] = defaultdict(list)
    for group in student_groups:
        grouped[group.cohort_id].append(group.id)
    return {
        cohort_id: tuple(sorted(group_ids))
        for cohort_id, group_ids in grouped.items()
    }


def learner_resource_ids(
    section: CourseSection,
    cohort_groups: Mapping[str, tuple[str, ...]],
) -> tuple[str, ...]:
    """Return the indivisible learner resources attending a section."""
    if section.student_group_ids:
        return section.student_group_ids

    resources: list[str] = []
    for cohort_id in section.cohort_ids:
        resources.extend(cohort_groups.get(cohort_id, (cohort_id,)))
    return tuple(resources)
