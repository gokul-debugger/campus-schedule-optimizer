# University Schedule Optimizer

A graph-based timetable generator for universities with multiple academic schools,
shared teaching staff, specialized rooms, recurring classes, and cross-school
courses.

Unlike a subject-only timetable demo, this project models the academic structure
of a university. A school is the primary department-level unit, such as the
School of Computer Science or School of Artificial Intelligence. Subject areas
organize courses within each school.

## What It Solves

The scheduler assigns every course meeting to a time and room while enforcing
these constraints:

- professors, lecturers, and mentors cannot teach two classes at once
- student cohorts cannot attend overlapping classes
- rooms cannot be double-booked
- room capacity must meet expected enrollment
- laboratories must provide all required equipment
- staff and course availability must be respected
- recurring meetings for one section must occur on different days
- staff may teach across schools only when affiliated with each relevant school

The result is independently validated after generation, rather than trusting the
search algorithm alone.

## University Model

```text
University
├── School of Computer Science
│   ├── BSc Computer Science cohorts
│   ├── Software Foundations
│   ├── Systems
│   └── Data Engineering
└── School of Artificial Intelligence
    ├── BSc Artificial Intelligence cohorts
    ├── Machine Learning
    ├── AI Engineering
    └── AI Governance
```

Each school can contain multiple programs and cohorts. Shared professors,
university electives, central classrooms, and specialist laboratories connect
the schools into one university-wide scheduling problem.

## Algorithms and Data Structures

| Component | Technique | Purpose |
|---|---|---|
| Academic conflicts | Undirected adjacency-list graph | Represents shared cohorts and instructors |
| Variable selection | Minimum Remaining Values | Schedules the most constrained meeting first |
| Tie breaking | Conflict-graph degree | Prioritizes meetings affecting more neighbors |
| Candidate ordering | Weighted preference score | Favors preferred times and home-school rooms |
| Constraint solving | Backtracking with early rejection | Recovers when a locally valid choice blocks the timetable |
| Substitute matching | Eligibility filtering with scarce-first assignment | Finds qualified, available cover without timetable collisions |
| Resource tracking | Hash sets and indexed dictionaries | Detects room, staff, and cohort collisions efficiently |
| Verification | Independent constraint pass | Checks every generated assignment for hard violations |

For the included demonstration university, the engine schedules 22 meetings
covering 28 occupied periods. A 50-run benchmark on an Apple Silicon laptop had
a median runtime of approximately 65 ms. Runtime will increase with denser
conflict graphs and more restricted availability.

## Application

The Streamlit interface includes:

- editable schools, cohorts, staff, rooms, periods, and course sections
- linked selectors that prevent invalid cross-record references
- permanent weekly availability management for every staff member
- temporary emergency-leave recording and removal
- qualified substitute suggestions with collision and absence checks
- saved cover indicators on the weekly timetable
- downloadable substitute coverage plans
- recurring `.ics` calendar export by cohort, instructor, room, or school
- university-wide schedule generation
- weekly timetable views by cohort, instructor, room, and school
- complete course, instructor, room, and building details
- room-utilization and teaching-workload views
- algorithm diagnostics and independent validation results
- JSON configuration upload
- validated JSON configuration export
- timetable CSV export

The included fictional dataset contains:

| Resource | Count |
|---|---:|
| Academic schools | 2 |
| Student cohorts | 6 |
| Course sections | 14 |
| Professors, lecturers, and mentors | 10 |
| Teaching rooms and laboratories | 8 |
| Available weekly periods | 25 |
| Recurring meetings to schedule | 22 |

## Project Structure

```text
campus-schedule-optimizer/
├── .github/workflows/tests.yml
├── app/app.py
├── benchmarks/benchmark_demo.py
├── examples/demo_university.json
├── reports/
├── scripts/generate_schedule.py
├── src/unischedule/
│   ├── graph.py
│   ├── calendar.py
│   ├── configuration.py
│   ├── io.py
│   ├── models.py
│   ├── operations.py
│   ├── reporting.py
│   └── scheduler.py
├── tests/
├── LICENSE
├── pyproject.toml
├── requirements-dev.txt
└── requirements.txt
```

## Run Locally

The project uses Python 3.12 and its own virtual environment.

```bash
cd "/Users/paco/Documents/Git Projects/campus-schedule-optimizer"
source .venv/bin/activate
streamlit run app/app.py
```

To recreate the environment:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Command-Line Export

Generate a validated CSV timetable without opening the dashboard:

```bash
python scripts/generate_schedule.py examples/demo_university.json \
  --output reports/demo_schedule.csv
```

## Configuration Format

University data is supplied as JSON with six main collections:

```json
{
  "university": "Example University",
  "schools": [],
  "cohorts": [],
  "time_slots": [],
  "staff": [],
  "rooms": [],
  "course_sections": []
}
```

The Administration workspace edits the same structure used by the scheduler.
Changes are converted back to JSON and validated before they replace the active
configuration. Invalid references, unsuitable rooms, duplicate IDs, and incomplete
rows are rejected without damaging the working schedule.

Staff records can include `qualified_subject_areas`. Substitute recommendations
use these qualifications together with school affiliation, permanent availability,
temporary absence, and the generated timetable. An empty qualification list acts
as general cover eligibility within the staff member's affiliated schools.

Temporary leave and substitute assignments are operational session data. They do
not alter the uploaded or built-in university configuration. A completed cover plan
can be exported as CSV for coordinators and teaching staff.

Each filtered timetable can also be exported as an RFC 5545 `.ics` calendar. The
app normalizes the selected first teaching week to Monday and creates weekly
recurring events for the chosen semester length. The file can be imported into
Apple Calendar, Google Calendar, Outlook, and other compatible calendar clients.

The complete example in `examples/demo_university.json` is both a demonstration
dataset and an input template. Empty staff availability means the staff member is
available in every configured period.

## Quality Checks

```bash
ruff check .
pytest
python benchmarks/benchmark_demo.py
```

The test suite covers graph construction, editable-table conversion, configuration
validation, cross-school staff rules, cohort references, room suitability, complete
schedule generation, recurring-meeting distribution, independent verification,
permanent availability updates, substitute eligibility, cover-plan validation, and
calendar generation, and impossible schedules. GitHub Actions runs linting and
tests for every push and pull request.

## Current Scope

The search engine is designed for small and medium teaching schedules. Very large
universities may require decomposition by school, constraint programming, or an
integer optimization backend. Current soft preferences cover preferred periods
and home-school rooms; instructor workload balancing and student choice groups
are suitable next additions.

## Author

Gokul Krishna  
[GitHub profile](https://github.com/gokul-debugger)

## License

Released under the MIT License.
