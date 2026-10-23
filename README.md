# Contract Intelligence

Explainable contract compliance and negotiation intelligence for reviewing uploaded contracts.

## What this project does

This application accepts a real-world PDF or DOCX contract, extracts text, identifies likely contract types, discovers clauses, checks compliance with required contractual terms, scores risk, explains findings, suggests negotiation language, and summarizes financial-risk indicators.

## Supported input

- PDF
- DOCX

The system accepts an original contract document without requiring the user to pre-separate or rename clauses.

## Architecture

- Backend: FastAPI API in `backend/main.py`
- Static frontend: `index.html`, `app.js`, `style.css`
- Service layer: `backend/services/`
- ML models: `ml/models/` when present

## How it works

1. Upload a contract file from the dashboard.
2. The backend validates the file type and size.
3. Text is extracted from the document.
4. The contract-type detector classifies the document using a heuristic baseline.
5. The clause extractor identifies sections and contractual provisions.
6. Compliance/risk/explanation/negotiation engines process the extracted clauses.
7. Financial impact terms are flagged from the text.
8. The Law Analysis module uses the same extracted text and clause evidence to identify explicit governing-law/dispute terms, party names and stated location connections, contract topics, uncertainties, and company-specific contract findings.
9. The dashboard renders the completed analysis, including a dedicated Law Analysis section.

## Law Analysis

The existing authenticated `POST /api/analyze` route now returns an additive `legal_analysis` object alongside the existing clause, risk, compliance, negotiation, and financial-impact fields. It is built from that upload's extracted text and existing clause results; no second upload or pasted text is required.

The dashboard's **Law Analysis** tab shows detected parties and roles, only explicitly supported party-country/location connections, any express governing-law clause, court/arbitration evidence, uncertainty, company-specific contract topics, evidence excerpts, and actions for legal review. Country of incorporation is not treated as the governing law. An express governing-law clause is not represented as excluding other mandatory laws.

The rules-based service recognizes India, the United Kingdom (England and Wales, Scotland, Northern Ireland distinctions), Germany and relevant EU context, the United States (federal/state distinction and selected named states), the United Arab Emirates (mainland/DIFC/ADGM distinctions), Israel, China (mainland/Hong Kong/Macau distinctions), and France and relevant EU context. A jurisdiction appears only when supported by contract text; this is not an exhaustive conflicts-of-law engine. Party-country recognition requires nearby explicit incorporation/office wording.

Official research portals are maintained in `backend/services/legal_sources.py`: India Code; legislation.gov.uk; Gesetze im Internet and EUR-Lex; the U.S. Code and Congress.gov; UAE Legislation, DIFC and ADGM; Israeli government legislation; China's National People's Congress; and Légifrance and EUR-Lex. The response provides source URLs and status. **The module does not currently retrieve, identify, or verify individual statutes, article numbers, quotations, or legal applicability.** It never presents a provision citation as verified. If enabled, the optional live check only checks reachability of each relevant jurisdiction's primary portal and explicitly reports that provisions remain unverified.

To opt in to the primary-portal availability check for relevant jurisdictions, set this before starting the app:

```powershell
$env:LEGAL_SOURCE_LIVE_CHECK = "true"
```

The check is off by default, uses a short timeout, and does not send contract text to external services. A reachable portal is not verification of a legal provision. The service has no LLM component; findings are evidence-oriented summaries and legal issues need qualified counsel review.

## Running the project

From the repository root:

```bash
.\.venv\Scripts\Activate.ps1
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Open `http://127.0.0.1:8000/login` (or the root URL, which redirects to login). Use the app-served pages rather than opening `index.html` directly from disk: the backend enforces dashboard access and session authentication.

## Environment notes

- The project uses the repository virtual environment when available.
- Some ML dependencies such as `torch` and `transformers` may be missing in a local environment. In that case, the backend falls back to rule-based analysis rather than crashing.
- Models are loaded only when their files are present and compatible.

## Scanned PDF OCR on Windows

Text-based PDFs continue to use `pypdf`. When a PDF page has little or no selectable text, the parser OCRs that page only. It preserves the PDF page order and reports which pages needed OCR. OCR is bounded to 60 PDF pages, 180 DPI, 1600 pixels on the long dimension, and 30 seconds per page. A PDF over the page limit is rejected with a clear error; scanned PDFs with no usable OCR output are not reported as successfully analyzed.

