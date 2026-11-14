"""Calendar-window and action-passport regression tests; no external services."""
import sqlite3
import unittest
from datetime import date, timedelta
from unittest.mock import patch
from unitka import calc_action_plan as a


class ActionWindowTests(unittest.TestCase):
    def test_14_dates_including_today(self):
        self.assertEqual(a._calendar_window(date(2026,11,14),14),("2026-11-01","2026-11-15"))

    def test_30_dates_including_today(self):
        self.assertEqual(a._calendar_window(date(2026,11,14),30),("2026-10-16","2026-11-15"))

    def test_one_day(self):
        self.assertEqual(a._calendar_window(date(2026,11,14),1),("2026-11-14","2026-11-15"))

    def test_year_transition(self):
        self.assertEqual(a._calendar_window(date(2027,1,1),14),("2026-12-19","2027-01-02"))

    def test_leap_day(self):
        self.assertEqual(a._calendar_window(date(2024,3,1),2),("2024-02-29","2024-03-02"))

    def test_lengths_across_months(self):
        for today in (date(2026,1,1),date(2026,3,1),date(2024,3,1),date(2026,12,31)):
            for n in (1,14,30):
                start,stop=a._calendar_window(today,n)
                with self.subTest(today=today,n=n):
                    self.assertEqual((date.fromisoformat(stop)-date.fromisoformat(start)).days,n)
                    self.assertEqual(date.fromisoformat(stop)-timedelta(days=1),today)

    def test_invalid_window_rejected(self):
        for days in (0,-1,True,1.5,"14",None):
            with self.subTest(days=days),self.assertRaises(ValueError):
                a._calendar_window(date(2026,11,14),days)

    def fixture(self):
        conn=sqlite3.connect(":memory:");self.addCleanup(conn.close)
        conn.execute("CREATE TABLE events(day TEXT)")
        conn.executemany("INSERT INTO events VALUES(?)",[(d,) for d in (
            "2026-10-15","2026-10-16","2026-10-31","2026-11-01","2026-11-14","2026-11-15")])
        conn.commit();conn.execute("PRAGMA query_only=ON")
        calls=[]
        def economy(cur,start,stop):
            n=cur.execute("SELECT COUNT(*) FROM events WHERE day>=? AND day<?",(start,stop)).fetchone()[0]
            calls.append((start,stop,n))
            return {"skus":{1:{"stock":1,"cost_unit":400,"offer_id":"A",
                "delivered":n,"income":n*1000,"direct_profit":n*100}}}
        return conn,calls,economy

    def collect(self,tax=None,unit=None):
        conn,calls,economy=self.fixture()
        with patch.object(a.unit_core,"sku_economics",side_effect=economy), \
             patch.object(a.unit_core,"min_prices",return_value={1:{"price":1000,"min_direct":800}}) as floors:
            result=a.collect_sku_data(conn.cursor(),tax,unit,today=date(2026,11,14))
        return conn,calls,result,floors

    def test_collect_uses_correct_windows_and_excludes_future_year_rows(self):
        _,calls,_,_=self.collect()
        self.assertEqual(calls,[("2026-01-01","2026-11-15",5),
                                ("2026-10-16","2026-11-15",4),
                                ("2026-11-01","2026-11-15",2)])

    def test_30_day_income_does_not_include_31st_date(self):
        _,_,rows,_=self.collect()
        self.assertEqual(rows[0]["revenue_30d"],4000)

    def test_14_day_deliveries_do_not_include_15th_date(self):
        _,_,rows,_=self.collect()
        self.assertEqual(rows[0]["sold_14d"],2)

    def test_margin_formula_and_passport_fields_preserved(self):
        _,_,rows,_=self.collect()
        self.assertEqual(rows[0]["margin_pct"],10)
        self.assertEqual(rows[0]["cost"],400)
        self.assertEqual(rows[0]["min_price"],800)
        self.assertEqual(rows[0]["avg_price"],1000)
        self.assertEqual(rows[0]["sku"],"1")

    def test_settings_forwarded_without_replacement(self):
        tax={"rate_pct":5};unit={"target_margin_pct":20}
        _,_,_,floors=self.collect(tax,unit)
        self.assertIs(floors.call_args.args[2],tax)
        self.assertIs(floors.call_args.args[3],unit)

    def test_readonly_fixture_is_not_modified(self):
        conn,_,_,_=self.collect()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM events").fetchone()[0],6)
        with self.assertRaises(sqlite3.OperationalError):conn.execute("DELETE FROM events")

    def test_status_rule_mapping_unchanged(self):
        self.assertEqual(a._legacy_rule("Нет в наличии, но было 2 продаж"),"out_of_stock")
        self.assertEqual(a._legacy_rule("Маржинальность -10%"),"negative_margin")


if __name__ == "__main__":
    unittest.main()
