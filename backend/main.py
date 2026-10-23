import os
import secrets
import sys
import tempfile
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from backend.auth import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    AuthenticatedUser,
    authenticate,
    csrf_valid,
    ensure_csrf_token,
    get_session,
    revoke_session,
)

try:
    import torch
except Exception:  # pragma: no cover - optional dependency
    torch = None

try:
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
except Exception:  # pragma: no cover - optional dependency
    AutoTokenizer = None
    AutoModelForSequenceClassification = None

from backend.services.clause_extractor import extract_clauses
from backend.services.compliance_engine import analyze_compliance
from backend.services.contract_type_detector import detect_contract_type
from backend.services.document_parser import (
    DocumentExtractionError,
    extract_document,
)
from backend.services.financial_impact_engine import analyze_financial_impact
from backend.services.law_analysis import analyze_law_context
from backend.services.negotiation_engine import generate_negotiation_suggestions
from backend.services.risk_engine import calculate_risk, generate_explanations

app = FastAPI(title="Contract Intelligence API")
FRONTEND_DIR = Path(ROOT_DIR)

MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx"}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = ROOT_DIR
MODELS = {
    "clause": os.path.join(BASE_DIR, "ml", "models", "tinybert_clause_classifier"),
    "risk": os.path.join(BASE_DIR, "ml", "models", "tinybert_risk_classifier"),
    "compliance": os.path.join(BASE_DIR, "ml", "models", "tinybert_compliance_classifier"),
}
model_cache = {}


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=1024)
    remember_me: bool = False


def secure_cookies() -> bool:
    configured = os.environ.get("AUTH_COOKIE_SECURE")
    if configured is not None:
        return configured.strip().lower() in {"1", "true", "yes", "on"}
    return os.environ.get("APP_ENV", "development").lower() == "production"


def set_csrf_cookie(response, token: str) -> None:
    response.set_cookie(
        CSRF_COOKIE,
        token,
        httponly=False,
        secure=secure_cookies(),
        samesite="strict",
        path="/",
        max_age=30 * 24 * 60 * 60,
    )


def delete_auth_cookies(response) -> None:
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        secure=secure_cookies(),
        httponly=True,
        samesite="strict",
    )
    response.delete_cookie(
        CSRF_COOKIE,
        path="/",
        secure=secure_cookies(),
        httponly=False,
        samesite="strict",
    )


def require_authenticated_user(request: Request) -> AuthenticatedUser:
    user = get_session(request.cookies.get(SESSION_COOKIE))
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return user


def require_csrf(request: Request, user: AuthenticatedUser | None = None) -> None:
    origin = request.headers.get("Origin")
    if origin and origin.rstrip("/") != str(request.base_url).rstrip("/"):
        raise HTTPException(status_code=403, detail="CSRF validation failed. Refresh and try again.")
    if request.headers.get("Sec-Fetch-Site", "").lower() == "cross-site":
        raise HTTPException(status_code=403, detail="CSRF validation failed. Refresh and try again.")
    session = user or get_session(request.cookies.get(SESSION_COOKIE))
    if not csrf_valid(
        session,
        request.cookies.get(CSRF_COOKIE, ""),
        request.headers.get("X-CSRF-Token", ""),
    ):
        raise HTTPException(status_code=403, detail="CSRF validation failed. Refresh and try again.")


def model_available() -> bool:
    return (
        torch is not None
        and AutoTokenizer is not None
        and AutoModelForSequenceClassification is not None
    )


