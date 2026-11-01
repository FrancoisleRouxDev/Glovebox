"""Look up a car on Wikipedia and return the page summary.

Two public endpoints, no API key needed:
1. MediaWiki search API, to find candidate page titles for "<make> <model>".
2. REST summary API, to get the intro text and canonical URL for a title.

The summaries come straight from Wikipedia, so the app never shows AI-written
"facts" here. Grounding an AI answer on these summaries can be added later.
"""

import logging
import re
from urllib.parse import quote

import httpx

from app.schemas import FactsResponse

logger = logging.getLogger(__name__)

SEARCH_URL = "https://en.wikipedia.org/w/api.php"
SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
SEARCH_LIMIT = 5
MAX_SUMMARIES_TO_TRY = 3


class FactsUnavailableError(Exception):
    """Wikipedia couldn't be reached or returned an error."""


def _normalise(text: str) -> str:
    """Lower-case and drop everything except letters and digits ("MX-5" -> "mx5")."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def rank_titles(titles: list[str], make: str, model: str) -> list[str]:
    """Put titles that mention both the make and the model first, keeping search order otherwise."""
    make_n, model_n = _normalise(make), _normalise(model)

    def score(title: str) -> int:
        t = _normalise(title)
        return int(make_n in t) + int(model_n in t)

    # sorted() is stable, so equal scores keep Wikipedia's relevance order.
    return sorted(titles, key=score, reverse=True)


async def fetch_car_facts(client: httpx.AsyncClient, make: str, model: str) -> FactsResponse | None:
    """Return the best matching Wikipedia summary, or None if nothing suitable exists."""
    try:
        search = await client.get(
            SEARCH_URL,
            params={
                "action": "query",
                "list": "search",
                "srsearch": f"{make} {model}",
                "srlimit": SEARCH_LIMIT,
                "format": "json",
                "formatversion": 2,
            },
        )
        search.raise_for_status()
        hits = search.json().get("query", {}).get("search", [])
        titles = rank_titles([h["title"] for h in hits], make, model)

        for title in titles[:MAX_SUMMARIES_TO_TRY]:
            resp = await client.get(SUMMARY_URL.format(title=quote(title.replace(" ", "_"), safe="")))
            if resp.status_code == 404:
                continue
            resp.raise_for_status()
            page = resp.json()
            # Skip disambiguation pages ("Mustang may refer to...") and empty extracts.
            if page.get("type") != "standard" or not page.get("extract"):
                continue
            return FactsResponse(
                title=page["title"],
                summary=page["extract"],
                source_url=page["content_urls"]["desktop"]["page"],
                thumbnail_url=(page.get("thumbnail") or {}).get("source"),
            )
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        logger.warning("wikipedia lookup failed for %r %r: %s", make, model, exc)
        raise FactsUnavailableError(str(exc)) from exc

    return None
