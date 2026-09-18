"""University-wide timetable optimization tools."""

from unischedule.io import load_university
from unischedule.quality import ScheduleQuality, evaluate_schedule_quality
from unischedule.scheduler import ScheduleResult, UniversityScheduler

__all__ = [
    "ScheduleQuality",
    "ScheduleResult",
    "UniversityScheduler",
    "evaluate_schedule_quality",
    "load_university",
]
