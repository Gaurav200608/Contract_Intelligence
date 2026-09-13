import torch
from transformers import AutoTokenizer, AutoModel

model_path = "ml/models/tinybert"

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

tokenizer = AutoTokenizer.from_pretrained(model_path)
model = AutoModel.from_pretrained(model_path)

model = model.to(device)

text = "The service provider shall protect confidential information."

inputs = tokenizer(
    text,
    return_tensors="pt",
    padding=True,
    truncation=True
)

inputs = {key: value.to(device) for key, value in inputs.items()}

with torch.no_grad():
    outputs = model(**inputs)

print("Device:", device)
print("GPU:", torch.cuda.get_device_name(0))
print("Output shape:", outputs.last_hidden_state.shape)
print("TinyBERT GPU test successful.")