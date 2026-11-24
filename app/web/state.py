"""Shared web state (single runner for the app process)."""

from app.core.jobs import JobRunner

runner = JobRunner()
