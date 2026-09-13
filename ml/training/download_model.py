from transformers import AutoTokenizer, AutoModel

model_name = "huawei-noah/TinyBERT_General_4L_312D"

tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModel.from_pretrained(model_name)

tokenizer.save_pretrained("ml/models/tinybert")
model.save_pretrained("ml/models/tinybert")

print("TinyBERT downloaded successfully.")