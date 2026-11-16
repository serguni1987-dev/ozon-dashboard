import unittest
from unittest.mock import Mock
from unitka import calc_unit_summary as summary


class SummaryPresentationTests(unittest.TestCase):
    def block(self, estimated=True):
        return {"title": "TEST", "from": "2026-11-01", "to": "2026-11-14",
                "cogs_estimated": estimated, "items": [],
                "totals": {"revenue": 0, "cogs": 0, "exp": 0, "profit": 0}}

    def test_estimated_note(self):
        self.assertIn("включает оценку", summary._quality_note(self.block()))

    def test_not_estimated_is_not_completeness(self):
        note = summary._quality_note(self.block(False))
        self.assertIn("не подтверждает полноту", note)

    def test_unknown_flag(self):
        self.assertIn("недоступен", summary._quality_note({}))

    def test_render_without_database_or_sheets(self):
        rows, marks = summary.render_rows([self.block()], "TEST-TIME", {"accruals": "2026-11-13"})
        text = "\n".join(str(cell) for row in rows for cell in row)
        self.assertIn("2026-11-13", text)
        self.assertIn("2026-11-01", text)
        self.assertIn("включает оценку", text)
        self.assertIn("Мин. цена (не рассчитана)", text)
        self.assertTrue(all(0 <= index < len(rows) for index, _ in marks))

    def test_source_dates_queries(self):
        cur = Mock()
        cur.fetchone.side_effect = [("2026-11-13",), (None,), ("2026-11-12",)]
        result = summary._source_dates(cur)
        self.assertEqual(result["accruals"], "2026-11-13")
        self.assertIsNone(result["finance_transactions"])
        self.assertEqual(cur.execute.call_count, 3)
