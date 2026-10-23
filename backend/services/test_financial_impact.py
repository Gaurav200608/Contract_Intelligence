import unittest

from backend.services.financial_impact_engine import analyze_financial_impact


class FinancialImpactTests(unittest.TestCase):
    def test_decimal_interest_rate_is_not_mistaken_for_principal(self):
        result = analyze_financial_impact(
            "Late payments may attract interest at 1.5% per month."
        )

        self.assertEqual(result["financial_terms_detected"], 1)
        item = result["items"][0]
        self.assertEqual(item["evidence"], "Late payments may attract interest at 1.5% per month.")
        self.assertEqual(item["percentages"], [1.5])
        self.assertEqual(item["amounts"], [])
        self.assertEqual(item["calculation_status"], "not_calculable")
        self.assertIsNone(item["calculated_exposure"])

    def test_interest_calculation_uses_principal_rate_and_numeric_duration(self):
        result = analyze_financial_impact(
            "Interest on USD 1,000 at 1.5% for 30 days."
        )

        self.assertEqual(len(result["calculations"]), 1)
        self.assertEqual(result["calculations"][0]["amount"], 1.23)
        self.assertEqual(result["calculations"][0]["currency"], "USD")

    def test_contract_value_and_penalty_exposure_are_compared(self):
        result = analyze_financial_impact(
            "Contract value is USD 10,000. "
            "The Supplier shall pay a fixed penalty of USD 2,000 for delay."
        )

        self.assertEqual(result["contract_value"]["amount"], 10000)
        self.assertEqual(result["total_calculated_exposure"], 2000)
        self.assertEqual(result["exposure_ratio"], 0.2)

    def test_uncapped_liability_is_not_scored_as_low_financial_risk(self):
        result = analyze_financial_impact(
            "The Supplier has unlimited liability for all losses."
        )

        self.assertEqual(result["financial_risk"], "High")
        self.assertEqual(result["risk_factors"][0]["severity"], "High")

    def test_repeated_medium_factors_do_not_inflate_the_score(self):
        result = analyze_financial_impact(
            "Limitation of Liability. "
            "Neither party shall be liable for indirect damages. "
            "Aggregate liability shall be agreed in a schedule. "
            "Late payments may attract interest at 1.5% per month."
        )

        self.assertEqual(
            sum(factor["severity"] == "Medium" for factor in result["risk_factors"]),
            3,
        )
        self.assertEqual(result["financial_risk"], "Medium")

    def test_annual_renewal_fee_estimates_stated_term_total(self):
        result = analyze_financial_impact(
            "The annual renewal fee is USD 12,000 for each of 2 years."
        )

        self.assertEqual(result["total_calculated_exposure"], 24000)
        self.assertEqual(result["exposure_currency"], "USD")


if __name__ == "__main__":
    unittest.main()
