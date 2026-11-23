"""ORM models per SPEC section 2."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


LEAD_STATUSES = ("new", "in_base", "contacted", "waiting_reply", "replied", "deal", "rejected")
JOB_STATUSES = ("queued", "running", "paused", "needs_human", "done", "failed", "stopped")
PAIR_STATUSES = ("pending", "running", "done", "failed", "skipped")
MESSAGE_CHANNELS = ("whatsapp", "telegram", "instagram", "viber", "call", "email")
SOCIAL_KEYS = ("instagram", "telegram", "whatsapp", "viber", "vk", "facebook", "youtube")


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dedupe_key: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(500), default="")
    category: Mapped[str] = mapped_column(String(300), default="")
    address: Mapped[str] = mapped_column(String(500), default="")
    city: Mapped[str] = mapped_column(String(200), default="", index=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    phones: Mapped[list] = mapped_column(JSON, default=list)
    emails: Mapped[list] = mapped_column(JSON, default=list)
    website: Mapped[str] = mapped_column(String(1000), default="")
    socials: Mapped[dict] = mapped_column(JSON, default=dict)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    reviews_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    hours: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    attributes: Mapped[list] = mapped_column(JSON, default=list)
    price_range: Mapped[str] = mapped_column(String(100), default="")
    plus_code: Mapped[str] = mapped_column(String(100), default="")
    photos_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    top_reviews: Mapped[list] = mapped_column(JSON, default=list)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)
    maps: Mapped[dict] = mapped_column(JSON, default=dict)
    flags: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="new", index=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)

    messages: Mapped[list[Message]] = relationship(back_populates="lead", cascade="all, delete-orphan")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "dedupe_key": self.dedupe_key,
            "name": self.name,
            "category": self.category,
            "address": self.address,
            "city": self.city,
            "lat": self.lat,
            "lon": self.lon,
            "phones": self.phones or [],
            "emails": self.emails or [],
            "website": self.website,
            "socials": self.socials or {},
            "rating": self.rating,
            "reviews_count": self.reviews_count,
            "description": self.description,
            "hours": self.hours,
            "attributes": self.attributes or [],
            "price_range": self.price_range,
            "plus_code": self.plus_code,
            "photos_count": self.photos_count,
            "top_reviews": self.top_reviews or [],
            "extra": self.extra or {},
            "maps": self.maps or {},
            "flags": self.flags or {},
            "status": self.status,
            "notes": self.notes,
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "job_id": self.job_id,
        }


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    counters: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    pairs: Mapped[list[JobPair]] = relationship(back_populates="job", cascade="all, delete-orphan")


class JobPair(Base):
    __tablename__ = "job_pairs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    city: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(300))
    source: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), default="pending")
    found: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    job: Mapped[Job] = relationship(back_populates="pairs")


class PairHistory(Base):
    __tablename__ = "pair_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    city: Mapped[str] = mapped_column(String(200), index=True)
    category: Mapped[str] = mapped_column(String(300))
    source: Mapped[str] = mapped_column(String(30))
    searched_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True)
    channel: Mapped[str] = mapped_column(String(30))
    direction: Mapped[str] = mapped_column(String(10), default="out")
    text: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    lead: Mapped[Lead] = relationship(back_populates="messages")


class Template(Base):
    __tablename__ = "templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    channel: Mapped[str] = mapped_column(String(30), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    for_flag: Mapped[str] = mapped_column(String(50), default="")


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON, default=None)
