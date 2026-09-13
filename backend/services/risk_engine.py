def calculate_risk(results):
    risk_weights = {
        "High": 3,
        "Medium": 2,
        "Low": 1
    }

    total_score = 0

    for result in results:
        total_score += risk_weights[result["risk"]]

    if total_score >= 18:
        overall_risk = "High"
    elif total_score >= 10:
        overall_risk = "Medium"
    else:
        overall_risk = "Low"

    return {
        "overall_risk": overall_risk,
        "risk_score": total_score
    }


def generate_explanations(results):
    explanations = []

    for result in results:
        if result["status"] == "Missing":
            explanations.append({
                "clause": result["clause"],
                "risk": "High",
                "reason": result["explanation"],
                "impact": f"Missing {result['clause']} terms may create contractual ambiguity or increase business risk.",
                "recommendation": f"Add a clearly defined {result['clause']} clause."
            })

        else:
            explanations.append({
                "clause": result["clause"],
                "risk": result["risk"],
                "reason": result["explanation"],
                "impact": "The required contractual provision has been identified.",
                "recommendation": f"Review the {result['clause']} clause to ensure it meets organizational requirements."
            })

    return explanations