import os
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

from backend.services.legal_sources import legal_sources_for


class LawFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding_id: str
    title: str
    affected_party: Optional[str]
    affected_party_role: Optional[str]
    jurisdiction: Optional[str]
    contract_topic: str
    contract_clause_text: Optional[str]
    contract_clause_reference: Optional[str]
    applicability_reason: str
    legal_provision_name: Optional[str]
    legal_provision_reference: Optional[str]
    legal_explanation: str
    legal_boundary: str
    potential_conflict: Optional[str]
    missing_protection: Optional[str]
    severity: str
    confidence: float = Field(ge=0, le=1)
    recommended_action: str
    official_source_url: Optional[str]
    source_verification_status: str
    source_verified_at: Optional[str]
    requires_lawyer_review: bool


class LawAnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    analysis_status: str
    method: str
    contract_type: str
    governing_law: Optional[str]
    jurisdiction: Optional[str]
    venue: Optional[str]
    arbitration: Optional[str]
    source_notes: List[str]
    evidence: List[Dict[str, str]]
    overview: Dict[str, Any]
    company_analyses: List[Dict[str, Any]]
    findings: List[LawFinding]
    issues_to_resolve: List[Dict[str, Any]]
    legal_sources: List[Dict[str, Any]]
    source_verification: Dict[str, Any]
    limitations: List[str]


COUNTRY_PATTERNS: Dict[str, List[str]] = {
    "India": [r"\bIndia\b", r"\bIndian law\b", r"\bMumbai\b", r"\bDelhi\b"],
    "United Kingdom": [
        r"\bUnited Kingdom\b",
        r"\bU\.?K\.?\b",
        r"\bEngland and Wales\b",
        r"\bEngland\b",
        r"\bScotland\b",
        r"\bNorthern Ireland\b",
        r"\bEnglish law\b",
    ],
    "Germany": [r"\bGermany\b", r"\bGerman law\b", r"\bFederal Republic of Germany\b"],
    "United States of America": [
        r"\bUnited States(?: of America)?\b",
        r"\bU\.?S\.?A?\.?\b",
        r"\b(?:New York|California|Delaware|Texas) law\b",
        r"\blaws? of (?:New York|California|Delaware|Texas)\b",
    ],
    "United Arab Emirates": [
        r"\bUnited Arab Emirates\b",
        r"\bU\.?A\.?E\.?\b",
        r"\bDubai\b",
        r"\bAbu Dhabi\b",
        r"\bDIFC\b",
        r"\bADGM\b",
    ],
    "Israel": [r"\bIsrael\b", r"\bIsraeli law\b"],
    "China": [
        r"\bChina\b",
        r"\bPeople'?s Republic of China\b",
        r"\bPRC law\b",
        r"\bHong Kong\b",
        r"\bMacau\b",
        r"\bMacao\b",
    ],
    "France": [r"\bFrance\b", r"\bFrench law\b"],
}
CITY_JURISDICTIONS = {
    "India": {
        "Mumbai": r"\bMumbai\b",
        "New Delhi": r"\bNew Delhi\b",
        "Bengaluru": r"\b(?:Bengaluru|Bangalore)\b",
        "Chennai": r"\bChennai\b",
    },
    "United Kingdom": {
        "London": r"\bLondon\b",
        "Scotland": r"\bEdinburgh\b",
        "Northern Ireland": r"\bBelfast\b",
        "England and Wales": r"\bCardiff\b",
    },
    "Germany": {
        "Berlin": r"\bBerlin\b",
        "Munich": r"\bMunich\b",
        "Frankfurt": r"\bFrankfurt\b",
        "Hamburg": r"\bHamburg\b",
    },
    "United States of America": {
        "New York": r"\bNew York\b",
        "Washington, D.C.": r"\bWashington,? D\.?C\.?\b",
        "California": r"\b(?:San Francisco|Los Angeles)\b",
    },
    "United Arab Emirates": {
        "Dubai": r"\bDubai\b",
        "Abu Dhabi": r"\bAbu Dhabi\b",
    },
    "China": {
        "Beijing": r"\bBeijing\b",
        "Shanghai": r"\bShanghai\b",
        "Shenzhen": r"\bShenzhen\b",
    },
    "France": {
        "Paris": r"\bParis\b",
        "Lyon": r"\bLyon\b",
        "Marseille": r"\bMarseille\b",
    },
}

