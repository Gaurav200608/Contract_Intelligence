from document_parser import extract_text

file_path = "data/sample_contracts/sample_contract.pdf"

text = extract_text(file_path)

print("\n--- EXTRACTED TEXT ---\n")
print(text[:3000])