"""Conflict graph construction and graph metrics."""

from __future__ import annotations

from collections import defaultdict

from unischedule.models import CourseSection


def sections_conflict(left: CourseSection, right: CourseSection) -> bool:
    """Return whether two sections cannot meet at the same time."""
    return bool(set(left.instructor_ids) & set(right.instructor_ids)) or (
        students_conflict(left, right)
    )


def students_conflict(left: CourseSection, right: CourseSection) -> bool:
    """Return whether the same learners attend both course sections."""
    if not set(left.cohort_ids) & set(right.cohort_ids):
        return False
    if not left.student_group_ids or not right.student_group_ids:
        return True
    return bool(set(left.student_group_ids) & set(right.student_group_ids))


def build_conflict_graph(
    sections: tuple[CourseSection, ...],
) -> dict[str, frozenset[str]]:
    """Build an undirected adjacency-list graph for course conflicts."""
    graph: dict[str, set[str]] = defaultdict(set)
    for section in sections:
        graph[section.id]

    for index, left in enumerate(sections):
        for right in sections[index + 1 :]:
            if sections_conflict(left, right):
                graph[left.id].add(right.id)
                graph[right.id].add(left.id)

    return {node: frozenset(neighbors) for node, neighbors in graph.items()}


def graph_density(graph: dict[str, frozenset[str]]) -> float:
    """Return the proportion of possible conflict edges that exist."""
    node_count = len(graph)
    if node_count < 2:
        return 0.0
    edge_count = sum(len(neighbors) for neighbors in graph.values()) / 2
    return edge_count / (node_count * (node_count - 1) / 2)