ENTITY_PATTERN = re.compile(
    r"\b((?:[A-Z][A-Za-z0-9&'’\-]*\s+){0,5}"
    r"(?:Private Limited|Pvt\.?\s*Ltd\.?|Limited|Ltd\.?|LLC|L\.L.C\.|"
    r"Inc\.?|Incorporated|Corporation|Corp\.?|GmbH|AG|S\.A\.S?\.?|"
    r"PLC|LLP|FZ-LLC))\b"
)
INDIVIDUAL_PARTY_PATTERN = re.compile(
    r"\b([A-Z][a-z]+(?:[-'][A-Z][a-z]+)?"
    r"(?:\s+[A-Z][a-z]+(?:[-'][A-Z][a-z]+)?){1,3})"
    r"(?=\s*(?:\(\s*['\"“]?(?i:(?:the\s+)?(?:customer|client|supplier|vendor|"
    r"provider|contractor|consultant|licensor|licensee|buyer|seller|"
    r"employer|employee|party\s+[A-Z]))\b|\s*,\s*"
    r"(?i:(?:an?\s+)?(?:individual|natural person))\b))"
)
NAMED_PARTY_ROLE_PATTERN = re.compile(
    r"\b((?:[A-Z][A-Za-z0-9&'’.\-]*\s+){1,5}"
    r"[A-Z][A-Za-z0-9&'’.\-]*)\s+\(\s*(?i:(?:the\s+)?"
    r"(?:customer|client|supplier|vendor|service provider|provider|"
    r"contractor|consultant|licensor|licensee|buyer|seller|employer|"
    r"employee|party\s+[A-Z]))\s*\)"
)
ROLE_PATTERN = re.compile(
    r"\b(customer|client|supplier|vendor|service provider|provider|"
    r"contractor|consultant|licensor|licensee|buyer|seller|employer|"
    r"employee|data controller|controller|data processor|processor|"
    r"company|party\s+[A-Z])\b",
    re.IGNORECASE,
)
ROLE_ALIAS_PATTERN = re.compile(
    r"\(\s*(?:the\s+)?(customer|client|supplier|vendor|service provider|"
    r"provider|contractor|consultant|licensor|licensee|buyer|seller|"
    r"employer|employee|company|party\s+[A-Z])\s*\)",
    re.IGNORECASE,
)
TOPIC_PATTERNS: Dict[str, re.Pattern] = {
    "Services and performance": re.compile(
        r"\b(?:scope of services?|provide.{0,50}services?|"
        r"service provider.{0,50}(?:provide|perform|deliver|render)|"
        r"services? shall|services? will|services? are|deliverables?|"
        r"statement of work|performance standards?)\b",
        re.IGNORECASE,
    ),
    "Payment and tax": re.compile(
        r"\b(?:payment|fees?|invoice|tax(?:es)?|withholding)\b", re.IGNORECASE
    ),
    "Intellectual property": re.compile(
        r"\b(?:intellectual property|ownership|source code|licen[cs]e|copyright)\b",
        re.IGNORECASE,
    ),
    "Confidentiality": re.compile(
        r"\b(?:confidentiality|confidential information|non-disclosure|"
        r"(?:keep|protect|maintain) confidential)\b",
        re.IGNORECASE,
    ),
    "Data protection and transfers": re.compile(
        r"\b(?:personal data|data protection|data processing|privacy|data breach|"
        r"cross-border transfer)\b",
        re.IGNORECASE,
    ),
    "Liability and indemnity": re.compile(
        r"\b(?:liability|indemnity|indemnify|damages|limitation of liability)\b",
        re.IGNORECASE,
    ),
    "Termination": re.compile(r"\b(?:termination|terminate|notice period)\b", re.IGNORECASE),
    "Dispute resolution": re.compile(
        r"\b(?:arbitration|dispute resolution|jurisdiction|courts? of|venue)\b",
        re.IGNORECASE,
    ),
}
TOPIC_SPECIFIC_EVIDENCE: Dict[str, re.Pattern] = {
    "Services and performance": re.compile(
        r"\b(?:provide.{0,50}services?|service provider.{0,50}"
        r"(?:provide|perform|deliver|render)|deliverables?|performance standards?)\b",
        re.IGNORECASE,
    ),
    "Payment and tax": re.compile(
        r"\b(?:shall pay|must pay|payable|invoices? (?:are )?payable|"
        r"payment is due|withholding)\b",
        re.IGNORECASE,
    ),
    "Intellectual property": re.compile(
        r"\b(?:ownership|shall belong|owned by|license|licence|source code)\b",
        re.IGNORECASE,
    ),
    "Confidentiality": re.compile(
        r"\b(?:confidentiality|non-disclosure|keep confidential|"
        r"protect confidential information)\b",
        re.IGNORECASE,
    ),
    "Data protection and transfers": re.compile(
        r"\b(?:personal data|data protection|data breach|data processing|privacy)\b",
        re.IGNORECASE,
    ),
    "Liability and indemnity": re.compile(
        r"\b(?:liable|liability cap|limitation of liability|indemnif(?:y|ies)|"
        r"aggregate liability)\b",
        re.IGNORECASE,
    ),
    "Termination": re.compile(
        r"\b(?:terminate|termination fee|notice period|cure period)\b",
        re.IGNORECASE,
    ),
    "Dispute resolution": re.compile(
        r"\b(?:arbitration|court|resolve disputes?|dispute resolution)\b",
        re.IGNORECASE,
    ),
}

