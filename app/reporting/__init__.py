"""app.reporting — standalone DOCX report generation package (v2.0)."""
from .docx_report import (
    build_report_docx,
    build_planning_docx,
    make_charts,
    ProjectMeta,
    KPI,
    TimeseriesRow,
    Insights,
)

__all__ = [
    "build_report_docx",
    "build_planning_docx",
    "make_charts",
    "ProjectMeta",
    "KPI",
    "TimeseriesRow",
    "Insights",
]
