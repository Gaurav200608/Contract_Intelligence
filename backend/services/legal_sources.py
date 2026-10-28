"""Metadata for authoritative legal sources and their declared coverage."""

from datetime import datetime, timezone
from functools import lru_cache
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def _source(
    source_id,
    organization,
    jurisdiction,
    base_url,
    retrieval_method,
    document_types,
    subject_areas,
    query_methods,
    coverage,
    text_coverage,
    connector_status="manual_access_required",
    api_docs_url=None,
):
    return {
        "source_id": source_id,
        "organization": organization,
        "jurisdiction": jurisdiction,
        "base_url": base_url,
        "url": base_url,
        "retrieval_method": retrieval_method,
        "api_docs_url": api_docs_url,
        "supported_document_types": document_types,
        "supported_subject_areas": subject_areas,
        "supported_query_methods": query_methods,
        "coverage_limitations": coverage,
        "text_coverage": text_coverage,
        "connector_status": connector_status,
    }


SOURCE_REGISTRY = {
    "us_ecfr": _source(
        "us_ecfr",
        "Office of the Federal Register / National Archives",
        "United States — federal",
        "https://www.ecfr.gov/",
        "Official JSON search API and versioned full-text XML API",
        ["codified federal regulation"],
        ["federal regulatory requirements"],
        ["full-text query", "title/part/section identifier", "version-date retrieval"],
        "Federal regulations only; not the United States Code, state law, agency guidance, or case law. Search matches are candidates, not an applicability determination.",
        "Current consolidated eCFR text with version-date retrieval; historical versions are available through the official versioner API.",
        "operational",
        "https://www.ecfr.gov/developers/documentation/api/v1",
    ),
    "us_code": _source(
        "us_code",
        "Office of the Law Revision Counsel, U.S. House of Representatives",
        "United States — federal",
        "https://uscode.house.gov/",
        "Official release-point page and title-specific USLM XML ZIP downloads",
        ["federal statute", "United States Code"],
        ["federal legislation"],
        ["exact title/section citation lookup", "release-point retrieval"],
        "Exact U.S.C. citations in contract text can be retrieved; no general full-corpus search or state-law retrieval is implemented.",
        "On-demand current release-point title XML; historical-edition selection and provision-level currentness are not implemented.",
        "operational",
    ),
    "us_state_law": _source(
        "us_state_law",
        "Official state legislature and code portals",
        "United States — state and territorial",
        "https://www.usa.gov/state-governments",
        "Manual access through the official legislature/code portal for the identified state",
        ["state statute", "state regulation"],
        ["state legislation and regulations"],
        ["state selection", "official portal search", "citation lookup (manual)"],
        "No state-specific connector or complete state-portal directory is implemented; state law is not inferred from federal law.",
        "Depends on the official state publisher; not retrieved by this app.",
    ),
    "canada_federal": _source(
        "canada_federal",
        "Department of Justice Canada",
        "Canada — federal",
        "https://laws-lois.justice.gc.ca/",
        "Official Justice Laws website and published formats; app connector not implemented",
        ["act", "regulation"],
        ["federal legislation and regulations"],
        ["title search", "citation lookup", "official portal (manual)"],
        "Federal texts only; this app does not retrieve individual provisions or determine federal applicability.",
        "Consolidated federal statutes and regulations are available from the source; historical-version handling is not integrated.",
    ),
    "canada_provincial": _source(
        "canada_provincial",
        "Official provincial and territorial publishers",
        "Canada — provincial and territorial",
        "https://www.canada.ca/en/government/system/laws.html",
        "Manual access through the official publisher for the identified province or territory",
        ["provincial/territorial act", "regulation"],
        ["provincial and territorial legislation"],
        ["province/territory selection", "official portal search", "citation lookup (manual)"],
        "No province/territory connector or complete publisher directory is implemented.",
        "Depends on the publisher; not retrieved by this app.",
    ),
    "uk_legislation": _source(
        "uk_legislation",
        "The National Archives",
        "United Kingdom — England and Wales, Scotland, Northern Ireland, or UK-wide",
        "https://www.legislation.gov.uk/",
        "Official legislation portal; XML/RDF representations exist, but the app connector is not implemented",
        ["act", "statutory instrument", "measure", "uk legislation"],
        ["UK legislation"],
        ["title search", "citation lookup", "official XML/RDF formats (manual)"],
        "Territorial extent, commencement, amendments, and devolved legal system must be checked for each instrument. Automated retrieval is not enabled.",
        "The site provides revised and as-enacted material; this app does not retrieve or verify a version.",
        api_docs_url="https://www.legislation.gov.uk/developer",
    ),
    "germany_federal": _source(
        "germany_federal",
        "Federal Ministry of Justice / Federal Office of Justice",
        "Germany — federal",
        "https://www.gesetze-im-internet.de/",
        "Official federal legislation portal; app connector not implemented",
        ["federal act", "ordinance"],
        ["German federal legislation"],
        ["title search", "citation lookup", "official portal (manual)"],
        "Federal legislation only; state law and EU law are separate. The app does not retrieve texts.",
        "Consolidated federal texts are published; historical version coverage is not integrated.",
    ),
    "eu_lex": _source(
        "eu_lex",
        "Publications Office of the European Union",
        "European Union",
        "https://eur-lex.europa.eu/",
        "Official EUR-Lex portal; app API/Cellar connector not implemented",
        ["treaty", "regulation", "directive", "decision", "judgment", "recommendation"],
        ["EU legislation, treaties, case law, and related materials"],
        ["CELEX identifier", "title/search query", "document type and date filters (manual)"],
        "EU instruments have different effects; directives, judgments, and recommendations are not interchangeable. Application to a contract requires scope and national-law analysis.",
        "Original and consolidated documents are published; no version is retrieved or checked by this app.",
        api_docs_url="https://eur-lex.europa.eu/content/help/data-reuse/reuse-contents-eurlex-details.html",
    ),
    "uae_federal": _source(
        "uae_federal",
        "UAE Government",
        "United Arab Emirates — federal",
        "https://uaelegislation.gov.ae/",
        "Official legislation portal; app connector not implemented",
        ["federal decree-law", "law", "regulation"],
        ["UAE federal legislation"],
        ["title/citation search (manual)"],
        "Does not cover emirate-specific, DIFC, or ADGM law; language/version must be confirmed.",
        "Portal publication/version information is not automatically retrieved.",
    ),
    "uae_emirate": _source(
        "uae_emirate",
        "Official UAE emirate authorities",
        "United Arab Emirates — emirate",
        "https://u.ae/en/about-the-uae/the-seven-emirates",
        "Manual access through the relevant emirate's official portal",
        ["emirate law", "local regulation"],
        ["emirate-level legislation"],
        ["emirate selection", "official portal search (manual)"],
        "No emirate-level connector or portal directory is implemented.",
        "Not retrieved by this app.",
    ),
    "uae_difc": _source(
        "uae_difc",
        "Dubai International Financial Centre",
        "United Arab Emirates — DIFC",
        "https://www.difc.com/business/laws-and-regulations/legal-database",
        "Official DIFC legal database; app connector not implemented",
        ["DIFC law", "DIFC regulation", "consultation material"],
        ["DIFC laws and regulatory materials"],
        ["title/citation search (manual)"],
        "DIFC is a distinct legal framework and must not be conflated with UAE federal or Dubai mainland law.",
        "Current and historical versions are not retrieved by this app.",
    ),
    "uae_adgm": _source(
        "uae_adgm",
        "Abu Dhabi Global Market",
        "United Arab Emirates — ADGM",
        "https://www.adgm.com/legal-framework/legislation",
        "Official ADGM legislation portal; app connector not implemented",
        ["ADGM regulation", "ADGM rules"],
        ["ADGM legal framework"],
        ["title/citation search (manual)"],
        "ADGM's legal framework is distinct from other UAE legal systems; no connector is implemented.",
        "Not retrieved by this app.",
    ),
    "israel_legislation": _source(
        "israel_legislation",
        "Israeli Government",
        "Israel",
        "https://www.gov.il/en/departments/topics/legislation/govil-landing-page",
        "Official government legislation information; app connector not implemented",
        ["primary legislation", "regulation", "official material"],
        ["Israeli legislation and government regulatory materials"],
        ["portal search and citation lookup (manual)"],
        "No authoritative legislation search/retrieval connector is implemented; language and version require confirmation.",
        "Not retrieved by this app.",
    ),
    "china_mainland": _source(
        "china_mainland",
        "National People's Congress of China",
        "China — mainland",
        "https://www.npc.gov.cn/",
        "Official NPC portal; app connector not implemented",
        ["law", "national legislation"],
        ["Mainland China national legislation"],
        ["title/citation search (manual)"],
        "Does not cover Hong Kong or Macau, which have separate legal systems. No official-source retrieval is implemented.",
        "Not retrieved by this app; source language and translation status require review.",
    ),
    "china_hong_kong": _source(
        "china_hong_kong",
        "Hong Kong e-Legislation",
        "Hong Kong",
        "https://www.elegislation.gov.hk/",
        "Official Hong Kong legislation portal; app connector not implemented",
        ["ordinance", "subsidiary legislation"],
        ["Hong Kong legislation"],
        ["title/citation search (manual)"],
        "Separate legal system from mainland China and Macau; not retrieved by this app.",
        "Portal versions are not automatically retrieved.",
    ),
    "china_macau": _source(
        "china_macau",
        "Macao SAR Government",
        "Macau",
        "https://bo.io.gov.mo/",
        "Official Macao Gazette portal; app connector not implemented",
        ["law", "administrative regulation"],
        ["Macau legislation"],
        ["gazette/title/citation search (manual)"],
        "Separate legal system from mainland China and Hong Kong; not retrieved by this app.",
        "Portal versions are not automatically retrieved; language requires confirmation.",
    ),
    "india_central": _source(
        "india_central",
        "Legislative Department, Ministry of Law and Justice",
        "India — central",
        "https://www.indiacode.nic.in/",
        "Official India Code portal; app connector not implemented",
        ["central act", "central legislation"],
        ["Indian central legislation"],
        ["title/citation search (manual)"],
        "Central legislation only; rules, notifications, and state law may be separate. No text retrieval is integrated.",
        "Portal consolidation/version status is not automatically checked.",
    ),
    "india_state": _source(
        "india_state",
        "Official state and union-territory publishers",
        "India — state and union territory",
        "https://legislative.gov.in/",
        "Manual access through the relevant state/UT official publisher",
        ["state act", "state rule", "notification"],
        ["Indian state and union-territory law"],
        ["state/UT selection", "official portal search (manual)"],
        "No complete state/UT registry or connector is implemented.",
        "Not retrieved by this app.",
    ),
    "italy_normattiva": _source(
        "italy_normattiva",
        "Italian Government",
        "Italy",
        "https://www.normattiva.it/",
        "Official Normattiva portal; app connector not implemented",
        ["law", "decree", "regulation"],
        ["Italian national legislation"],
        ["title/citation search (manual)"],
        "National law only; EU instruments and regional law are separate. No individual document retrieval is integrated.",
        "Portal provides consolidated versions; historical version retrieval is not integrated.",
    ),
    "wto": _source(
        "wto",
        "World Trade Organization",
        "World Trade Organization",
        "https://www.wto.org/",
        "Official WTO agreements, member information, and dispute-settlement portals; app connector not implemented",
        ["agreement", "member schedule/commitment", "dispute report", "decision"],
        ["international trade"],
        ["agreement/case/member search (manual)"],
        "WTO agreements bind members under international law and do not automatically create direct obligations between private contract parties.",
        "No treaty-status, member-commitment, or dispute-material retrieval is integrated.",
    ),
    "uncitral": _source(
        "uncitral",
        "United Nations Commission on International Trade Law",
        "United Nations / UNCITRAL",
        "https://uncitral.un.org/",
        "Official UNCITRAL instruments and status pages; app connector not implemented",
        ["convention", "model law", "rules", "guide"],
        ["international trade law"],
        ["instrument/country-status lookup (manual)"],
        "Model laws and recommendations are not domestic law unless enacted; treaty effect depends on state status and scope.",
        "No instrument text or enactment/status data is retrieved by this app.",
    ),
    "un_treaties": _source(
        "un_treaties",
        "United Nations Treaty Collection",
        "United Nations",
        "https://treaties.un.org/",
        "Official treaty text and status portal; app connector not implemented",
        ["treaty", "protocol", "declaration", "status record"],
        ["multilateral treaties"],
        ["treaty title/volume/participant/status search (manual)"],
        "Signature, ratification, entry into force, reservations, and territorial application require instrument- and state-specific checks.",
        "No treaty text or status is retrieved or evaluated by this app.",
    ),
    "france_legislation": _source(
        "france_legislation",
        "Direction de l'information légale et administrative",
        "France",
        "https://www.legifrance.gouv.fr/",
        "Official Légifrance portal; app connector not implemented",
        ["code", "law", "decree", "decision"],
        ["French national law"],
        ["title/citation search (manual)"],
        "National law only; EU law is separate. No text retrieval is integrated.",
        "Consolidated and historical materials are available at the portal; not retrieved by this app.",
    ),
    "oecd": _source(
        "oecd",
        "Organisation for Economic Co-operation and Development",
        "OECD",
        "https://www.oecd.org/",
        "Extensible registry entry; no connector",
        ["recommendation", "guideline", "convention", "report"],
        ["international economic policy"],
        ["document/country search (manual)"],
        "Recommendations and guidance are generally non-binding; legal status must be checked.",
        "Not retrieved by this app.",
    ),
    "wipo": _source(
        "wipo",
        "World Intellectual Property Organization",
        "WIPO",
        "https://www.wipo.int/",
        "Extensible registry entry; no connector",
        ["treaty", "model law", "guidance", "member status"],
        ["intellectual property"],
        ["treaty/country status and document search (manual)"],
        "Treaty obligations depend on parties, ratification, scope, and implementation; no connector.",
        "Not retrieved by this app.",
    ),
    "ilo": _source(
        "ilo",
        "International Labour Organization",
        "ILO",
        "https://www.ilo.org/",
        "Extensible registry entry; no connector",
        ["convention", "recommendation", "decision", "guidance"],
        ["international labour standards"],
        ["instrument/country ratification search (manual)"],
        "Recommendations are not conventions; treaty obligations and domestic effect depend on ratification and implementation.",
        "Not retrieved by this app.",
    ),
    "hcch": _source(
        "hcch",
        "Hague Conference on Private International Law",
        "HCCH",
        "https://www.hcch.net/",
        "Extensible registry entry; no connector",
        ["convention", "protocol", "status table", "guide"],
        ["private international law"],
        ["instrument/country status search (manual)"],
        "Treaty status, declarations, reservations, and state implementation require instrument-specific review.",
        "Not retrieved by this app.",
    ),
}


