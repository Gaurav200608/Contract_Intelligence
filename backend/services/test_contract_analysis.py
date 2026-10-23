import os
import unittest

from backend.services.clause_extractor import extract_clauses
from backend.services.contract_type_detector import detect_contract_type
from backend.services.document_parser import extract_text
from backend.services.law_analysis import analyze_law_context


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SAMPLE_CONTRACT = os.path.join(ROOT_DIR, "data", "sample_contracts", "sample_contract.pdf")


class ContractAnalysisTests(unittest.TestCase):
    def test_extract_text_from_sample_contract(self):
        text = extract_text(SAMPLE_CONTRACT)
        self.assertIsInstance(text, str)
        self.assertGreater(len(text), 200)
        self.assertIn("agreement", text.lower())

    def test_extract_clauses_recognizes_known_patterns(self):
        text = (
            "1. Payment. Payment shall be made within 30 days of invoice.\n\n"
            "2. Confidentiality. The recipient shall protect confidential information.\n\n"
            "3. Termination. Either party may terminate on 30 days' notice."
        )
        clauses = extract_clauses(text)
        clause_types = {entry["type"] for entry in clauses}
        self.assertTrue(clauses)
        self.assertIn("Payment", clause_types)
        self.assertIn("Confidentiality", clause_types)

    def test_detect_contract_type_uses_keyword_signals(self):
        text = (
            "This consulting agreement sets out professional services, fees, and payment terms. "
            "The consultant shall protect confidential information and deliver work product."
        )
        result = detect_contract_type(text)
        self.assertNotEqual(result["category"], "Other/Unknown")
        self.assertGreaterEqual(result["confidence"], 0.3)

    def test_law_analysis_returns_informational_summary(self):
        result = analyze_law_context(
            "This Agreement shall be governed by the laws of India and subject to the jurisdiction of the courts in Mumbai.",
            "Service agreement",
        )
        self.assertEqual(result["status"], "informational")
        self.assertEqual(result["governing_law"], "India")


if __name__ == "__main__":
    unittest.main()