from document_parser import extract_text
from clause_extractor import extract_clauses
from compliance_engine import analyze_compliance
from risk_engine import calculate_risk, generate_explanations


file_path = "data/sample_contracts/sample_contract.pdf"

text = extract_text(file_path)

clauses = extract_clauses(text)

results = analyze_compliance(clauses)

risk = calculate_risk(results)

explanations = generate_explanations(results)

print("\n--- OVERALL RISK ---\n")
print("Risk Level:", risk["overall_risk"])
print("Risk Score:", risk["risk_score"])

print("\n--- EXPLAINABLE ANALYSIS ---\n")

for item in explanations:
    print("CLAUSE:", item["clause"])
    print("RISK:", item["risk"])
    print("REASON:", item["reason"])
    print("IMPACT:", item["impact"])
    print("RECOMMENDATION:", item["recommendation"])
    print("-" * 60)