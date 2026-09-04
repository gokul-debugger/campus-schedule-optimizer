"""Repeatable benchmark for the demonstration university."""

from __future__ import annotations

import statistics
import sys
from pathlib import Path
from time import perf_counter

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from unischedule import UniversityScheduler, load_university  # noqa: E402


def main(runs: int = 50) -> None:
    university = load_university(PROJECT_ROOT / "examples" / "demo_university.json")
    timings = []
    explored_states = []
    for _ in range(runs):
        started = perf_counter()
        result = UniversityScheduler(university).solve()
        timings.append((perf_counter() - started) * 1_000)
        explored_states.append(result.explored_states)
        if not result.success:
            raise RuntimeError("The demonstration schedule unexpectedly failed")

    print(f"Runs: {runs}")
    print(f"Median runtime: {statistics.median(timings):.2f} ms")
    print(f"95th percentile: {sorted(timings)[int(runs * 0.95) - 1]:.2f} ms")
    print(f"Median explored states: {statistics.median(explored_states):.0f}")


if __name__ == "__main__":
    main()

