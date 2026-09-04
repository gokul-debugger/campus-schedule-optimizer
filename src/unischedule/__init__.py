"""University-wide timetable optimization tools."""

from unischedule.io import load_university
from unischedule.scheduler import ScheduleResult, UniversityScheduler

__all__ = ["ScheduleResult", "UniversityScheduler", "load_university"]

