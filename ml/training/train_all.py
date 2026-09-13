import os
import json
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

BASE = "ml/dataset"
TINYBERT = "ml/models/tinybert"

FULL_DATA = f"{BASE}/cuad_project_dataset.csv"
TRAIN_DATA = f"{BASE}/ml_train.csv"
VAL_DATA = f"{BASE}/ml_validation.csv"

device = "cuda" if torch.cuda.is_available() else "cpu"

print("=" * 60)
print("FULL CONTRACT INTELLIGENCE FINE-TUNING")
print("=" * 60)
print("Device:", device)

if torch.cuda.is_available():
    print("GPU:", torch.cuda.get_device_name(0))

full_df = pd.read_csv(FULL_DATA)
train_df = pd.read_csv(TRAIN_DATA)
val_df = pd.read_csv(VAL_DATA)

def train_classifier(
    train_df,
    val_df,
    column,
    labels,
    output_name
):
    print("\n" + "=" * 60)
    print("TRAINING:", column)
    print("=" * 60)

    label2id = {label: i for i, label in enumerate(labels)}
    id2label = {i: label for label, i in label2id.items()}

    train = train_df[["text", column]].dropna().copy()
    val = val_df[["text", column]].dropna().copy()

    train["label"] = train[column].map(label2id)
    val["label"] = val[column].map(label2id)

    train = train.dropna()
    val = val.dropna()

    train["label"] = train["label"].astype(int)
    val["label"] = val["label"].astype(int)

    train_dataset = Dataset.from_pandas(
        train[["text", "label"]],
        preserve_index=False
    )

    val_dataset = Dataset.from_pandas(
        val[["text", "label"]],
        preserve_index=False
    )

    tokenizer = AutoTokenizer.from_pretrained(TINYBERT)

    def tokenize(batch):
        return tokenizer(
            batch["text"],
            padding="max_length",
            truncation=True,
            max_length=256
        )

    train_dataset = train_dataset.map(
        tokenize,
        batched=True
    )

    val_dataset = val_dataset.map(
        tokenize,
        batched=True
    )

    train_dataset = train_dataset.remove_columns(["text"])
    val_dataset = val_dataset.remove_columns(["text"])

    model = AutoModelForSequenceClassification.from_pretrained(
        TINYBERT,
        num_labels=len(labels),
        id2label=id2label,
        label2id=label2id
    )

    def compute_metrics(eval_pred):
        predictions, true_labels = eval_pred
        predictions = np.argmax(predictions, axis=1)

        return {
            "accuracy": accuracy_score(
                true_labels,
                predictions
            ),
            "f1": f1_score(
                true_labels,
                predictions,
                average="weighted",
                zero_division=0
            )
        }

    output_path = f"ml/models/{output_name}"

    training_args = TrainingArguments(
        output_dir=output_path,
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
        fp16=torch.cuda.is_available(),
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

    print("Classes:", labels)
    print("Training samples:", len(train_dataset))
    print("Validation samples:", len(val_dataset))

    trainer.train()

    trainer.save_model(output_path)
    tokenizer.save_pretrained(output_path)

    with open(
        f"{output_path}/labels.json",
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            {
                "label2id": label2id,
                "id2label": id2label
            },
            f,
            indent=4
        )

    print("Completed:", column)
    print("Saved:", output_path)

    return trainer


print("\nFULL DATASET")
print("Rows:", len(full_df))
print("Columns:", list(full_df.columns))

risk_train = train_df.copy()
risk_val = val_df.copy()

train_classifier(
    risk_train,
    risk_val,
    "risk_level",
    ["High", "Low", "Medium"],
    "tinybert_risk_classifier"
)

print("\nPreparing compliance dataset...")

compliance_columns = [
    "id",
    "text",
    "compliance_status"
]

compliance_df = full_df[compliance_columns].dropna()

train_ids = set(train_df["id"])
val_ids = set(val_df["id"])

compliance_train = compliance_df[
    compliance_df["id"].isin(train_ids)
].copy()

compliance_val = compliance_df[
    compliance_df["id"].isin(val_ids)
].copy()

train_classifier(
    compliance_train,
    compliance_val,
    "compliance_status",
    [
        "Compliant",
        "Needs Review",
        "Non-Compliant"
    ],
    "tinybert_compliance_classifier"
)

print("\n" + "=" * 60)
print("PREPARING NEGOTIATION KNOWLEDGE")
print("=" * 60)

negotiation_columns = [
    "id",
    "text",
    "clause_type",
    "risk_level",
    "compliance_status",
    "explanation",
    "recommendation",
    "negotiation_suggestion",
    "suggested_wording"
]

negotiation_df = full_df[negotiation_columns].copy()

negotiation_df = negotiation_df.fillna("")

os.makedirs(
    "ml/models/negotiation_knowledge",
    exist_ok=True
)

negotiation_df.to_json(
    "ml/models/negotiation_knowledge/negotiation_rules.json",
    orient="records",
    indent=2
)

print(
    "Negotiation knowledge saved to:",
    "ml/models/negotiation_knowledge/negotiation_rules.json"
)

print("\n" + "=" * 60)
print("ALL FINE-TUNING / MODEL PREPARATION COMPLETED")
print("=" * 60)

print("\nModels:")
print("1. ml/models/tinybert_clause_classifier")
print("2. ml/models/tinybert_risk_classifier")
print("3. ml/models/tinybert_compliance_classifier")
print("4. ml/models/negotiation_knowledge")

print("\nContract Intelligence ML pipeline ready.")