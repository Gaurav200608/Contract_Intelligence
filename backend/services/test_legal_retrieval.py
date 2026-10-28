import json
import os
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from io import BytesIO
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

from backend.services.legal_retrieval import (
    ECFR_API,
    LegalResearchResult,
    LegalSourceStore,
    _build_document,
    _parse_section,
    _parse_uscode_section,
    _request_json,
    retrieve_official_materials,
)
from backend.services.legal_sources import SOURCE_REGISTRY
from backend.main import app


SYNTHETIC_SECTION_XML = (
    '<DIV8 N="164.520" TYPE="SECTION">'
    "<HEAD>§ 164.520 Synthetic parser fixture section.</HEAD>"
    "<P>(a) This text is a synthetic XML parsing fixture, not legal text.</P>"
    "</DIV8>"
)
SYNTHETIC_USCODE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<uscDoc xmlns="http://xml.house.gov/schemas/uslm/1.0" identifier="/us/usc/t17">
  <meta><docTitle>Title 17 - COPYRIGHTS</docTitle></meta>
  <main><title><section identifier="/us/usc/t17/s107">
    <num value="107">Section 107.</num>
    <heading>Limitations on exclusive rights: Fair use</heading>
    <chapeau>The text of subsection (a) is a synthetic test fixture.</chapeau>
    <notes>Editorial notes are excluded from the section text.</notes>
  </section></title></main>
