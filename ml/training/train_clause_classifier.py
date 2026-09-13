import pandas as pd
import numpy as np
import torch

from datasets import Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    TrainingArguments,
    Trainer
)
from sklearn.metrics import accuracy_score, f1_score

TRAIN_PATH = "ml/dataset/ml_train.csv"
VAL_PATH = "ml/dataset/ml_validation.csv"
MODEL_PATH = "ml/models/tinybert"
OUTPUT_PATH = "ml/models/tinybert_clause_classifier"

train_df = pd.read_csv(TRAIN_PATH)
val_df = pd.read_csv(VAL_PATH)

labels = sorted(train_df["clause_type"].unique())

label2id = {label: i for i, label in enumerate(labels)}
id2label = {i: label for label, i in label2id.items()}

train_df["label"] = train_df["clause_type"].map(label2id)
val_df["label"] = val_df["clause_type"].map(label2id)

train_dataset = Dataset.from_pandas(
    train_df[["text", "label"]],
    preserve_index=False
)

val_dataset = Dataset.from_pandas(
    val_df[["text", "label"]],
    preserve_index=False
)

tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)

def tokenize(batch):
    return tokenizer(
        batch["text"],
        padding="max_length",
        truncation=True,
        max_length=256
    )

train_dataset = train_dataset.map(tokenize, batched=True)
val_dataset = val_dataset.map(tokenize, batched=True)

train_dataset = train_dataset.remove_columns(["text"])
val_dataset = val_dataset.remove_columns(["text"])

model = AutoModelForSequenceClassification.from_pretrained(
    MODEL_PATH,
    num_labels=len(labels),
    id2label=id2label,
    label2id=label2id
)

def compute_metrics(eval_pred):
    predictions, labels_true = eval_pred

    predictions = np.argmax(predictions, axis=1)

    accuracy = accuracy_score(labels_true, predictions)
    f1 = f1_score(
        labels_true,
        predictions,
        average="weighted"
    )

    return {
        "accuracy": accuracy,
        "f1": f1
    }

training_args = TrainingArguments(
    output_dir=OUTPUT_PATH,
    eval_strategy="epoch",
    save_strategy="epoch",
    learning_rate=2e-5,
    per_device_train_batch_size=8,
    per_device_eval_batch_size=8,
    num_train_epochs=3,
    weight_decay=0.01,
    logging_steps=50,
    load_best_model_at_end=True,
    metric_for_best_model="f1",
    greater_is_better=True,
    fp16=True,
    report_to="none"
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_dataset,
    eval_dataset=val_dataset,
    processing_class=tokenizer,
    compute_metrics=compute_metrics
)

print("Training device:", "cuda" if torch.cuda.is_available() else "cpu")
print("GPU:", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "None")
print("Number of classes:", len(labels))
print("Classes:", labels)
print("Training samples:", len(train_dataset))
print("Validation samples:", len(val_dataset))

trainer.train()

trainer.save_model(OUTPUT_PATH)
tokenizer.save_pretrained(OUTPUT_PATH)

print("Training completed successfully.")
print("Model saved to:", OUTPUT_PATH)