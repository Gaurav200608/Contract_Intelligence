NEGOTIATION_RULES = {
    "Payment": {
        "suggestion": "Request a clear payment deadline and protection against excessive payment delays.",
        "wording": "Invoices shall be payable within 30 days of receipt. Late payments may be subject to reasonable interest."
    },
    "Confidentiality": {
        "suggestion": "Request a confidentiality clause covering business, technical, financial, and customer information.",
        "wording": "Each party shall protect all confidential information received from the other party and shall not disclose it without authorization."
    },
    "Termination": {
        "suggestion": "Request a clearly defined termination notice period and cure period for breaches.",
        "wording": "Either party may terminate this Agreement by providing 30 days' written notice. Material breaches shall have a 15-day cure period."
    },
    "Intellectual Property": {
        "suggestion": "Clarify ownership of deliverables while protecting each party's pre-existing intellectual property.",
        "wording": "Project-specific deliverables shall belong to the Client after full payment. Pre-existing intellectual property shall remain with its original owner."
    },
    "Data Protection": {
        "suggestion": "Request explicit responsibilities for data security and breach notification.",
        "wording": "The Service Provider shall implement reasonable security measures and notify the Client of confirmed data breaches without undue delay."
    },
    "Liability": {
        "suggestion": "Negotiate specific exceptions to the general liability cap for serious contractual violations.",
        "wording": "The general liability limitation shall not apply to confidentiality breaches, data-protection violations, or infringement of intellectual property rights."
    },
    "Dispute Resolution": {
        "suggestion": "Request a clear dispute-resolution process with negotiation followed by arbitration or court proceedings.",
        "wording": "The parties shall first attempt good-faith negotiation. Unresolved disputes shall be referred to arbitration."
    },
    "Governing Law": {
        "suggestion": "Ensure the governing law and jurisdiction are explicitly stated and commercially acceptable.",
        "wording": "This Agreement shall be governed by the laws of India and subject to the agreed jurisdiction."
    }
}


def generate_negotiation_suggestions(results):
    suggestions = []

    for result in results:
        clause = result["clause"]

        if clause not in NEGOTIATION_RULES:
            continue

        rule = NEGOTIATION_RULES[clause]

        if result["status"] == "Missing":
            priority = "High"
        elif result["risk"] == "Medium":
            priority = "Medium"
        else:
            priority = "Low"

        suggestions.append({
            "clause": clause,
            "priority": priority,
            "suggestion": rule["suggestion"],
            "suggested_wording": rule["wording"]
        })

    return suggestions