JURISDICTION_SOURCES = {
    "United States of America": {
        "regions": ["United States federal law", "Relevant state or territorial law"],
        "source_ids": ["us_ecfr", "us_code", "us_state_law"],
    },
    "Canada": {
        "regions": ["Canada federal law", "Relevant province or territory"],
        "source_ids": ["canada_federal", "canada_provincial"],
    },
    "United Kingdom": {
        "regions": ["England and Wales", "Scotland", "Northern Ireland", "UK-wide legislation"],
        "source_ids": ["uk_legislation"],
    },
    "Germany": {
        "regions": ["Germany (federal law)", "European Union (where separately relevant)"],
        "source_ids": ["germany_federal", "eu_lex"],
    },
    "United Arab Emirates": {
        "regions": ["UAE federal and emirate law", "DIFC", "ADGM"],
        "source_ids": ["uae_federal", "uae_emirate", "uae_difc", "uae_adgm"],
    },
    "Israel": {
        "regions": ["Israel (national law)"],
        "source_ids": ["israel_legislation"],
    },
    "China": {
        "regions": ["Mainland China", "Hong Kong (separate legal system)", "Macau (separate legal system)"],
        "source_ids": ["china_mainland", "china_hong_kong", "china_macau"],
    },
    "India": {
        "regions": ["India (central law)", "Relevant state or union territory"],
        "source_ids": ["india_central", "india_state"],
    },
    "Italy": {
        "regions": ["Italy (national law)", "European Union (where separately relevant)"],
        "source_ids": ["italy_normattiva", "eu_lex"],
    },
    "European Union": {
        "regions": ["European Union instruments and case law"],
        "source_ids": ["eu_lex"],
    },
    "World Trade Organization": {
        "regions": ["WTO member obligations and dispute-settlement materials"],
        "source_ids": ["wto"],
    },
    "UNCITRAL": {
        "regions": ["UNCITRAL instruments and model laws"],
        "source_ids": ["uncitral"],
    },
    "United Nations": {
        "regions": ["United Nations Treaty Collection"],
        "source_ids": ["un_treaties"],
    },
    "France": {
        "regions": ["France (national law)", "European Union (where separately relevant)"],
        "source_ids": ["france_legislation", "eu_lex"],
    },
    "OECD": {
        "regions": ["OECD instruments and recommendations"],
        "source_ids": ["oecd"],
    },
    "WIPO": {
        "regions": ["WIPO treaties, member status, and materials"],
        "source_ids": ["wipo"],
    },
    "ILO": {
        "regions": ["ILO conventions, recommendations, and materials"],
        "source_ids": ["ilo"],
    },
    "HCCH": {
        "regions": ["HCCH conventions and status material"],
        "source_ids": ["hcch"],
    },
}


