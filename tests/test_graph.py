from __future__ import annotations

from unischedule.attendance import groups_by_cohort, learner_resource_ids
from unischedule.graph import build_conflict_graph, graph_density, students_conflict
from unischedule.models import CourseSection, StudentGroup


def section(
    identifier: str,
    cohorts: tuple[str, ...],
    instructors: tuple[str, ...],
    student_groups: tuple[str, ...] = (),
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
        student_group_ids=student_groups,
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


def test_disjoint_elective_groups_do_not_conflict() -> None:
    data_track = section("DATA", ("Y3",), ("T1",), ("Y3-DATA",))
    security_track = section("SEC", ("Y3",), ("T2",), ("Y3-SEC",))
    shared_track = section("SHARED", ("Y3",), ("T3",), ("Y3-DATA",))
    compulsory = section("CORE", ("Y3",), ("T4",))

    assert not students_conflict(data_track, security_track)
    assert students_conflict(data_track, shared_track)
    assert students_conflict(data_track, compulsory)

    graph = build_conflict_graph(
        (data_track, security_track, shared_track, compulsory)
    )

    assert "SEC" not in graph["DATA"]
    assert graph["DATA"] == frozenset({"SHARED", "CORE"})


def test_whole_cohort_section_expands_to_all_configured_groups() -> None:
    groups = (
        StudentGroup("Y3-A", "Track A", "Y3", 10),
        StudentGroup("Y3-B", "Track B", "Y3", 10),
    )
    cohort_groups = groups_by_cohort(groups)

    assert learner_resource_ids(section("CORE", ("Y3",), ("T1",)), cohort_groups) == (
        "Y3-A",
        "Y3-B",
    )
    assert learner_resource_ids(
        section("ELECTIVE", ("Y3",), ("T1",), ("Y3-A",)),
        cohort_groups,
    ) == ("Y3-A",)
    assert learner_resource_ids(
        section("LEGACY", ("Y2",), ("T1",)),
        cohort_groups,
    ) == ("Y2",)
