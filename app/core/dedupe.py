"""Dedupe and merge of scraped leads (SPEC 5)."""

from __future__ import annotations

import hashlib
from typing import Any

from rapidfuzz.fuzz import token_set_ratio

from app.core.normalize import normalize_name, normalize_phone
from app.models import Lead
from app.scrapers.base import RawPlace, distance_m


def dedupe_key_for(place: RawPlace, phone_region: str = "RU") -> str:
    for raw in place.phones:
        phone = normalize_phone(raw, phone_region)
        if phone:
            return "tel:" + phone
    name_norm = normalize_name(place.name)
    lat = round(place.lat or 0, 3)
    lon = round(place.lon or 0, 3)
    digest = hashlib.sha1(f"{name_norm}|{lat}|{lon}".encode()).hexdigest()
    return "geo:" + digest


def is_same_lead(a: RawPlace, b: RawPlace, phone_region: str = "RU") -> bool:
    phones_a = {normalize_phone(p, phone_region) for p in a.phones if normalize_phone(p, phone_region)}
    phones_b = {normalize_phone(p, phone_region) for p in b.phones if normalize_phone(p, phone_region)}
    if phones_a & phones_b:
        return True
    if a.lat is None or a.lon is None or b.lat is None or b.lon is None:
        return False
    score = token_set_ratio(normalize_name(a.name), normalize_name(b.name))
    if score < 90:
        return False
    return distance_m(a.lat, a.lon, b.lat, b.lon) <= 150


def merge_places(places: list[RawPlace], phone_region: str = "RU") -> list[dict[str, Any]]:
    """Merge a list of RawPlace into lead dictionaries."""
    merged: list[dict[str, Any]] = []
    for place in places:
        target = None
        for candidate in merged:
            probe = RawPlace(**{k: v for k, v in candidate.items() if k in RawPlace.model_fields})
            if is_same_lead(probe, place, phone_region):
                target = candidate
                break
        if target is None:
            target = _to_lead_dict(place, phone_region)
            merged.append(target)
        else:
            _merge_into(target, place, phone_region)
    return merged


def _to_lead_dict(place: RawPlace, phone_region: str) -> dict[str, Any]:
    phones = [p for raw in place.phones if (p := normalize_phone(raw, phone_region))]
    maps: dict[str, Any] = {}
    if place.source and place.source_id:
        maps[place.source] = {"id": place.source_id, "url": place.url or ""}
    return {
        "dedupe_key": dedupe_key_for(place, phone_region),
        "name": place.name,
        "category": place.category,
        "address": place.address,
        "city": place.city if hasattr(place, "city") else "",
        "lat": place.lat,
        "lon": place.lon,
        "phones": phones,
        "emails": list(place.emails),
        "website": place.website,
        "socials": dict(place.socials),
        "rating": place.rating,
        "reviews_count": place.reviews_count or 0,
        "description": place.description,
        "hours": dict(place.hours),
        "attributes": list(place.attributes),
        "price_range": place.price_range,
        "plus_code": place.plus_code,
        "photos_count": place.photos_count,
        "top_reviews": list(place.top_reviews),
        "extra": dict(place.extra),
        "maps": maps,
        "flags": {},
        "status": "new",
        "notes": "",
    }


def _merge_into(target: dict[str, Any], place: RawPlace, phone_region: str) -> None:
    for raw in place.phones:
        phone = normalize_phone(raw, phone_region)
        if phone and phone not in target["phones"]:
            target["phones"].append(phone)
    for email in place.emails:
        if email and email not in target["emails"]:
            target["emails"].append(email)
    for key, value in place.socials.items():
        if value and not target["socials"].get(key):
            target["socials"][key] = value
    for field in ("name", "category", "address", "city", "lat", "lon", "website", "description", "price_range", "plus_code"):
        if not target.get(field) and getattr(place, field, None):
            target[field] = getattr(place, field)
    if place.photos_count and not target.get("photos_count"):
        target["photos_count"] = place.photos_count
    for h, v in place.hours.items():
        target.setdefault("hours", {}).setdefault(h, v)
    for a in place.attributes:
        if a not in target["attributes"]:
            target["attributes"].append(a)
    if place.top_reviews and len(target.get("top_reviews", [])) < 5:
        target.setdefault("top_reviews", []).extend(place.top_reviews[: 5 - len(target.get("top_reviews", []))])
    target.setdefault("extra", {}).update(place.extra or {})
    if place.source and place.source_id:
        target.setdefault("maps", {})[place.source] = {"id": place.source_id, "url": place.url or ""}
    if (place.reviews_count or 0) > (target.get("reviews_count") or 0):
        target["rating"] = place.rating
        target["reviews_count"] = place.reviews_count or 0
    if not target["dedupe_key"].startswith("tel:") and place.phones:
        phone = normalize_phone(place.phones[0], phone_region)
        if phone:
            target["dedupe_key"] = "tel:" + phone


def upsert_lead(session, data: dict[str, Any], job_id: int | None = None) -> Lead:
    lead = session.query(Lead).filter_by(dedupe_key=data["dedupe_key"]).one_or_none()
    if lead is None:
        lead = Lead(**{k: v for k, v in data.items() if hasattr(Lead, k)})
        lead.job_id = job_id
        session.add(lead)
        session.flush()
    else:
        merged_dict = {k: getattr(lead, k) for k in data}
        from app.core.normalize import normalize_phone

        for raw_phone in data.get("phones", []):
            phone = normalize_phone(raw_phone)
            if phone and phone not in merged_dict.get("phones", []):
                merged_dict.setdefault("phones", []).append(phone)
        for email in data.get("emails", []):
            if email and email not in merged_dict.get("emails", []):
                merged_dict.setdefault("emails", []).append(email)
        for key, value in (data.get("socials") or {}).items():
            if value and not merged_dict.get("socials", {}).get(key):
                merged_dict.setdefault("socials", {})[key] = value
        _merge_into(merged_dict, RawPlace(
                source="google",
                name=data.get("name", ""),
                phones=data.get("phones", []),
                website=data.get("website", ""),
                socials=data.get("socials", {}),
                emails=data.get("emails", []),
                lat=data.get("lat"),
                lon=data.get("lon"),
                category=data.get("category", ""),
                address=data.get("address", ""),
                rating=data.get("rating"),
                reviews_count=data.get("reviews_count"),
                hours=data.get("hours") or {},
                attributes=data.get("attributes") or [],
                top_reviews=data.get("top_reviews") or [],
                extra=data.get("extra") or {},
            ),
            phone_region="RU",
        )
        for key, value in data.items():
            if key in ("dedupe_key", "maps", "flags", "status"):
                continue
            if hasattr(lead, key) and (value or not getattr(lead, key, None)):
                setattr(lead, key, value)
        existing_maps = dict(lead.maps or {})
        existing_maps.update(data.get("maps") or {})
        lead.maps = existing_maps
        if job_id and not lead.job_id:
            lead.job_id = job_id
    session.flush()
    return lead
