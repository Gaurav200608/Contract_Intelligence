from document_parser import extract_text
from clause_extractor import extract_clauses

file_path = "data/sample_contracts/sample_contract.pdf"

text = extract_text(file_path)

clauses = extract_clauses(text)

print("\n--- EXTRACTED CLAUSES ---\n")

for clause in clauses:
    print("TYPE:", clause["type"])
    print("TITLE:", clause["title"])
    print("TEXT:", clause["text"])
    print("-" * 60)