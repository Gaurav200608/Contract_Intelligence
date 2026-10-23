import re
from typing import Any, Dict, List, Tuple


CONTRACT_TYPE_PATTERNS: Dict[str, List[str]] = {
    "Non-disclosure agreement": [
        r"\bnon[- ]disclosure\b",
        r"\bconfidential information\b",
        r"\bconfidentiality obligations\b",
        r"\bproprietary information\b",
        r"\bsecrecy obligations\b",
    ],
    "Employment agreement": [
        r"\bemployment\b",
        r"\bemployee\b",
        r"\bcompensation\b",
        r"\bposition\b",
        r"\btermination for cause\b",
    ],
    "Service agreement": [
        r"\bservice(s)?\b",
        r"\bstatement of work\b",
        r"\bdeliverables\b",
        r"\bservice provider\b",
        r"\bperformance standards\b",
    ],
    "Lease or rental agreement": [
        r"\blease\b",
        r"\brental\b",
        r"\btenant\b",
        r"\blandlord\b",
        r"\bpremises\b",
    ],
    "Sales or purchase agreement": [
        r"\bpurchase\b",
        r"\bsale\b",
        r"\bbuyer\b",
        r"\bseller\b",
        r"\bgoods\b",
        r"\bdelivery\b",
    ],
    "Vendor or supplier agreement": [
        r"\bvendor\b",
        r"\bsupplier\b",
        r"\bprocurement\b",
        r"\bpurchase order\b",
        r"\bproduct specifications\b",
    ],
    "Loan or financing agreement": [
        r"\bloan\b",
        r"\bfinance\b",
        r"\bprincipal\b",
        r"\binterest rate\b",
        r"\brepayment\b",
        r"\bsecurity interest\b",
    ],
    "Consulting agreement": [
        r"\bconsulting\b",
        r"\bconsultant\b",
        r"\bprofessional services\b",
        r"\bengagement\b",
        r"\bfees\b",
    ],
    "Partnership agreement": [
        r"\bpartnership\b",
        r"\bpartners?\b",
        r"\bcapital contribution\b",
        r"\bprofit sharing\b",
        r"\bjoint venture\b",
    ],
    "Licensing agreement": [
        r"\blicensing\b",
        r"\blicence\b",
        r"\blicense\b",
        r"\broyalty\b",
        r"\bintellectual property rights\b",
    ],
    "Construction agreement": [
        r"\bconstruction\b",
        r"\bcontractor\b",
        r"\bproject\b",
        r"\bsite\b",
        r"\bcompletion date\b",
    ],
    "Independent contractor agreement": [
        r"\bindependent contractor\b",
        r"\bcontractor\b",
        r"\bwork product\b",
        r"\bindependent status\b",
        r"\bfees and expenses\b",
    ],
    "Privacy or data-processing agreement": [
        r"\bdata processing\b",
        r"\bprivacy\b",
        r"\bpersonal data\b",
        r"\bdata protection\b",
        r"\bprocessing of personal data\b",
    ],
    "Insurance agreement": [
        r"\binsurance\b",
        r"\bpolicy\b",
        r"\bcoverage\b",
        r"\bpremium\b",
        r"\bclaim\b",
    ],
    "General commercial agreement": [
        r"\bagreement\b",
        r"\bterms and conditions\b",
        r"\bparties\b",
        r"\bcommercial terms\b",
        r"\bapplicable law\b",
    ],
}


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


def detect_contract_type(text: str, clauses: List[Dict[str, Any]] | None = None) -> Dict[str, Any]:
    """Heuristic contract-type detector used when a model is unavailable or uncertain."""
    normalized = _normalize_text(text)
    if len(normalized) < 80:
        return {
            "category": "Other/Unknown",
            "confidence": 0.0,
            "indicators": [],
            "ambiguity": "Document is too short for a reliable contract-type assessment.",
            "method": "heuristic",
        }

    scores: List[Tuple[str, int, List[str]]] = []
    for category, patterns in CONTRACT_TYPE_PATTERNS.items():
        found = []
        for pattern in patterns:
            if re.search(pattern, normalized):
                found.append(pattern)
        if found:
            scores.append((category, len(found), found))

    if not scores:
        return {
            "category": "Other/Unknown",
            "confidence": 0.15,
            "indicators": [],
            "ambiguity": "No strong contract-type indicators were found.",
            "method": "heuristic",
        }

    scores.sort(key=lambda item: (item[1], item[0]), reverse=True)
    best_category, best_score, indicators = scores[0]
    second_score = scores[1][1] if len(scores) > 1 else 0

    if best_score <= 1 and second_score == best_score:
        category = "Other/Unknown"
        confidence = 0.28
        ambiguity = "Multiple categories had similar signal strength."
    elif best_score <= 1:
        category = "Other/Unknown"
        confidence = 0.35
        ambiguity = "The document had only weak evidence for a specific contract type."
    else:
        category = best_category
        confidence = min(0.97, 0.45 + (best_score * 0.09))
        ambiguity = "" if best_score > second_score else "The category is somewhat ambiguous."

    return {
        "category": category,
        "confidence": round(confidence, 3),
        "indicators": indicators[:5],
        "ambiguity": ambiguity,
        "method": "heuristic",
    }