The Python packages alone do **not** install the Tesseract or Poppler applications. Install/configure all of the following on Windows:

1. Install the Python packages in the project's environment:

   ```powershell
   .\venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   ```

2. Install **Tesseract OCR** for Windows (for example, the UB Mannheim Windows installer). Add the directory containing `tesseract.exe` to `PATH`, or set the executable path before starting the backend:

   ```powershell
   $env:TESSERACT_CMD = "C:\Program Files\Tesseract-OCR\tesseract.exe"
   ```

3. Install **Poppler for Windows** and add its `Library\bin` directory to `PATH`, or set:

   ```powershell
   $env:POPPLER_PATH = "C:\path\to\poppler\Library\bin"
   ```

   `POPPLER_PATH` is the directory containing `pdftoppm.exe` (or `pdftocairo.exe`), not the executable itself.

Restart the backend after changing `PATH` or either environment variable. If a scanned PDF is uploaded without the Python OCR packages or the Tesseract/Poppler executables, the API returns a specific setup error instead of an empty analysis. OCR quality depends on scan resolution, orientation, language packs, and document quality; review extracted text and findings.

## Testing

Run a focused validation suite from the project root:

```bash
.\venv\Scripts\python -m unittest backend.services.test_ocr_ingestion backend.services.test_contract_analysis
```

The OCR ingestion tests use generated image-only/mixed PDF fixtures and mock the OCR call so they run without installing Tesseract or Poppler. To verify real OCR, install the Windows prerequisites above and upload a scanned PDF through the existing dashboard.

## Known limitations

- Contract-type detection is heuristic and should be treated as a baseline, not a legal classification.
- ML predictions are optional and only used when model files are found.
- Legal analysis is informational and must be reviewed by a qualified professional.
- OCR requires separately installed Tesseract OCR and Poppler Windows applications; the Python packages do not include those binaries.
- The file `document_8.pdf` was not present in the repository when this change was made, so it has not been tested here.

## Sign-in and administrator setup

The project did not have an existing user/account database. Authentication uses a separate SQLite database (default `backend/auth_data/accounts.sqlite3`) and does not touch contract data. The database is initialized with additive `CREATE TABLE IF NOT EXISTS` statements. Passwords are stored as Argon2id hashes. Random opaque session tokens are stored only as SHA-256 hashes in the server-side session table. The session cookie is HTTP-only and `SameSite=Strict`; a separate same-site CSRF cookie is paired with request headers. Sessions expire after 12 hours by default or 30 days when Remember me is selected. Login attempts are throttled after eight failures per account/IP in a 15-minute window. CSRF and origin checks protect login, logout, and contract-analysis POST requests.

There is no public registration or password-reset flow. Create the initial administrator interactively; the password is entered without echo and must be at least 12 characters. Run this in the same PowerShell environment and with the same database path as the application:

```powershell
Set-Location D:\Contract_Intelligence
.\.venv\Scripts\Activate.ps1
$env:AUTH_DATABASE_PATH = "backend\auth_data\accounts.sqlite3"
$env:AUTH_COOKIE_SECURE = "false"
python -m backend.auth create-admin
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

The account command is safe to run again for a different admin username/email; existing users and sessions are not erased. The database path can be changed with `AUTH_DATABASE_PATH`. For HTTPS production, set `APP_ENV=production` or `AUTH_COOKIE_SECURE=true`; do not disable secure cookies on a public deployment. `.env.example` lists supported configuration, but the application reads process environment variables and does not automatically parse `.env`. Do not commit account databases or credentials.

After sign-in, the existing dashboard is served at `/dashboard`; `/index.html` is also protected. `/api/health` remains public for monitoring. The API enforces authentication independently of frontend redirects, so opening a saved dashboard page cannot authorize analysis requests.

## Authentication tests

Run the auth, parser/OCR, and analysis tests:

```powershell
.\.venv\Scripts\python -m unittest backend.test_auth backend.services.test_ocr_ingestion backend.services.test_contract_analysis
```

The authentication tests use a temporary SQLite database and do not create or modify the default application account database. Run the Law Analysis service tests and browser-rendering harness with:

```powershell
.\.venv\Scripts\python -m unittest backend.services.test_law_analysis
node --test test_law_analysis_ui.js
```