INCORPORATION_PATTERN = re.compile(
    r"\b(?:incorporated|organized|registered|registered office|principal office|"
    r"headquartered|having its (?:registered )?office|with offices)\b",
    re.IGNORECASE,
)
OPERATION_PATTERN = re.compile(
    r"\b(?:services? (?:are )?(?:performed|provided|delivered)|perform(?:ed|ance)? "
    r"in|located in|operat(?:es|ing) in|work is carried out in|data (?:is )?"
    r"(?:stored|hosted|processed|transferred) in|processing in|"
    r"process(?:es|ing) personal data in)\b",
    re.IGNORECASE,
)
GOVERNING_PATTERN = re.compile(
    r"\b(?:governed by|governing law(?: shall be| is| of)?|laws of|"
    r"construed in accordance with)\b",
    re.IGNORECASE,
)
COURT_PATTERN = re.compile(
    r"\b(?:courts?|jurisdiction|venue|exclusive jurisdiction|submit to)\b",
    re.IGNORECASE,
)
ARBITRATION_PATTERN = re.compile(
    r"\b(?:arbitration|arbitral|arbitrator|arbitration seat|seat of arbitration)\b",
    re.IGNORECASE,
)
SECTION_HEADING_PATTERN = re.compile(
    r"^\s*(?:\d+(?:\.\d+)*[.)]?\s*)?"
    r"(?:governing law|jurisdiction|venue|arbitration|dispute resolution|"
    r"court jurisdiction)(?:\s+and\s+venue)?(?:\s+clause)?\s*[:.-]?\s*$",
    re.IGNORECASE,
)


def _sentences(text: str) -> List[str]:
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"---\s*Page\s+\d+\s*---", "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"(?<![.!?;])\n\s*(?=[a-z])", " ", normalized)
    normalized = re.sub(r"[ \t]+", " ", normalized)
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", normalized)
        if sentence.strip()
    ]


def _country_matches(text: str) -> List[Tuple[str, str]]:
    matches = []
    for jurisdiction, patterns in COUNTRY_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, text or "", re.IGNORECASE)
            if match:
                matches.append((match.start(), jurisdiction, match.group(0)))
                break
    matches.sort(key=lambda item: item[0])
    return [(jurisdiction, matched_text) for _, jurisdiction, matched_text in matches]


def _regional_detail(jurisdiction: str, text: str) -> Optional[str]:
    normalized = text.lower()
    if jurisdiction == "United Kingdom":
        for region in ("England and Wales", "Scotland", "Northern Ireland"):
            if region.lower() in normalized:
                return region
        if re.search(r"\bEngland\b", text, re.IGNORECASE):
            return "England (territorial scope requires confirmation)"
        if re.search(r"\bEnglish law\b", text, re.IGNORECASE):
            return "England and Wales (English law reference; court venue not inferred)"
    if jurisdiction == "United States of America":
        for state in ("New York", "California", "Delaware", "Texas"):
            if re.search(rf"\b{state}\b", text, re.IGNORECASE):
                return f"United States — {state}"
        return "United States — federal/state distinction unresolved"
    if jurisdiction == "United Arab Emirates":
        if re.search(r"\bDIFC\b", text, re.IGNORECASE):
            return "Dubai International Financial Centre (DIFC)"
        if re.search(r"\bADGM\b", text, re.IGNORECASE):
            return "Abu Dhabi Global Market (ADGM)"
        if re.search(r"\bmainland\b", text, re.IGNORECASE):
            return "UAE mainland (specific emirate not resolved)"
        if re.search(r"\bDubai\b", text, re.IGNORECASE):
            return "Dubai (mainland/DIFC distinction unresolved)"
    if jurisdiction == "China":
        if re.search(r"\bHong Kong\b", text, re.IGNORECASE):
            return "Hong Kong (separate legal system)"
        if re.search(r"\bMacau|Macao\b", text, re.IGNORECASE):
            return "Macau (separate legal system)"
        if re.search(r"\bmainland China\b", text, re.IGNORECASE):
            return "Mainland China"
    return None


def _find_jurisdictions(text: str, governing_excerpt: str = "") -> List[Dict[str, Any]]:
    connections: Dict[str, Dict[str, Any]] = {}
    for sentence in _sentences(text):
        for jurisdiction, _ in _country_matches(sentence):
            kinds = []
            if GOVERNING_PATTERN.search(sentence):
                kinds.append("governing_law")
            if ARBITRATION_PATTERN.search(sentence) or COURT_PATTERN.search(sentence):
                kinds.append("dispute_resolution")
            if INCORPORATION_PATTERN.search(sentence):
                kinds.append("party_incorporation_or_office")
            if OPERATION_PATTERN.search(sentence):
                kinds.append("operations_or_data_location")
            if not kinds:
                kinds.append("explicit_contract_mention")
            entry = connections.setdefault(
                jurisdiction, {"jurisdiction": jurisdiction, "connection_types": [], "evidence": []}
            )
            for kind in kinds:
                if kind not in entry["connection_types"]:
                    entry["connection_types"].append(kind)
            evidence = sentence[:500]
            if evidence not in entry["evidence"] and len(entry["evidence"]) < 3:
                entry["evidence"].append(evidence)
            regional = _regional_detail(jurisdiction, sentence)
            if regional:
                entry["region"] = regional

        location_context = bool(
            ARBITRATION_PATTERN.search(sentence)
            or COURT_PATTERN.search(sentence)
            or OPERATION_PATTERN.search(sentence)
        )
        if location_context:
            for jurisdiction, cities in CITY_JURISDICTIONS.items():
                for region, pattern in cities.items():
                    city_match = re.search(pattern, sentence, re.IGNORECASE)
                    if not city_match:
                        continue
                    entry = connections.setdefault(
                        jurisdiction,
                        {
                            "jurisdiction": jurisdiction,
                            "connection_types": [],
                            "evidence": [],
                        },
                    )
                    if "stated_city_or_forum_location" not in entry["connection_types"]:
                        entry["connection_types"].append(
                            "stated_city_or_forum_location"
                        )
                    if sentence[:500] not in entry["evidence"] and len(entry["evidence"]) < 3:
                        entry["evidence"].append(sentence[:500])
                    entry["region"] = (
                        f"{region}, {jurisdiction} (location stated; governing law not inferred)"
                    )
                    break

    for jurisdiction, _ in _country_matches(governing_excerpt):
        entry = connections.setdefault(
            jurisdiction, {"jurisdiction": jurisdiction, "connection_types": [], "evidence": []}
        )
        if "governing_law" not in entry["connection_types"]:
            entry["connection_types"].append("governing_law")
        entry["region"] = _regional_detail(jurisdiction, governing_excerpt) or entry.get("region")

    return list(connections.values())


