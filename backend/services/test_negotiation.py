from document_parser import extract_text
from clause_extractor import extract_clauses
from compliance_engine import analyze_compliance
from negotiation_engine import generate_negotiation_suggestions


file_path = "data/sample_contracts/sample_contract.pdf"

text = extract_text(file_path)

clauses = extract_clauses(text)

results = analyze_compliance(clauses)

suggestions = generate_negotiation_suggestions(results)

print("\n--- NEGOTIATION INTELLIGENCE ---\n")

for item in suggestions:
    print("CLAUSE:", item["clause"])
    print("PRIORITY:", item["priority"])
    print("SUGGESTION:", item["suggestion"])
    print("SUGGESTED WORDING:", item["suggested_wording"])
    print("-" * 60)