"""Generate a timetable CSV from a university JSON configuration."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from unischedule import UniversityScheduler, load_university  # noqa: E402
from unischedule.reporting import schedule_records, validate_schedule  # noqa: E402

REPORT_COLUMNS = (
    "day",
    "start",
    "end",
    "school",
    "course",
    "title",
    "subject_area",
    "program",
    "cohorts",
    "instructors",
    "room",
    "building",
    "occurrence",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("configuration", type=Path)
    parser.add_argument("--output", type=Path, default=Path("reports/schedule.csv"))
    parser.add_argument("--max-states", type=int, default=100_000)
    arguments = parser.parse_args()

    university = load_university(arguments.configuration)
    result = UniversityScheduler(university, max_states=arguments.max_states).solve()
    if not result.success:
        print(result.message)
        return 1

    violations = validate_schedule(university, result)
    if violations:
        print("Schedule validation failed:")
        for violation in violations:
            print(f"- {violation}")
        return 2

    records = schedule_records(university, result)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    with arguments.output.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=REPORT_COLUMNS)
        writer.writeheader()
        writer.writerows(
            {column: record[column] for column in REPORT_COLUMNS}
            for record in records
        )

    print(
        f"Scheduled {len(result.meetings)} meetings in {result.elapsed_ms:.1f} ms. "
        f"Saved {arguments.output}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
