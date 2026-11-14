"""Price signals are review requests, not approval to set estimated floors."""
import unittest
from unitka import rules as r


def data(**changes):
    value=dict(sku="1",offer_id="A",stock=1,price=1000,min_price=1200,
               margin_pct=-10,revenue_30d=10000,cost=400,sold_14d=0,days_no_sales=0)
    value.update(changes)
    return value


class PriceAdviceTests(unittest.TestCase):
    def setUp(self):r.set_thresholds(None)
    def tearDown(self):r.set_thresholds(None)

    def test_gap_amount_unchanged_but_not_called_loss(self):
        task=r.check_price_below_min(data(stock=2))
        self.assertEqual(task.money_impact,400)
        self.assertIn("не денежный убыток",task.problem)

    def test_gap_requires_separate_price_approval(self):
        action=r.check_price_below_min(data()).action
        self.assertIn("согласовать отдельно",action)
        self.assertNotIn("Поднять цену",action)

    def test_negative_margin_below_floor_requires_review(self):
        task=r.check_negative_margin(data())
        self.assertEqual(task.money_impact,1000)
        self.assertIn("согласовать отдельно",task.action)
        self.assertNotIn("Поднять цену",task.action)
        self.assertIn("оценка прямого убытка",task.problem)

    def test_above_floor_loss_still_reviews_services_and_returns(self):
        task=r.check_negative_margin(data(price=1300))
        self.assertIn("уже выше",task.action)
        self.assertIn("услуги и возвраты",task.action)

    def test_unknown_floor_does_not_recommend_raise_or_disable(self):
        task=r.check_negative_margin(data(min_price=None))
        self.assertIn("не менять цену",task.action)
        self.assertNotIn("отключить",task.action)

    def test_unknown_current_price_requires_review(self):
        self.assertIn("не менять цену",r.check_negative_margin(data(price=None)).action)

    def test_invalid_price_inputs_do_not_create_gap(self):
        for field in ("price","min_price","stock"):
            for value in (None,float("nan"),float("inf"),True,"bad",-1):
                with self.subTest(field=field,value=value):
                    self.assertIsNone(r.check_price_below_min(data(**{field:value})))

    def test_invalid_margin_inputs_do_not_create_fake_loss(self):
        for field in ("margin_pct","revenue_30d"):
            for value in (None,float("nan"),float("inf"),True,"bad"):
                with self.subTest(field=field,value=value):
                    self.assertIsNone(r.check_negative_margin(data(**{field:value})))

    def test_no_stock_no_gap(self):
        self.assertIsNone(r.check_price_below_min(data(stock=0)))

    def test_price_at_or_above_floor_no_gap(self):
        for price in (1200,1300):
            self.assertIsNone(r.check_price_below_min(data(price=price)))

    def test_zero_revenue_no_margin_loss(self):
        self.assertIsNone(r.check_negative_margin(data(revenue_30d=0)))

    def test_margin_threshold_preserved(self):
        self.assertIsNone(r.check_negative_margin(data(margin_pct=-5)))
        self.assertIsNotNone(r.check_negative_margin(data(margin_pct=-5.01)))

    def test_extreme_gap_fails_closed(self):
        self.assertIsNone(r.check_price_below_min(data(price=1,min_price=1e308,stock=1e308)))

    def test_extreme_loss_fails_closed(self):
        self.assertIsNone(r.check_negative_margin(data(revenue_30d=1e308,margin_pct=-1e308)))

    def test_actual_two_loss_amounts_reproduced(self):
        for revenue,margin,expected in ((7918,-36.35665572114169,2878.72),
                                        (12969,-5.703215359703907,739.65)):
            task=r.check_negative_margin(data(revenue_30d=revenue,margin_pct=margin))
            self.assertAlmostEqual(task.money_impact,expected,places=2)
            self.assertIn("согласовать отдельно",task.action)

    def test_legacy_prefixes_and_rule_ids_preserved(self):
        price=r.check_price_below_min(data());loss=r.check_negative_margin(data())
        self.assertEqual(price.rule_id,"price_below_min");self.assertTrue(price.problem.startswith("Цена"))
        self.assertEqual(loss.rule_id,"negative_margin");self.assertTrue(loss.problem.startswith("Маржинальность"))

    def test_other_rule_safety_preserved(self):
        task=r.check_out_of_stock(data(stock=0,sold_14d=2,avg_price=1000))
        self.assertIn("не рекомендовано",task.action)
        self.assertEqual(r.check_dead_stock(data(stock=2,days_no_sales=90)).money_impact,800)


if __name__ == "__main__":
    unittest.main()
