# Legal-source audit, gap report, and coverage

## Repository audit

The existing application is a FastAPI contract-analysis service, not a new app scaffold. The active API is `backend/main.py`; the root `main.py` is a separate legacy entry point. The current authenticated `POST /api/analyze` route validates PDF/DOCX uploads, calls the existing parser/OCR service, clause extractor, contract-type detector, TinyBERT prediction wrapper, compliance/risk/explanation/negotiation engines, and financial-impact engine.

The existing service `backend/services/law_analysis.py` extracts contract-supported parties, governing-law and dispute-resolution wording, jurisdictional context, and clause/topic evidence. Before this work, `backend/services/legal_sources.py` only exposed portal links and an optional reachability check. It did not retrieve statutes or preserve official provisions. The dashboard already had a Law Analysis page and client-side text-safe rendering; this implementation extends that page instead of replacing it.

`index.html`, `app.js`, and `style.css` are the root dashboard assets served by FastAPI. The active analysis response had no retrieved legal document schema or source-text store. Existing `backend/services/test_law_analysis.py` and `test_law_analysis_ui.js` cover the old analysis/display; the repository uses `unittest` and Node's built-in test runner. Both `.venv` and `venv` exist: `.venv` has FastAPI, `requests`, and parser packages but no `torch`/`transformers`; `venv` contains the model dependencies. No dependency manifest change is required because the retrieval connector uses the already-installed `requests` package and Python's built-in SQLite/XML modules.

## Implemented scope

- Added a metadata registry with individual entries for the required national, regional, EU, and international sources. Each entry declares organization, official URL, retrieval method, supported document types/subjects/query methods, text/version coverage, limitations, and connector status. Manual-only entries are not represented as working integrations.
- Added two actual U.S. federal connectors: eCFR official JSON search plus its versioned full-text XML endpoint, and exact-citation U.S. Code retrieval from the current official release-point page and title-specific USLM XML ZIP. The U.S. Code connector is limited to citations explicitly present in contract text; it does not search the full Code. Both connectors preserve source text, source links, version/retrieval metadata, and applicability limitations.
- Retrieves at most three generic subject queries and two provisions total per analysis. Contract text, parties, and filename are not sent. Generic subject phrases are selected locally; exact CFR citation identifiers may be sent to eCFR. U.S.C. citations are used locally to identify the title and section within the retrieved title archive; the citation itself is not sent to OLRC. Contract excerpts remain local.
- Stores the registry metadata, connector state, source text, provenance metadata, and content hash in SQLite. Provision records use `(source, document identifier, source version)` keys; a new version is retained rather than overwriting old text. SQLite FTS5 supports full-text search, with exact identifier lookup.
- Adds typed `legal_analysis.legal_research` data to the existing analysis response. Search hits are explicitly candidates. The comparison pairs the contract excerpt with the exact retrieved official text and uses `insufficient_evidence` rather than inferring that a provision applies, conflicts, or validates the contract.
- Adds connector status/errors, source coverage, version/effective dates when supplied, retrieved excerpts, exact-source links, contract evidence, and limitations to the existing Law Analysis dashboard. Contract/source content is assigned via DOM text APIs.
- Every upload reruns contract-topic retrieval when the source's jurisdiction and topic are evidenced. The source date is refreshed, and older source versions remain in the archive. A source date older than seven days is flagged as stale. No contract effective date is inferred; historical legal applicability remains unresolved.

## Connector coverage matrix

“Metadata/manual” means an official source is registered and linked, but this application does not retrieve its legal text. A portal being reachable does not change that status.

