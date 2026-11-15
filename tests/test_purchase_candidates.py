import unittest
from unitka.purchase_candidates import forecast_candidates, candidate_text


class PurchaseCandidateTests(unittest.TestCase):
    def row(self, **changes):
        row = dict(sku="123", offer_id="ART-1", forecast_qty=10, forecast_revenue=1000)
        row.update(changes)
        return row

    def test_identifiers_kept_separate(self):
        result = forecast_candidates([self.row()])[0]
        self.assertEqual((result["sku"], result["offer_id"]), ("123", "ART-1"))

    def test_forecast_never_approves_purchase(self):
        result = forecast_candidates([self.row()])[0]
        self.assertIs(result["purchase_approved"], False)
        self.assertNotIn("buy_qty", result)
        self.assertIn("Закупка не согласована", candidate_text(result))

    def test_invalid_quantities_omitted(self):
        for value in (None, True, 0, -1, "bad", float("nan"), float("inf")):
            with self.subTest(value=value):
                self.assertEqual(forecast_candidates([self.row(forecast_qty=value)]), [])

    def test_invalid_sku_omitted(self):
        for value in (None, True, "", "ABC", "0", "-1", "1.2"):
            with self.subTest(value=value):
                self.assertEqual(forecast_candidates([self.row(sku=value)]), [])

    def test_duplicate_sku_omitted_even_if_other_row_invalid(self):
        self.assertEqual(forecast_candidates([self.row(), self.row(sku="0123", forecast_qty=None)]), [])

    def test_unknown_revenue_not_zero(self):
        for value in (None, "bad", float("nan"), float("inf"), True):
            result = forecast_candidates([self.row(forecast_revenue=value)])[0]
            self.assertIsNone(result["forecast_revenue"])
            self.assertIs(result["purchase_approved"], False)

    def test_negative_revenue_omitted(self):
        self.assertEqual(forecast_candidates([self.row(forecast_revenue=-1)]), [])

    def test_missing_offer_uses_sku(self):
        result = forecast_candidates([self.row(offer_id=None)])[0]
        self.assertIn("123 (SKU 123)", candidate_text(result))

    def test_sort_is_deterministic(self):
        rows = [self.row(sku="2"), self.row(sku="1")]
        self.assertEqual([r["sku"] for r in forecast_candidates(rows)], ["1", "2"])

    def test_input_not_mutated(self):
        row = self.row()
        before = dict(row)
        forecast_candidates([row])
        self.assertEqual(row, before)


if __name__ == "__main__":
    unittest.main()