def _extract_designations(text: str, pattern: re.Pattern) -> List[str]:
    results = []
    for sentence in _sentences(text):
        if (
            pattern.search(sentence)
            and not SECTION_HEADING_PATTERN.fullmatch(sentence)
            and len(sentence) <= 1000
        ):
            if sentence not in results:
                results.append(sentence[:500])
    return results[:5]


def _extract_parties(text: str) -> List[Dict[str, Any]]:
    parties = []
    seen = set()
    for match in ENTITY_PATTERN.finditer(text or ""):
        name = re.sub(r"\s+", " ", match.group(1)).strip(" ,.;")
        name = re.sub(r"^(?:for|by|between|and)\s+", "", name, flags=re.IGNORECASE)
        key = re.sub(r"[^a-z0-9]", "", name.casefold())
        if key in seen:
            continue
        seen.add(key)
        start, end = max(0, match.start() - 220), min(len(text), match.end() + 220)
        context = text[start:end]
        role_matches = list(ROLE_PATTERN.finditer(context))
        entity_center = (match.start() + match.end()) // 2
        role_after_entity = context[match.end() - start : match.end() - start + 120]
        explicit_role = ROLE_ALIAS_PATTERN.search(role_after_entity)
        after_entity = [
            item
            for item in role_matches
            if match.end() - start <= item.start() <= match.end() - start + 100
        ]
        role_match = (
            explicit_role
            if explicit_role
            else after_entity[0]
            if after_entity
            else min(
                role_matches,
                key=lambda item: abs(
                    start + (item.start() + item.end()) // 2 - entity_center
                ),
            )
            if role_matches
            else None
        )
        role = (
            explicit_role.group(1)
            if explicit_role
            else role_match.group(0)
            if role_match
            else None
        )
        incorporation_evidence = next(
            (
                sentence
                for sentence in _sentences(context)
                if INCORPORATION_PATTERN.search(sentence)
                and _country_matches(sentence)
            ),
            None,
        )
        country = None
        if incorporation_evidence:
            evidence_matches = []
            evidence_offset = context.find(incorporation_evidence)
            for jurisdiction, patterns in COUNTRY_PATTERNS.items():
                for pattern in patterns:
                    for country_match in re.finditer(
                        pattern, incorporation_evidence, re.IGNORECASE
                    ):
                        evidence_matches.append(
                            (
                                abs(
                                    start
                                    + evidence_offset
                                    + country_match.start()
                                    - entity_center
                                ),
                                jurisdiction,
                            )
                        )
            if evidence_matches:
                country = min(evidence_matches, key=lambda item: item[0])[1]
        parties.append(
            {
                "name": name,
                "role": role,
                "party_type": "organization",
                "country": country,
                "country_basis": (
                    "explicit incorporation/office wording near party name"
                    if country
                    else "not stated clearly near the identified party name"
                ),
                "country_evidence": (
                    incorporation_evidence[:350]
                    if incorporation_evidence and country
                    else None
                ),
            }
        )
        if len(parties) >= 12:
            break
    individual_names = {
        match.group(1).casefold()
        for match in INDIVIDUAL_PARTY_PATTERN.finditer(text or "")
    }
    for match in NAMED_PARTY_ROLE_PATTERN.finditer(text or ""):
        name = re.sub(r"^(?:for|by|between|and)\s+", "", match.group(1).strip(" ,.;"), flags=re.IGNORECASE)
        key = re.sub(r"[^a-z0-9]", "", name.casefold())
        if key in seen or name.casefold() in individual_names:
            continue
        seen.add(key)
        start, end = max(0, match.start() - 200), min(len(text), match.end() + 200)
        context = text[start:end]
        role_matches = list(ROLE_PATTERN.finditer(context))
        party_center = (match.start() + match.end()) // 2
        role_after_party = context[match.end() - start : match.end() - start + 120]
        explicit_role = ROLE_ALIAS_PATTERN.search(role_after_party)
        role_match = (
            explicit_role
            if explicit_role
            else min(
                role_matches,
                key=lambda item: abs(
                    start + (item.start() + item.end()) // 2 - party_center
                ),
            )
            if role_matches
            else None
        )
        incorporation_evidence = next(
            (
                sentence
                for sentence in _sentences(context)
                if INCORPORATION_PATTERN.search(sentence)
                and _country_matches(sentence)
            ),
            None,
        )
        party_country = None
        if incorporation_evidence:
            country_matches = []
            evidence_start = start + context.find(incorporation_evidence)
            for jurisdiction, patterns in COUNTRY_PATTERNS.items():
                for pattern in patterns:
                    for country_match in re.finditer(
                        pattern, incorporation_evidence, re.IGNORECASE
                    ):
                        country_matches.append(
                            (
                                abs(
                                    evidence_start
                                    + country_match.start()
                                    - party_center
                                ),
                                jurisdiction,
                            )
                        )
            if country_matches:
                party_country = min(country_matches, key=lambda item: item[0])[1]
        parties.append(
            {
                "name": name,
                "role": (
                    explicit_role.group(1)
                    if explicit_role
                    else role_match.group(0)
                    if role_match
                    else None
                ),
                "party_type": "named_party",
                "country": party_country,
                "country_basis": (
                    "explicit incorporation/office wording near party name"
                    if party_country
                    else "not stated clearly near the identified party name"
                ),
                "country_evidence": (
                    incorporation_evidence[:350] if incorporation_evidence else None
                ),
            }
        )
        if len(parties) >= 12:
            break
    for match in INDIVIDUAL_PARTY_PATTERN.finditer(text or ""):
        name = match.group(1).strip()
        key = re.sub(r"[^a-z0-9]", "", name.casefold())
        if key in seen:
            continue
        seen.add(key)
        start, end = max(0, match.start() - 180), min(len(text), match.end() + 180)
        context = text[start:end]
        role_matches = list(ROLE_PATTERN.finditer(context))
        role_match = next(
            (
                item
                for item in role_matches
                if match.end() - start <= item.start() <= match.end() - start + 90
            ),
            None,
        )
        location_evidence = next(
            (
                sentence
                for sentence in _sentences(context)
                if re.search(
                    r"\b(?:resident|residing|citizen|based)\s+(?:in|of)\b",
                    sentence,
                    re.IGNORECASE,
                )
                and _country_matches(sentence)
            ),
            None,
        )
        country = _country_matches(location_evidence or "")
        parties.append(
            {
                "name": name,
                "role": role_match.group(0) if role_match else None,
                "party_type": "individual",
                "country": country[0][0] if country else None,
                "country_basis": (
                    "explicit individual residence/citizenship wording"
                    if country
                    else "country not stated clearly near the identified individual"
                ),
                "country_evidence": (
                    location_evidence[:350] if location_evidence else None
                ),
            }
        )
        if len(parties) >= 12:
            break
    return parties


