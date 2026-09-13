import pandas as pd
from pathlib import Path

base = Path("ml/dataset")

full = pd.read_csv(base / "cuad_project_dataset.csv")

labels = full[["id", "clause_type"]].drop_duplicates("id")

for filename in ["ml_validation.csv", "ml_test.csv"]:
    path = base / filename

    df = pd.read_csv(path)

    if "clause_type" not in df.columns:
        df = df.merge(
            labels,
            on="id",
            how="left",
            validate="one_to_one"
        )

    df = df[["id", "text", "clause_type", "risk_level"]]

    df.to_csv(path, index=False)

    print(filename)
    print("Shape:", df.shape)
    print("Missing clause_type:", df["clause_type"].isna().sum())
    print()

print("Validation and test datasets fixed successfully.")