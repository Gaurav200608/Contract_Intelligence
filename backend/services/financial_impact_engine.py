
"""Evidence-linked, contextual contract financial-risk analysis prototype."""
from __future__ import annotations

import re
from typing import Any


AMOUNT_RE = re.compile(
    r'(?P<currency>₹|INR\b|Rs\.?\s*|\$|USD\b|€|EUR\b|£|GBP\b)?\s*'
    r'(?P<amount>\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+(?:\.\d+)?)'
    r'(?:\s*(?P<scale>thousand|million|billion|lakh|lakhs|crore|crores))?',
    re.I
)

PCT_RE = re.compile(r'(\d+(?:\.\d+)?)\s*(?:%|percent\b)', re.I)

DURATION_RE = re.compile(
    r'(\d+(?:\.\d+)?)\s*(days?|weeks?|months?|years?)\b',
    re.I
)

CLAUSES = {
    "contract_value": re.compile(
        r'\b(?:contract|agreement)\s+value\b|'
        r'\btotal consideration\b|\bcontract price\b',
        re.I
    ),
    "penalty": re.compile(
        r'\bpenalt(?:y|ies)|liquidated damages|late fee|delay damages\b',
        re.I
    ),
    "interest": re.compile(
        r'\binterest\b|late[- ]payment charge|financing charge',
        re.I
    ),
    "liability": re.compile(
        r'\bliability\b|\bliable\b|limitation of liability|liability cap',
        re.I
    ),
    "indemnity": re.compile(
        r'\bindemnif(?:y|ies|ication)\b|hold harmless',
        re.I
    ),
    "termination": re.compile(
        r'termination fee|early termination|termination charge|break fee',
        re.I
    ),
    "renewal": re.compile(
        r'\brenewal\b|auto[- ]renew|automatic renewal|extension fee',
        re.I
    ),
    "payment": re.compile(
        r'\bpayment\b|\binvoice\b|\bpayable\b|\bwithhold(?:ing)?\b',
        re.I
    ),
    "refund": re.compile(
        r'\brefund\b|non[- ]refundable|reimbursement',
        re.I
    ),
    "warranty": re.compile(
        r'\bwarranty\b|\bguarantee\b|service credit',
        re.I
    ),
}

RISK_PATTERNS = {
    "Uncapped Liability": (
        re.compile(
            r'unlimited liability|without limitation|no liability cap|'
            r'shall not be limited',
            re.I
        ),
        "High",
        "The wording appears to remove or omit a clear limit on liability."
    ),
    "Broad Indemnity": (
        re.compile(
            r'indemnif\w{0,20}.{0,100}(?:any|all)|'
            r'any and all claims|regardless of fault',
            re.I
        ),
        "High",
        "The indemnity may cover broad claims or losses."
    ),
    "Unilateral Discretion": (
        re.compile(
            r'sole discretion|may unilaterally|without prior consent|'
            r'without notice',
            re.I
        ),
        "Medium",
        "One party appears to have unilateral discretion or rights."
    ),
    "Automatic Renewal": (
        re.compile(r'automatically renew|auto[- ]renew', re.I),
        "Medium",
        "A missed notice deadline may create continuing obligations."
    ),
    "Strict Deadline": (
        re.compile(
            r'time is of the essence|strict deadline|non[- ]extendable',
            re.I
        ),
        "Medium",
        "Strict timing language may increase the consequences of delay."
    ),
    "Non-refundable Amount": (
        re.compile(r'non[- ]refundable', re.I),
        "Medium",
        "The amount may be difficult to recover if circumstances change."
    ),
    "Withholding / Set-off": (
        re.compile(
            r'withhold payment|withhold any payment|set[- ]off',
            re.I
        ),
        "Medium",
        "Withholding or set-off rights may delay or reduce cash received."
    ),
    "No Cure Period": (
        re.compile(
            r'immediate termination|terminate immediately|'
            r'without opportunity to cure',
            re.I
        ),
        "High",
        "The wording may remove an opportunity to remedy a breach."
    ),
}

SCALES = {
    "thousand": 1_000,
    "million": 1_000_000,
    "billion": 1_000_000_000,
    "lakh": 100_000,
    "lakhs": 100_000,
    "crore": 10_000_000,
    "crores": 10_000_000,
}


def _currency(value: str | None) -> str | None:
    if not value:
        return None

    value = value.lower()

    if "₹" in value or "inr" in value or "rs" in value:
        return "INR"
    if "$" in value or "usd" in value:
        return "USD"
    if "€" in value or "eur" in value:
        return "EUR"
    if "£" in value or "gbp" in value:
        return "GBP"

    return None