def _topic_evidence(text: str, clauses: Iterable[Dict[str, Any]]) -> List[Dict[str, str]]:
    candidates: Dict[str, List[str]] = {}
    for clause in clauses or []:
        clause_text = str(clause.get("text", "")).strip()
        if not clause_text:
            continue
        for sentence in _sentences(clause_text):
            for topic, pattern in TOPIC_PATTERNS.items():
                if pattern.search(sentence):
                    candidates.setdefault(topic, []).append(sentence[:1200])
    for sentence in _sentences(text):
        for topic, pattern in TOPIC_PATTERNS.items():
            if pattern.search(sentence):
                candidates.setdefault(topic, []).append(sentence[:1200])

    evidence = {}
    duty_pattern = re.compile(
        r"\b(?:shall|must|will|may|agrees? to|is required to|is entitled to|"
        r"belongs? to|remain(?:s)? the property of|pay(?:s)?|provide(?:s)?)\b",
        re.IGNORECASE,
    )
    for topic, snippets in candidates.items():
        unique = list(dict.fromkeys(snippets))
        evidence[topic] = max(
            unique,
            key=lambda snippet: (
                bool(TOPIC_SPECIFIC_EVIDENCE[topic].search(snippet)),
                bool(ROLE_PATTERN.search(snippet) or re.search(r"\b(?:each|either|neither) party\b", snippet, re.IGNORECASE)),
                bool(duty_pattern.search(snippet)),
                len(snippet),
            ),
        )
    return [
        {"contract_topic": topic, "contract_clause_text": clause_text}
        for topic, clause_text in evidence.items()
    ]


def _clause_mentions_party(party: Dict[str, Any], clause_text: str) -> bool:
    if party["name"].casefold() in clause_text.casefold():
        return True
    role = party.get("role")
    if role and re.search(rf"\b{re.escape(role)}\b", clause_text, re.IGNORECASE):
        return True
    return bool(
        re.search(
            r"\b(?:each party|either party|both parties|the parties|all parties|"
                r"neither party|each of the parties|parties agree|parties shall)\b",
            clause_text,
            re.IGNORECASE,
        )
    )


