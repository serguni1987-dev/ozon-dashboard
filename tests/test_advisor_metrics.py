"""Separated financial metrics and AI-output guards; entirely offline."""
import contextlib
import copy
import io
import sys
import types
import unittest
from unittest.mock import patch
import unitka
from unitka import ai_advisor as a


def task(rule,amount,sku="1",**extra):
    result=dict(severity="1",offer_id="A"+sku,sku=sku,problem="Проверка",action="Проверить расходы",
                amount=amount,status="",rule_id=rule,kind="other",kind_label="old")
    result.update(extra)
    return result


class AdvisorMetricsTests(unittest.TestCase):
    def test_mixed_metrics_have_no_total(self):
        facts=a.build_facts([task("negative_margin",100),task("price_below_min",200,"2"),
                            task("out_of_stock",300,"3"),task("dead_stock",400,"4")],10)
        self.assertIsNone(facts["loss_total"])
        self.assertIsNone(facts["top_sum"])
        self.assertFalse(facts["mixed_total_available"])
        self.assertEqual(facts["totals"],dict(loss_30d=100,loss_stock=200,lost_revenue=300,frozen=400,other=0))

    def test_same_kind_sums_only_within_kind(self):
        facts=a.build_facts([task("negative_margin",100),task("negative_margin",200,"2")])
        self.assertEqual(facts["totals"]["loss_30d"],300)
        self.assertEqual(facts["totals"]["loss_stock"],0)

    def test_exact_duplicates_not_double_counted(self):
        row=task("negative_margin",100)
        facts=a.build_facts([row,dict(row)])
        self.assertEqual(facts["totals"]["loss_30d"],100)
        self.assertEqual(facts["duplicate_rows_ignored"],1)

    def test_conflicting_amounts_excluded(self):
        facts=a.build_facts([task("negative_margin",100),task("negative_margin",200)])
        self.assertEqual(facts["conflicting_groups"],1)
        self.assertEqual(facts["totals"]["loss_30d"],0)
        self.assertEqual(facts["top"],[])

    def test_conflicting_actions_excluded(self):
        facts=a.build_facts([task("negative_margin",100),task("negative_margin",100,action="Другой вариант")])
        self.assertEqual(facts["conflicting_groups"],1)

    def test_closed_rows_excluded(self):
        facts=a.build_facts([task("negative_margin",100,status="Выполнено")])
        self.assertEqual(facts["done_count"],1)
        self.assertEqual(facts["open_count"],0)

    def test_invalid_money_never_aggregated(self):
        for value in (None,float("nan"),float("inf"),"bad",-100,0,True):
            facts=a.build_facts([task("negative_margin",value)])
            with self.subTest(value=value):
                self.assertEqual(facts["totals"]["loss_30d"],0)
                self.assertEqual(facts["unpriced_groups"],1)

    def test_russian_number_formats(self):
        for value in ("1 234,50 ₽","1\u00a0234,50","1\u202f234,50"):
            self.assertEqual(a._num(value),1234.5)

    def test_rule_controls_kind_not_input_label(self):
        facts=a.build_facts([task("price_below_min",100,kind="loss_30d")])
        self.assertEqual(facts["totals"]["loss_stock"],100)
        self.assertEqual(facts["totals"]["loss_30d"],0)

    def test_same_sku_different_kinds_not_combined(self):
        facts=a.build_facts([task("negative_margin",100),task("price_below_min",200)])
        self.assertEqual(len(facts["top"]),1)
        self.assertEqual(facts["totals"]["loss_30d"],100)
        self.assertEqual(facts["totals"]["loss_stock"],200)

    def test_unknown_rule_kept_separate(self):
        self.assertEqual(a.build_facts([task("new_rule",100)])["totals"]["other"],100)

    def test_input_not_mutated(self):
        rows=[task("negative_margin",100)];before=copy.deepcopy(rows)
        a.build_facts(rows)
        self.assertEqual(rows,before)

    def test_empty_top_does_not_claim_plan_completed(self):
        facts=a.build_facts([task("negative_margin",None)])
        self.assertNotIn("План действий выполнен",a.render_cfo(facts))
        self.assertIn("не означает",a.render_cfo(facts))
        self.assertIn("не подтверждено",a.render_mentor(facts))

    def test_render_labels_price_gap_correctly(self):
        text=a.render_cfo(a.build_facts([task("price_below_min",100)]))
        self.assertIn("ценовой разрыв",text.lower())
        self.assertIn("не денежный убыток",text)
        self.assertNotIn("Сумма по топ",text)

    def test_mentor_template_has_no_combined_threat_amount(self):
        facts=a.build_facts([task("negative_margin",100),task("dead_stock",200,"2")])
        self.assertNotIn("Под угрозой",a.render_mentor(facts))
        self.assertIn("не складываются",a.render_mentor(facts))

    def test_legacy_sheet_rows_parse_and_keep_unknown_amount(self):
        rows=[[],[],[],["1","A","1","Цена ниже порога","Проверить","bad",""]]
        result=a.tasks_from_rows(rows)
        self.assertEqual(result[0]["rule_id"],"price_below_min")
        self.assertIsNone(result[0]["amount"])

    def test_mentor_payload_omits_mixed_totals(self):
        facts=a.build_facts([task("negative_margin",100)])
        with patch.object(a,"ask_model",return_value=({"text":"Проверьте исходные расходы."},"")) as ask:
            text,_=a.mentor_from_model(facts,"model")
        self.assertTrue(text)
        payload=ask.call_args.args[1]
        self.assertNotIn("loss_total",payload)
        self.assertNotIn("top_sum",payload)

    def test_mentor_rejects_numbers_even_if_known(self):
        facts=a.build_facts([task("negative_margin",100)])
        with patch.object(a,"ask_model",return_value=({"text":"Убыток 100 рублей."},"")):
            self.assertEqual(a.mentor_from_model(facts,"model")[0],"")

    def test_mentor_rejects_aggregate_claim(self):
        facts=a.build_facts([task("negative_margin",100)])
        with patch.object(a,"ask_model",return_value=({"text":"Общая сумма потерь велика."},"")):
            self.assertEqual(a.mentor_from_model(facts,"model")[0],"")

    def test_why_rejects_digits_bool_index_and_foreign(self):
        facts=a.build_facts([task("negative_margin",100)])
        for item in ({"n":1,"why":"Убыток 100"},{"n":True,"why":"Расходы высоки"},{"n":1,"why":"漢字"}):
            with self.subTest(item=item),patch.object(a,"ask_model",return_value=({"items":[item]},"")):
                self.assertEqual(a.why_from_model(facts,"model")[0],{})

    def test_malformed_model_response_falls_back(self):
        facts=a.build_facts([task("negative_margin",100)])
        with patch.object(a,"ask_model",return_value=([1,2],"bad")):
            self.assertEqual(a.why_from_model(facts,"model")[0],{})
            self.assertEqual(a.mentor_from_model(facts,"model")[0],"")

    def test_local_no_ai_neither_calls_model_nor_writes(self):
        config=types.ModuleType("unitka.config");config.AI_MODEL="test"
        with patch.object(unitka,"config",config,create=True),patch.dict(sys.modules,{"unitka.config":config}), \
             patch.object(sys,"argv",["ai_advisor","--local","--no-ai"]), \
             patch.object(a,"tasks_from_db",return_value=[task("negative_margin",100)]), \
             patch.object(a,"ask_model") as model,patch.object(a,"write_summary") as write, \
             contextlib.redirect_stdout(io.StringIO()):
            a.main()
        model.assert_not_called();write.assert_not_called()


if __name__ == "__main__":
    unittest.main()
