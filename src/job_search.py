"""Job search via Adzuna API."""
import logging
from typing import Any

import httpx

from src.config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://api.adzuna.com/v1/api/jobs"
RESULTS_PER_PAGE = 20


def search_jobs(
    query: str | None = None,
    location: str | None = None,
    page: int = 1,
    results_per_page: int = RESULTS_PER_PAGE,
) -> list[dict[str, Any]]:
    """
    Search jobs using Adzuna API.

    Args:
        query: Job title or keyword (what).
        location: Location filter (where).
        page: 1-based page number.
        results_per_page: Max results per page (API default 20).

    Returns:
        List of search result dicts with keys: title, company, location, url,
        description, created, salary_min, salary_max, contract_type.
    """
    if not settings.adzuna_app_id or not settings.adzuna_app_key:
        raise ValueError(
            "Adzuna API not configured. Set ADZUNA_APP_ID and ADZUNA_APP_KEY in .env"
        )
    country = (settings.adzuna_country or "gb").lower()
    url = f"{BASE_URL}/{country}/search/{page}"
    params: dict[str, Any] = {
        "app_id": settings.adzuna_app_id,
        "app_key": settings.adzuna_app_key,
        "results_per_page": min(results_per_page, 50),
    }
    if query and query.strip():
        params["what"] = query.strip()
    if location and location.strip():
        params["where"] = location.strip()

    logger.info("job_search: GET %s params=%s", url, {k: v for k, v in params.items() if k not in ("app_id", "app_key")})
    with httpx.Client(timeout=30) as client:
        resp = client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    results = data.get("results") or []
    out: list[dict[str, Any]] = []
    for r in results:
        company = r.get("company") or {}
        loc = r.get("location") or {}
        out.append({
            "title": r.get("title") or "",
            "company": company.get("display_name", ""),
            "location": loc.get("display_name", ""),
            "url": r.get("redirect_url") or r.get("url", ""),
            "description": (r.get("description") or "")[:500],
            "created": r.get("created"),
            "salary_min": r.get("salary_min"),
            "salary_max": r.get("salary_max"),
            "contract_type": r.get("contract_type"),
        })
    logger.info("job_search: got %d results", len(out))
    return out
