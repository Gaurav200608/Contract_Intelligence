from document_parser import extract_text
from clause_extractor import extract_clauses
from compliance_engine import analyze_compliance


file_path = "data/sample_contracts/sample_contract.pdf"

text = extract_text(file_path)

clauses = extract_clauses(text)

results = analyze_compliance(clauses)

print("\n--- COMPLIANCE ANALYSIS ---\n")

for result in results:
    print("CLAUSE:", result["clause"])
    print("STATUS:", result["status"])
    print("RISK:", result["risk"])
    print("EXPLANATION:", result["explanation"])
    print()