</uscDoc>""".encode("utf-8")
SYNTHETIC_USCODE_DOWNLOAD_PAGE = b"""<h3 class="releasepointinformation">Public Law 119-134</h3>
<p>All files are current through Public Law 119-134 (October 20, 2026).</p>
<a href="download/releasepoints/us/pl/119/134/xml_usc17@119-134.zip">[XML]</a>"""


def _search_result(version="2026-10-23"):
    return {
        "starts_on": "2024-06-25",
        "ends_on": None,
        "type": "Section",
        "hierarchy": {
            "title": "45",
            "subtitle": "A",
            "chapter": None,
            "subchapter": "C",
            "part": "164",
            "subpart": "E",
            "section": "164.520",
            "appendix": None,
        },
        "full_text_excerpt": "Synthetic search excerpt.",
        "score": 12.5,
    }


class FakeResponse:
    def __init__(
        self,
        *,
        status_code=200,
        json_data=None,
        text="",
        content=None,
        headers=None,
        url=None,
    ):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text
        self.content = content if content is not None else (
            json.dumps(json_data).encode("utf-8")
            if json_data is not None
            else text.encode("utf-8")
        )
        self.headers = headers or {}
        if url is not None:
            self.url = url

    def json(self):
        return self._json_data


class LegalRetrievalTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.store_path = Path(self.temporary_directory.name) / "sources.sqlite3"

    def tearDown(self):
        self.temporary_directory.cleanup()

    def _fake_http(self, current_date="2026-10-23", section_xml=SYNTHETIC_SECTION_XML):
        def fake_get(url, params=None, **kwargs):
            if url == f"{ECFR_API}/versioner/v1/titles":
                return FakeResponse(
                    json_data={
                        "meta": {
                            "date": current_date,
                            "import_in_progress": False,
                        },
                        "titles": [],
                    }
                )
            if url == f"{ECFR_API}/search/v1/results":
                return FakeResponse(json_data={"results": [_search_result()]})
            if "/versioner/v1/full/" in url:
                return FakeResponse(text=section_xml)
            raise AssertionError(f"Unexpected URL: {url}")

        return fake_get

    def _retrieve(self):
        return retrieve_official_materials(
            [{"jurisdiction": "United States of America"}],
            [
                {
                    "contract_topic": "Data protection and transfers",
                    "contract_clause_text": "The processor handles personal information.",
                }
            ],
            self.store_path,
        )

    @staticmethod
    def _uscode_zip(xml=SYNTHETIC_USCODE_XML):
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("usc17.xml", xml)
        return buffer.getvalue()

    def test_source_registry_identifies_only_the_ecfr_as_live_operational(self):
        self.assertEqual(SOURCE_REGISTRY["us_ecfr"]["connector_status"], "operational")
        self.assertEqual(SOURCE_REGISTRY["us_code"]["connector_status"], "operational")
        self.assertEqual(SOURCE_REGISTRY["us_ecfr"]["organization"], "Office of the Federal Register / National Archives")
        self.assertEqual(SOURCE_REGISTRY["us_ecfr"]["text_coverage"].split(";")[0], "Current consolidated eCFR text with version-date retrieval")
        for source_id in ("canada_federal", "uk_legislation", "eu_lex", "wto", "uncitral", "un_treaties"):
            self.assertEqual(
                SOURCE_REGISTRY[source_id]["connector_status"],
                "manual_access_required",
            )

    def test_uscode_uslm_parser_preserves_section_and_excludes_editorial_notes(self):
        parsed = _parse_uscode_section(SYNTHETIC_USCODE_XML, 17, "107")
        self.assertIn("Limitations on exclusive rights: Fair use", parsed["title"])
        self.assertIn("synthetic test fixture", parsed["text"])
        self.assertNotIn("Editorial notes", parsed["text"])
        with self.assertRaisesRegex(Exception, "did not contain"):
            _parse_uscode_section(SYNTHETIC_USCODE_XML, 17, "999")

    def test_exact_uscode_citation_retrieves_official_releasepoint_text_and_archives_it(self):
        requests_seen = []

        def fake_get(url, **kwargs):
            requests_seen.append(url)
            if url == "https://uscode.house.gov/download.html":
                return FakeResponse(content=SYNTHETIC_USCODE_DOWNLOAD_PAGE)
            if url.endswith("/xml_usc17@119-134.zip"):
                return FakeResponse(content=self._uscode_zip())
            raise AssertionError(f"Unexpected URL: {url}")

        contract_excerpt = "The parties shall comply with 17 U.S.C. § 107."
        with patch("backend.services.legal_retrieval.requests.get", side_effect=fake_get):
            result = retrieve_official_materials([], [], self.store_path, contract_excerpt)

        self.assertEqual(len(requests_seen), 2)
        self.assertEqual(result["status"], "retrieved")
        connector = next(item for item in result["connectors"] if item["source_id"] == "us_code")
        self.assertEqual(connector["retrieval_status"], "retrieved")
        document = result["documents"][0]
        self.assertEqual(document["document_id"], "17 U.S.C. § 107")
        self.assertEqual(document["document_type"], "statute")
        self.assertEqual(document["source_id"], "us_code")
        self.assertEqual(document["source_as_of_date"], "2026-10-20")
        self.assertTrue(document["canonical_url"].startswith("https://uscode.house.gov/download/"))
        self.assertIn("synthetic test fixture", document["source_text"])
        self.assertEqual(document["contract_excerpt"], contract_excerpt)
        self.assertEqual(
            result["query_disclosure"]["exact_citation_identifiers_sent"],
            [],
        )
        self.assertEqual(
            result["query_disclosure"]["uscode_citation_identifiers_used_for_local_lookup"],
            ["17 U.S.C. § 107"],
        )
        self.assertFalse(result["query_disclosure"]["contract_text_sent"])
        self.assertEqual(
            result["comparisons"][0]["support_assessment"],
            "insufficient_evidence",
        )
        LegalResearchResult.model_validate(result)
        exact = LegalSourceStore(self.store_path).search("17 U.S.C. § 107", "us_code")
        self.assertEqual(len(exact), 1)

    def test_uscode_missing_section_returns_explicit_error_and_no_document(self):
        def fake_get(url, **kwargs):
            if url == "https://uscode.house.gov/download.html":
                return FakeResponse(content=SYNTHETIC_USCODE_DOWNLOAD_PAGE)
            if url.endswith("/xml_usc17@119-134.zip"):
                return FakeResponse(content=self._uscode_zip())
            raise AssertionError(f"Unexpected URL: {url}")

        with patch("backend.services.legal_retrieval.requests.get", side_effect=fake_get):
            result = retrieve_official_materials(
                [],
                [],
                self.store_path,
                "The agreement cites 17 U.S.C. § 999.",
            )

        connector = next(item for item in result["connectors"] if item["source_id"] == "us_code")
        self.assertEqual(connector["retrieval_status"], "provision_not_found")
        self.assertEqual(result["documents"], [])
        self.assertEqual(result["comparisons"], [])
        state = LegalSourceStore(self.store_path).source_state("us_code")
        self.assertIsNone(state["last_successful_retrieval_at"])

    def test_existing_analyze_endpoint_exposes_typed_legal_research_schema(self):
        response_schema = app.openapi()["paths"]["/api/analyze"]["post"]["responses"]["200"]["content"]["application/json"]["schema"]
        response_model = app.openapi()["components"]["schemas"]["ContractAnalysisResponse"]
        legal_schema = app.openapi()["components"]["schemas"]["LawAnalysisResult"]
        self.assertIn("$ref", response_schema)
        self.assertIn("legal_analysis", response_model["properties"])
        self.assertIn("legal_research", legal_schema["properties"])
        self.assertIn("LegalResearchResult", json.dumps(legal_schema))

    def test_official_ecfr_xml_parser_preserves_section_and_text(self):
        parsed = _parse_section(SYNTHETIC_SECTION_XML, "164.520")
        self.assertEqual(parsed["title"], "§ 164.520 Synthetic parser fixture section.")
        self.assertIn("synthetic XML parsing fixture", parsed["text"])
        with self.assertRaises(Exception):
            _parse_section(SYNTHETIC_SECTION_XML, "164.999")

    def test_retrieval_returns_exact_official_identifier_and_source_attribution(self):
        with patch("backend.services.legal_retrieval.requests.get", side_effect=self._fake_http()):
            result = self._retrieve()

        self.assertEqual(result["status"], "retrieved")
        self.assertEqual(result["connectors"][0]["retrieval_status"], "retrieved")
        document = result["documents"][0]
        self.assertEqual(document["document_id"], "45 CFR 164.520")
        self.assertEqual(document["provision_reference"], "45 CFR 164.520")
        self.assertEqual(
            document["canonical_url"],
            "https://www.ecfr.gov/current/title-45/subtitle-A/subchapter-C/part-164/subpart-E/section-164.520",
        )
        self.assertEqual(document["source_id"], "us_ecfr")
        self.assertEqual(document["source_as_of_date"], "2026-10-23")
        self.assertEqual(document["effective_date"], "2024-06-25")
        self.assertIsNone(document["adoption_date"])
        self.assertEqual(
            result["comparisons"][0]["support_assessment"],
            "insufficient_evidence",
        )
        self.assertEqual(
            result["comparisons"][0]["contract_excerpt"],
            "The processor handles personal information.",
        )
        self.assertFalse(result["query_disclosure"]["contract_text_sent"])
        self.assertFalse(result["query_disclosure"]["party_names_sent"])
        LegalResearchResult.model_validate(result)

    def test_contract_cfr_citation_fetches_exact_section_without_sending_contract_text(self):
        requests_seen = []

        def fake_get(url, params=None, **kwargs):
            requests_seen.append((url, params))
            if url == f"{ECFR_API}/versioner/v1/titles":
                return FakeResponse(
                    json_data={
                        "meta": {"date": "2026-10-23", "import_in_progress": False}
                    }
                )
            if "/versioner/v1/full/" in url:
                self.assertEqual(params, {"part": "164", "section": "164.520"})
                return FakeResponse(text=SYNTHETIC_SECTION_XML)
            raise AssertionError(f"Unexpected URL: {url}")

        contract_excerpt = (
            "The processor shall comply with 45 C.F.R. § 164.520 in performing its obligations."
        )
        with patch(
            "backend.services.legal_retrieval.requests.get",
            side_effect=fake_get,
        ):
            result = retrieve_official_materials(
                [{"jurisdiction": "United States of America"}],
                [],
                self.store_path,
                contract_excerpt,
            )

        self.assertEqual(
            [url for url, _ in requests_seen],
            [
                f"{ECFR_API}/versioner/v1/titles",
                f"{ECFR_API}/versioner/v1/full/2026-10-23/title-45.xml",
            ],
        )
        self.assertEqual(result["documents"][0]["document_id"], "45 CFR 164.520")
        self.assertEqual(result["documents"][0]["contract_excerpt"], contract_excerpt)
        self.assertEqual(
            result["query_disclosure"]["exact_citation_identifiers_sent"],
            ["45 CFR 164.520"],
        )
        self.assertFalse(result["query_disclosure"]["contract_text_sent"])
        self.assertEqual(
            result["comparisons"][0]["support_assessment"],
            "insufficient_evidence",
        )
        LegalResearchResult.model_validate(result)

    def test_exact_citation_with_unavailable_section_returns_no_fabricated_document(self):
        def fake_get(url, params=None, **kwargs):
            if url == f"{ECFR_API}/versioner/v1/titles":
                return FakeResponse(
                    json_data={
                        "meta": {"date": "2026-10-23", "import_in_progress": False}
                    }
                )
            if "/versioner/v1/full/" in url:
                return FakeResponse(text=SYNTHETIC_SECTION_XML)
            raise AssertionError(f"Unexpected URL: {url}")

        with patch(
            "backend.services.legal_retrieval.requests.get",
            side_effect=fake_get,
        ):
            result = retrieve_official_materials(
                [{"jurisdiction": "United States of America"}],
                [],
                self.store_path,
                "The parties cite 45 CFR 999.999.",
            )

        connector = result["connectors"][0]
        self.assertEqual(connector["retrieval_status"], "provision_not_found")
        self.assertEqual(connector["errors"][0]["provision_reference"], "45 CFR 999.999")
        self.assertEqual(result["documents"], [])
        self.assertEqual(result["comparisons"], [])
        state = LegalSourceStore(self.store_path).source_state("us_ecfr")
        self.assertIsNone(state["last_successful_retrieval_at"])

    def test_retrieval_archives_versioned_text_and_supports_exact_and_full_text_search(self):
        with patch("backend.services.legal_retrieval.requests.get", side_effect=self._fake_http("2026-10-23")):
            first = self._retrieve()
        with patch("backend.services.legal_retrieval.requests.get", side_effect=self._fake_http("2026-10-24")):
            second = self._retrieve()

        self.assertTrue(first["documents"][0]["version_id"].startswith("2026-10-23:"))
        self.assertTrue(second["documents"][0]["version_id"].startswith("2026-10-24:"))
        store = LegalSourceStore(self.store_path)
        exact = store.search("45 CFR 164.520", "us_ecfr")
        full_text = store.search("synthetic XML parsing fixture", "us_ecfr")
        self.assertEqual(len(exact), 2)
        self.assertEqual({row["version_id"] for row in exact}, {
            first["documents"][0]["version_id"],
            second["documents"][0]["version_id"],
        })
        self.assertEqual(len(full_text), 2)
        with closing(sqlite3.connect(self.store_path)) as connection:
            self.assertGreater(
                connection.execute(
                    "SELECT COUNT(*) FROM legal_source_registry"
                ).fetchone()[0],
                10,
            )
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM legal_documents").fetchone()[0],
                2,
            )

    def test_changed_text_on_same_source_date_is_retained_as_a_distinct_snapshot(self):
        changed_xml = SYNTHETIC_SECTION_XML.replace(
            "not legal text", "changed synthetic fixture text"
        )
        with patch(
            "backend.services.legal_retrieval.requests.get",
            side_effect=self._fake_http(section_xml=SYNTHETIC_SECTION_XML),
        ):
            first = self._retrieve()
        with patch(
            "backend.services.legal_retrieval.requests.get",
            side_effect=self._fake_http(section_xml=changed_xml),
        ):
            second = self._retrieve()

        self.assertEqual(first["documents"][0]["source_as_of_date"], "2026-10-23")
        self.assertEqual(second["documents"][0]["source_as_of_date"], "2026-10-23")
        self.assertNotEqual(first["documents"][0]["version_id"], second["documents"][0]["version_id"])
        self.assertEqual(
            len(LegalSourceStore(self.store_path).search("45 CFR 164.520", "us_ecfr")),
            2,
        )

    def test_old_source_version_is_flagged_and_unknown_dates_stay_unknown(self):
        with patch(
            "backend.services.legal_retrieval._request_text",
            return_value=SYNTHETIC_SECTION_XML,
        ):
            result = _build_document(
                _search_result(),
                "2000-01-01",
                "Data protection and transfers",
                "Contract excerpt.",
            )
        self.assertEqual(result["currency_status"], "stale_source_date")
        self.assertIsNone(result["publication_date"])
        self.assertIsNone(result["adoption_date"])
        self.assertIsNone(result["entry_into_force_date"])

    def test_timeout_rate_limit_and_http_errors_are_explicit(self):
        with patch(
            "backend.services.legal_retrieval.requests.get",
            side_effect=requests.Timeout(),
        ):
            with self.assertRaisesRegex(Exception, "timed out") as timeout:
                _request_json(f"{ECFR_API}/search/v1/results")
        self.assertEqual(timeout.exception.status, "timeout")

        with patch(
            "backend.services.legal_retrieval.requests.get",
            return_value=FakeResponse(status_code=429, headers={"Retry-After": "30"}),
        ):
            with self.assertRaisesRegex(Exception, "rate limit") as limited:
                _request_json(f"{ECFR_API}/search/v1/results")
        self.assertEqual(limited.exception.status, "rate_limited")
        self.assertEqual(limited.exception.retry_after, "30")

        with patch(
            "backend.services.legal_retrieval.requests.get",
            return_value=FakeResponse(status_code=503),
        ):
            with self.assertRaisesRegex(Exception, "HTTP 503") as unavailable:
                _request_json(f"{ECFR_API}/search/v1/results")
        self.assertEqual(unavailable.exception.status, "http_error")

    def test_connector_failure_is_reported_without_a_success_shaped_result(self):
        with patch(
            "backend.services.legal_retrieval.requests.get",
            side_effect=requests.Timeout(),
        ):
            result = self._retrieve()
        connector = result["connectors"][0]
        self.assertEqual(connector["retrieval_status"], "timeout")
        self.assertEqual(connector["errors"][0]["status"], "timeout")
        self.assertEqual(result["documents"], [])
        self.assertEqual(result["comparisons"], [])
        state = LegalSourceStore(self.store_path).source_state("us_ecfr")
        self.assertEqual(state["retrieval_status"], "timeout")
        self.assertIsNone(state["last_successful_retrieval_at"])

    def test_no_us_jurisdiction_does_not_send_search_request(self):
        with patch("backend.services.legal_retrieval.requests.get") as request:
            result = retrieve_official_materials(
                [{"jurisdiction": "Germany"}],
                [
                    {
                        "contract_topic": "Data protection and transfers",
                        "contract_clause_text": "Contract text.",
                    }
                ],
                self.store_path,
            )
        request.assert_not_called()
        self.assertEqual(
            result["connectors"][0]["retrieval_status"],
            "not_searched_jurisdiction_not_identified",
        )
        self.assertEqual(result["documents"], [])

    def test_live_ecfr_search_and_versioned_text_retrieval(self):
        if os.environ.get("RUN_LIVE_LEGAL_SOURCE_TESTS") != "1":
            self.skipTest("Set RUN_LIVE_LEGAL_SOURCE_TESTS=1 for the official-source integration test.")
        result = retrieve_official_materials(
            [{"jurisdiction": "United States of America"}],
            [
                {
                    "contract_topic": "Data protection and transfers",
                    "contract_clause_text": "Synthetic integration-test evidence only.",
                }
            ],
            self.store_path,
        )
        self.assertIn(result["connectors"][0]["retrieval_status"], {"retrieved", "partial_failure"})
        self.assertTrue(result["documents"], result["connectors"][0]["errors"])
        for document in result["documents"]:
            self.assertTrue(document["canonical_url"].startswith("https://www.ecfr.gov/"))
            self.assertRegex(document["document_id"], r"^\d+ CFR ")
            self.assertTrue(document["source_text"])
            self.assertEqual(document["verification_status"], "official_text_retrieved; applicability_not_verified")

    def test_live_uscode_exact_section_download(self):
        if os.environ.get("RUN_LIVE_LEGAL_SOURCE_TESTS") != "1":
            self.skipTest("Set RUN_LIVE_LEGAL_SOURCE_TESTS=1 for the official-source integration test.")
        result = retrieve_official_materials(
            [],
            [],
            self.store_path,
            "The agreement references 17 U.S.C. § 512(a).",
        )
        connector = next(item for item in result["connectors"] if item["source_id"] == "us_code")
        self.assertEqual(connector["retrieval_status"], "retrieved", connector["errors"])
        self.assertEqual(len(result["documents"]), 1)
        document = result["documents"][0]
        self.assertEqual(document["document_id"], "17 U.S.C. § 512(a)")
        self.assertTrue(document["title"])
        self.assertIn("(a)", document["source_text"])
        self.assertTrue(document["canonical_url"].startswith("https://uscode.house.gov/download/"))
        self.assertEqual(document["verification_status"], "official_text_retrieved; applicability_not_verified")
        LegalResearchResult.model_validate(result)


if __name__ == "__main__":
    unittest.main()
