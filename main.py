import os
<<<<<<< HEAD
import tempfile
import torch

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from transformers import AutoTokenizer, AutoModelForSequenceClassification
=======
import sys
import tempfile

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Make `services` importable as a package regardless of the working
# directory the app is launched from (e.g. `uvicorn main:app` from
# inside backend/, or `uvicorn backend.main:app` from the repo root).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
>>>>>>> 15b92ba76e4f02c8cc8e9c68848ebd3d980e6056

from services.document_parser import extract_text
from services.clause_extractor import extract_clauses
from services.compliance_engine import analyze_compliance
from services.risk_engine import calculate_risk, generate_explanations
from services.negotiation_engine import generate_negotiation_suggestions

<<<<<<< HEAD

app = FastAPI(title="Contract Intelligence API")


=======
MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB — matches the frontend's limit
ALLOWED_EXTENSIONS = {".pdf", ".docx"}

app = FastAPI(title="Contract Intelligence API")

# Allow the static frontend (served from a different origin/port during
# development) to call this API. Tighten allow_origins to your deployed
# frontend's URL before shipping to production.
>>>>>>> 15b92ba76e4f02c8cc8e9c68848ebd3d980e6056
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


<<<<<<< HEAD
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


MODELS = {
    "clause": os.path.join(
        BASE_DIR,
        "ml",
        "models",
        "tinybert_clause_classifier"
    ),
    "risk": os.path.join(
        BASE_DIR,
        "ml",
        "models",
        "tinybert_risk_classifier"
    ),
    "compliance": os.path.join(
        BASE_DIR,
        "ml",
        "models",
        "tinybert_compliance_classifier"
    )
}


device = torch.device(
    "cuda" if torch.cuda.is_available() else "cpu"
)


model_cache = {}


def predict(model_type, text):

    if model_type not in model_cache:

        tokenizer = AutoTokenizer.from_pretrained(
            MODELS[model_type]
        )

        model = AutoModelForSequenceClassification.from_pretrained(
            MODELS[model_type]
        )

        model.to(device)
        model.eval()

        model_cache[model_type] = (
            tokenizer,
            model
        )

    tokenizer, model = model_cache[model_type]

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

    probabilities = torch.softmax(
        outputs.logits,
        dim=-1
    )

    confidence, prediction = torch.max(
        probabilities,
        dim=-1
    )

    label = model.config.id2label[
        prediction.item()
    ]

    return label, float(confidence.item())


@app.get("/")
def home():
    return {
        "message": "Contract Intelligence API is running"
    }
=======
@app.get("/")
def home():
    return {"message": "Contract Intelligence API is running"}
>>>>>>> 15b92ba76e4f02c8cc8e9c68848ebd3d980e6056


@app.get("/api/health")
def health():
<<<<<<< HEAD
    return {
        "status": "ok"
    }


@app.post("/api/analyze")
async def analyze_contract(
    file: UploadFile = File(...)
):

    filename = file.filename or ""
    extension = os.path.splitext(filename)[1].lower()

    if extension not in [".pdf", ".docx"]:
        raise HTTPException(
            status_code=400,
            detail="Only PDF and DOCX files are supported."
=======
    """Used by the frontend's 'Test connection' button in API settings."""
    return {"status": "ok"}


@app.post("/api/analyze")
async def analyze_contract(file: UploadFile = File(...)):
    """
    Runs the full pipeline the services/ modules already implement:
    parse -> extract clauses -> check compliance -> score risk
    -> explain -> suggest negotiation language.
    """
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Only .pdf and .docx files are supported.",
>>>>>>> 15b92ba76e4f02c8cc8e9c68848ebd3d980e6056
        )

    contents = await file.read()

    if not contents:
<<<<<<< HEAD
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty."
        )

    temp_path = None

    try:

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=extension
        ) as temp:

            temp.write(contents)
            temp_path = temp.name

        try:
            text = extract_text(temp_path)
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Could not read file: {exc}"
            )
=======
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the 100 MB limit.")

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(contents)
            tmp_path = tmp.name

        try:
            text = extract_text(tmp_path)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Could not read file: {exc}")
>>>>>>> 15b92ba76e4f02c8cc8e9c68848ebd3d980e6056

        if not text.strip():
            raise HTTPException(
                status_code=422,
<<<<<<< HEAD
                detail="No extractable text found in the file."
            )

        clauses = extract_clauses(text)

        clause_predictions = []

        for clause in clauses:

            label, confidence = predict(
                "clause",
                clause["text"]
            )

            clause_predictions.append({
                "type": label,
                "title": clause["title"],
                "text": clause["text"],
                "confidence": round(
                    confidence * 100,
                    2
                )
            })

        compliance = analyze_compliance(
            clauses
        )

        risk = calculate_risk(
            compliance
        )

        explanations = generate_explanations(
            compliance
        )

        negotiation = generate_negotiation_suggestions(
            compliance
        )

        risk_label, risk_confidence = predict(
            "risk",
            text
        )

        compliance_label, compliance_confidence = predict(
            "compliance",
            text
        )

        return {
            "filename": filename,
            "text_length": len(text),
            "clauses": clause_predictions,
            "compliance": compliance,
            "risk": {
                "overall_risk": risk["overall_risk"],
                "risk_score": risk["risk_score"],
                "model_prediction": risk_label,
                "confidence": round(
                    risk_confidence * 100,
                    2
                )
            },
            "compliance_prediction": {
                "status": compliance_label,
                "confidence": round(
                    compliance_confidence * 100,
                    2
                )
            },
            "explanations": explanations,
            "negotiation": negotiation
        }

    finally:

        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
=======
                detail="No extractable text found in the file.",
            )

        clauses = extract_clauses(text)
        compliance = analyze_compliance(clauses)
        risk = calculate_risk(compliance)
        explanations = generate_explanations(compliance)
        negotiation = generate_negotiation_suggestions(compliance)

        return {
            "filename": file.filename,
            "clauses": clauses,
            "compliance": compliance,
            "risk": risk,
            "explanations": explanations,
            "negotiation": negotiation,
        }
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
>>>>>>> 15b92ba76e4f02c8cc8e9c68848ebd3d980e6056