def _make_finding(
    *,
    finding_id: str,
    title: str,
    affected_party: Optional[str],
    affected_party_role: Optional[str],
    jurisdiction: Optional[str],
    topic: str,
    clause_text: Optional[str],
    reason: str,
    explanation: str,
    boundary: str,
    conflict: Optional[str],
    missing: Optional[str],
    severity: str,
    action: str,
    source_by_jurisdiction: Dict[str, Dict[str, Any]],
    confidence: float,
) -> Dict[str, Any]:
    source = source_by_jurisdiction.get(jurisdiction or "", {})
    portals = source.get("sources", [])
    portal = portals[0] if portals else {}
    return {
        "finding_id": finding_id,
        "title": title,
        "affected_party": affected_party,
        "affected_party_role": affected_party_role,
        "jurisdiction": jurisdiction,
        "contract_topic": topic,
        "contract_clause_text": clause_text,
        "contract_clause_reference": None,
        "applicability_reason": reason,
        "legal_provision_name": None,
        "legal_provision_reference": None,
        "legal_explanation": explanation,
        "legal_boundary": boundary,
        "potential_conflict": conflict,
        "missing_protection": missing,
        "severity": severity,
        "confidence": confidence,
        "recommended_action": action,
        "official_source_url": portal.get("url"),
        "source_verification_status": portal.get(
            "verification_status", "no_jurisdiction_specific_source"
        ),
        "source_verified_at": None,
        "requires_lawyer_review": True,
    }


