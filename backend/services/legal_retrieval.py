"""Official-source retrieval, versioned storage, and evidence-only comparisons."""

import hashlib
import json
import os
import re
import sqlite3
import zipfile
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlencode, urljoin, urlsplit

from pydantic import BaseModel, ConfigDict
import requests

from backend.services.legal_sources import SOURCE_REGISTRY


ECFR_API = "https://www.ecfr.gov/api"
REQUEST_TIMEOUT = (2.0, 5.0)
MAX_RESPONSE_BYTES = 1_000_000
MAX_USCODE_ZIP_BYTES = 20_000_000
MAX_USCODE_XML_BYTES = 40_000_000
MAX_SEARCH_QUERIES = 3
MAX_RETRIEVED_PROVISIONS = 2
MAX_PROVISION_CHARACTERS = 100_000
STALE_AFTER_DAYS = 7
CFR_CITATION_PATTERN = re.compile(
    r"\b(?P<title>\d{1,2})\s+C\s*\.?\s*F\s*\.?\s*R\s*\.?\s*"
    r"(?:§+\s*)?(?P<section>\d+(?:\.[A-Za-z0-9-]+)+)",
    re.IGNORECASE,
)
USCODE_CITATION_PATTERN = re.compile(
    r"\b(?P<title>\d{1,2})\s+U\s*\.?\s*S\s*\.?\s*C\s*\.?\s*"
    r"§+\s*(?P<section>\d+[A-Za-z]?(?:-\d+[A-Za-z]?)?)"
    r"(?P<subsections>(?:\s*\([A-Za-z0-9]+\))*)",
    re.IGNORECASE,
)

TOPIC_SEARCH_TERMS = {
    "Services and performance": "services performance standards",
    "Payment and tax": "commercial payments taxes invoices",
    "Intellectual property": "intellectual property licensing ownership",
    "Confidentiality": "confidential information disclosure",
    "Data protection and transfers": "data privacy personal information security",
    "Liability and indemnity": "liability indemnification damages",
    "Termination": "contract termination cancellation notice",
    "Dispute resolution": "dispute resolution arbitration courts",
}
class LegalDocumentRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    source_name: str
    jurisdiction: str
    document_type: str
    authority_status: str
    document_id: str
    provision_reference: str
    title: str
    canonical_url: str
    source_text: str
    contract_topic: str
    contract_excerpt: str
    contract_clause_reference: Optional[str] = None
    publication_date: Optional[str]
    adoption_date: Optional[str]
    entry_into_force_date: Optional[str]
    effective_date: Optional[str]
    version_id: str
    version_status: str
    source_as_of_date: str
    source_text_sha256: str
    currency_status: str
    amendment_repeal_status: str
    retrieved_at: str
    last_verified_at: str
    source_language: str
    authenticity: str
    verification_status: str
    source_endpoint: str
    source_score: Optional[float]
    source_match_excerpt: Optional[str]
    provision_text_truncated: bool


class LegalConnectorRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    organization: str
    jurisdiction: str
    connector_status: str
    retrieval_status: str
    queries: List[Dict[str, str]]
    documents: List[LegalDocumentRecord]
    errors: List[Any]
    last_attempt_at: Optional[str]
    last_successful_retrieval_at: Optional[str]
    last_error: Optional[str] = None
    coverage_limitations: str
    api_docs_url: Optional[str]
    storage_status: str


class LegalComparisonRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_topic: str
    contract_excerpt: str
    contract_clause_reference: Optional[str]
    legal_document_title: str
    legal_provision_reference: str
    legal_excerpt: str
    official_source_url: str
    relationship: str
    support_assessment: str
    explanation: str
    missing_facts: List[str]


class LegalResearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    query_disclosure: Dict[str, Any]
    historical_law_status: str
    connectors: List[LegalConnectorRecord]
    documents: List[LegalDocumentRecord]
    comparisons: List[LegalComparisonRecord]
    storage: Dict[str, str]
    limitations: List[str]


class ConnectorError(Exception):
    def __init__(self, status: str, message: str, retry_after: Optional[str] = None):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_store_path() -> Path:
    configured = os.environ.get("LEGAL_SOURCE_DATABASE_PATH")
    if configured:
        return Path(configured).expanduser().resolve()
    root = Path(__file__).resolve().parents[2]
    return root / "outputs" / "legal_sources.sqlite3"


