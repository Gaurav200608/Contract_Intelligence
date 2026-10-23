import re
from typing import Dict, List


CLAUSE_PATTERNS: Dict[str, str] = {
    "Payment": r"(?i)(payment terms?|fees?|invoice|late payment|payable|withholding)",
    "Confidentiality": r"(?i)(confidentiality|confidential|non-disclosure|nda|proprietary information)",
    "Termination": r"(?i)(termination|terminate|notice period|breach|cure period)",
    "Intellectual Property": r"(?i)(intellectual property|ownership|source code|deliverables|copyright|patent)",
    "Data Protection": r"(?i)(data protection|personal data|data breach|privacy|processing of personal data)",
    "Liability": r"(?i)(limitation of liability|liability|damages|indemnity|cap on liability)",
    "Dispute Resolution": r"(?i)(dispute resolution|arbitration|jurisdiction|venue)",
    "Governing Law": r"(?i)(governing law|laws of|applicable law)",
    "Non-Solicitation": r"(?i)(non-solicitation|solicit for employment|non-compete)",
    "Services": r"(?i)(scope of services|service(s)?|deliverables|performance standards)",
    "Insurance": r"(?i)(insurance|coverage|premium|claims)",
    "Assignment": r"(?i)(assignment|transfer|novation)",
    "Warranties": r"(?i)(warranty|guarantee|representations and warranties)",
    "Force Majeure": r"(?i)(force majeure|unforeseeable circumstances)",
}


def _split_sections(text: str) -> List[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    blocks = []
    for chunk in re.split(r"\n\s*\n+", normalized):
        if not chunk.strip():
            continue
        blocks.append(chunk.strip())

    sections: List[str] = []
    for block in blocks:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if not lines:
            continue

        # Numbered clauses such as "12. Termination" or "12.1 Payment".
        if re.match(r"^(?:\d+|\d+\.\d+)[\.)]?\s+", lines[0], re.I):
            sections.append(block)
            continue

        # Headings and their subsequent paragraphs are treated as a coherent section.
        if re.match(r"^(?:[A-Z][A-Za-z0-9 &/()-]+|[A-Z][A-Za-z0-9 &/()-]+:)", lines[0]) and len(lines) > 1:
            sections.append(block)
            continue

        # Unnumbered but meaningful paragraphs are kept as sections when they are not too short.
        if len(block) > 150:
            sections.append(block)
            continue

        # Fall back to sentence-based chunks so small sections aren't discarded.
        sentences = re.split(r"(?<=[.!?])\s+", block)
        for sentence in sentences:
            if sentence.strip():
                sections.append(sentence.strip())

    return sections


def _detect_clause_type(section: str) -> str:
    for name, pattern in CLAUSE_PATTERNS.items():
        if re.search(pattern, section):
            return name
    return "Other/Unknown"


def extract_clauses(text):
    if not text or not text.strip():
        return []

    clauses = []
    for section in _split_sections(text):
        section = section.strip()
        if not section:
            continue

        title = section.split("\n")[0].strip()
        title = re.sub(r"^(?:\d+(?:[.\)]\d*)?\s+)?", "", title)
        title = title.strip(" -:;") or "Section"

        clause_type = _detect_clause_type(section)
        clauses.append({
            "type": clause_type,
            "title": title,
            "text": section,
            "source": "heuristic",
        })

    if not clauses:
        clauses.append({
            "type": "Other/Unknown",
            "title": "Document",
            "text": text.strip(),
            "source": "heuristic",
        })

    return clauses