EXTENSIBLE_SOURCE_IDS = ["oecd", "wipo", "ilo", "hcch"]


@lru_cache(maxsize=64)
def _check_portal(url):
    request = Request(
        url,
        headers={"User-Agent": "ContractIntelligence-LegalSourceCheck/1.0"},
    )
    try:
        with urlopen(request, timeout=1.5) as response:
            return response.status < 400, datetime.now(timezone.utc).isoformat()
    except (TimeoutError, URLError, OSError):
        return False, datetime.now(timezone.utc).isoformat()


def legal_sources_for(jurisdictions, live_check=False, source_states=None):
    """Return source metadata without claiming that a provision was verified."""
    source_states = source_states or {}
    results = []
    for jurisdiction in jurisdictions:
        entry = JURISDICTION_SOURCES.get(jurisdiction)
        if not entry:
            continue
        sources = []
        for index, source_id in enumerate(entry["source_ids"]):
            source = SOURCE_REGISTRY[source_id].copy()
            source["verification_status"] = "not_checked"
            source["checked_at"] = None
            source["provision_verified"] = False
            state = source_states.get(source_id, {})
            source["last_attempt_at"] = state.get("last_attempt_at")
            source["last_successful_retrieval_at"] = state.get(
                "last_successful_retrieval_at"
            )
            source["retrieval_status"] = state.get(
                "retrieval_status", "not_attempted"
            )
            source["last_error"] = state.get("last_error")
            if live_check and index == 0:
                reachable, checked_at = _check_portal(source["base_url"])
                source["verification_status"] = (
                    "portal_reachable_provision_not_verified"
                    if reachable
                    else "portal_unavailable_provision_not_verified"
                )
                source["checked_at"] = checked_at
            sources.append(source)
        results.append(
            {
                "jurisdiction": jurisdiction,
                "regions": entry["regions"],
                "sources": sources,
            }
        )
    return results


def official_source_host(source_id):
    """Return a configured source hostname for strict retrieval URL checks."""
    source = SOURCE_REGISTRY[source_id]
    return urlsplit(source["base_url"]).hostname