def _amounts(sentence: str) -> list[dict[str, Any]]:
    results = []

    for match in AMOUNT_RE.finditer(sentence):
        tail = sentence[match.end():match.end() + 12].lower()

        if re.match(
            r'\s*(?:%|percent\b|days?\b|weeks?\b|months?\b|years?\b)',
            tail
        ):
            continue

        amount = (
            float(match.group("amount").replace(",", ""))
            * SCALES.get((match.group("scale") or "").lower(), 1)
        )

        if amount > 0:
            results.append({
                "amount": round(amount, 2),
                "currency": _currency(match.group("currency")),
                "source_text": match.group(0).strip()
            })

    return results


def _sentences(text: str) -> list[tuple[int, int, str]]:
    sentences = []
    start = 0
    separators = re.compile(
        r'(?<!\d)\.(?!\d)|(?<=\d)\.(?=\s|$)|[!?;]|\n+'
    )
    for match in separators.finditer(text):
        raw = text[start:match.start()]
        leading = len(raw) - len(raw.lstrip())
        separator = match.group()
        sentence = raw + (
            separator if separator and separator[0] in ".!?;" else ""
        )
        sentence = sentence.strip()
        if sentence:
            sentence_start = start + leading
            sentences.append((sentence_start, sentence_start + len(sentence), sentence))
        start = match.end()

    raw = text[start:]
    leading = len(raw) - len(raw.lstrip())
    sentence = raw.strip()
    if sentence:
        sentence_start = start + leading
        sentences.append((sentence_start, sentence_start + len(sentence), sentence))

    return sentences


def _durations(sentence: str) -> list[dict[str, Any]]:
    results = []

    for match in DURATION_RE.finditer(sentence):
        value = float(match.group(1))
        unit = match.group(2).lower()

        if unit.startswith("year"):
            days = value * 365
        elif unit.startswith("month"):
            days = value * 30.4375
        elif unit.startswith("week"):
            days = value * 7
        else:
            days = value

        results.append({
            "value": value,
            "unit": unit,
            "days_approx": round(days, 2),
            "source_text": match.group()
        })

    return results


