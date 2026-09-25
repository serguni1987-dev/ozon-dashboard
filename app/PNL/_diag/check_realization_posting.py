"""
check_realization_posting.py — сравнение /v1/finance/realization/posting
"""
import os
import json
import requests
import sqlite3
from datetime import datetime
from dotenv import load_dotenv

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(APP_DIR, "ozon.db")
load_dotenv(os.path.join(APP_DIR, ".env"))

H = {
    "Client-Id": os.getenv("OZON_CLIENT_ID"),
    "Api-Key": os.getenv("OZON_API_KEY"),
    "Content-Type": "application/json",
}
URL = "https://api-seller.ozon.ru/v1/finance/realization/posting"

print("=" * 80)
print("ПРОВЕРКА /v1/finance/realization/posting ЗА АВГУСТ")
print("=" * 80)

body = {"month": 8, "year": 2026}
r = requests.post(URL, headers=H, json=body, timeout=120)
print(f"\nHTTP: {r.status_code}")
if r.status_code != 200:
    print(f"Ошибка: {r.text[:500]}")
    raise SystemExit

data = r.json()
result = data.get("result") or {}
header = result.get("header") or {}
rows = result.get("rows") or []

print(f"Строк: {len(rows)}")
print(f"Номер отчёта: {header.get('number', '?')}")
print(f"Период: {header.get('start_date', '?')} - {header.get('stop_date', '?')}")

# Считаем итоги
total_seller_price = 0
total_sale_price = 0
total_commission = 0
total_bonus = 0
total_coinv = 0
n_posting = 0

for row in rows:
    item = row.get("item") or {}
    dc = row.get("delivery_commission") or {}
    rc = row.get("return_commission") or {}

    qty_dc = int(dc.get("quantity") or 0)
    qty_rc = int(rc.get("quantity") or 0)

    sp = float(row.get("seller_price_per_instance") or 0)

    if dc:
        total_seller_price += sp * qty_dc
        total_sale_price += float(dc.get("amount") or 0)
        total_commission += float(dc.get("commission") or 0)
        total_bonus += float(dc.get("bonus") or 0)
        total_coinv += float(dc.get("bank_coinvestment") or 0)
        total_coinv += float(dc.get("pick_up_point_coinvestment") or 0)
        n_posting += 1
    if rc:
        total_seller_price -= sp * qty_rc
        total_sale_price -= float(rc.get("amount") or 0)
        total_commission -= float(rc.get("commission") or 0)
        total_bonus -= float(rc.get("bonus") or 0)
        total_coinv -= float(rc.get("bank_coinvestment") or 0)
        total_coinv -= float(rc.get("pick_up_point_coinvestment") or 0)

print(f"\n[СУММЫ ИЗ /v1/finance/realization/posting]")
print(f"  seller_price:   {total_seller_price:>14,.2f}")
print(f"  sale_price:     {total_sale_price:>14,.2f}")
print(f"  commission:     {total_commission:>14,.2f}")
print(f"  bonus:          {total_bonus:>14,.2f}")
print(f"  coinvestment:   {total_coinv:>14,.2f}")

print(f"\n[СРАВНЕНИЕ С ПРИЛОЖЕНИЕМ]")
print(f"  {'Метрика':<20} {'posting':>15} {'Приложение':>15}")
print("  " + "-" * 52)
print(f"  {'sale_price':<20} {total_sale_price:>15,.2f} {161382.96:>15,.2f}")
print(f"  {'commission':<20} {total_commission:>15,.2f} {-151050.09:>15,.2f}")
print(f"  {'bonus':<20} {total_bonus:>15,.2f} {139902.77:>15,.2f}")
print(f"  {'coinvestment':<20} {total_coinv:>15,.2f} {1681.27:>15,.2f}")
