"""Official legal research portals; portal links do not verify specific laws."""

from datetime import datetime, timezone
from functools import lru_cache
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


JURISDICTION_SOURCES = {
    "India": {
        "regions": ["India (national; state-specific rules may also matter)"],
        "sources": [
            {
                "name": "India Code",
                "url": "https://www.indiacode.nic.in/",
                "host": "www.indiacode.nic.in",
            }
        ],
    },
    "United Kingdom": {
        "regions": [
            "England and Wales",
            "Scotland",
            "Northern Ireland",
            "United Kingdom (specific legal system not identified)",
        ],
        "sources": [
            {
                "name": "legislation.gov.uk",
                "url": "https://www.legislation.gov.uk/",
                "host": "www.legislation.gov.uk",
            }
        ],
    },
    "Germany": {
        "regions": ["Germany (national law)", "European Union (where applicable)"],
        "sources": [
            {
                "name": "Gesetze im Internet",
                "url": "https://www.gesetze-im-internet.de/",
                "host": "www.gesetze-im-internet.de",
            },
            {
                "name": "EUR-Lex",
                "url": "https://eur-lex.europa.eu/",
                "host": "eur-lex.europa.eu",
            },
        ],
    },
    "United States of America": {
        "regions": [
            "United States federal law",
            "Relevant state law (state not identified unless stated)",
        ],
        "sources": [
            {
                "name": "United States Code",
                "url": "https://uscode.house.gov/",
                "host": "uscode.house.gov",
            },
            {
                "name": "Congress.gov",
                "url": "https://www.congress.gov/",
                "host": "www.congress.gov",
            },
        ],
    },
    "United Arab Emirates": {
        "regions": [
            "UAE mainland/federal and emirate law",
            "Dubai International Financial Centre (DIFC), if expressly relevant",
            "Abu Dhabi Global Market (ADGM), if expressly relevant",
        ],
        "sources": [
            {
                "name": "UAE Legislation",
                "url": "https://uaelegislation.gov.ae/",
                "host": "uaelegislation.gov.ae",
            },
            {
                "name": "DIFC Laws",
                "url": "https://www.difc.com/business/laws-and-regulations/legal-database",
                "host": "www.difc.com",
            },
            {
                "name": "ADGM Legislation",
                "url": "https://www.adgm.com/legal-framework/legislation",
                "host": "www.adgm.com",
            },
        ],
    },
    "Israel": {
        "regions": ["Israel (national law)"],
        "sources": [
            {
                "name": "Israeli Government",
                "url": "https://www.gov.il/en/departments/topics/legislation/govil-landing-page",
                "host": "www.gov.il",
            }
        ],
    },
    "China": {
        "regions": [
            "Mainland China",
            "Hong Kong (separate legal system)",
            "Macau (separate legal system)",
        ],
        "sources": [
            {
                "name": "National People's Congress of China",
                "url": "https://www.npc.gov.cn/",
                "host": "www.npc.gov.cn",
            }
        ],
    },
    "France": {
        "regions": ["France (national law)", "European Union (where applicable)"],
        "sources": [
            {
                "name": "Légifrance",
                "url": "https://www.legifrance.gouv.fr/",
                "host": "www.legifrance.gouv.fr",
            },
            {
                "name": "EUR-Lex",
                "url": "https://eur-lex.europa.eu/",
                "host": "eur-lex.europa.eu",
            },
        ],
    },
}


@lru_cache(maxsize=32)
def _check_portal(url: str):
    request = Request(url, headers={"User-Agent": "ContractIntelligence-LegalSourceCheck/1.0"})
    try:
        with urlopen(request, timeout=1.5) as response:
            return response.status < 400, datetime.now(timezone.utc).isoformat()
    except (TimeoutError, URLError, OSError):
        return False, datetime.now(timezone.utc).isoformat()


def legal_sources_for(jurisdictions, live_check=False):
    """Return official research portals without asserting that a law was verified."""
    results = []
    for jurisdiction in jurisdictions:
        entry = JURISDICTION_SOURCES.get(jurisdiction)
        if not entry:
            continue
        sources = []
        for index, source in enumerate(entry["sources"]):
            allowed = source["host"] in {
                urlsplit(item["url"]).hostname
                for configured in JURISDICTION_SOURCES.values()
                for item in configured["sources"]
            }
            if not allowed:
                continue
            source_status = "not_checked"
            checked_at = None
            if live_check and index == 0:
                reachable, checked_at = _check_portal(source["url"])
                source_status = (
                    "portal_reachable_provision_not_verified"
                    if reachable
                    else "portal_unavailable_provision_not_verified"
                )
            sources.append(
                {
                    "name": source["name"],
                    "url": source["url"],
                    "verification_status": source_status,
                    "checked_at": checked_at,
                    "provision_verified": False,
                }
            )
        results.append(
            {
                "jurisdiction": jurisdiction,
                "regions": entry["regions"],
                "sources": sources,
            }
        )
    return results