def predict(model_type: str, text: str):
    if not model_available():
        return "Unavailable", 0.0
    if model_type not in MODELS:
        return "Unavailable", 0.0
    if model_type not in model_cache and os.path.isdir(MODELS[model_type]):
        try:
            tokenizer = AutoTokenizer.from_pretrained(MODELS[model_type])
            model = AutoModelForSequenceClassification.from_pretrained(MODELS[model_type])
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            model.to(device)
            model.eval()
            model_cache[model_type] = (tokenizer, model, device)
        except Exception:
            return "Unavailable", 0.0

    if model_type not in model_cache:
        return "Unavailable", 0.0

    tokenizer, model, device = model_cache[model_type]
    try:
        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=256)
        inputs = {key: value.to(device) for key, value in inputs.items()}
        with torch.no_grad():
            output = model(**inputs)
        probabilities = torch.softmax(output.logits, dim=-1)
        confidence, prediction = torch.max(probabilities, dim=-1)
        label = model.config.id2label[prediction.item()]
        return label, float(confidence.item())
    except Exception:
        return "Unavailable", 0.0


@app.get("/")
def home(request: Request):
    user = get_session(request.cookies.get(SESSION_COOKIE))
    return RedirectResponse("/dashboard" if user else "/login", status_code=303)


@app.get("/login", include_in_schema=False)
def login_page():
    return FileResponse(
        FRONTEND_DIR / "login.html",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/dashboard", include_in_schema=False)
@app.get("/index.html", include_in_schema=False)
def dashboard_page(request: Request):
    if get_session(request.cookies.get(SESSION_COOKIE)) is None:
        return RedirectResponse("/login", status_code=303)
    return FileResponse(
        FRONTEND_DIR / "index.html",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/style.css", include_in_schema=False)
def dashboard_stylesheet():
    return FileResponse(
        FRONTEND_DIR / "style.css",
        media_type="text/css",
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/app.js", include_in_schema=False)
def dashboard_script():
    return FileResponse(
        FRONTEND_DIR / "app.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/login.js", include_in_schema=False)
def login_script():
    return FileResponse(
        FRONTEND_DIR / "login.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)


@app.get("/api/auth/csrf")
def csrf_token(request: Request):
    session_token = request.cookies.get(SESSION_COOKIE)
    user = get_session(session_token)
    if user:
        token = ensure_csrf_token(
            session_token, user, request.cookies.get(CSRF_COOKIE, "")
        )
    else:
        token = request.cookies.get(CSRF_COOKIE) or secrets.token_urlsafe(32)
    response = JSONResponse(
        {"csrf_token": token},
        headers={"Cache-Control": "no-store"},
    )
    set_csrf_cookie(response, token)
    return response


@app.post("/api/auth/login")
def login(payload: LoginRequest, request: Request):
    require_csrf(request)
    client_ip = request.client.host if request.client else "unknown"
    user, limited = authenticate(
        payload.username,
        payload.password,
        payload.remember_me,
        client_ip,
    )
    if limited:
        raise HTTPException(
            status_code=429,
            detail="Too many sign-in attempts. Wait 15 minutes and try again.",
            headers={"Retry-After": "900"},
        )
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid username/email or password.")

    from backend.auth import REMEMBER_SECONDS

    revoke_session(request.cookies.get(SESSION_COOKIE))

    response = JSONResponse(
        {
            "authenticated": True,
            "user": {
                "username": user.username,
                "email": user.email,
                "role": user.role,
            },
            "csrf_token": user.csrf_token,
        },
        headers={"Cache-Control": "no-store"},
    )
    response.set_cookie(
        SESSION_COOKIE,
        user.session_token,
        max_age=REMEMBER_SECONDS if payload.remember_me else None,
        httponly=True,
        secure=secure_cookies(),
        samesite="strict",
        path="/",
    )
    set_csrf_cookie(response, user.csrf_token)
    return response


@app.get("/api/auth/status")
def auth_status(request: Request):
    session_token = request.cookies.get(SESSION_COOKIE)
    user = get_session(session_token)
    if user is None:
        response = JSONResponse(
            {"authenticated": False},
            headers={"Cache-Control": "no-store"},
        )
        if session_token:
            delete_auth_cookies(response)
        return response
    csrf = ensure_csrf_token(
        session_token, user, request.cookies.get(CSRF_COOKIE, "")
    )
    response = JSONResponse(
        {
            "authenticated": True,
            "user": {
                "username": user.username,
                "email": user.email,
                "role": user.role,
            },
            "csrf_token": csrf,
        },
        headers={"Cache-Control": "no-store"},
    )
    set_csrf_cookie(response, csrf)
    return response


@app.post("/api/auth/logout")
def logout(request: Request, user: AuthenticatedUser = Depends(require_authenticated_user)):
    require_csrf(request, user)
    revoke_session(request.cookies.get(SESSION_COOKIE))
    response = JSONResponse({"authenticated": False})
    delete_auth_cookies(response)
    return response


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/analyze")
async def analyze_contract(
    request: Request,
    file: UploadFile = File(...),
    user: AuthenticatedUser = Depends(require_authenticated_user),
):
    require_csrf(request, user)
    if file is None:
        raise HTTPException(status_code=400, detail="No file was uploaded.")

    filename = os.path.basename(file.filename or "")
    extension = os.path.splitext(filename)[1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported.")

    contents = await file.read(MAX_FILE_SIZE_BYTES + 1)
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="Uploaded file is too large.")
    if extension == ".pdf" and b"%PDF-" not in contents[:1024]:
        raise HTTPException(status_code=422, detail="The uploaded file is not a valid PDF.")
    if extension == ".docx" and not contents.startswith(b"PK"):
        raise HTTPException(status_code=422, detail="The uploaded file is not a valid DOCX.")

    warnings = []
    if not model_available():
        warnings.append(
            "TinyBERT model dependencies are not available in this environment; rule-based analysis is being used."
        )

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=extension, prefix="contract_") as temp:
            temp.write(contents)
            temp_path = temp.name

        try:
            extracted = extract_document(temp_path)
            text = extracted["text"]
        except DocumentExtractionError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        except Exception as exc:  # pragma: no cover - defensive handling
            raise HTTPException(status_code=422, detail="The uploaded document could not be processed.") from exc

        if not text.strip():
            raise HTTPException(status_code=422, detail="No extractable text was found in the document.")

        clauses = extract_clauses(text)
        contract_type = detect_contract_type(text, clauses)
        warnings.extend(extracted["summary"].get("warnings", []))

        if not clauses:
            warnings.append("No clauses were extracted from the document.")

        clause_predictions = []
        for clause in clauses:
            label, confidence = predict("clause", clause["text"])
            classification_method = "tinybert"
            if label == "Unavailable":
                label = clause["type"]
                confidence = None
                classification_method = "heuristic"
            clause_predictions.append({
                "type": label,
                "title": clause["title"],
                "text": clause["text"],
                "confidence": round(confidence * 100, 2) if confidence is not None else None,
                "classification_method": classification_method,
            })

        compliance = analyze_compliance(clauses)
        risk = calculate_risk(compliance)
        explanations = generate_explanations(compliance)
        negotiation = generate_negotiation_suggestions(compliance)
        financial_impact = analyze_financial_impact(text)

        risk_label, risk_confidence = predict("risk", text)
        compliance_label, compliance_confidence = predict("compliance", text)

        legal_analysis = analyze_law_context(
            text,
            contract_type.get("category", "Other/Unknown"),
            clause_predictions,
        )

        return {
            "filename": filename,
            "text_length": len(text),
            "contract_type": contract_type,
            "warnings": warnings,
            "extraction_summary": extracted["summary"],
            "clauses": clause_predictions,
            "compliance": compliance,
            "risk": {
                "overall_risk": risk["overall_risk"],
                "risk_score": risk["risk_score"],
                "model_prediction": risk_label,
                "confidence": round(risk_confidence * 100, 2),
            },
            "compliance_prediction": {
                "status": compliance_label,
                "confidence": round(compliance_confidence * 100, 2),
            },
            "explanations": explanations,
            "negotiation": negotiation,
            "financial_impact": financial_impact,
            "legal_analysis": legal_analysis,
        }
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