def analyze_law_context(
    text: str,
    contract_type: str = "Other/Unknown",
    clauses: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Extract contract-supported law facts without asserting unverified legal rules."""
    text = text or ""
    governing_sentences = _extract_designations(text, GOVERNING_PATTERN)
    governing_excerpt = governing_sentences[0] if governing_sentences else ""
    governing_matches = _country_matches(governing_excerpt)
    governing_law = governing_matches[0][0] if governing_matches else None
    governing_region = (
        _regional_detail(governing_law, governing_excerpt) if governing_law else None
    )

    court_sentences = _extract_designations(text, COURT_PATTERN)
    arbitration_sentences = _extract_designations(text, ARBITRATION_PATTERN)
    dispute_texts = list(dict.fromkeys(court_sentences + arbitration_sentences))
    dispute_text = " ".join(dispute_texts)
    jurisdictions = _find_jurisdictions(text, governing_excerpt)

    for jurisdiction, _ in _country_matches(dispute_text):
        if not any(item["jurisdiction"] == jurisdiction for item in jurisdictions):
            jurisdictions.append(
                {
                    "jurisdiction": jurisdiction,
                    "connection_types": ["dispute_resolution"],
                    "evidence": [next(
                        sentence[:500]
                        for sentence in dispute_texts
                        if _country_matches(sentence)
                    )],
                }
            )

    live_check = os.environ.get("LEGAL_SOURCE_LIVE_CHECK", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    source_records = legal_sources_for(
        [item["jurisdiction"] for item in jurisdictions], live_check=live_check
    )
    source_by_jurisdiction = {
        item["jurisdiction"]: item for item in source_records
    }
    for jurisdiction in jurisdictions:
        jurisdiction["applicability_reason"] = ", ".join(
            jurisdiction["connection_types"]
        )
        jurisdiction["source_verification_status"] = (
            source_by_jurisdiction.get(jurisdiction["jurisdiction"], {})
            .get("sources", [{}])[0]
            .get("verification_status", "not_checked")
        )

    parties = _extract_parties(text)
    topic_evidence = _topic_evidence(text, clauses or [])
    findings = []

    if not governing_sentences:
        findings.append(
            _make_finding(
                finding_id="missing-governing-law",
                title="Governing-law provision not identified",
                affected_party=None,
                affected_party_role=None,
                jurisdiction=None,
                topic="Governing law",
                clause_text=None,
                reason="No governing-law wording was identified in the extracted contract text.",
                explanation="The contract text available to this review does not identify an express choice of governing law.",
                boundary="This extraction may miss a provision due to document quality, unusual wording, or an attachment not included in the upload.",
                conflict=None,
                missing="A clear governing-law provision was not found.",
                severity="Medium",
                action="Confirm whether the complete agreement and incorporated schedules state governing law; obtain legal review before selecting a jurisdiction.",
                source_by_jurisdiction=source_by_jurisdiction,
                confidence=0.93,
            )
        )
    elif not governing_law:
        findings.append(
            _make_finding(
                finding_id="governing-law-unresolved",
                title="Governing-law wording needs jurisdiction confirmation",
                affected_party=None,
                affected_party_role=None,
                jurisdiction=None,
                topic="Governing law",
                clause_text=governing_excerpt[:1200],
                reason="A governing-law clause appears in the text, but its jurisdiction could not be mapped confidently.",
                explanation="The detected clause should be reviewed to determine the exact legal system it selects.",
                boundary="No jurisdiction or legal provision is inferred from ambiguous wording.",
                conflict=None,
                missing=None,
                severity="Medium",
                action="Confirm the complete governing-law clause and identify the intended country and sub-jurisdiction.",
                source_by_jurisdiction=source_by_jurisdiction,
                confidence=0.61,
            )
        )

    if not dispute_texts:
        findings.append(
            _make_finding(
                finding_id="missing-dispute-resolution",
                title="Court or arbitration terms not identified",
                affected_party=None,
                affected_party_role=None,
                jurisdiction=None,
                topic="Dispute resolution",
                clause_text=None,
                reason="No court-jurisdiction or arbitration wording was identified in the extracted text.",
                explanation="The uploaded text does not provide a dispute forum that this extraction can identify.",
                boundary="A missing result is not proof that the complete contract or incorporated terms lack such a provision.",
                conflict=None,
                missing="Court jurisdiction, arbitration seat/rules, or another dispute mechanism was not identified.",
                severity="Medium",
                action="Check all contract schedules and referenced terms, then have counsel confirm an appropriate dispute forum and mechanism.",
                source_by_jurisdiction=source_by_jurisdiction,
                confidence=0.9,
            )
        )

    if len(governing_sentences) > 1:
        findings.append(
            _make_finding(
                finding_id="multiple-governing-law-clauses",
                title="Multiple governing-law references require comparison",
                affected_party=None,
                affected_party_role=None,
                jurisdiction=governing_law,
                topic="Governing law",
                clause_text="\n\n".join(governing_sentences)[:1200],
                reason="More than one distinct sentence contains governing-law wording.",
                explanation="The clauses may apply to different documents or may be inconsistent; their scope cannot be resolved from keyword detection alone.",
                boundary="No legal conflict is concluded without reviewing the complete contract hierarchy and incorporated documents.",
                conflict="Multiple governing-law references were detected.",
                missing=None,
                severity="Medium",
                action="Compare clause scope, precedence, schedules, and incorporated terms with counsel.",
                source_by_jurisdiction=source_by_jurisdiction,
                confidence=0.74,
            )
        )

    party_topics: Dict[str, List[str]] = {party["name"]: [] for party in parties}
    party_index = {party["name"]: index for index, party in enumerate(parties, start=1)}
    for topic_index, item in enumerate(topic_evidence, start=1):
        topic = item["contract_topic"]
        clause_text = item["contract_clause_text"]
        affected_parties = [
            party for party in parties if _clause_mentions_party(party, clause_text)
        ]
        severity = (
            "Medium"
            if topic in {"Data protection and transfers", "Liability and indemnity", "Payment and tax"}
            else "Low"
        )
        action = (
            "Confirm the responsible party, processing locations, transfer arrangements, and any applicable mandatory requirements with privacy counsel."
            if topic == "Data protection and transfers"
            else "Confirm the parties' responsibilities, scope, and any mandatory local-law requirements with counsel."
        )
        if not affected_parties:
            finding = _make_finding(
                finding_id=f"unassigned-topic-{topic_index}",
                title=f"Party responsibility for {topic.lower()} needs confirmation",
                affected_party=None,
                affected_party_role=None,
                jurisdiction=governing_law,
                topic=topic,
                clause_text=clause_text,
                reason="A contract term was found, but its text does not reliably identify which named party is responsible.",
                explanation="The clause is shown as contract evidence; this analysis does not assign a duty or entitlement to a company without text supporting that attribution.",
                boundary="Review surrounding clauses, definitions, and schedules. No statutory provision has been verified.",
                conflict=None,
                missing="The responsible party is not explicit in the identified clause.",
                severity=severity,
                action="Confirm and, if needed, clarify the responsible party and scope in the contract.",
                source_by_jurisdiction=source_by_jurisdiction,
                confidence=0.61,
            )
            findings.append(finding)
            continue

        for party in affected_parties:
            party_number = party_index[party["name"]]
            jurisdiction_matches = _country_matches(clause_text)
            jurisdiction = (
                jurisdiction_matches[0][0]
                if topic == "Data protection and transfers" and jurisdiction_matches
                else party["country"] or governing_law
            )
            finding = _make_finding(
                finding_id=f"party-{party_number}-topic-{topic_index}",
                title=f"Contractual {topic.lower()} term identified",
                affected_party=party["name"],
                affected_party_role=party["role"],
                jurisdiction=jurisdiction,
                topic=topic,
                clause_text=clause_text,
                reason=(
                    f"The clause text refers to {party['name']}"
                    + (f" in the role of {party['role']}" if party["role"] else "")
                    + f" and concerns {topic.lower()}."
                ),
                explanation=(
                    "Contract evidence: "
                    + clause_text[:700]
                    + " This is a text-grounded summary, not a conclusion that a statute imposes or validates the term."
                ),
                boundary=(
                    "The contract alone may not establish all activities, locations, data flows, or mandatory laws. No specific statutory provision has been verified."
                ),
                conflict=None,
                missing=None,
                severity=severity,
                action=action,
                source_by_jurisdiction=source_by_jurisdiction,
                confidence=0.76 if party["role"] else 0.62,
            )
            findings.append(finding)
            party_topics[party["name"]].append(finding["finding_id"])

    company_analyses = []
    for party in parties:
        related = [
            item
            for item in findings
            if item["affected_party"] == party["name"]
        ]
        company_analyses.append(
            {
                **party,
                "contractual_obligations": [
                    {
                        "topic": item["contract_topic"],
                        "summary": (
                            f"The clause states: {item['contract_clause_text']}"
                        ),
                        "contract_clause_text": item["contract_clause_text"],
                        "finding_id": item["finding_id"],
                    }
                    for item in related
                ],
                "potential_statutory_obligations": [
                    {
                        "topic": item["contract_topic"],
                        "status": "requires_fact_and_lawyer_review",
                        "note": "Potential legal requirements cannot be determined from this contract text alone; no statute is asserted as applicable.",
                    }
                    for item in related
                    if item["contract_topic"]
                    in {"Data protection and transfers", "Payment and tax"}
                ],
                "contractual_rights_and_restrictions": [
                    {
                        "topic": item["contract_topic"],
                        "contract_clause_text": item["contract_clause_text"],
                        "boundary": "This is the contract wording; no entitlement beyond its text is inferred.",
                    }
                    for item in related
                    if item["contract_topic"]
                    in {
                        "Intellectual property",
                        "Termination",
                        "Confidentiality",
                        "Services and performance",
                        "Liability and indemnity",
                    }
                ],
                "rights_and_boundaries": [
                    *[
                        f"{item['contract_topic']} rights or restrictions are limited to the wording in the quoted clause; no additional entitlement is inferred."
                        for item in related
                        if item["contract_topic"] in {
                            "Intellectual property",
                            "Termination",
                            "Confidentiality",
                            "Services and performance",
                        }
                    ],
                    "Only the contractual rights or restrictions stated in the evidence above are summarized.",
                    "Incorporation country, if explicitly stated, does not by itself determine the governing law for every contract.",
                ],
                "finding_ids": party_topics.get(party["name"], []),
            }
        )

    missing_information = []
    if not parties:
        missing_information.append(
            "No company party name could be confidently extracted from the available text."
        )
    if any(party["country"] is None for party in parties):
        missing_information.append(
            "One or more identified parties have no clearly stated incorporation or registered-office country."
        )
    if not governing_sentences:
        missing_information.append("An express governing-law clause was not identified.")
    if not dispute_texts:
        missing_information.append(
            "Court jurisdiction and arbitration provisions were not identified."
        )
    if not any(item["connection_types"] for item in jurisdictions):
        missing_information.append(
            "No supported operational, data-processing, party-location, or selected-law jurisdiction could be established."
        )

    legacy_evidence = []
    for label, present in (
        ("governing law", bool(governing_sentences)),
        ("jurisdiction", bool(court_sentences)),
        ("venue", any(re.search(r"\bvenue\b", sentence, re.IGNORECASE) for sentence in court_sentences)),
        ("arbitration", bool(arbitration_sentences)),
    ):
        if present:
            legacy_evidence.append({"label": label, "match": label})

    result = {
        "status": "informational",
        "analysis_status": "complete_with_review_required",
        "method": "evidence_based_rules",
        "contract_type": contract_type,
        "governing_law": governing_law,
        "jurisdiction": (
            "Court jurisdiction referenced in the contract" if court_sentences else None
        ),
        "venue": "Venue clause present" if any(
            re.search(r"\bvenue\b", sentence, re.IGNORECASE)
            for sentence in court_sentences
        ) else None,
        "arbitration": "Arbitration clause present" if arbitration_sentences else None,
        "source_notes": [
            "This summary is derived only from the uploaded contract text and is not legal advice.",
            "Official-source portals are provided as research starting points; specific provisions must be checked by qualified counsel.",
        ],
        "evidence": legacy_evidence,
        "overview": {
            "parties": parties,
            "governing_law": {
                "jurisdiction": governing_law,
                "region": governing_region,
                "clause_found": bool(governing_sentences),
                "evidence": governing_excerpt[:1200] or None,
            },
            "dispute_resolution": {
                "court_jurisdiction_evidence": court_sentences,
                "arbitration_evidence": arbitration_sentences,
                "summary": (
                    "Detected provisions require review; the court, seat, and rules are not legally validated."
                    if dispute_texts
                    else "No court-jurisdiction or arbitration provision was identified."
                ),
            },
            "transaction_context": [
                item
                for item in topic_evidence
                if item["contract_topic"]
                in {
                    "Services and performance",
                    "Payment and tax",
                    "Data protection and transfers",
                    "Intellectual property",
                }
            ],
            "potential_jurisdictions": jurisdictions,
            "missing_or_uncertain_information": missing_information,
        },
        "company_analyses": company_analyses,
        "findings": findings,
        "issues_to_resolve": [
            {
                "finding_id": item["finding_id"],
                "title": item["title"],
                "severity": item["severity"],
                "recommended_action": item["recommended_action"],
            }
            for item in findings
            if item["missing_protection"] or item["potential_conflict"]
        ],
        "legal_sources": source_records,
        "source_verification": {
            "live_portal_check_enabled": live_check,
            "notice": (
                "Official-source portals may be linked, but no legal provision or citation is considered verified by this analysis."
            ),
            "verified_provisions": [],
        },
        "limitations": [
            "This rule-based module summarizes evidence found in the uploaded contract; it does not determine governing law or legal outcomes.",
            "Mandatory laws may apply despite a governing-law clause; their applicability depends on facts and qualified legal analysis.",
            "No legal provision, section, article, or quotation is presented as verified.",
            "Party-country identification requires explicit nearby incorporation or office wording; a party's home country is not assumed to be governing law.",
        ],
    }
    return LawAnalysisResult.model_validate(result).model_dump()
