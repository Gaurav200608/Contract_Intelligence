REQUIRED_CLAUSES = {
    "Payment": "Payment terms should clearly define fees, invoice timing, and payment deadlines.",
    "Confidentiality": "A confidentiality clause should protect non-public information.",
    "Termination": "Termination conditions and notice periods should be clearly defined.",
    "Intellectual Property": "Ownership of intellectual property and deliverables should be clearly defined.",
    "Data Protection": "The contract should define responsibilities for protecting personal and confidential data.",
    "Liability": "Liability limits and exclusions should be clearly defined.",
    "Dispute Resolution": "The contract should specify how disputes will be resolved.",
    "Governing Law": "The governing law should be explicitly stated."
}


def analyze_compliance(clauses):
    results = []

    detected_types = {clause["type"] for clause in clauses}

    for clause_name, requirement in REQUIRED_CLAUSES.items():

        if clause_name in detected_types:
            matching_clause = next(
                clause for clause in clauses
                if clause["type"] == clause_name
            )

            results.append({
                "clause": clause_name,
                "status": "Compliant",
                "risk": "Low",
                "explanation": f"{clause_name} clause is present in the contract.",
                "requirement": requirement,
                "text": matching_clause["text"]
            })

        else:
            results.append({
                "clause": clause_name,
                "status": "Missing",
                "risk": "High",
                "explanation": f"{clause_name} clause is missing from the contract.",
                "requirement": requirement,
                "text": ""
            })

    return results