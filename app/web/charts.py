"""Charts data aggregation (vendored Chart.js)."""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.db import session_scope
from app.models import Lead


def charts_data() -> dict[str, Any]:
    with session_scope() as s:
        leads = s.query(Lead).all()
    by_day = Counter(str(lead.first_seen.date()) for lead in leads if lead.first_seen)
    by_source = Counter()
    by_flag = Counter()
    by_status = Counter(lead.status for lead in leads)
    by_city = Counter(lead.city for lead in leads if lead.city)
    by_category = Counter(lead.category for lead in leads if lead.category)
    for lead in leads:
        for source in (lead.maps or {}):
            by_source[source] += 1
        for flag, enabled in (lead.flags or {}).items():
            if enabled and isinstance(enabled, bool):
                by_flag[flag] += 1
    return {
        "leads_per_day": sorted(by_day.items()),
        "leads_per_source": by_source.most_common(),
        "leads_per_flag": by_flag.most_common(),
        "funnel": by_status.most_common(),
        "top_cities": by_city.most_common(10),
        "top_categories": by_category.most_common(10),
    }
