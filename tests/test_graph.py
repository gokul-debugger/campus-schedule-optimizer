from __future__ import annotations

from unischedule.graph import build_conflict_graph, graph_density
from unischedule.models import CourseSection


def section(
    identifier: str,
    cohorts: tuple[str, ...],
    instructors: tuple[str, ...],
) -> CourseSection:
    return CourseSection(
        id=identifier,
        code=identifier,
        title=identifier,
        school_id="S1",
        subject_area="Computing",
        program="BSc",
        cohort_ids=cohorts,
        instructor_ids=instructors,
        meetings_per_week=1,
        duration_slots=1,
        expected_students=20,
    )


def test_conflict_graph_tracks_staff_and_cohort_collisions() -> None:
    sections = (
        section("A", ("Y1",), ("T1",)),
        section("B", ("Y1",), ("T2",)),
        section("C", ("Y2",), ("T1",)),
        section("D", ("Y3",), ("T3",)),
    )

    graph = build_conflict_graph(sections)

    assert graph["A"] == frozenset({"B", "C"})
    assert graph["B"] == frozenset({"A"})
    assert graph["C"] == frozenset({"A"})
    assert graph["D"] == frozenset()
    assert graph_density(graph) == 2 / 6

