import os
import sys
import tempfile

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Make `services` importable as a package regardless of the working
# directory the app is launched from (e.g. `uvicorn main:app` from
# inside backend/, or `uvicorn backend.main:app` from the repo root).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.document_parser import extract_text
from services.clause_extractor import extract_clauses
from services.compliance_engine import analyze_compliance
from services.risk_engine import calculate_risk, generate_explanations
from services.negotiation_engine import generate_negotiation_suggestions

MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB — matches the frontend's limit
ALLOWED_EXTENSIONS = {".pdf", ".docx"}

app = FastAPI(title="Contract Intelligence API")

# Allow the static frontend (served from a different origin/port during
# development) to call this API. Tighten allow_origins to your deployed
# frontend's URL before shipping to production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return {"message": "Contract Intelligence API is running"}


@app.get("/api/health")
def health():
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
        )

    contents = await file.read()

    if not contents:
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

        if not text.strip():
            raise HTTPException(
                status_code=422,
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
