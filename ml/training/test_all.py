import json
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

MODELS = {
    "Clause": "ml/models/tinybert_clause_classifier",
    "Risk": "ml/models/tinybert_risk_classifier",
    "Compliance": "ml/models/tinybert_compliance_classifier"
}

text = """
The Service Provider shall protect all confidential information received
from the Client and shall not disclose such information to any third party.
The Client shall pay all invoices within 30 days of receipt. Either party
may terminate this agreement by providing 30 days written notice.
The Service Provider shall implement reasonable security measures and notify
the Client of any confirmed data breach without undue delay.
"""

print("=" * 70)
print("CONTRACT INTELLIGENCE MODEL TEST")
print("=" * 70)

print("\nInput Contract Clause:")
print(text.strip())

print("\nDevice:", device)

if torch.cuda.is_available():
    print("GPU:", torch.cuda.get_device_name(0))


def predict(model_path, text):
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForSequenceClassification.from_pretrained(model_path)

    model.to(device)
    model.eval()

    inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        max_length=256
    )

    inputs = {
        key: value.to(device)
        for key, value in inputs.items()
    }

    with torch.no_grad():
        outputs = model(**inputs)

    probabilities = torch.softmax(outputs.logits, dim=-1)
    confidence, prediction = torch.max(probabilities, dim=-1)

    label = model.config.id2label[prediction.item()]

    return label, confidence.item()


for name, path in MODELS.items():
    print("\n" + "-" * 70)
    print(name.upper() + " PREDICTION")
    print("-" * 70)

    label, confidence = predict(path, text)

    print("Prediction:", label)
    print("Confidence:", f"{confidence * 100:.2f}%")

print("\n" + "=" * 70)
print("NEGOTIATION KNOWLEDGE TEST")
print("=" * 70)

with open(
    "ml/models/negotiation_knowledge/negotiation_rules.json",
    "r",
    encoding="utf-8"
) as f:
    negotiation_data = json.load(f)

matches = []

keywords = [
    "confidential",
    "payment",
    "termination",
    "data breach",
    "security"
]

for item in negotiation_data:
    item_text = item["text"].lower()

    if any(keyword in item_text for keyword in keywords):
        matches.append(item)

for item in matches[:5]:
    print("\nClause Type:", item["clause_type"])
    print("Risk:", item["risk_level"])
    print("Compliance:", item["compliance_status"])
    print("Explanation:", item["explanation"])
    print("Recommendation:", item["recommendation"])
    print("Negotiation:", item["negotiation_suggestion"])

    if item["suggested_wording"]:
        print("Suggested Wording:", item["suggested_wording"])

print("\n" + "=" * 70)
print("TEST COMPLETED")
print("=" * 70)