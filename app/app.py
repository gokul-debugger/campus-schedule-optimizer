"""Streamlit interface for university-wide schedule generation."""

from __future__ import annotations

import hashlib
import html
import json
import sys
from datetime import date, timedelta
from io import StringIO
from pathlib import Path
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from unischedule.calendar import build_ics_calendar  # noqa: E402
from unischedule.configuration import (  # noqa: E402
    configuration_from_editor,
    editor_rows,
)
from unischedule.io import UniversityDataError, university_from_dict  # noqa: E402
from unischedule.operations import (  # noqa: E402
    StaffAbsence,
    coverage_plan_records,
    eligible_substitutes,
    find_coverage_needs,
    propose_coverage_assignments,
    update_staff_availability,
    validate_coverage_assignments,
)
from unischedule.reporting import (  # noqa: E402
    room_utilization,
    schedule_records,
    validate_schedule,
)
from unischedule.scheduler import UniversityScheduler, workload_by_staff  # noqa: E402

DEMO_PATH = PROJECT_ROOT / "examples" / "demo_university.json"
SCHOOL_COLORS = ("#0f766e", "#c26631", "#496b8a", "#7a5c9e", "#8a6d24")

st.set_page_config(
    page_title="UniSchedule",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .stApp { background: #f5f7f8; color: #172026; }
    [data-testid="stSidebar"] { background: #17242b; }
    [data-testid="stSidebar"] * { color: #f4f7f8; }
    [data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #dbe2e6;
        border-radius: 6px;
        padding: 14px 16px;
    }
    [data-testid="stMetricLabel"] * { color: #53626a !important; }
    [data-testid="stMetricValue"] * { color: #172026 !important; }
    .status-ok, .status-error {
        padding: 12px 14px;
        margin: 8px 0 4px;
    }
    .status-ok {
        border-left: 4px solid #16815f;
        background: #e9f6f1;
        color: #124f3e;
    }
    .status-error {
        border-left: 4px solid #bd3c39;
        background: #faeceb;
        color: #742623;
    }
    .timetable-wrap {
        overflow-x: auto;
        border: 1px solid #d7dfe3;
        background: #ffffff;
    }
    .timetable-grid {
        display: grid;
    }
    .grid-header, .time-cell, .schedule-cell {
        border-right: 1px solid #dfe5e8;
        border-bottom: 1px solid #dfe5e8;
        padding: 10px;
    }
    .grid-header {
        background: #e8eef0;
        color: #35454d;
        font-size: 0.82rem;
        font-weight: 700;
        min-height: 44px;
    }
    .time-cell {
        background: #f7f9fa;
        color: #53626a;
        font-size: 0.78rem;
        min-height: 104px;
    }
    .schedule-cell { min-height: 104px; }
    .meeting {
        border-left: 4px solid #0f766e;
        background: #f1f5f5;
        border-radius: 4px;
        margin-bottom: 6px;
        padding: 7px 8px;
        color: #172026;
    }
    .meeting-code { font-size: 0.82rem; font-weight: 750; }
    .meeting-title { font-size: 0.76rem; margin-top: 2px; }
    .meeting-room { color: #66757c; font-size: 0.7rem; margin-top: 4px; }
    .meeting-cover {
        background: #e9f6f1;
        color: #125c47;
        font-size: 0.7rem;
        font-weight: 650;
        margin-top: 6px;
        padding: 4px 6px;
    }
    h1, h2, h3 { letter-spacing: 0; }
    @media (max-width: 640px) {
        h1 { font-size: 2rem !important; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def read_demo() -> dict[str, Any]:
    return json.loads(DEMO_PATH.read_text(encoding="utf-8"))


def activate_configuration(data: dict[str, Any], source: str) -> None:
    university_from_dict(data)
    st.session_state["active_configuration"] = data
    st.session_state["configuration_source"] = source
    version = st.session_state.get("editor_version", 0)
    st.session_state["editor_version"] = version + 1
    st.session_state.pop("schedule_key", None)
    st.session_state.pop("staff_absences", None)
    st.session_state.pop("coverage_assignments", None)
    clear_coverage_widgets()


def clear_coverage_widgets() -> None:
    for key in list(st.session_state):
        if key.startswith("cover_"):
            st.session_state.pop(key)


def initialize_configuration() -> None:
    if "active_configuration" not in st.session_state:
        activate_configuration(read_demo(), "Built-in demonstration")

    uploaded = st.sidebar.file_uploader("University configuration", type=["json"])
    if uploaded is None:
        return

    payload = uploaded.getvalue()
    fingerprint = hashlib.sha256(payload).hexdigest()
    st.session_state["current_upload_fingerprint"] = fingerprint
    if st.session_state.get("ignored_upload_fingerprint") == fingerprint:
        return
    if st.session_state.get("upload_fingerprint") == fingerprint:
        return
    try:
        candidate = json.loads(payload)
        activate_configuration(candidate, uploaded.name)
        st.session_state["upload_fingerprint"] = fingerprint
        st.session_state["notice"] = f"Loaded {uploaded.name}"
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        st.sidebar.error(f"Configuration rejected: {error}")


def reset_demo() -> None:
    activate_configuration(read_demo(), "Built-in demonstration")
    st.session_state["upload_fingerprint"] = None
    st.session_state["ignored_upload_fingerprint"] = st.session_state.get(
        "current_upload_fingerprint"
    )
    st.session_state["notice"] = "Demonstration data restored"


def csv_download(dataframe: pd.DataFrame) -> bytes:
    buffer = StringIO()
    dataframe.to_csv(buffer, index=False)
    return buffer.getvalue().encode("utf-8")


def school_color_map(school_ids: list[str]) -> dict[str, str]:
    return {
        school_id: SCHOOL_COLORS[index % len(SCHOOL_COLORS)]
        for index, school_id in enumerate(school_ids)
    }


def timetable_filter(
    schedule: pd.DataFrame,
    view: str,
    selected_id: str,
) -> pd.DataFrame:
    if view == "Cohort":
        mask = schedule["cohort_ids"].apply(lambda values: selected_id in values)
    elif view == "Instructor":
        mask = schedule["instructor_ids"].apply(lambda values: selected_id in values)
    elif view == "Room":
        mask = schedule["room_id"] == selected_id
    else:
        mask = schedule["school_id"] == selected_id
    return schedule[mask].copy()


def render_timetable(
    university: Any,
    filtered: pd.DataFrame,
    colors: dict[str, str],
    coverage_labels: dict[tuple[str, int], list[str]],
) -> None:
    days = list(dict.fromkeys(slot.day for slot in university.slots))
    periods: dict[int, tuple[str, str]] = {}
    for slot in university.slots:
        periods.setdefault(slot.period, (slot.start, slot.end))

    minimum_width = 108 + (160 * len(days))
    grid_style = (
        f"grid-template-columns:108px repeat({len(days)}, minmax(160px, 1fr));"
        f"min-width:{minimum_width}px"
    )
    blocks = [
        '<div class="timetable-wrap">'
        f'<div class="timetable-grid" style="{grid_style}">'
    ]
    blocks.append('<div class="grid-header">Time</div>')
    for day in days:
        blocks.append(f'<div class="grid-header">{html.escape(day)}</div>')

    for period, (start, end) in sorted(periods.items()):
        blocks.append(
            '<div class="time-cell">'
            f"<strong>Period {period}</strong><br>{html.escape(start)}<br>"
            f"{html.escape(end)}</div>"
        )
        for day in days:
            meetings = filtered[
                (filtered["day"] == day) & (filtered["period"] == period)
            ]
            blocks.append('<div class="schedule-cell">')
            for meeting in meetings.to_dict("records"):
                color = colors.get(meeting["school_id"], SCHOOL_COLORS[0])
                course = html.escape(meeting["course"])
                title = html.escape(meeting["title"])
                room = html.escape(meeting["room"])
                building = html.escape(meeting["building"])
                cover = "".join(
                    f'<div class="meeting-cover">{html.escape(label)}</div>'
                    for label in coverage_labels.get(
                        (meeting["section_id"], meeting["occurrence"]),
                        [],
                    )
                )
                blocks.append(
                    f'<div class="meeting" style="border-left-color:{color}">'
                    f'<div class="meeting-code">{course}</div>'
                    f'<div class="meeting-title">{title}</div>'
                    f'<div class="meeting-room">{room} · {building}</div>'
                    f"{cover}</div>"
                )
            blocks.append("</div>")
    blocks.append("</div></div>")
    st.markdown("".join(blocks), unsafe_allow_html=True)


def editor_dataframe(rows: list[dict[str, Any]], columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=columns)


st.sidebar.title("UniSchedule")
st.sidebar.caption("University timetable control")
initialize_configuration()

if st.sidebar.button(
    "Restore demonstration",
    icon=":material/restart_alt:",
    width="stretch",
):
    reset_demo()
    st.rerun()

search_limit = st.sidebar.number_input(
    "Maximum search states",
    min_value=1_000,
    max_value=1_000_000,
    value=100_000,
    step=10_000,
)
generate = st.sidebar.button(
    "Generate timetable",
    icon=":material/calendar_month:",
    type="primary",
    width="stretch",
)
st.sidebar.caption(f"Source: {st.session_state['configuration_source']}")

raw_data = st.session_state["active_configuration"]
university = university_from_dict(raw_data)
state_key = json.dumps(raw_data, sort_keys=True) + str(search_limit)
if generate or st.session_state.get("schedule_key") != state_key:
    with st.spinner("Resolving university-wide constraints..."):
        st.session_state["schedule_result"] = UniversityScheduler(
            university,
            max_states=int(search_limit),
        ).solve()
        st.session_state["schedule_key"] = state_key

if notice := st.session_state.pop("notice", None):
    st.toast(notice)

result = st.session_state["schedule_result"]
violations = validate_schedule(university, result)
records = schedule_records(university, result) if result.success else []
schedule_df = pd.DataFrame(records)
school_lookup = {school.id: school.name for school in university.schools}
staff_lookup = {member.id: member.name for member in university.staff}
staff_role_lookup = {member.id: member.role for member in university.staff}
room_lookup = {room.id: room.name for room in university.rooms}
cohort_lookup = {cohort.id: cohort.name for cohort in university.cohorts}
slot_lookup = {slot.id: slot for slot in university.slots}
section_lookup = {section.id: section for section in university.sections}
colors = school_color_map(list(school_lookup))
active_absences: tuple[StaffAbsence, ...] = tuple(
    st.session_state.get("staff_absences", ())
)
coverage_needs = find_coverage_needs(university, result, active_absences)
coverage_assignments: dict[str, str] = st.session_state.get(
    "coverage_assignments",
    {},
)
coverage_labels: dict[tuple[str, int], list[str]] = {}
for need in coverage_needs:
    substitute_id = coverage_assignments.get(need.id)
    if substitute_id in staff_lookup:
        key = (need.section_id, need.occurrence)
        label = (
            f"Cover: {staff_lookup[substitute_id]} for "
            f"{staff_lookup[need.absent_staff_id]}"
        )
        coverage_labels.setdefault(key, []).append(label)

st.title("University Schedule Optimizer")
st.caption(university.name)

metric_columns = st.columns(6)
metric_columns[0].metric("Schools", len(university.schools))
metric_columns[1].metric("Cohorts", len(university.cohorts))
metric_columns[2].metric("Course sections", len(university.sections))
metric_columns[3].metric("Teaching staff", len(university.staff))
metric_columns[4].metric("Rooms", len(university.rooms))
metric_columns[5].metric("Scheduled periods", len(schedule_df))

if result.success and not violations:
    st.markdown(
        '<div class="status-ok"><strong>Schedule valid</strong><br>'
        "All meetings are assigned without staff, cohort, or room conflicts.</div>",
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        '<div class="status-error"><strong>Action required</strong><br>'
        f"{html.escape(result.message)}</div>",
        unsafe_allow_html=True,
    )

(
    schedule_tab,
    schools_tab,
    staff_tab,
    resources_tab,
    algorithm_tab,
    config_tab,
) = st.tabs(
    [
        "Timetable",
        "Schools",
        "Staff operations",
        "Resources",
        "Algorithm",
        "Administration",
    ]
)

with schedule_tab:
    if not result.success:
        st.warning(result.message)
    else:
        control_columns = st.columns([1, 2])
        view = control_columns[0].segmented_control(
            "View by",
            ["Cohort", "Instructor", "Room", "School"],
            default="Cohort",
        ) or "Cohort"
        lookup_by_view = {
            "Cohort": cohort_lookup,
            "Instructor": staff_lookup,
            "Room": room_lookup,
            "School": school_lookup,
        }
        lookup = lookup_by_view[view]
        selected_id = control_columns[1].selectbox(
            view,
            options=list(lookup),
            format_func=lookup.get,
        )
        filtered = timetable_filter(schedule_df, view, selected_id)
        render_timetable(university, filtered, colors, coverage_labels)

        display_columns = [
            "day",
            "start",
            "end",
            "school",
            "course",
            "title",
            "cohorts",
            "instructors",
            "room",
        ]
        with st.expander("Schedule records"):
            st.dataframe(
                filtered[display_columns],
                hide_index=True,
                width="stretch",
                height=360,
            )
        st.download_button(
            "Download this timetable",
            data=csv_download(filtered[display_columns]),
            file_name=f"{view.lower()}_{selected_id}_schedule.csv",
            mime="text/csv",
            icon=":material/download:",
        )
        with st.expander("Calendar export"):
            calendar_columns = st.columns(2)
            current_monday = date.today() - timedelta(days=date.today().weekday())
            first_week = calendar_columns[0].date_input(
                "First teaching week",
                value=current_monday,
                help="Any date is accepted and normalized to that week's Monday.",
            )
            teaching_weeks = calendar_columns[1].number_input(
                "Teaching weeks",
                min_value=1,
                max_value=52,
                value=12,
                step=1,
            )
            first_monday = first_week - timedelta(days=first_week.weekday())
            st.caption(
                f"Weekly events will begin on {first_monday:%d %B %Y} and repeat "
                f"for {int(teaching_weeks)} weeks."
            )
            meeting_ids = {
                (row["section_id"], int(row["occurrence"]))
                for row in filtered.to_dict("records")
            }
            calendar_data = build_ics_calendar(
                university,
                result,
                first_week=first_week,
                weeks=int(teaching_weeks),
                meeting_ids=meeting_ids,
                calendar_name=(
                    f"{university.name} | {view}: {lookup[selected_id]}"
                ),
            )
            st.download_button(
                "Download calendar",
                data=calendar_data,
                file_name=f"{view.lower()}_{selected_id}_calendar.ics",
                mime="text/calendar",
                icon=":material/calendar_add_on:",
            )

with schools_tab:
    selected_school_id = st.selectbox(
        "School",
        options=list(school_lookup),
        format_func=school_lookup.get,
        key="school_overview",
    )
    school_staff = [
        member for member in university.staff if selected_school_id in member.school_ids
    ]
    school_cohorts = [
        cohort
        for cohort in university.cohorts
        if cohort.school_id == selected_school_id
    ]
    school_sections = [
        section
        for section in university.sections
        if section.school_id == selected_school_id
    ]
    school_rooms = [
        room for room in university.rooms if room.school_id == selected_school_id
    ]
    summary_columns = st.columns(4)
    summary_columns[0].metric("Cohorts", len(school_cohorts))
    summary_columns[1].metric("Staff", len(school_staff))
    summary_columns[2].metric("Course sections", len(school_sections))
    summary_columns[3].metric("Dedicated rooms", len(school_rooms))

    section_rows = [
        {
            "course": section.code,
            "title": section.title,
            "subject_area": section.subject_area,
            "program": section.program,
            "cohorts": ", ".join(section.cohort_ids),
            "weekly_meetings": section.meetings_per_week,
        }
        for section in school_sections
    ]
    staff_rows = [
        {
            "name": member.name,
            "role": member.role,
            "school_affiliations": ", ".join(
                school_lookup[item] for item in member.school_ids
            ),
        }
        for member in school_staff
    ]
    left, right = st.columns([3, 2])
    with left:
        st.subheader("Course portfolio")
        st.dataframe(pd.DataFrame(section_rows), hide_index=True, width="stretch")
    with right:
        st.subheader("Academic staff")
        st.dataframe(pd.DataFrame(staff_rows), hide_index=True, width="stretch")

with staff_tab:
    st.subheader("Weekly availability")
    st.caption(
        "Permanent availability changes regenerate the timetable. Empty availability "
        "in the configuration means the staff member is available for every period."
    )
    availability_columns = st.columns([2, 2, 1])
    availability_staff_id = availability_columns[0].selectbox(
        "Staff member",
        options=list(staff_lookup),
        format_func=staff_lookup.get,
        key="availability_staff",
    )
    availability_member = next(
        member for member in university.staff if member.id == availability_staff_id
    )
    all_periods = availability_columns[2].checkbox(
        "All periods",
        value=not availability_member.available_slot_ids,
        key=f"all_periods_{availability_staff_id}",
    )
    slot_label = lambda slot_id: (  # noqa: E731
        f"{slot_lookup[slot_id].day} | "
        f"{slot_lookup[slot_id].start}-{slot_lookup[slot_id].end}"
    )
    if all_periods:
        selected_availability = list(slot_lookup)
        availability_columns[1].multiselect(
            "Available teaching periods",
            options=list(slot_lookup),
            default=list(slot_lookup),
            format_func=slot_label,
            disabled=True,
            key=f"availability_slots_all_{availability_staff_id}",
        )
    else:
        selected_availability = availability_columns[1].multiselect(
            "Available teaching periods",
            options=list(slot_lookup),
            default=list(availability_member.available_slot_ids),
            format_func=slot_label,
            key=f"availability_slots_{availability_staff_id}",
        )

    if st.button(
        "Save weekly availability",
        icon=":material/schedule:",
        disabled=not all_periods and not selected_availability,
    ):
        stored_slots = [] if all_periods else selected_availability
        candidate = update_staff_availability(
            raw_data,
            availability_staff_id,
            stored_slots,
        )
        activate_configuration(candidate, "Edited workspace")
        st.session_state["notice"] = (
            f"Availability updated for {staff_lookup[availability_staff_id]}"
        )
        st.rerun()

    st.divider()
    st.subheader("Emergency leave")
    leave_columns = st.columns([2, 1, 2])
    leave_staff_id = leave_columns[0].selectbox(
        "Absent staff member",
        options=list(staff_lookup),
        format_func=staff_lookup.get,
        key="leave_staff",
    )
    days = list(dict.fromkeys(slot.day for slot in university.slots))
    leave_day = leave_columns[1].selectbox("Day", options=days, key="leave_day")
    day_slot_ids = [
        slot.id for slot in university.slots if slot.day == leave_day
    ]
    leave_slot_ids = leave_columns[2].multiselect(
        "Affected periods",
        options=day_slot_ids,
        default=day_slot_ids,
        format_func=slot_label,
        key=f"leave_slots_{leave_staff_id}_{leave_day}",
    )
    leave_reason = st.text_input(
        "Reason or note",
        value="Emergency leave",
        key="leave_reason",
    )
    if st.button(
        "Record temporary leave",
        icon=":material/event_busy:",
        disabled=not leave_slot_ids,
    ):
        already_absent = {
            slot_id
            for absence in active_absences
            if absence.staff_id == leave_staff_id
            for slot_id in absence.slot_ids
        }
        new_slots = tuple(
            slot_id for slot_id in leave_slot_ids if slot_id not in already_absent
        )
        if not new_slots:
            st.warning(
                "Those leave periods are already recorded for this staff member."
            )
        else:
            counter = st.session_state.get("absence_counter", 0) + 1
            st.session_state["absence_counter"] = counter
            st.session_state["staff_absences"] = [
                *active_absences,
                StaffAbsence(
                    id=f"leave-{counter}",
                    staff_id=leave_staff_id,
                    slot_ids=new_slots,
                    reason=leave_reason.strip() or "Emergency leave",
                ),
            ]
            st.session_state["coverage_assignments"] = {}
            clear_coverage_widgets()
            st.session_state["notice"] = "Temporary leave recorded"
            st.rerun()

    if active_absences:
        absence_rows = []
        absence_labels = {}
        for absence in active_absences:
            leave_slots = [slot_lookup[slot_id] for slot_id in absence.slot_ids]
            days_text = ", ".join(dict.fromkeys(slot.day for slot in leave_slots))
            periods_text = ", ".join(
                f"{slot.start}-{slot.end}" for slot in leave_slots
            )
            absence_rows.append(
                {
                    "staff_member": staff_lookup[absence.staff_id],
                    "day": days_text,
                    "periods": periods_text,
                    "reason": absence.reason,
                }
            )
            absence_labels[absence.id] = (
                f"{staff_lookup[absence.staff_id]} | {days_text} | {periods_text}"
            )
        st.dataframe(pd.DataFrame(absence_rows), hide_index=True, width="stretch")
        removal_columns = st.columns([3, 1, 1])
        remove_absence_id = removal_columns[0].selectbox(
            "Leave entry",
            options=list(absence_labels),
            format_func=absence_labels.get,
            label_visibility="collapsed",
        )
        if removal_columns[1].button(
            "Remove",
            icon=":material/delete:",
            width="stretch",
        ):
            st.session_state["staff_absences"] = [
                absence
                for absence in active_absences
                if absence.id != remove_absence_id
            ]
            st.session_state["coverage_assignments"] = {}
            clear_coverage_widgets()
            st.rerun()
        if removal_columns[2].button("Clear all", width="stretch"):
            st.session_state["staff_absences"] = []
            st.session_state["coverage_assignments"] = {}
            clear_coverage_widgets()
            st.rerun()

    st.divider()
    st.subheader("Substitute coverage")
    covered_count = sum(
        need.id in coverage_assignments for need in coverage_needs
    )
    coverage_metrics = st.columns(4)
    coverage_metrics[0].metric("Active leave entries", len(active_absences))
    coverage_metrics[1].metric("Classes needing cover", len(coverage_needs))
    coverage_metrics[2].metric("Covered", covered_count)
    coverage_metrics[3].metric(
        "Open",
        max(len(coverage_needs) - covered_count, 0),
    )

    if not active_absences:
        st.info("Record temporary leave to check its effect on the timetable.")
    elif not coverage_needs:
        st.success("No scheduled classes are affected by the recorded leave.")
    else:
        if st.button(
            "Suggest best available cover",
            icon=":material/auto_awesome:",
        ):
            suggestions = propose_coverage_assignments(
                university,
                result,
                coverage_needs,
                active_absences,
            )
            clear_coverage_widgets()
            st.session_state["coverage_assignments"] = suggestions
            for need_id, substitute_id in suggestions.items():
                st.session_state[f"cover_{need_id}"] = substitute_id
            st.rerun()

        proposed_assignments = {}
        coverage_save_failed = False
        for need in coverage_needs:
            section = section_lookup[need.section_id]
            first_slot = slot_lookup[need.slot_ids[0]]
            last_slot = slot_lookup[need.slot_ids[-1]]
            st.markdown(
                f"**{section.code} · {section.title}**  \n"
                f"{first_slot.day}, {first_slot.start}-{last_slot.end} · "
                f"covering {staff_lookup[need.absent_staff_id]}"
            )
            candidates = eligible_substitutes(
                university,
                result,
                need,
                active_absences,
            )
            if not candidates:
                st.error("No qualified and conflict-free substitute is available.")
                continue
            saved = coverage_assignments.get(need.id, "")
            widget_key = f"cover_{need.id}"
            if saved in candidates and widget_key not in st.session_state:
                st.session_state[widget_key] = saved
            selected = st.selectbox(
                "Substitute",
                options=candidates,
                index=None,
                placeholder="Select substitute",
                format_func=lambda staff_id: (
                    f"{staff_lookup[staff_id]} · {staff_role_lookup[staff_id]}"
                ),
                key=widget_key,
            )
            if selected:
                proposed_assignments[need.id] = selected

        if st.button(
            "Save coverage plan",
            icon=":material/check_circle:",
            type="primary",
        ):
            coverage_violations = validate_coverage_assignments(
                university,
                result,
                coverage_needs,
                active_absences,
                proposed_assignments,
            )
            if coverage_violations:
                coverage_save_failed = True
                for violation in coverage_violations:
                    st.error(violation)
            else:
                st.session_state["coverage_assignments"] = proposed_assignments
                st.session_state["notice"] = "Substitute coverage plan saved"
                st.rerun()

        saved_coverage_violations = validate_coverage_assignments(
            university,
            result,
            coverage_needs,
            active_absences,
            coverage_assignments,
        )
        if (
            coverage_assignments
            and not saved_coverage_violations
            and not coverage_save_failed
        ):
            plan_df = pd.DataFrame(
                coverage_plan_records(
                    university,
                    coverage_needs,
                    coverage_assignments,
                )
            )
            st.success("Every affected class has valid substitute coverage.")
            st.dataframe(plan_df, hide_index=True, width="stretch")
            st.download_button(
                "Download coverage plan",
                data=csv_download(plan_df),
                file_name="substitute_coverage_plan.csv",
                mime="text/csv",
                icon=":material/download:",
            )

with resources_tab:
    utilization_df = pd.DataFrame(room_utilization(university, result))
    workload = workload_by_staff(result, university)
    workload_df = pd.DataFrame(
        [
            {
                "staff_member": member.name,
                "role": member.role,
                "schools": ", ".join(school_lookup[item] for item in member.school_ids),
                "scheduled_periods": workload.get(member.id, 0),
            }
            for member in university.staff
        ]
    )
    left, right = st.columns(2)
    with left:
        st.subheader("Room utilization")
        room_chart = (
            alt.Chart(utilization_df)
            .mark_bar(color="#0f766e")
            .encode(
                x=alt.X(
                    "utilization_pct:Q",
                    title="Utilization (%)",
                    scale=alt.Scale(domain=[0, 100]),
                ),
                y=alt.Y("room:N", title=None, sort="-x"),
                tooltip=["room:N", "occupied_periods:Q", "utilization_pct:Q"],
            )
        )
        st.altair_chart(room_chart, width="stretch")
        st.dataframe(utilization_df, hide_index=True, width="stretch")
    with right:
        st.subheader("Teaching workload")
        workload_chart = (
            alt.Chart(workload_df)
            .mark_bar(color="#c26631")
            .encode(
                x=alt.X("scheduled_periods:Q", title="Scheduled periods"),
                y=alt.Y("staff_member:N", title=None, sort="-x"),
                tooltip=["staff_member:N", "role:N", "scheduled_periods:Q"],
            )
        )
        st.altair_chart(workload_chart, width="stretch")
        st.dataframe(workload_df, hide_index=True, width="stretch")

with algorithm_tab:
    algorithm_metrics = st.columns(4)
    algorithm_metrics[0].metric("Conflict edges", result.conflict_edges)
    algorithm_metrics[1].metric("Graph density", f"{result.graph_density:.1%}")
    algorithm_metrics[2].metric("States explored", result.explored_states)
    algorithm_metrics[3].metric("Runtime", f"{result.elapsed_ms:.1f} ms")
    method_rows = [
        {"stage": "Conflict model", "method": "Adjacency-list graph"},
        {"stage": "Variable choice", "method": "Minimum Remaining Values"},
        {"stage": "Tie breaking", "method": "Conflict degree"},
        {"stage": "Search", "method": "Backtracking with early rejection"},
        {"stage": "Verification", "method": "Independent constraint pass"},
    ]
    st.dataframe(pd.DataFrame(method_rows), hide_index=True, width="stretch")
    st.subheader("Independent validation")
    if violations:
        for violation in violations:
            st.error(violation)
    else:
        st.success("No hard-constraint violations were detected.")
    st.caption(
        f"Backtracks: {result.backtracks:,} | "
        f"Search limit: {int(search_limit):,}"
    )

with config_tab:
    version = st.session_state["editor_version"]
    rows = editor_rows(raw_data)
    university_name = st.text_input(
        "University name",
        value=raw_data["university"],
        key=f"university_name_{version}",
    )
    room_features = sorted(
        {
            "accessibility",
            "computers",
            "gpu_workstations",
            "network_lab",
            "projector",
            "robotics_kits",
            "video_conference",
        }
        | {
            feature
            for row in rows["rooms"]
            for feature in row.get("features", [])
        }
    )
    subject_areas = sorted(
        {row["subject_area"] for row in rows["course_sections"]}
    )
    editor_tabs = st.tabs(
        ["Schools", "Cohorts", "Time slots", "Staff", "Rooms", "Courses"]
    )

    with editor_tabs[0]:
        schools_edit = st.data_editor(
            editor_dataframe(rows["schools"], ["id", "name", "code"]),
            num_rows="dynamic",
            hide_index=True,
            width="stretch",
            key=f"schools_{version}",
        )
    edited_school_ids = [
        value.strip()
        for value in schools_edit["id"].tolist()
        if isinstance(value, str) and value.strip()
    ]

    with editor_tabs[1]:
        cohorts_edit = st.data_editor(
            editor_dataframe(
                rows["cohorts"],
                ["id", "name", "school_id", "program", "size"],
            ),
            column_config={
                "school_id": st.column_config.SelectboxColumn(
                    "School",
                    options=edited_school_ids,
                    required=True,
                ),
                "size": st.column_config.NumberColumn(
                    "Students",
                    min_value=1,
                    step=1,
                    required=True,
                ),
            },
            num_rows="dynamic",
            hide_index=True,
            width="stretch",
            key=f"cohorts_{version}",
        )
    edited_cohort_ids = [
        value.strip()
        for value in cohorts_edit["id"].tolist()
        if isinstance(value, str) and value.strip()
    ]

    with editor_tabs[2]:
        slots_edit = st.data_editor(
            editor_dataframe(
                rows["time_slots"],
                ["id", "day", "period", "start", "end"],
            ),
            column_config={
                "day": st.column_config.SelectboxColumn(
                    "Day",
                    options=[
                        "Monday",
                        "Tuesday",
                        "Wednesday",
                        "Thursday",
                        "Friday",
                        "Saturday",
                    ],
                    required=True,
                ),
                "period": st.column_config.NumberColumn(
                    "Period",
                    min_value=1,
                    step=1,
                    required=True,
                ),
            },
            num_rows="dynamic",
            hide_index=True,
            width="stretch",
            key=f"slots_{version}",
        )
    edited_slot_ids = [
        value.strip()
        for value in slots_edit["id"].tolist()
        if isinstance(value, str) and value.strip()
    ]

    with editor_tabs[3]:
        staff_edit = st.data_editor(
            editor_dataframe(
                rows["staff"],
                [
                    "id",
                    "name",
                    "role",
                    "school_ids",
                    "qualified_subject_areas",
                    "available_slot_ids",
                ],
            ),
            column_config={
                "role": st.column_config.SelectboxColumn(
                    "Role",
                    options=[
                        "Professor",
                        "Associate Professor",
                        "Lecturer",
                        "Lab Mentor",
                    ],
                    required=True,
                ),
                "school_ids": st.column_config.MultiselectColumn(
                    "Schools",
                    options=edited_school_ids,
                    required=True,
                ),
                "qualified_subject_areas": st.column_config.MultiselectColumn(
                    "Qualified subjects",
                    options=subject_areas,
                ),
                "available_slot_ids": st.column_config.MultiselectColumn(
                    "Available periods",
                    options=edited_slot_ids,
                ),
            },
            num_rows="dynamic",
            hide_index=True,
            width="stretch",
            key=f"staff_{version}",
        )
    edited_staff_ids = [
        value.strip()
        for value in staff_edit["id"].tolist()
        if isinstance(value, str) and value.strip()
    ]

    with editor_tabs[4]:
        rooms_edit = st.data_editor(
            editor_dataframe(
                rows["rooms"],
                ["id", "name", "building", "capacity", "school_id", "features"],
            ),
            column_config={
                "capacity": st.column_config.NumberColumn(
                    "Capacity",
                    min_value=1,
                    step=1,
                    required=True,
                ),
                "school_id": st.column_config.SelectboxColumn(
                    "Home school",
                    options=edited_school_ids,
                ),
                "features": st.column_config.MultiselectColumn(
                    "Features",
                    options=room_features,
                ),
            },
            num_rows="dynamic",
            hide_index=True,
            width="stretch",
            key=f"rooms_{version}",
        )

    with editor_tabs[5]:
        courses_edit = st.data_editor(
            editor_dataframe(
                rows["course_sections"],
                [
                    "id",
                    "code",
                    "title",
                    "school_id",
                    "subject_area",
                    "program",
                    "cohort_ids",
                    "instructor_ids",
                    "meetings_per_week",
                    "duration_slots",
                    "expected_students",
                    "required_room_features",
                    "preferred_slot_ids",
                    "unavailable_slot_ids",
                ],
            ),
            column_config={
                "school_id": st.column_config.SelectboxColumn(
                    "School",
                    options=edited_school_ids,
                    required=True,
                ),
                "cohort_ids": st.column_config.MultiselectColumn(
                    "Cohorts",
                    options=edited_cohort_ids,
                    required=True,
                ),
                "instructor_ids": st.column_config.MultiselectColumn(
                    "Teaching staff",
                    options=edited_staff_ids,
                    required=True,
                ),
                "meetings_per_week": st.column_config.NumberColumn(
                    "Meetings/week",
                    min_value=1,
                    step=1,
                    required=True,
                ),
                "duration_slots": st.column_config.NumberColumn(
                    "Periods/meeting",
                    min_value=1,
                    step=1,
                    required=True,
                ),
                "expected_students": st.column_config.NumberColumn(
                    "Students",
                    min_value=1,
                    step=1,
                    required=True,
                ),
                "required_room_features": st.column_config.MultiselectColumn(
                    "Required room features",
                    options=room_features,
                ),
                "preferred_slot_ids": st.column_config.MultiselectColumn(
                    "Preferred periods",
                    options=edited_slot_ids,
                ),
                "unavailable_slot_ids": st.column_config.MultiselectColumn(
                    "Unavailable periods",
                    options=edited_slot_ids,
                ),
            },
            num_rows="dynamic",
            hide_index=True,
            width="stretch",
            key=f"courses_{version}",
        )

    action_columns = st.columns([1, 1, 3])
    apply_changes = action_columns[0].button(
        "Apply changes",
        icon=":material/check:",
        type="primary",
        width="stretch",
    )
    action_columns[1].download_button(
        "Export JSON",
        data=json.dumps(raw_data, indent=2),
        file_name="university_configuration.json",
        mime="application/json",
        icon=":material/download:",
        width="stretch",
    )

    if apply_changes:
        try:
            tables = {
                "schools": schools_edit.to_dict("records"),
                "cohorts": cohorts_edit.to_dict("records"),
                "staff": staff_edit.to_dict("records"),
                "rooms": rooms_edit.to_dict("records"),
                "time_slots": slots_edit.to_dict("records"),
                "course_sections": courses_edit.to_dict("records"),
            }
            candidate = configuration_from_editor(university_name, tables)
            activate_configuration(candidate, "Edited workspace")
            st.session_state["notice"] = "Configuration validated and applied"
            st.rerun()
        except (KeyError, TypeError, ValueError, UniversityDataError) as error:
            st.error(f"Changes were not applied: {error}")