class LegalSourceStore:
    """SQLite archive with immutable source/version keys and a full-text index."""

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path is not None else _default_store_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS legal_documents (
                    source_id TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    version_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    canonical_url TEXT NOT NULL,
                    source_text TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    content_sha256 TEXT NOT NULL,
                    first_retrieved_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    PRIMARY KEY (source_id, document_id, version_id)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS legal_source_state (
                    source_id TEXT PRIMARY KEY,
                    last_attempt_at TEXT,
                    last_successful_retrieval_at TEXT,
                    retrieval_status TEXT NOT NULL,
                    last_error TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS legal_source_registry (
                    source_id TEXT PRIMARY KEY,
                    metadata_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS legal_document_fts
                USING fts5(source_id UNINDEXED, document_id UNINDEXED,
                           version_id UNINDEXED, title, source_text)
                """
            )
            registry_timestamp = _utc_now()
            for source_id, metadata in SOURCE_REGISTRY.items():
                connection.execute(
                    """
                    INSERT INTO legal_source_registry
                        (source_id, metadata_json, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(source_id) DO UPDATE SET
                        metadata_json=excluded.metadata_json,
                        updated_at=excluded.updated_at
                    """,
                    (
                        source_id,
                        json.dumps(metadata, ensure_ascii=False),
                        registry_timestamp,
                    ),
                )

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(str(self.path), timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def record_attempt(self, source_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO legal_source_state
                    (source_id, last_attempt_at, retrieval_status, last_error)
                VALUES (?, ?, 'retrieving', NULL)
                ON CONFLICT(source_id) DO UPDATE SET
                    last_attempt_at=excluded.last_attempt_at,
                    retrieval_status='retrieving',
                    last_error=NULL
                """,
                (source_id, _utc_now()),
            )

    def record_result(
        self,
        source_id: str,
        status: str,
        error: Optional[str] = None,
        succeeded: bool = False,
    ) -> None:
        now = _utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO legal_source_state
                    (source_id, last_attempt_at, last_successful_retrieval_at,
                     retrieval_status, last_error)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                    last_attempt_at=excluded.last_attempt_at,
                    last_successful_retrieval_at=COALESCE(
                        excluded.last_successful_retrieval_at,
                        legal_source_state.last_successful_retrieval_at
                    ),
                    retrieval_status=excluded.retrieval_status,
                    last_error=excluded.last_error
                """,
                (source_id, now, now if succeeded else None, status, error),
            )

    def source_state(self, source_id: str) -> Dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM legal_source_state WHERE source_id=?",
                (source_id,),
            ).fetchone()
        return dict(row) if row else {}

    def save_document(self, document: Dict[str, Any]) -> None:
        now = _utc_now()
        source_id = document["source_id"]
        document_id = document["document_id"]
        version_id = document["version_id"]
        content = document["source_text"]
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        metadata = {
            key: value
            for key, value in document.items()
            if key not in {"source_text", "contract_excerpt"}
        }
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO legal_documents
                    (source_id, document_id, version_id, title, canonical_url,
                     source_text, metadata_json, content_sha256,
                     first_retrieved_at, last_seen_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id, document_id, version_id) DO UPDATE SET
                    last_seen_at=excluded.last_seen_at
                """,
                (
                    source_id,
                    document_id,
                    version_id,
                    document["title"],
                    document["canonical_url"],
                    content,
                    json.dumps(metadata, ensure_ascii=False),
                    digest,
                    now,
                    now,
                ),
            )
            connection.execute(
                """
                DELETE FROM legal_document_fts
                WHERE source_id=? AND document_id=? AND version_id=?
                """,
                (source_id, document_id, version_id),
            )
            connection.execute(
                """
                INSERT INTO legal_document_fts
                    (source_id, document_id, version_id, title, source_text)
                VALUES (?, ?, ?, ?, ?)
                """,
                (source_id, document_id, version_id, document["title"], content),
            )

    def search(
        self, query: str, source_id: Optional[str] = None, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Search archived text; exact identifiers are checked before FTS terms."""
        with self._connect() as connection:
            if re.fullmatch(r"[A-Za-z0-9 .:/()§-]{3,100}", query or ""):
                exact = connection.execute(
                    """
                    SELECT source_id, document_id, version_id, title, canonical_url,
                           source_text, metadata_json, content_sha256
                    FROM legal_documents
                    WHERE (document_id=? OR document_id LIKE ?)
                      AND (? IS NULL OR source_id=?)
                    ORDER BY last_seen_at DESC LIMIT ?
                    """,
                    (query.strip(), f"%{query.strip()}%", source_id, source_id, limit),
                ).fetchall()
                if exact:
                    return [self._stored_result(row) for row in exact]

            terms = re.findall(r"[A-Za-z0-9]{3,}", query or "")
            if not terms:
                return []
            fts_query = " AND ".join(f'"{term}"' for term in terms[:12])
            rows = connection.execute(
                """
                SELECT d.source_id, d.document_id, d.version_id, d.title,
                       d.canonical_url, d.source_text, d.metadata_json,
                       d.content_sha256
                FROM legal_document_fts f
                JOIN legal_documents d
                  ON d.source_id=f.source_id
                 AND d.document_id=f.document_id
                 AND d.version_id=f.version_id
                WHERE legal_document_fts MATCH ?
                  AND (? IS NULL OR d.source_id=?)
                ORDER BY rank LIMIT ?
                """,
                (fts_query, source_id, source_id, limit),
            ).fetchall()
        return [self._stored_result(row) for row in rows]

    @staticmethod
    def _stored_result(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "source_id": row["source_id"],
            "document_id": row["document_id"],
            "version_id": row["version_id"],
            "title": row["title"],
            "canonical_url": row["canonical_url"],
            "source_text": row["source_text"],
            "metadata": json.loads(row["metadata_json"]),
            "content_sha256": row["content_sha256"],
        }


def _request_json(url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    try:
        response = requests.get(
            url,
            params=params,
            headers={
                "User-Agent": "ContractIntelligenceLegalResearch/1.0",
                "Accept": "application/json",
            },
            timeout=REQUEST_TIMEOUT,
        )
    except requests.Timeout as exc:
        raise ConnectorError("timeout", "The official eCFR API request timed out.") from exc
    except requests.RequestException as exc:
        raise ConnectorError("unavailable", "The official eCFR API could not be reached.") from exc
    response_host = urlsplit(getattr(response, "url", url)).hostname
    if response_host not in {"ecfr.gov", "www.ecfr.gov"}:
        raise ConnectorError("untrusted_redirect", "The eCFR API redirected outside its official domain.")
    if response.status_code == 429:
        raise ConnectorError(
            "rate_limited",
            "The official eCFR API returned a rate limit response.",
            response.headers.get("Retry-After"),
        )
    if response.status_code >= 400:
        raise ConnectorError(
            "http_error",
            f"The official eCFR API returned HTTP {response.status_code}.",
        )
    if len(response.content) > MAX_RESPONSE_BYTES:
        raise ConnectorError("response_too_large", "The eCFR response exceeded the configured size limit.")
    try:
        result = response.json()
    except ValueError as exc:
        raise ConnectorError("invalid_response", "The eCFR API did not return valid JSON.") from exc
    if not isinstance(result, dict):
        raise ConnectorError("invalid_response", "The eCFR API response had an unexpected structure.")
    return result


def _request_text(url: str, params: Dict[str, str]) -> str:
    try:
        response = requests.get(
            url,
            params=params,
            headers={
                "User-Agent": "ContractIntelligenceLegalResearch/1.0",
                "Accept": "application/xml",
                "Accept-Encoding": "gzip",
            },
            timeout=REQUEST_TIMEOUT,
        )
    except requests.Timeout as exc:
        raise ConnectorError("timeout", "The official eCFR provision request timed out.") from exc
    except requests.RequestException as exc:
        raise ConnectorError("unavailable", "The official eCFR provision could not be reached.") from exc
    response_host = urlsplit(getattr(response, "url", url)).hostname
    if response_host not in {"ecfr.gov", "www.ecfr.gov"}:
        raise ConnectorError("untrusted_redirect", "The eCFR API redirected outside its official domain.")
    if response.status_code == 429:
        raise ConnectorError(
            "rate_limited",
            "The official eCFR API returned a rate limit response.",
            response.headers.get("Retry-After"),
        )
    if response.status_code >= 400:
        raise ConnectorError(
            "http_error",
            f"The official eCFR API returned HTTP {response.status_code} for a provision.",
        )
    if len(response.content) > MAX_RESPONSE_BYTES:
        raise ConnectorError("response_too_large", "The eCFR provision exceeded the configured size limit.")
    return response.text


def _parse_section(xml_text: str, section_id: str) -> Dict[str, Any]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ConnectorError("invalid_response", "The eCFR provision was not valid XML.") from exc
    target = next(
        (
            element
            for element in root.iter()
            if element.attrib.get("TYPE") == "SECTION"
            and element.attrib.get("N") == section_id
        ),
        None,
    )
    if target is None and root.attrib.get("N") == section_id:
        target = root
    if target is None:
        raise ConnectorError(
            "provision_not_found",
            "The eCFR response did not contain the requested section identifier.",
        )
    blocks = []
    title = None
    for element in target:
        name = element.tag.rsplit("}", 1)[-1].upper()
        text = " ".join("".join(element.itertext()).split())
        if not text:
            continue
        if name == "HEAD" and title is None:
            title = text
        elif name in {"P", "FP", "HD", "HEAD"}:
            blocks.append(text)
    content = "\n".join(blocks)
    if len(content) > MAX_PROVISION_CHARACTERS:
        content = content[:MAX_PROVISION_CHARACTERS]
    if not content:
        content = " ".join("".join(target.itertext()).split())
        if len(content) > MAX_PROVISION_CHARACTERS:
            content = content[:MAX_PROVISION_CHARACTERS]
    if not content:
        raise ConnectorError("empty_provision", "The eCFR section contained no extractable text.")
    return {"title": title or f"Section {section_id}", "text": content}


def _canonical_ecfr_url(hierarchy: Dict[str, Any]) -> str:
    title = hierarchy.get("title")
    if not str(title or "").isdigit():
        raise ConnectorError("invalid_response", "The eCFR result had no valid title identifier.")
    segments = [f"title-{title}"]
    for key, prefix in (
        ("subtitle", "subtitle"),
        ("chapter", "chapter"),
        ("subchapter", "subchapter"),
        ("part", "part"),
        ("subpart", "subpart"),
        ("section", "section"),
    ):
        value = hierarchy.get(key)
        if value is not None:
            value = str(value).strip()
            if not re.fullmatch(r"[A-Za-z0-9.-]+", value):
                raise ConnectorError("invalid_response", f"The eCFR {key} identifier was invalid.")
            segments.append(f"{prefix}-{value}")
    return "https://www.ecfr.gov/current/" + "/".join(segments)


def _candidate_records(query: str) -> List[Dict[str, Any]]:
    response = _request_json(
        f"{ECFR_API}/search/v1/results",
        {"query": query, "per_page": 10, "order": "relevance"},
    )
    results = response.get("results")
    if not isinstance(results, list):
        raise ConnectorError("invalid_response", "The eCFR search response had no results list.")
    current_sections = [
        item
        for item in results
        if isinstance(item, dict)
        and item.get("type") == "Section"
        and item.get("ends_on") is None
        and not item.get("reserved")
        and not item.get("removed")
        and isinstance(item.get("hierarchy"), dict)
    ]
    return current_sections


def _build_document(
    result: Dict[str, Any],
    current_as_of: str,
    contract_topic: str,
    contract_excerpt: str,
) -> Dict[str, Any]:
    hierarchy = result["hierarchy"]
    title_number = str(hierarchy.get("title", ""))
    part = str(hierarchy.get("part", ""))
    section = str(hierarchy.get("section", ""))
    if not title_number.isdigit() or not part.isdigit() or not re.fullmatch(
        r"[A-Za-z0-9.-]+", section
    ):
        raise ConnectorError("invalid_response", "The eCFR result had an invalid provision citation.")
    starts_on = result.get("starts_on")
    if starts_on and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(starts_on)):
        starts_on = None
    canonical_url = _canonical_ecfr_url(hierarchy)
    api_url = (
        f"{ECFR_API}/versioner/v1/full/{current_as_of}/title-{title_number}.xml"
    )
    xml_text = _request_text(api_url, {"part": part, "section": section})
    provision = _parse_section(xml_text, section)
    retrieved_at = _utc_now()
    as_of_date = date.fromisoformat(current_as_of)
    stale = as_of_date < (date.today() - timedelta(days=STALE_AFTER_DAYS))
    document_id = f"{title_number} CFR {section}"
    content_hash = hashlib.sha256(provision["text"].encode("utf-8")).hexdigest()
    return {
        "source_id": "us_ecfr",
        "source_name": SOURCE_REGISTRY["us_ecfr"]["organization"],
        "jurisdiction": "United States — federal",
        "document_type": "regulation",
        "authority_status": "Federal regulation; authority and applicability to this contract have not been assessed.",
        "document_id": document_id,
        "provision_reference": document_id,
        "title": provision["title"],
        "canonical_url": canonical_url,
        "source_text": provision["text"],
        "contract_topic": contract_topic,
        "contract_excerpt": contract_excerpt[:1500],
        "publication_date": None,
        "adoption_date": None,
        "entry_into_force_date": None,
        "effective_date": starts_on,
        "version_id": f"{current_as_of}:{content_hash[:16]}",
        "version_status": "current consolidated eCFR text as of source date",
        "source_as_of_date": current_as_of,
        "source_text_sha256": content_hash,
        "currency_status": (
            "stale_source_date"
            if stale
            else "retrieved_as_of_source_date_not_guaranteed_current"
        ),
        "amendment_repeal_status": (
            "search result is not marked removed or reserved; complete amendment history not evaluated"
        ),
        "retrieved_at": retrieved_at,
        "last_verified_at": retrieved_at,
        "source_language": "en",
        "authenticity": "Retrieved over HTTPS from the official ecfr.gov versioner API.",
        "verification_status": "official_text_retrieved; applicability_not_verified",
        "source_endpoint": api_url + "?" + urlencode({"part": part, "section": section}),
        "source_score": result.get("score"),
        "source_match_excerpt": result.get("full_text_excerpt"),
        "provision_text_truncated": len(provision["text"]) >= MAX_PROVISION_CHARACTERS,
    }


def _get_current_as_of_date() -> str:
    response = _request_json(f"{ECFR_API}/versioner/v1/titles")
    metadata = response.get("meta")
    current_as_of = metadata.get("date") if isinstance(metadata, dict) else None
    if not isinstance(current_as_of, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}", current_as_of
    ):
        raise ConnectorError("invalid_response", "The eCFR API did not provide its source version date.")
    if metadata.get("import_in_progress"):
        raise ConnectorError("source_update_in_progress", "The eCFR reports that its source update is in progress.")
    return current_as_of


def _topic_queries(topic_evidence: Iterable[Dict[str, Any]]) -> List[Dict[str, str]]:
    queries = []
    for item in topic_evidence:
        topic = item.get("contract_topic")
        query = TOPIC_SEARCH_TERMS.get(topic)
        excerpt = item.get("contract_clause_text")
        if topic and query and excerpt:
            queries.append(
                {
                    "topic": topic,
                    "query": query,
                    "contract_excerpt": str(excerpt),
                }
            )
        if len(queries) >= MAX_SEARCH_QUERIES:
            break
    return queries


def _exact_cfr_citations(contract_text: str) -> List[Dict[str, str]]:
    citations = []
    seen = set()
    for match in CFR_CITATION_PATTERN.finditer(contract_text or ""):
        title = match.group("title")
        section = match.group("section").rstrip(".,;:")
        citation = f"{title} CFR {section}"
        if (title, section) in seen:
            continue
        seen.add((title, section))
        line_start = contract_text.rfind("\n", 0, match.start()) + 1
        line_end = contract_text.find("\n", match.end())
        if line_end < 0:
            line_end = len(contract_text)
        if line_end - line_start > 1500:
            excerpt_start = max(line_start, match.start() - 750)
            excerpt_end = min(line_end, match.end() + 750)
        else:
            excerpt_start, excerpt_end = line_start, line_end
        citations.append(
            {
                "title": title,
                "section": section,
                "citation": citation,
                "contract_excerpt": contract_text[excerpt_start:excerpt_end].strip()[:1500],
            }
        )
        if len(citations) >= MAX_RETRIEVED_PROVISIONS:
            break
    return citations


def _exact_uscode_citations(contract_text: str) -> List[Dict[str, str]]:
    citations = []
    seen = set()
    for match in USCODE_CITATION_PATTERN.finditer(contract_text or ""):
        title = int(match.group("title"))
        section = match.group("section")
        subsections = re.sub(r"\s+", "", match.group("subsections") or "")
        citation = f"{title} U.S.C. § {section}{subsections}"
        if not 1 <= title <= 54 or (title, citation) in seen:
            continue
        seen.add((title, citation))
        line_start = contract_text.rfind("\n", 0, match.start()) + 1
        line_end = contract_text.find("\n", match.end())
        if line_end < 0:
            line_end = len(contract_text)
        if line_end - line_start > 1500:
            excerpt_start = max(line_start, match.start() - 750)
            excerpt_end = min(line_end, match.end() + 750)
        else:
            excerpt_start, excerpt_end = line_start, line_end
        citations.append(
            {
                "title": title,
                "section": section,
                "citation": citation,
                "contract_excerpt": contract_text[excerpt_start:excerpt_end].strip()[:1500],
            }
        )
        if len(citations) >= MAX_RETRIEVED_PROVISIONS:
            break
    return citations


def _request_uscode(url: str, max_bytes: int) -> bytes:
    try:
        response = requests.get(
            url,
            headers={
                "User-Agent": "ContractIntelligenceLegalResearch/1.0",
                "Accept": "text/html, application/zip, application/xml",
            },
            timeout=REQUEST_TIMEOUT,
        )
    except requests.Timeout as exc:
        raise ConnectorError("timeout", "The official U.S. Code request timed out.") from exc
    except requests.RequestException as exc:
        raise ConnectorError("unavailable", "The official U.S. Code source could not be reached.") from exc
    response_host = urlsplit(getattr(response, "url", url)).hostname
    if response_host != "uscode.house.gov":
        raise ConnectorError("untrusted_redirect", "The U.S. Code source redirected outside its official domain.")
    if response.status_code == 429:
        raise ConnectorError(
            "rate_limited",
            "The official U.S. Code source returned a rate limit response.",
            response.headers.get("Retry-After"),
        )
    if response.status_code >= 400:
        raise ConnectorError(
            "http_error",
            f"The official U.S. Code source returned HTTP {response.status_code}.",
        )
    if len(response.content) > max_bytes:
        raise ConnectorError("response_too_large", "The official U.S. Code response exceeded the configured size limit.")
    return response.content


def _uscode_releasepoint(title: int) -> Dict[str, str]:
    page = _request_uscode(
        "https://uscode.house.gov/download.html",
        MAX_RESPONSE_BYTES,
    ).decode("utf-8", errors="replace")
    release_match = re.search(
        r'<h3[^>]*class=["\'][^"\']*releasepointinformation[^"\']*["\'][^>]*>\s*Public Law\s+(\d+-\d+)',
        page,
        re.IGNORECASE,
    )
    as_of_match = re.search(
        r"All files are current through Public Law\s+\d+-\d+\s*\(([^)]+)\)",
        page,
        re.IGNORECASE,
    )
    if not release_match or not as_of_match:
        raise ConnectorError("invalid_response", "The official U.S. Code page did not identify its release point.")
    release_point = release_match.group(1)
    if not re.fullmatch(r"\d{1,3}-\d{1,4}", release_point):
        raise ConnectorError("invalid_response", "The U.S. Code release-point identifier was malformed.")
    try:
        source_date = datetime.strptime(as_of_match.group(1).strip(), "%B %d, %Y").date().isoformat()
    except ValueError as exc:
        raise ConnectorError("invalid_response", "The U.S. Code page did not provide a valid release date.") from exc
    title_code = f"{title:02d}"
    link_match = re.search(
        rf'href=["\'](download/releasepoints/us/pl/\d{{1,3}}/\d{{1,4}}/xml_usc{title_code}@{re.escape(release_point)}\.zip)["\']',
        page,
        re.IGNORECASE,
    )
    if not link_match:
        raise ConnectorError(
            "title_unavailable",
            f"The official U.S. Code release page did not provide an XML download for title {title}.",
        )
    zip_url = urljoin("https://uscode.house.gov/", link_match.group(1))
    if urlsplit(zip_url).hostname != "uscode.house.gov":
        raise ConnectorError("untrusted_redirect", "The U.S. Code title download URL was not on the official domain.")
    return {
        "release_point": release_point,
        "source_date": source_date,
        "zip_url": zip_url,
    }


def _uslm_element_text(element: ET.Element) -> str:
    parts = []

    def collect(node: ET.Element) -> None:
        if node.tag.rsplit("}", 1)[-1].lower() == "notes":
            return
        if node.text:
            parts.append(node.text)
        for child in node:
            collect(child)
            if child.tail:
                parts.append(child.tail)

    collect(element)
    return " ".join("".join(parts).split())


def _parse_uscode_section(xml_bytes: bytes, title: int, section: str) -> Dict[str, str]:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise ConnectorError("invalid_response", "The U.S. Code title download was not valid USLM XML.") from exc
    expected_identifier = f"/us/usc/t{title}/s{section}"
    target = next(
        (
            element
            for element in root.iter()
            if element.tag.rsplit("}", 1)[-1].lower() == "section"
            and element.attrib.get("identifier") == expected_identifier
        ),
        None,
    )
    if target is None:
        raise ConnectorError(
            "provision_not_found",
            "The official U.S. Code title did not contain the requested section identifier.",
        )
    heading = next(
        (
            _uslm_element_text(child)
            for child in target
            if child.tag.rsplit("}", 1)[-1].lower() == "heading"
        ),
        "",
    )
    source_text = "\n".join(
        text
        for child in target
        if child.tag.rsplit("}", 1)[-1].lower() != "notes"
        and (text := _uslm_element_text(child))
    )
    if not source_text:
        raise ConnectorError("empty_provision", "The official U.S. Code section contained no extractable text.")
    if len(source_text) > MAX_PROVISION_CHARACTERS:
        source_text = source_text[:MAX_PROVISION_CHARACTERS]
    return {"title": heading or f"Section {section}", "text": source_text}


def _build_uscode_document(
    citation: Dict[str, Any],
    release: Dict[str, str],
    section_xml: bytes,
) -> Dict[str, Any]:
    title = citation["title"]
    section = citation["section"]
    provision = _parse_uscode_section(section_xml, title, section)
    retrieved_at = _utc_now()
    digest = hashlib.sha256(provision["text"].encode("utf-8")).hexdigest()
    document_id = citation["citation"]
    return {
        "source_id": "us_code",
        "source_name": SOURCE_REGISTRY["us_code"]["organization"],
        "jurisdiction": "United States — federal",
        "document_type": "statute",
        "authority_status": "Official federal statutory compilation; title-level codification status and applicability to this contract have not been independently assessed.",
        "document_id": document_id,
        "provision_reference": citation["citation"],
        "title": provision["title"],
        "canonical_url": release["zip_url"],
        "source_text": provision["text"],
        "contract_topic": "Exact citation in contract",
        "contract_excerpt": citation["contract_excerpt"][:1500],
        "publication_date": None,
        "adoption_date": None,
        "entry_into_force_date": None,
        "effective_date": None,
        "version_id": f"{release['release_point']}:{digest[:16]}",
        "version_status": f"Consolidated U.S. Code release point {release['release_point']}",
        "source_as_of_date": release["source_date"],
        "source_text_sha256": digest,
        "currency_status": "official_release_point_retrieved; provision-level currentness_not_independently_verified",
        "amendment_repeal_status": (
            f"Section appears in official release point {release['release_point']}; "
            "source credits and provision-specific amendment history require review."
        ),
        "retrieved_at": retrieved_at,
        "last_verified_at": retrieved_at,
        "source_language": "en",
        "authenticity": "Retrieved over HTTPS from the official House Office of the Law Revision Counsel XML download.",
        "verification_status": "official_text_retrieved; applicability_not_verified",
        "source_endpoint": release["zip_url"],
        "source_score": None,
        "source_match_excerpt": None,
        "provision_text_truncated": len(provision["text"]) >= MAX_PROVISION_CHARACTERS,
    }


def _retrieve_uscode_citations(
    citations: List[Dict[str, Any]],
    store: Optional[LegalSourceStore],
) -> Dict[str, Any]:
    source = SOURCE_REGISTRY["us_code"]
    connector = {
        "source_id": "us_code",
        "organization": source["organization"],
        "jurisdiction": source["jurisdiction"],
        "connector_status": source["connector_status"],
        "retrieval_status": "not_searched_no_exact_citation",
        "queries": [],
        "documents": [],
        "errors": [],
        "last_attempt_at": None,
        "last_successful_retrieval_at": None,
        "last_error": None,
        "coverage_limitations": source["coverage_limitations"],
        "api_docs_url": None,
        "storage_status": "available" if store else "unavailable",
    }
    if store:
        try:
            state = store.source_state("us_code")
            connector["last_attempt_at"] = state.get("last_attempt_at")
            connector["last_successful_retrieval_at"] = state.get(
                "last_successful_retrieval_at"
            )
            connector["last_error"] = state.get("last_error")
        except sqlite3.Error as exc:
            connector["storage_status"] = "write_failed"
            connector["errors"].append(
                f"U.S. Code retrieval state could not be read ({type(exc).__name__})."
            )
    if not citations:
        return connector
    connector["queries"] = [
        {"contract_topic": "Exact citation in contract", "query": item["citation"]}
        for item in citations
    ]
    connector["retrieval_status"] = "retrieving"
    connector["last_attempt_at"] = _utc_now()
    if store:
        try:
            store.record_attempt("us_code")
        except sqlite3.Error as exc:
            connector["storage_status"] = "write_failed"
            connector["errors"].append(
                f"U.S. Code retrieval state could not be archived ({type(exc).__name__})."
            )

    xml_by_title: Dict[int, tuple] = {}
    for citation in citations:
        title = citation["title"]
        try:
            if title not in xml_by_title:
                release = _uscode_releasepoint(title)
                zip_content = _request_uscode(release["zip_url"], MAX_USCODE_ZIP_BYTES)
                try:
                    with zipfile.ZipFile(BytesIO(zip_content)) as archive:
                        expected_name = f"usc{title:02d}.xml"
                        try:
                            member = archive.getinfo(expected_name)
                        except KeyError as exc:
                            raise ConnectorError(
                                "invalid_response",
                                "The official U.S. Code title archive omitted its expected XML file.",
                            ) from exc
                        if member.file_size > MAX_USCODE_XML_BYTES:
                            raise ConnectorError(
                                "response_too_large",
                                "The U.S. Code title XML exceeded the configured size limit.",
                            )
                        xml_content = archive.read(member)
                except zipfile.BadZipFile as exc:
                    raise ConnectorError("invalid_response", "The U.S. Code download was not a valid ZIP archive.") from exc
                xml_by_title[title] = (release, xml_content)
            release, xml_content = xml_by_title[title]
            document = _build_uscode_document(citation, release, xml_content)
            if store:
                try:
                    store.save_document(document)
                except sqlite3.Error as exc:
                    connector["storage_status"] = "write_failed"
                    connector["errors"].append(
                        f"Retrieved U.S. Code text could not be archived ({type(exc).__name__})."
                    )
            connector["documents"].append(document)
        except ConnectorError as exc:
            error = {
                "status": exc.status,
                "message": str(exc),
                "retry_after": exc.retry_after,
                "provision_reference": citation["citation"],
            }
            connector["errors"].append(error)
            connector["last_error"] = str(exc)
            if exc.status == "rate_limited":
                break

    if connector["errors"] and connector["documents"]:
        connector["retrieval_status"] = "partial_failure"
    elif connector["errors"]:
        connector["retrieval_status"] = connector["errors"][0]["status"]
    elif connector["documents"]:
        connector["retrieval_status"] = "retrieved"
    else:
        connector["retrieval_status"] = "no_results"

    if connector["documents"]:
        connector["last_successful_retrieval_at"] = _utc_now()
    if store:
        try:
            store.record_result(
                "us_code",
                connector["retrieval_status"],
                "; ".join(str(item["message"]) for item in connector["errors"]) or None,
                succeeded=bool(connector["documents"]),
            )
        except sqlite3.Error as exc:
            connector["storage_status"] = "write_failed"
            connector["errors"].append(
                f"U.S. Code retrieval status could not be archived ({type(exc).__name__})."
            )
    return connector


def retrieve_official_materials(
    jurisdictions: Iterable[Dict[str, Any]],
    topic_evidence: Iterable[Dict[str, Any]],
    store_path: Optional[Path] = None,
    contract_text: str = "",
) -> Dict[str, Any]:
    """Search only official connectors relevant to the contract's stated context."""
    contract_uscode_citations = _exact_uscode_citations(contract_text)
    contract_cfr_citations = _exact_cfr_citations(contract_text)
    us_relevant = (
        any(item.get("jurisdiction") == "United States of America" for item in jurisdictions)
        or bool(contract_uscode_citations)
        or bool(contract_cfr_citations)
    )
    queries = _topic_queries(topic_evidence) if us_relevant else []
    citations = contract_cfr_citations if us_relevant else []
    uscode_citations = contract_uscode_citations if us_relevant else []
    ecfr_requested = bool(queries or citations)
    source = SOURCE_REGISTRY["us_ecfr"]
    store = None
    state = {}
    storage_error = None
    try:
        store = LegalSourceStore(store_path)
        state = store.source_state("us_ecfr")
    except sqlite3.Error as exc:
        store = None
        storage_error = f"Legal-source database is unavailable ({type(exc).__name__})."

    uscode_connector = _retrieve_uscode_citations(uscode_citations, store)
    remaining_provision_slots = max(
        0,
        MAX_RETRIEVED_PROVISIONS - len(uscode_connector["documents"]),
    )
    should_retrieve = ecfr_requested and remaining_provision_slots > 0
    if store and should_retrieve:
        try:
            store.record_attempt("us_ecfr")
        except sqlite3.Error as exc:
            storage_error = f"Legal-source database is unavailable ({type(exc).__name__})."
    connector = {
        "source_id": "us_ecfr",
        "organization": source["organization"],
        "jurisdiction": source["jurisdiction"],
        "connector_status": source["connector_status"],
        "retrieval_status": "not_applicable",
        "queries": [],
        "documents": [],
        "errors": [],
        "last_attempt_at": state.get("last_attempt_at"),
        "last_successful_retrieval_at": state.get("last_successful_retrieval_at"),
        "last_error": state.get("last_error"),
        "coverage_limitations": source["coverage_limitations"],
        "api_docs_url": source["api_docs_url"],
    }
    if storage_error:
        connector["errors"].append(storage_error)
        connector["storage_status"] = "unavailable"
    else:
        connector["storage_status"] = "available"
    if not us_relevant:
        connector["retrieval_status"] = "not_searched_jurisdiction_not_identified"
    elif not ecfr_requested:
        connector["retrieval_status"] = "not_searched_no_topic_or_exact_citation_evidence"
    elif not should_retrieve:
        connector["retrieval_status"] = "not_searched_analysis_provision_limit_reached"
    else:
        connector["queries"] = [
            {"contract_topic": item["topic"], "query": item["query"]}
            for item in queries
        ]
        connector["queries"].extend(
            {
                "contract_topic": "Exact citation in contract",
                "query": citation["citation"],
            }
            for citation in citations
        )
        connector["retrieval_status"] = "retrieving"
        connector["last_attempt_at"] = _utc_now()

    if should_retrieve:
        try:
            current_as_of = _get_current_as_of_date()
            seen = set()
            errors = []
            def add_document(result, topic, excerpt):
                nonlocal store
                hierarchy = result["hierarchy"]
                reference = f"{hierarchy.get('title')} CFR {hierarchy.get('section')}"
                if reference in seen:
                    return False
                seen.add(reference)
                try:
                    document = _build_document(
                        result,
                        current_as_of,
                        topic,
                        excerpt,
                    )
                except ConnectorError as exc:
                    errors.append(
                        {
                            "status": exc.status,
                            "message": str(exc),
                            "retry_after": exc.retry_after,
                            "provision_reference": reference,
                        }
                    )
                    return exc.status == "rate_limited"
                if store:
                    try:
                        store.save_document(document)
                    except sqlite3.Error as exc:
                        connector["storage_status"] = "write_failed"
                        connector["errors"].append(
                            f"Retrieved text could not be archived ({type(exc).__name__})."
                        )
                        store = None
                connector["documents"].append(document)
                return (
                    len(connector["documents"]) + len(uscode_connector["documents"])
                    >= MAX_RETRIEVED_PROVISIONS
                )

            for citation in citations:
                section = citation["section"]
                result = {
                    "starts_on": None,
                    "ends_on": None,
                    "type": "Section",
                    "hierarchy": {
                        "title": citation["title"],
                        "subtitle": None,
                        "chapter": None,
                        "subchapter": None,
                        "part": section.split(".", 1)[0],
                        "subpart": None,
                        "section": section,
                    },
                    "full_text_excerpt": None,
                    "score": None,
                }
                if add_document(
                    result,
                    "Exact citation in contract",
                    citation["contract_excerpt"],
                ):
                    break
                if errors and errors[-1]["status"] == "rate_limited":
                    break

            if (
                (not errors or errors[-1]["status"] != "rate_limited")
                and len(connector["documents"]) + len(uscode_connector["documents"])
                < MAX_RETRIEVED_PROVISIONS
            ):
                for query_info in queries:
                    records = _candidate_records(query_info["query"])
                    for result in records:
                        if add_document(
                            result,
                            query_info["topic"],
                            query_info["contract_excerpt"],
                        ):
                            break
                        if errors and errors[-1]["status"] == "rate_limited":
                            break
                    if (
                        len(connector["documents"]) + len(uscode_connector["documents"])
                        >= MAX_RETRIEVED_PROVISIONS
                    ):
                        break
                    if errors and errors[-1]["status"] == "rate_limited":
                        break
            connector["errors"].extend(errors)
            if connector["errors"] and connector["documents"]:
                connector["retrieval_status"] = "partial_failure"
            elif connector["errors"]:
                connector["retrieval_status"] = connector["errors"][0]["status"]
            elif connector["documents"]:
                connector["retrieval_status"] = "retrieved"
            else:
                connector["retrieval_status"] = "no_results"
            retrieval_succeeded = bool(connector["documents"]) or not errors
            if retrieval_succeeded:
                connector["last_successful_retrieval_at"] = _utc_now()
            elif errors:
                connector["last_error"] = errors[0]["message"]
            if store:
                try:
                    store.record_result(
                        "us_ecfr",
                        connector["retrieval_status"],
                        "; ".join(
                            str(error.get("message", ""))
                            for error in errors
                            if isinstance(error, dict)
                        )
                        or None,
                        succeeded=retrieval_succeeded,
                    )
                except sqlite3.Error as exc:
                    connector["storage_status"] = "write_failed"
                    connector["errors"].append(
                        f"Successful retrieval metadata could not be archived ({type(exc).__name__})."
                    )
            elif not storage_error and retrieval_succeeded:
                connector["last_successful_retrieval_at"] = _utc_now()
        except ConnectorError as exc:
            connector["retrieval_status"] = exc.status
            connector["last_attempt_at"] = _utc_now()
            connector["last_error"] = str(exc)
            error = {
                "status": exc.status,
                "message": str(exc),
                "retry_after": exc.retry_after,
            }
            connector["errors"].append(error)
            if store:
                try:
                    store.record_result(
                        "us_ecfr",
                        exc.status,
                        str(exc),
                    )
                except sqlite3.Error as db_exc:
                    connector["storage_status"] = "write_failed"
                    connector["errors"].append(
                        f"Source failure could not be archived ({type(db_exc).__name__})."
                    )

    documents = uscode_connector["documents"] + connector["documents"]
    comparisons = [
        {
            "contract_topic": item["contract_topic"],
            "contract_excerpt": item["contract_excerpt"],
            "contract_clause_reference": None,
            "legal_document_title": item["title"],
            "legal_provision_reference": item["provision_reference"],
            "legal_excerpt": item["source_text"],
            "official_source_url": item["canonical_url"],
            "relationship": (
                "official_text_retrieved_for_statutory_citation_identifier_found_in_contract"
                if item["source_id"] == "us_code"
                else (
                    "official_text_retrieved_for_citation_identifier_found_in_contract"
                    if item["contract_topic"] == "Exact citation in contract"
                    else "official_full_text_retrieved_as_a_search_candidate"
                )
            ),
            "support_assessment": "insufficient_evidence",
            "explanation": (
                (
                    "The contract contains this U.S. Code citation and the corresponding official consolidated "
                    "section text was retrieved. This confirms a source-backed citation match, not that the "
                    "statute applies to the parties or that the contract complies with it."
                    if item["source_id"] == "us_code"
                    else (
                        "The contract contains this citation identifier and the corresponding official eCFR "
                        "section was retrieved. This does not establish that the citation is accurate in context, "
                        "that the provision applies on the contract date, or that it affects the clause."
                        if item["contract_topic"] == "Exact citation in contract"
                        else
                        "The official text was retrieved from a topic search. Search relevance alone does not "
                        "establish that this provision applies to, conflicts with, or validates the contract clause."
                    )
                )
            ),
            "missing_facts": [
                "The activity, entities, territory, and any statutory scope criteria have not been legally validated.",
                "The contract's effective date and historical law applicable on that date have not been established.",
            ],
        }
        for item in documents
    ]
    if documents:
        status = (
            "partial_failure"
            if connector["errors"] or uscode_connector["errors"]
            else "retrieved"
        )
    elif uscode_citations:
        status = uscode_connector["retrieval_status"]
    else:
        status = connector["retrieval_status"]
    return {
        "status": status,
        "query_disclosure": {
            "contract_text_sent": False,
            "party_names_sent": False,
            "filename_sent": False,
            "exact_citation_identifiers_sent": [
                citation["citation"] for citation in citations
            ],
            "uscode_citation_identifiers_used_for_local_lookup": [
                citation["citation"] for citation in uscode_citations
            ],
            "query_basis": (
                "Generic subject search terms are selected from contract topics extracted locally; "
                "exact CFR citation identifiers may be sent to eCFR; U.S. Code citation identifiers "
                "are matched locally against an official title XML download."
            ),
            "external_sources": [
                source
                for source, used in (
                    ("Official eCFR API", bool(queries or citations)),
                    ("Official U.S. Code release-point XML", bool(uscode_citations)),
                )
                if used
            ],
        },
        "historical_law_status": (
            "The contract's legally effective date was not established; retrieved text is versioned only by the source date."
        ),
        "connectors": [connector, uscode_connector],
        "documents": documents,
        "comparisons": comparisons,
        "storage": {
            "backend": "SQLite with FTS5 full text index and version-keyed source documents",
            "status": (
                "available"
                if connector["storage_status"] == "available"
                and uscode_connector["storage_status"] == "available"
                else "partial_or_unavailable"
            ),
            "version_retention": "Each source document/version is retained under a separate version key.",
        },
        "limitations": [
            "Only the U.S. eCFR and exact-citation U.S. Code connectors currently perform live retrieval.",
            "eCFR contains federal regulations, not federal statutes, state law, or case law.",
            "U.S. Code retrieval is limited to exact citations present in the contract; it is not a general corpus search.",
            "Retrieved documents are search candidates; no automated legal applicability or compliance conclusion is produced.",
            "A source's version date does not establish that the text is current on the contract's effective date.",
        ],
    }
