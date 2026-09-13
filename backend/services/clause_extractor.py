import re


CLAUSE_PATTERNS = {
    "Payment": r"(?i)(payment terms?|payment|fees?|invoice|late payment)",
    "Confidentiality": r"(?i)(confidentiality|confidential|non-disclosure|nda)",
    "Termination": r"(?i)(termination|terminate|notice period)",
    "Intellectual Property": r"(?i)(intellectual property|ownership|source code|deliverables)",
    "Data Protection": r"(?i)(data protection|personal data|data breach|privacy)",
    "Liability": r"(?i)(limitation of liability|liability|damages)",
    "Dispute Resolution": r"(?i)(dispute resolution|arbitration|jurisdiction)",
    "Governing Law": r"(?i)(governing law|laws of)",
    "Non-Solicitation": r"(?i)(non-solicitation|solicit for employment)",
    "Services": r"(?i)(scope of services|services)"
}


def extract_clauses(text):
    clauses = []

    sections = re.split(r"\n(?=\d+\.\s)", text)

    for section in sections:
        section = section.strip()

        if not section:
            continue

        first_line = section.split("\n")[0].strip()

        clause_type = "Other"

        for name, pattern in CLAUSE_PATTERNS.items():
            if re.search(pattern, section):
                clause_type = name
                break

        clauses.append({
            "type": clause_type,
            "title": first_line,
            "text": section
        })

    return clauses