def analyze_financial_impact(text: str) -> dict[str, Any]:
    """
    Analyze financial clauses, preserve source evidence, and score
    contextual indicators.

    Monetary thresholds are not used to classify financial risk.
    Relative exposure is considered when a comparable contract value
    and currency are available.
    """

    if not isinstance(text, str) or not text.strip():
        return {
            "items": [],
            "calculations": [],
            "contract_value": None,
            "total_calculated_exposure": None,
            "exposure_currency": None,
            "exposure_ratio": None,
            "financial_risk": "Insufficient Information",
            "financial_risk_score": None,
            "financial_risk_reason": "No contract text was provided.",
            "risk_factors": [],
            "uncertainties": ["No contract text was provided."],
            "scenarios": [],
            "financial_terms_detected": 0
        }

    sentences = _sentences(text)
    items = []
    calculations = []
    uncertainties = []
    factors = []
    scenarios = []
    contract_value = None

    # Find a stated contract value.
    for start, end, sentence in sentences:
        if CLAUSES["contract_value"].search(sentence):
            values = _amounts(sentence)

            if values:
                contract_value = {
                    "amount": values[0]["amount"],
                    "currency": values[0]["currency"],
                    "evidence": sentence,
                    "source_start": start,
                    "source_end": end
                }
                break

    # Extract financial terms and calculate exposure when possible.
    for start, end, sentence in sentences:
        kinds = [
            kind
            for kind, pattern in CLAUSES.items()
            if kind != "contract_value" and pattern.search(sentence)
        ]

        if not kinds:
            continue

        amounts = _amounts(sentence)
        percentages = [
            float(match.group(1))
            for match in PCT_RE.finditer(sentence)
        ]
        durations = _durations(sentence)

        for kind in kinds:
            if re.search(
                r'\b(supplier|provider|contractor|seller)\b',
                sentence,
                re.I
            ):
                party_context = "supplier/provider"
            elif re.search(
                r'\b(customer|client|buyer)\b',
                sentence,
                re.I
            ):
                party_context = "customer/client"
            else:
                party_context = "not explicit"

            item = {
                "term_type": kind,
                "evidence": sentence,
                "source_start": start,
                "source_end": end,
                "amounts": amounts,
                "percentages": percentages,
                "durations": durations,
                "party_context": party_context,
                "calculation_status": "not_calculable",
                "calculated_exposure": None,
                "assumptions": []
            }

            calculated = None
            formula = None

            if kind == "penalty":
                if amounts and percentages:
                    calculated = (
                        amounts[0]["amount"]
                        * percentages[0]
                        / 100
                    )
                    formula = (
                        f"{amounts[0]['amount']:g} "
                        f"× {percentages[0]:g}%"
                    )
                    item["assumptions"].append(
                        "First stated amount treated as the percentage "
                        "calculation base; verify the clause meaning."
                    )

                elif amounts and re.search(
                    r'penalty of|liquidated damages of|fixed penalty|flat fee',
                    sentence,
                    re.I
                ):
                    calculated = amounts[0]["amount"]
                    formula = (
                        "Stated flat amount; trigger not independently validated"
                    )

                else:
                    uncertainties.append(
                        "Penalty clause found, but its amount, trigger, "
                        "or calculation basis is incomplete or ambiguous."
                    )

            elif kind == "interest":
                if amounts and percentages and durations:
                    days = durations[0]["days_approx"]
                    calculated = (
                        amounts[0]["amount"]
                        * percentages[0] / 100
                        * days / 365
                    )
                    formula = (
                        f"{amounts[0]['amount']:g} "
                        f"× {percentages[0]:g}% × {days:g}/365"
                    )
                    item["assumptions"].append(
                        "Simple interest prorated by stated duration; "
                        "compounding and day-count rules not inferred."
                    )
                else:
                    uncertainties.append(
                        "Interest clause found, but principal, rate, "
                        "or duration is missing."
                    )

            elif kind == "renewal":
                years = next(
                    (
                        duration["value"]
                        for duration in durations
                        if duration["unit"].startswith("year")
                    ),
                    None
                )

                if (
                    amounts
                    and years is not None
                    and re.search(
                        r'annual|annually|per year|each year|yearly',
                        sentence,
                        re.I
                    )
                ):
                    calculated = amounts[0]["amount"] * years
                    formula = (
                        f"{amounts[0]['amount']:g} × {years:g} years"
                    )
                    item["assumptions"].append(
                        "Amount treated as an annual renewal charge "
                        "for the stated years."
                    )

                elif amounts:
                    calculated = amounts[0]["amount"]
                    formula = (
                        "Stated amount only; total renewal term "
                        "or frequency not established"
                    )
                    uncertainties.append(
                        "Renewal amount detected, but total duration "
                        "or billing frequency is not clear."
                    )

                else:
                    uncertainties.append(
                        "Renewal clause found without a usable monetary amount."
                    )

            elif kind in ("liability", "indemnity"):
                if re.search(
                    r'unlimited|uncapped|without limitation|any and all|'
                    r'all losses|regardless of fault',
                    sentence,
                    re.I
                ):
                    factors.append({
                        "factor": "Potentially uncapped liability or broad indemnity",
                        "severity": "High",
                        "evidence": sentence,
                        "reason": (
                            "The wording may create exposure that is not "
                            "clearly limited to a defined cap."
                        )
                    })

                elif not amounts:
                    factors.append({
                        "factor": "Liability/indemnity limit unclear",
                        "severity": "Medium",
                        "evidence": sentence,
                        "reason": (
                            "No monetary cap was extracted from this sentence; "
                            "review the complete clause and cross-references."
                        )
                    })

            if calculated is not None:
                item["calculation_status"] = (
                    "estimated" if item["assumptions"] else "stated_amount"
                )
                item["calculated_exposure"] = round(calculated, 2)

                currency = amounts[0]["currency"] if amounts else None

                calculations.append({
                    "term_type": kind,
                    "amount": round(calculated, 2),
                    "currency": currency,
                    "formula": formula,
                    "evidence": sentence
                })

            items.append(item)

    # Find contextual risk wording and retain evidence.
    for label, (pattern, severity, reason) in RISK_PATTERNS.items():
        if (
            label == "Uncapped Liability"
            and any(
                "uncapped liability" in factor["factor"].lower()
                for factor in factors
            )
        ):
            continue

        match = pattern.search(text)

        if match:
            left = max(
                0,
                text.rfind("\n", 0, match.start()) + 1
            )
            right = text.find("\n", match.end())

            if right < 0:
                right = min(len(text), match.end() + 180)

            evidence = text[left:right].strip()

            if not evidence:
                evidence = text[
                    max(0, match.start() - 80):
                    min(len(text), match.end() + 120)
                ].strip()

            factors.append({
                "factor": label,
                "severity": severity,
                "evidence": evidence,
                "reason": reason
            })

    # Do not add amounts across currencies.
    by_currency = {}

    for calculation in calculations:
        currency = calculation["currency"]

        if currency:
            by_currency[currency] = (
                by_currency.get(currency, 0)
                + calculation["amount"]
            )

    if len(by_currency) == 1:
        currency, total = next(iter(by_currency.items()))
        total = round(total, 2)
    else:
        currency = None
        total = None

        if len(by_currency) > 1:
            uncertainties.append(
                "Amounts use multiple currencies and were not combined "
                "without an exchange rate."
            )
        elif calculations:
            uncertainties.append(
                "Some calculated amounts have no explicit currency; "
                "a comparable total cannot be safely reported."
            )

    # Compare calculated exposure with contract value when possible.
    ratio = None

    if (
        contract_value
        and contract_value["currency"]
        and currency == contract_value["currency"]
        and total is not None
        and contract_value["amount"] > 0
    ):
        ratio = round(
            total / contract_value["amount"],
            6
        )

    # Contextual scoring: relative exposure, clause severity, uncertainty.
    score = 0
    reasons = []

    if ratio is not None:
        if ratio >= 0.25:
            score += 4
            reasons.append(
                "Estimated exposure is at least 25% of stated contract value."
            )
        elif ratio >= 0.10:
            score += 3
            reasons.append(
                "Estimated exposure is at least 10% of stated contract value."
            )
        elif ratio >= 0.03:
            score += 2
            reasons.append(
                "Estimated exposure is at least 3% of stated contract value."
            )
        elif ratio > 0:
            score += 1
            reasons.append(
                "Estimated exposure is below 3% of stated contract value."
            )

    elif calculations:
        score += 1
        reasons.append(
            "Some exposure was calculated, but comparable contract value "
            "is unavailable."
        )

    scored_factors = {}
    for factor in factors:
        points = 7 if factor["severity"] == "High" else 3
        current = scored_factors.get(factor["factor"])
        if current is None or points > current[0]:
            scored_factors[factor["factor"]] = (points, factor["severity"])

    for label, (points, severity) in scored_factors.items():
        score += points
        reasons.append(
            f"{severity} contextual factor: {label}."
        )

    if len(uncertainties) >= 3:
        score += 2
        reasons.append(
            "Several financial terms cannot be calculated reliably "
            "because details are missing or ambiguous."
        )
    elif uncertainties:
        score += 1
        reasons.append(
            "At least one financial term needs clarification before "
            "exposure can be estimated reliably."
        )

    if not items and not factors:
        risk = "Insufficient Information"
        score_output = None
        reason = (
            "No recognizable financial-risk terms were found in extracted "
            "text. Verify text extraction and review manually."
        )
    else:
        score_output = score
        risk = (
            "High" if score >= 7
            else "Medium" if score >= 4
            else "Low"
        )
        reason = " ".join(reasons) or (
            "No significant contextual risk indicators were identified "
            "by the current rules."
        )

    # Conditional scenarios, not predictions that an event will occur.
    for item in items:
        if item["term_type"] in ("penalty", "interest", "renewal"):
            labels = {
                "penalty": "Penalty clause is triggered",
                "interest": "Payment is delayed for the stated duration",
                "renewal": "Contract renewal/extension occurs"
            }

            scenarios.append({
                "scenario": labels[item["term_type"]],
                "estimated_impact": item["calculated_exposure"],
                "currency": (
                    item["amounts"][0]["currency"]
                    if item["amounts"] else None
                ),
                "basis": item["evidence"],
                "conditional": True,
                "note": (
                    None
                    if item["calculated_exposure"] is not None
                    else "Cannot estimate until missing details are clarified."
                )
            })

    return {
        "items": items,
        "calculations": calculations,
        "contract_value": contract_value,
        "total_calculated_exposure": total,
        "exposure_currency": currency,
        "exposure_ratio": ratio,
        "financial_risk": risk,
        "financial_risk_score": score_output,
        "financial_risk_reason": reason,
        "risk_factors": factors,
        "uncertainties": list(dict.fromkeys(uncertainties)),
        "scenarios": scenarios,
        "financial_terms_detected": len(items),
        "analysis_method": (
            "Evidence-linked rules with relative exposure "
            "when contract value is available"
        ),
        "limitations": [
            "Prototype heuristic, not legal advice; expert validation is required.",
            "Currency conversion, taxes, compounding, cross-referenced clauses, "
            "and jurisdiction-specific enforceability are not inferred.",
            "Not every financial clause or unusual drafting pattern will be detected."
        ]
    }