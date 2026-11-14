"""Atomic price snapshot tests. HTTP and credentials are fake; no live API calls."""
import contextlib
import importlib.util
import io
import sqlite3
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

spec=importlib.util.spec_from_file_location("price_loader_tests_target",Path(__file__).resolve().parents[1]/"app"/"fetch_current_prices.py")
l=importlib.util.module_from_spec(spec);spec.loader.exec_module(l)


def item(offer="A",price=100,product_id=None):
    return dict(offer_id=offer,product_id=product_id or sum(map(ord,offer)),
        price=dict(price=price,old_price=0,min_price=0,marketing_seller_price=price,net_price=0,currency_code="RUB"),
        commissions=dict(sales_percent_fbo=0,sales_percent_fbs=52),acquiring=0,volume_weight=1)


def page(items,cursor="",**extra):
    return dict(items=items,cursor=cursor,**extra)


class PriceSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:");self.addCleanup(self.db.close)
        self.db.execute(l.CREATE_SQL)
        self.db.execute("INSERT INTO current_prices (offer_id,sku,price,fetched_at) VALUES('OLD',99,123,'2026-01-01 00:00:00')")
        self.db.commit()
        self.before=l._signature(self.db)

    def unchanged(self):self.assertEqual(l._signature(self.db),self.before)
    def rejected(self,fetcher,**kwargs):
        with self.assertRaises((l.PriceLoadError,sqlite3.Error)):
            l.refresh_prices(self.db,fetcher,**kwargs)
        self.unchanged()

    def test_complete_two_pages_replaces_snapshot(self):
        f=Mock(side_effect=[page([item("A")],"next",total=2),page([item("B")],"",total=2)])
        result=l.refresh_prices(self.db,f)
        self.assertEqual(result["rows"],2)
        self.assertEqual([x[0] for x in self.db.execute("SELECT offer_id FROM current_prices ORDER BY offer_id")],["A","B"])
        self.assertEqual([x.args[0] for x in f.call_args_list],["","next"])

    def test_total_items_supported_and_preferred(self):
        result=l.refresh_prices(self.db,lambda _:page([item()],total_items=1,total=999))
        self.assertEqual(result["declared_total"],1)

    def test_zero_numbers_preserved(self):
        row=l.parse_item(item(),"stamp")
        self.assertEqual(row[3],0);self.assertEqual(row[8],0);self.assertEqual(row[9],0)

    def test_first_page_failure_preserves_old(self):
        self.rejected(Mock(side_effect=l.PriceLoadError("HTTP 500")))

    def test_later_page_failure_preserves_old(self):
        self.rejected(Mock(side_effect=[page([item()],"next",total=2),l.PriceLoadError("timeout")]))

    def test_empty_snapshot_preserves_old(self):self.rejected(lambda _:page([],total=0))
    def test_incomplete_count_preserves_old(self):self.rejected(lambda _:page([item()],total=2))

    def test_changed_total_preserves_old(self):
        self.rejected(Mock(side_effect=[page([item()],"next",total=3),page([item("B")],total=2)]))

    def test_repeated_cursor_preserves_old(self):
        self.rejected(Mock(side_effect=[page([item()],"next"),page([item("B")],"next")]))

    def test_repeated_cursor_even_if_count_matches(self):
        self.rejected(Mock(side_effect=[page([item()],"next",total=2),page([item("B")],"next",total=2)]))

    def test_page_limit_preserves_old(self):self.rejected(lambda _:page([item()],"next"),max_pages=1)
    def test_duplicate_offer_preserves_old(self):self.rejected(lambda _:page([item(),item()]))
    def test_conflicting_offer_preserves_old(self):self.rejected(lambda _:page([item(),item(price=999)]))
    def test_conflicting_product_id_preserves_old(self):self.rejected(lambda _:page([item("A",product_id=1),item("B",product_id=1)]))

    def test_invalid_numbers_preserve_old(self):
        for number in ("bad",float("nan"),float("inf"),-1,True):
            with self.subTest(number=number):self.rejected(lambda _:page([item(price=number)]))

    def test_invalid_structure_preserves_old(self):
        for response in ({}, {"items":None},page([{}]),page([item()],cursor=123),page([item()],total=True)):
            with self.subTest(response=response):self.rejected(lambda _:response)

    def test_missing_currency_preserves_old(self):
        record=item();record["price"].pop("currency_code")
        self.rejected(lambda _:page([record]))

    def test_unpriced_snapshot_preserves_old(self):self.rejected(lambda _:page([item(price=0)]))

    def test_insert_failure_rolls_back_delete(self):
        self.db.execute("CREATE TRIGGER reject_price BEFORE INSERT ON current_prices BEGIN SELECT RAISE(ABORT,'test'); END")
        self.db.commit();self.rejected(lambda _:page([item()]))

    def test_schema_mismatch_rolls_back(self):
        self.db.execute("ALTER TABLE current_prices ADD COLUMN custom_note TEXT")
        self.db.commit();self.before=l._signature(self.db)
        self.rejected(lambda _:page([item()]))

    def test_caller_transaction_not_committed_or_rolled_back(self):
        self.db.execute("UPDATE current_prices SET price=456")
        fetcher=Mock()
        with self.assertRaises(l.PriceLoadError):l.refresh_prices(self.db,fetcher)
        self.assertTrue(self.db.in_transaction);fetcher.assert_not_called()
        self.db.rollback();self.unchanged()

    def test_large_drop_needs_explicit_override(self):
        self.db.execute("INSERT INTO current_prices (offer_id,sku,price) VALUES('OLD2',98,200)")
        self.db.commit();self.before=l._signature(self.db)
        self.rejected(lambda _:page([item()],total=1))
        l.refresh_prices(self.db,lambda _:page([item()],total=1),allow_large_drop=True)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM current_prices").fetchone()[0],1)

    def test_newer_snapshot_during_fetch_is_not_overwritten(self):
        def fetch(_):
            self.db.execute("UPDATE current_prices SET price=999");self.db.commit()
            return page([item()],total=1)
        with self.assertRaisesRegex(l.PriceLoadError,"changed during fetch"):
            l.refresh_prices(self.db,fetch)
        self.assertEqual(self.db.execute("SELECT price FROM current_prices").fetchone()[0],999)

    def test_http_error_not_converted_to_empty_success(self):
        post=Mock(return_value=types.SimpleNamespace(status_code=500))
        with self.assertRaises(l.PriceLoadError):l.fetch_page(post=post,headers={"test":"test"})

    def test_bad_json_not_converted_to_empty_success(self):
        response=types.SimpleNamespace(status_code=200,json=Mock(side_effect=ValueError("bad")))
        with self.assertRaises(l.PriceLoadError):l.fetch_page(post=Mock(return_value=response),headers={})

    def test_dry_run_does_not_modify_database_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"prices.db"
            disk=sqlite3.connect(path);self.db.backup(disk);disk.close();before=path.read_bytes()
            config=types.SimpleNamespace(DB_PATH=path,check_credentials=lambda:None,
                OZON_CLIENT_ID="test",OZON_API_KEY="test",OZON_BASE_URL="https://example.invalid")
            with patch.object(l,"_config",return_value=config),patch.object(l,"fetch_page",return_value=page([item()],total=1)),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(l.main(["--dry-run"]),0)
            self.assertEqual(path.read_bytes(),before)

    def test_first_snapshot_can_create_table_atomically(self):
        fresh=sqlite3.connect(":memory:");self.addCleanup(fresh.close)
        self.assertEqual(l.refresh_prices(fresh,lambda _:page([item()],total_items=1))["rows"],1)


if __name__ == "__main__":
    unittest.main()