| Jurisdiction/body | Official source coverage declared | Connector status | Live-tested here |
|---|---|---|---|
| United States | eCFR federal regulations and exact-citation current-release U.S. Code XML operational; state/territorial statutes separately identified | **Partial** — eCFR topic search, CFR exact citation, and U.S.C. exact citation; no comprehensive statutory corpus search | **Yes** — eCFR search/section retrieval and U.S. Code release-point title XML |
| Canada | Department of Justice federal laws; separate province/territory publishers | Metadata/manual; no app retrieval | No |
| United Kingdom | UK-wide and England/Wales, Scotland, and Northern Ireland distinctions | Metadata/manual; no app retrieval | No; a tested direct XML request received an access challenge |
| Germany | Federal legislation and separately identified EU law | Metadata/manual; no app retrieval | No |
| United Arab Emirates | Federal, emirate, DIFC, and ADGM sources separated | Metadata/manual; no app retrieval | No |
| Israel | Israeli government legislation and regulator material | Metadata/manual; no app retrieval | No |
| China | Mainland, Hong Kong, and Macau sources/legal systems separated | Metadata/manual; no app retrieval | No |
| India | India Code central law and separate state/UT law | Metadata/manual; no app retrieval | No |
| Italy | Normattiva national legislation and separately identified EU law | Metadata/manual; no app retrieval | No |
| European Union | EUR-Lex treaties, regulations, directives, decisions, judgments, and related materials | Metadata/manual; no app retrieval | No; live portal requests were challenged in this environment |
| World Trade Organization | Agreements, member commitments, and dispute-settlement source portals | Metadata/manual; no app retrieval | No |
| UNCITRAL | Conventions, model laws, instruments, and status material | Metadata/manual; no app retrieval | No |
| United Nations Treaty Collection | Treaty text and state/status information | Metadata/manual; no app retrieval | No |
| OECD, WIPO, ILO, HCCH | Extensible source metadata and authority limitations | Registry entries only; no connector | No |
| France (existing jurisdiction support) | Légifrance and EU source metadata retained | Metadata/manual; no app retrieval | No |

Live eCFR retrieval was tested against the official `ecfr.gov` API on 2026-10-28. Live U.S. Code retrieval was tested against the official OLRC release-point page and title-specific XML archive on 2026-10-28, including an exact statutory section lookup. A live eCFR run also encountered transient timeout/HTTP 503 responses for other candidate sections; the connector reports these errors rather than hiding them. This demonstrates only these specific U.S. retrieval paths—not coverage of all U.S. law or legal applicability.

## Authority and legal-effect boundaries

- eCFR records are labelled as federal regulation, with applicability and authority to the specific contract left for review.
- A U.S. eCFR result is federal regulation, not federal statute, state law, judgment, or agency guidance.
- U.S. Code results come from an official current release-point title download. The connector does not independently assess positive-law codification status for every title, currentness of each provision, or legal applicability.
- EUR-Lex entries distinguish EU instrument types; the current app does not fetch or assess EU material.
- The WTO entry states that member obligations do not automatically become private-contract duties.
- UNCITRAL model laws are not presented as enacted domestic law; treaty status and national enactment are not evaluated.
- Treaty status, reservations, territorial application, and entry into force are not inferred for UN, WTO, UNCITRAL, or other instruments.
- The software does not decide the applicability of domestic legislation, EU law, treaties, regulator guidance, or case law to a particular contract.

## Setup and operations

The existing `requests` dependency is used; no additional package is required. By default, the local archive is `outputs\legal_sources.sqlite3` (the `outputs` directory is ignored by Git). Override with `LEGAL_SOURCE_DATABASE_PATH` before starting the backend:

```powershell
$env:LEGAL_SOURCE_DATABASE_PATH = "D:\Contract_Intelligence\outputs\legal_sources.sqlite3"
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

The eCFR connector is invoked from contract analysis only when U.S. context and an extracted topic or exact CFR citation are present. The U.S. Code connector is invoked for exact U.S.C. citations found in the upload and downloads only the matching title's official USLM XML archive for the current release point. Both use bounded requests, timeouts, official-domain checks, source attribution and persistent versioned storage. `Retry-After` is returned when supplied; connectors do not retry around rate limits. An absent section returns an explicit error and no document. `LEGAL_SOURCE_LIVE_CHECK=true` enables only the pre-existing portal-reachability diagnostic; it is not legal-text verification.

## Remaining work / limitations

1. Implement and separately live-test permitted retrieval adapters for the additional national and international sources. Do not promote metadata-only entries to operational without validating their actual query and full-text/version endpoints.
2. Add state/province/emirate/state/territory-level publisher discovery and authority-specific retrieval where a stable official source is available.
3. Add source-specific update/delta workflows and historical-version selection for each adapter. Only eCFR source-date versioning is implemented.
4. Capture/validate a contract's effective date and support retrieval of law effective on that date; current analysis explicitly says this is unknown.
5. Improve legal-topic query generation and expand exact-citation recognition beyond CFR and U.S.C. No embedding model or semantic index is present; retrieval is official-source full-text search plus local FTS5.
6. Add broader legal authority and applicability review by qualified legal professionals. Current comparisons intentionally return insufficient evidence and do not produce legal conclusions.
7. Expand live-source integration tests and operational monitoring as additional connectors are implemented.

This project is legal-information and contract-review support, not a substitute for a qualified lawyer.
