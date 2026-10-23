import os
import unittest
from unittest.mock import patch

from backend.services.law_analysis import analyze_law_context
from backend.services.legal_sources import (
    JURISDICTION_SOURCES,
    _check_portal,
    legal_sources_for,
)
from backend.services.clause_extractor import extract_clauses
from backend.services.document_parser import extract_document


CROSS_BORDER_CONTRACT = (
    "This Software Services Agreement is between Beispiel GmbH, a company "
    "incorporated in Germany (Provider), and Bharat Tech Private Limited, "
    "incorporated in India (Customer). "
    "This Agreement shall be governed by the laws of Germany. "
    "The courts of Berlin shall have exclusive jurisdiction. "
    "Any disputes shall be resolved by arbitration seated in Berlin under "
    "the agreed rules. Provider processes personal data in India."
)


class LawAnalysisTests(unittest.TestCase):
    def test_repository_sample_pdf_law_analysis_uses_its_real_clause_text(self):
        sample_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "data",
            "sample_contracts",
            "sample_contract.pdf",
        )
        extracted = extract_document(sample_path)
        result = analyze_law_context(
            extracted["text"],
            "Service agreement",
            extract_clauses(extracted["text"]),
        )
        parties = result["overview"]["parties"]
        self.assertEqual(
            [(party["name"], party["role"]) for party in parties],
            [
                ("ABC Technologies Pvt. Ltd", "Company"),
                ("XYZ Solutions", "Service Provider"),
            ],
        )
        self.assertEqual(
            result["overview"]["governing_law"]["jurisdiction"], "India"
        )
        self.assertTrue(
            any(
                finding["contract_topic"] == "Data protection and transfers"
                and finding["affected_party"] == "XYZ Solutions"
                for finding in result["findings"]
            )
        )

    def test_cross_border_parties_law_and_dispute_terms_are_evidence_linked(self):
        result = analyze_law_context(
            CROSS_BORDER_CONTRACT,
            "Service agreement",
            [
                {
                    "type": "Data Protection",
                    "title": "Data",
                    "text": "Provider processes personal data in India.",
                }
            ],
        )

        parties = result["overview"]["parties"]
        self.assertEqual(
            [(party["name"], party["role"], party["country"]) for party in parties],
            [
                ("Beispiel GmbH", "Provider", "Germany"),
                ("Bharat Tech Private Limited", "Customer", "India"),
            ],
        )
        self.assertEqual(
            result["overview"]["governing_law"]["jurisdiction"], "Germany"
        )
        self.assertIn("Germany", {
            item["jurisdiction"]
            for item in result["overview"]["potential_jurisdictions"]
        })
        self.assertIn("India", {
            item["jurisdiction"]
            for item in result["overview"]["potential_jurisdictions"]
        })
        dispute = result["overview"]["dispute_resolution"]
        self.assertTrue(dispute["court_jurisdiction_evidence"])
        self.assertTrue(dispute["arbitration_evidence"])
        data_finding = next(
            item
            for item in result["findings"]
            if item["contract_topic"] == "Data protection and transfers"
        )
        self.assertIn("personal data", data_finding["contract_clause_text"])
        self.assertEqual(data_finding["affected_party"], "Beispiel GmbH")
        self.assertEqual(data_finding["jurisdiction"], "India")
        self.assertIsNone(data_finding["legal_provision_reference"])
        self.assertTrue(data_finding["requires_lawyer_review"])
        self.assertEqual(result["source_verification"]["verified_provisions"], [])

    def test_company_country_is_not_assumed_from_governing_law(self):
        result = analyze_law_context(
            "Acme GmbH (Provider) and Bharat Tech Private Limited (Customer) "
            "agree that this contract is governed by German law."
        )
        parties = result["overview"]["parties"]
        self.assertEqual([party["country"] for party in parties], [None, None])
        self.assertEqual(
            result["overview"]["governing_law"]["jurisdiction"], "Germany"
        )
        self.assertTrue(
            any("registered-office country" in item for item in result["overview"]["missing_or_uncertain_information"])
        )

    def test_individual_party_is_identified_only_with_party_role_evidence(self):
        result = analyze_law_context(
            "This agreement is between John Doe (Customer), an individual residing in India, "
            "and Example Systems Inc. (Provider), incorporated in Germany."
        )
        parties = result["overview"]["parties"]
        john = next(party for party in parties if party["name"] == "John Doe")
        self.assertEqual(john["party_type"], "individual")
        self.assertEqual(john["role"], "Customer")
        self.assertEqual(john["country"], "India")
        self.assertEqual(
            next(party for party in parties if party["name"] == "Example Systems Inc")["country"],
            "Germany",
        )

    def test_named_contract_party_without_corporate_suffix_is_recognized_by_role(self):
        result = analyze_law_context(
            "ABC Technologies Pvt. Ltd. (the Company) and XYZ Solutions "
            "(the Service Provider) enter into this agreement."
        )
        parties = result["overview"]["parties"]
        self.assertIn("ABC Technologies Pvt. Ltd", [party["name"] for party in parties])
        company = next(
            party for party in parties if party["name"] == "ABC Technologies Pvt. Ltd"
        )
        self.assertEqual(company["role"], "Company")
        provider = next(party for party in parties if party["name"] == "XYZ Solutions")
        self.assertEqual(provider["role"], "Service Provider")
        self.assertIsNone(provider["country"])

    def test_missing_governing_law_is_not_inferred_from_country_mentions(self):
        result = analyze_law_context(
            "The parties deliver services in Germany and India. The agreement covers payment."
        )
        self.assertFalse(result["overview"]["governing_law"]["clause_found"])
        self.assertIsNone(result["overview"]["governing_law"]["jurisdiction"])
        self.assertTrue(
            any(
                finding["finding_id"] == "missing-governing-law"
                for finding in result["findings"]
            )
        )

    def test_law_findings_match_structured_schema_and_never_fabricate_citations(self):
        result = analyze_law_context(
            CROSS_BORDER_CONTRACT,
            "Software services",
        )
        self.assertEqual(result["method"], "evidence_based_rules")
        for finding in result["findings"]:
            self.assertEqual(finding["legal_provision_name"], None)
            self.assertEqual(finding["legal_provision_reference"], None)
            self.assertEqual(finding["source_verified_at"], None)
            self.assertIn(
                finding["source_verification_status"],
                {
                    "not_checked",
                    "no_jurisdiction_specific_source",
                    "portal_reachable_provision_not_verified",
                    "portal_unavailable_provision_not_verified",
                },
            )

    def test_supported_jurisdiction_registry_preserves_regional_distinctions(self):
        self.assertEqual(
            set(JURISDICTION_SOURCES),
            {
                "India",
                "United Kingdom",
                "Germany",
                "United States of America",
                "United Arab Emirates",
                "Israel",
                "China",
                "France",
            },
        )
        self.assertTrue(
            any("Scotland" in region for region in JURISDICTION_SOURCES["United Kingdom"]["regions"])
        )
        self.assertTrue(
            any("DIFC" in region for region in JURISDICTION_SOURCES["United Arab Emirates"]["regions"])
        )
        self.assertTrue(
            any("Hong Kong" in region for region in JURISDICTION_SOURCES["China"]["regions"])
        )

    def test_governing_law_and_regional_variants_are_separated(self):
        cases = [
            ("laws of India", "India", None),
            ("laws of Scotland", "United Kingdom", "Scotland"),
            ("laws of England and Wales", "United Kingdom", "England and Wales"),
            ("New York law", "United States of America", "United States — New York"),
            ("laws of DIFC", "United Arab Emirates", "Dubai International Financial Centre (DIFC)"),
            ("laws of Hong Kong", "China", "Hong Kong (separate legal system)"),
            ("laws of France", "France", None),
            ("laws of Germany", "Germany", None),
            ("laws of Israel", "Israel", None),
        ]
        for clause, jurisdiction, region in cases:
            with self.subTest(clause=clause):
                result = analyze_law_context(f"This agreement is governed by {clause}.")
                self.assertEqual(
                    result["overview"]["governing_law"]["jurisdiction"],
                    jurisdiction,
                )
                if region:
                    self.assertEqual(
                        result["overview"]["governing_law"]["region"], region
                    )

    def test_source_links_are_not_called_verified_when_portal_is_reachable(self):
        _check_portal.cache_clear()
        response = type("Response", (), {"status": 200, "__enter__": lambda self: self, "__exit__": lambda *args: None})()
        with patch("backend.services.legal_sources.urlopen", return_value=response):
            with patch.dict(os.environ, {"LEGAL_SOURCE_LIVE_CHECK": "1"}):
                result = analyze_law_context(
                    "This contract is governed by German law."
                )
        germany = next(
            item for item in result["legal_sources"] if item["jurisdiction"] == "Germany"
        )
        self.assertEqual(
            germany["sources"][0]["verification_status"],
            "portal_reachable_provision_not_verified",
        )
        self.assertFalse(germany["sources"][0]["provision_verified"])
        _check_portal.cache_clear()

    def test_source_timeout_is_reported_as_unavailable_not_verified(self):
        _check_portal.cache_clear()
        with patch(
            "backend.services.legal_sources.urlopen", side_effect=TimeoutError
        ):
            with patch.dict(os.environ, {"LEGAL_SOURCE_LIVE_CHECK": "1"}):
                result = analyze_law_context(
                    "This agreement is governed by Indian law."
                )
        india = next(
            item for item in result["legal_sources"] if item["jurisdiction"] == "India"
        )
        source = india["sources"][0]
        self.assertEqual(
            source["verification_status"],
            "portal_unavailable_provision_not_verified",
        )
        self.assertFalse(source["provision_verified"])
        self.assertTrue(source["checked_at"])
        _check_portal.cache_clear()

    def test_ambiguous_or_unmentioned_law_sources_are_not_filled_with_all_countries(self):
        result = analyze_law_context(
            "A short agreement requires payment within thirty days."
        )
        self.assertEqual(result["legal_sources"], [])
        self.assertEqual(result["overview"]["potential_jurisdictions"], [])


if __name__ == "__main__":
    unittest.main()
