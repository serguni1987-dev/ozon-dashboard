"""Out-of-stock recommendation and threshold isolation tests."""
import math
import unittest
from unitka import rules as r


def sku(**changes):
    data = dict(sku="1",offer_id="A",stock=0,sold_14d=14,avg_price=1000,
                cost=400,min_price=800,price=1000,margin_pct=20,revenue_30d=30000)
    data.update(changes)
    return data


class PurchaseSafetyTests(unittest.TestCase):
    def setUp(self):r.set_thresholds(None)
    def tearDown(self):r.set_thresholds(None)

    def test_negative_margin_blocks_restock_recommendation(self):
        task=r.check_out_of_stock(sku(margin_pct=-20))
        self.assertIn("не рекомендовано",task.action)

    def test_zero_margin_blocks(self):
        self.assertIn("не рекомендовано",r.check_out_of_stock(sku(margin_pct=0)).action)

    def test_price_below_floor_blocks_even_if_history_positive(self):
        self.assertIn("не рекомендовано",r.check_out_of_stock(sku(price=700)).action)

    def test_missing_cost_blocks(self):
        self.assertIn("недостаточно",r.check_out_of_stock(sku(cost=0)).action)

    def test_missing_floor_blocks(self):
        self.assertIn("недостаточно",r.check_out_of_stock(sku(min_price=None)).action)

    def test_missing_margin_blocks(self):
        data=sku();data.pop("margin_pct")
        self.assertIn("недостаточно",r.check_out_of_stock(data).action)

    def test_nonfinite_economics_blocks(self):
        for field in ("cost","min_price","price","margin_pct","revenue_30d"):
            with self.subTest(field=field):
                self.assertIn("недостаточно",r.check_out_of_stock(sku(**{field:float("nan")})).action)

    def test_positive_direct_margin_still_requires_full_profit_check(self):
        task=r.check_out_of_stock(sku())
        self.assertIn("только после",task.action)
        self.assertIn("полной прибыли",task.action)
        self.assertNotIn("Срочно",task.action)

    def test_potential_revenue_formula_unchanged(self):
        task=r.check_out_of_stock(sku())
        self.assertEqual(task.money_impact,7000)
        self.assertIn("оценка",task.problem)

    def test_invalid_average_has_no_invented_amount(self):
        for average in (None,0,-1,float("inf")):
            with self.subTest(average=average):
                self.assertEqual(r.check_out_of_stock(sku(avg_price=average)).money_impact,0)

    def test_no_demand_no_task(self):
        self.assertIsNone(r.check_out_of_stock(sku(sold_14d=0)))

    def test_stock_available_no_task(self):
        self.assertIsNone(r.check_out_of_stock(sku(stock=2)))

    def test_unknown_stock_not_treated_as_zero(self):
        data=sku();data.pop("stock")
        self.assertIsNone(r.check_out_of_stock(data))

    def test_invalid_demand_no_task(self):
        for demand in (None,-1,float("nan"),True):
            with self.subTest(demand=demand):
                self.assertIsNone(r.check_out_of_stock(sku(sold_14d=demand)))

    def test_thresholds_reset_between_runs(self):
        r.set_thresholds({"oos_lost_days":30})
        self.assertEqual(r.THRESHOLDS["oos_lost_days"],30)
        r.set_thresholds(None)
        self.assertEqual(r.THRESHOLDS["oos_lost_days"],7)

    def test_partial_settings_do_not_leak_previous_override(self):
        r.set_thresholds({"oos_lost_days":30})
        r.set_thresholds({"dead_stock_days":90})
        self.assertEqual(r.THRESHOLDS["oos_lost_days"],7)
        self.assertEqual(r.THRESHOLDS["dead_stock_days"],90)

    def test_invalid_threshold_overrides_ignored(self):
        r.set_thresholds({"oos_lost_days":float("inf"),"dead_stock_days":True,
                          "negative_margin_pct":5,"unknown":10})
        self.assertEqual(r.THRESHOLDS,r.DEFAULT_THRESHOLDS)

    def test_other_rule_amounts_unchanged(self):
        self.assertEqual(r.check_price_below_min(sku(stock=2,price=700)).money_impact,200)
        self.assertEqual(r.check_negative_margin(sku(margin_pct=-10)).money_impact,3000)
        self.assertEqual(r.check_dead_stock(sku(stock=2,days_no_sales=90)).money_impact,800)

    def test_evaluate_keeps_out_of_stock_rule_id(self):
        tasks=r.evaluate_sku(sku())
        self.assertEqual([t.rule_id for t in tasks],["out_of_stock"])


if __name__ == "__main__":
    unittest.main()
