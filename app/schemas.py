"""Pydantic schemas shared between layers (RawPlace lives in scrapers.base)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class JobParams(BaseModel):
    country: str = "Россия"
    cities: list[str] = Field(default_factory=lambda: ["Саратов"])
    categories: list[str] = Field(default_factory=lambda: ["барбершоп"])
    sources: list[str] = Field(default_factory=lambda: ["google", "yandex", "twogis"])
    max_results_per_pair: int = 60
    max_minutes: int = 60
    skip_days: int = 14
    no_repeat: bool = True
    force: bool = False
    enrich: bool = True


class EstimateOut(BaseModel):
    pairs_total: int
    pairs_skipped: int
    pairs_to_run: int
    approx_minutes: float


class LeadOut(BaseModel):
    id: int
    name: str = ""
    category: str = ""
    address: str = ""
    city: str = ""
    lat: float | None = None
    lon: float | None = None
    phones: list[str] = Field(default_factory=list)
    emails: list[str] = Field(default_factory=list)
    website: str = ""
    socials: dict[str, Any] = Field(default_factory=dict)
    rating: float | None = None
    reviews_count: int | None = None
    flags: dict[str, Any] = Field(default_factory=dict)
    status: str = "new"
    maps: dict[str, Any] = Field(default_factory=dict)
