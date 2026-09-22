#!/usr/bin/env python3
"""
Ozon API Export Script – полный набор методов для работы с Ozon Seller API.
Версия: 2.1 (исправлен финансовый метод)
"""

import requests
import pandas as pd
import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# ----------------------------------------------------------------------
#  КЛАСС OzonAPIExporter
# ----------------------------------------------------------------------

class OzonAPIExporter:
    """Класс для выгрузки всех данных из Ozon Seller API."""

    def __init__(self, client_id: str, api_key: str, base_url: str = 'https://api-seller.ozon.ru'):
        self.client_id = client_id
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            'Client-Id': client_id,
            'Api-Key': api_key,
            'Content-Type': 'application/json'
        }

    # ------------------------------------------------------------------
    # 1. ТОВАРЫ
    # ------------------------------------------------------------------

    def get_products(self, limit: int = 1000) -> pd.DataFrame:
        """Список всех товаров (v3/product/list)"""
        try:
            products = []
            last_id = ''
            while True:
                response = requests.post(
                    f'{self.base_url}/v3/product/list',
                    headers=self.headers,
                    json={'filter': {'offer_id': []}, 'last_id': last_id, 'limit': limit}
                )
                if response.status_code != 200:
                    print(f'[WARN] get_products статус {response.status_code}')
                    break
                data = response.json()
                items = data.get('result', {}).get('items', [])
                products.extend(items)
                last_id = data.get('result', {}).get('last_id', '')
                if not data.get('result', {}).get('has_next', False):
                    break
                time.sleep(0.5)
            return pd.DataFrame(products)
        except Exception as e:
            print(f'[ERROR] get_products: {e}')
            return pd.DataFrame()

    def get_product_details(self, offer_ids: List[str]) -> pd.DataFrame:
        """Детальная информация по товарам (v3/product/info/list)"""
        try:
            details = []
            for offer_id in offer_ids:
                response = requests.post(
                    f'{self.base_url}/v3/product/info/list',
                    headers=self.headers,
                    json={'offer_id': [offer_id]}
                )
                if response.status_code != 200:
                    print(f'[WARN] get_product_details статус {response.status_code} для {offer_id}')
                    continue
                data = response.json()
                if data.get('items'):
                    details.extend(data['items'])
                time.sleep(0.3)
            return pd.DataFrame(details)
        except Exception as e:
            print(f'[ERROR] get_product_details: {e}')
            return pd.DataFrame()

    def get_pricing(self, product_ids: List[int]) -> pd.DataFrame:
        """Цены товаров (v5/product/info/prices) – опционально"""
        try:
            if not product_ids:
                return pd.DataFrame()
            response = requests.post(
                f'{self.base_url}/v5/product/info/prices',
                headers=self.headers,
                json={'filter': {'product_id': product_ids}, 'limit': 1000}
            )
            if response.status_code != 200:
                print(f'[WARN] get_pricing статус {response.status_code}')
                return pd.DataFrame()
            return pd.DataFrame(response.json().get('items', []))
        except Exception as e:
            print(f'[ERROR] get_pricing: {e}')
            return pd.DataFrame()

    def get_product_visibility(self, skus: List[int]) -> pd.DataFrame:
        """Видимость товара на витринах (v1/product/visibility/info) – бета"""
        try:
            if not skus:
                return pd.DataFrame()
            chunks = [skus[i:i+350] for i in range(0, len(skus), 350)]
            all_items = []
            for chunk in chunks:
                resp = requests.post(
                    f'{self.base_url}/v1/product/visibility/info',
                    headers=self.headers,
                    json={'skus': chunk}
                )
                if resp.status_code == 200:
                    all_items.extend(resp.json().get('items', []))
                time.sleep(0.3)
            return pd.DataFrame(all_items)
        except Exception as e:
            print(f'[ERROR] get_product_visibility: {e}')
            return pd.DataFrame()

    def set_product_visibility(self, sku: int, placement: str) -> bool:
        """Установить видимость товара (v1/product/visibility/set) – бета"""
        try:
            payload = {'item_placement': [{'sku': sku, 'placement': placement}]}
            resp = requests.post(
                f'{self.base_url}/v1/product/visibility/set',
                headers=self.headers,
                json=payload
            )
            return resp.status_code == 200
        except Exception:
            return False

    # ------------------------------------------------------------------
    # 2. АНАЛИТИКА (базовая)
    # ------------------------------------------------------------------

    def get_analytics(self, product_ids: List[int], date_from: str, date_to: str,
                      metric_type: str = 'hits') -> pd.DataFrame:
        """Аналитика показов/хитов (v1/analytics/data)"""
        try:
            if 'T' not in date_from:
                date_from = f"{date_from}T00:00:00Z"
            if 'T' not in date_to:
                date_to = f"{date_to}T23:59:59Z"

            payload = {
                'date_from': date_from,
                'date_to': date_to,
                'metric_type': metric_type,
                'product_ids': product_ids
            }
            response = requests.post(
                f'{self.base_url}/v1/analytics/data',
                headers=self.headers,
                json=payload
            )
            if response.status_code != 200:
                print(f'[WARN] get_analytics статус {response.status_code}')
                return pd.DataFrame()
            return pd.DataFrame(response.json().get('result', {}).get('data', []))
        except Exception as e:
            print(f'[ERROR] get_analytics: {e}')
            return pd.DataFrame()

    # ------------------------------------------------------------------
    # 3. ПРОДАЖИ / ЗАКАЗЫ (FBO и FBS)
    # ------------------------------------------------------------------

    def get_postings_fbo(self, date_from: str, date_to: str, limit: int = 100) -> pd.DataFrame:
        """Заказы FBO (v3/posting/fbo/list) с правильным форматом дат"""
        try:
            if 'T' not in date_from:
                date_from = f"{date_from}T00:00:00Z"
            if 'T' not in date_to:
                date_to = f"{date_to}T23:59:59Z"

            all_postings = []
            cursor = ''
            payload = {
                'filter': {
                    'since': date_from,
                    'to': date_to,
                    'statuses': ['awaiting_packaging', 'awaiting_deliver', 'delivering', 'delivered', 'cancelled']
                },
                'limit': limit,
                'sort_dir': 'ASC',
                'cursor': cursor
            }
            while True:
                resp = requests.post(
                    f'{self.base_url}/v3/posting/fbo/list',
                    headers=self.headers,
                    json=payload
                )
                if resp.status_code != 200:
                    print(f'[WARN] get_postings_fbo статус {resp.status_code}')
                    break
                data = resp.json()
                postings = data.get('postings', [])
                all_postings.extend(postings)
                if not data.get('has_next') or not data.get('cursor'):
                    break
                payload['cursor'] = data['cursor']
                time.sleep(0.3)
            return pd.DataFrame(all_postings)
        except Exception as e:
            print(f'[ERROR] get_postings_fbo: {e}')
            return pd.DataFrame()

    def get_postings_fbs(self, date_from: str, date_to: str, limit: int = 100) -> pd.DataFrame:
        """Заказы FBS (v4/posting/fbs/list)"""
        try:
            if 'T' not in date_from:
                date_from = f"{date_from}T00:00:00Z"
            if 'T' not in date_to:
                date_to = f"{date_to}T23:59:59Z"

            all_postings = []
            cursor = ''
            payload = {
                'filter': {'since': date_from, 'to': date_to},
                'limit': limit,
                'sort_dir': 'ASC',
                'cursor': cursor
            }
            while True:
                resp = requests.post(
                    f'{self.base_url}/v4/posting/fbs/list',
                    headers=self.headers,
                    json=payload
                )
                if resp.status_code != 200:
                    print(f'[WARN] get_postings_fbs статус {resp.status_code}')
                    break
                data = resp.json()
                postings = data.get('postings', [])
                all_postings.extend(postings)
                if not data.get('has_next') or not data.get('cursor'):
                    break
                payload['cursor'] = data['cursor']
                time.sleep(0.3)
            return pd.DataFrame(all_postings)
        except Exception as e:
            print(f'[ERROR] get_postings_fbs: {e}')
            return pd.DataFrame()

    def get_posting_info(self, posting_number: str) -> dict:
        """Информация об отправлении (v3/posting/fbs/get)"""
        try:
            resp = requests.post(
                f'{self.base_url}/v3/posting/fbs/get',
                headers=self.headers,
                json={'posting_number': posting_number}
            )
            if resp.status_code != 200:
                print(f'[WARN] get_posting_info статус {resp.status_code}')
                return {}
            return resp.json().get('result', {})
        except Exception as e:
            print(f'[ERROR] get_posting_info: {e}')
            return {}

    def get_posting_accruals(self, posting_numbers: List[str]) -> pd.DataFrame:
        """Начисления по отправлениям (v1/finance/accrual/postings) – бета"""
        try:
            if not posting_numbers:
                return pd.DataFrame()
            resp = requests.post(
                f'{self.base_url}/v1/finance/accrual/postings',
                headers=self.headers,
                json={'posting_numbers': posting_numbers[:200]}
            )
            if resp.status_code != 200:
                print(f'[WARN] get_posting_accruals статус {resp.status_code}')
                return pd.DataFrame()
            rows = []
            for pa in resp.json().get('posting_accruals', []):
                posting = pa['posting_number']
                for acc in pa.get('accruals', []):
                    rows.append({
                        'posting_number': posting,
                        'sku': acc.get('sku'),
                        'quantity': acc.get('quantity'),
                        'accrual_date': acc.get('accrual_date'),
                        'type_id': acc.get('type_id'),
                        'accrued_amount': acc.get('accrued', {}).get('amount'),
                        'accrued_currency': acc.get('accrued', {}).get('currency'),
                        'seller_price_amount': acc.get('seller_price', {}).get('amount'),
                        'seller_price_currency': acc.get('seller_price', {}).get('currency'),
                    })
            return pd.DataFrame(rows)
        except Exception as e:
            print(f'[ERROR] get_posting_accruals: {e}')
            return pd.DataFrame()

    # ------------------------------------------------------------------
    # 4. ВОЗВРАТЫ И ОТМЕНЫ
    # ------------------------------------------------------------------

    def get_returns(self, date_from: str, date_to: str, limit: int = 500) -> pd.DataFrame:
        """Возвраты (v1/returns/list)"""
        try:
            if 'T' not in date_from:
                date_from = f"{date_from}T00:00:00Z"
            if 'T' not in date_to:
                date_to = f"{date_to}T23:59:59Z"

            all_returns = []
            last_id = 0
            payload = {
                'filter': {'logistic_return_date': {'time_from': date_from, 'time_to': date_to}},
                'limit': limit,
                'last_id': last_id
            }
            while True:
                resp = requests.post(
                    f'{self.base_url}/v1/returns/list',
                    headers=self.headers,
                    json=payload
                )
                if resp.status_code != 200:
                    print(f'[WARN] get_returns статус {resp.status_code}')
                    break
                data = resp.json()
                items = data.get('returns', [])
                all_returns.extend(items)
                if not data.get('has_next') or not items:
                    break
                last_id = items[-1]['id']
                payload['last_id'] = last_id
                time.sleep(0.3)
            return pd.DataFrame(all_returns)
        except Exception as e:
            print(f'[ERROR] get_returns: {e}')
            return pd.DataFrame()

    def get_return_giveouts(self, limit: int = 500) -> pd.DataFrame:
        """Активные возвратные отгрузки (v1/return/giveout/list)"""
        try:
            all_giveouts = []
            last_id = 0
            payload = {'limit': limit, 'last_id': last_id}
            while True:
                resp = requests.post(
                    f'{self.base_url}/v1/return/giveout/list',
                    headers=self.headers,
                    json=payload
                )
                if resp.status_code != 200:
                    print(f'[WARN] get_return_giveouts статус {resp.status_code}')
                    break
                data = resp.json()
                items = data.get('giveouts', [])
                all_giveouts.extend(items)
                if len(items) < limit:
                    break
                last_id = items[-1]['giveout_id']
                payload['last_id'] = last_id
                time.sleep(0.3)
            return pd.DataFrame(all_giveouts)
        except Exception as e:
            print(f'[ERROR] get_return_giveouts: {e}')
            return pd.DataFrame()

    def get_return_giveout_info(self, giveout_id: int) -> dict:
        """Детали возвратной отгрузки (v1/return/giveout/info)"""
        try:
            resp = requests.post(
                f'{self.base_url}/v1/return/giveout/info',
                headers=self.headers,
                json={'giveout_id': giveout_id}
            )
            if resp.status_code != 200:
                print(f'[WARN] get_return_giveout_info статус {resp.status_code}')
                return {}
            return resp.json()
        except Exception as e:
            print(f'[ERROR] get_return_giveout_info: {e}')
            return {}

    def get_cancellations(self, state: str = 'ALL', limit: int = 500) -> pd.DataFrame:
        """Заявки на отмену rFBS (v2/conditional-cancellation/list)"""
        try:
            all_canc = []
            last_id = 0
            payload = {'filters': {'state': state}, 'limit': limit, 'last_id': last_id}
            while True:
                resp = requests.post(
                    f'{self.base_url}/v2/conditional-cancellation/list',
                    headers=self.headers,
                    json=payload
                )
                if resp.status_code != 200:
                    print(f'[WARN] get_cancellations статус {resp.status_code}')
                    break
                data = resp.json()
                items = data.get('result', [])
                all_canc.extend(items)
                if len(items) < limit or not data.get('last_id'):
                    break
                last_id = data['last_id']
                payload['last_id'] = last_id
                time.sleep(0.3)
            return pd.DataFrame(all_canc)
        except Exception as e:
            print(f'[ERROR] get_cancellations: {e}')
            return pd.DataFrame()

    def approve_cancellation(self, cancellation_id: int, comment: str = '') -> bool:
        """Подтвердить отмену (v2/conditional-cancellation/approve)"""
        try:
            resp = requests.post(
                f'{self.base_url}/v2/conditional-cancellation/approve',
                headers=self.headers,
                json={'cancellation_id': cancellation_id, 'comment': comment}
            )
            return resp.status_code == 200
        except Exception:
            return False

    def reject_cancellation(self, cancellation_id: int, comment: str = '') -> bool:
        """Отклонить отмену (v2/conditional-cancellation/reject)"""
        try:
            resp = requests.post(
                f'{self.base_url}/v2/conditional-cancellation/reject',
                headers=self.headers,
                json={'cancellation_id': cancellation_id, 'comment': comment}
            )
            return resp.status_code == 200
        except Exception:
            return False

    def get_removal_from_supply(self, date_from: str, date_to: str, limit: int = 500) -> pd.DataFrame:
        """Вывоз/утилизация с поставки FBO (v1/removal/from-supply/list) – бета"""
        try:
            all_rows = []
            last_id = ''
            payload = {'date_from': date_from, 'date_to': date_to, 'limit': limit, 'last_id': last_id}
            while True:
                resp = requests.post(
                    f'{self.base_url}/v1/removal/from-supply/list',
                    headers=self.headers,
                    json=payload
                )
                if resp.status_code != 200:
                    print(f'[WARN] get_removal_from_supply статус {resp.status_code}')
                    break
                data = resp.json()
                rows = data.get('returns_summary_report_rows', [])
                all_rows.extend(rows)
                if not data.get('last_id') or len(rows) < limit:
                    break
                last_id = data['last_id']
                payload['last_id'] = last_id
                time.sleep(0.3)
            return pd.DataFrame(all_rows)
        except Exception as e:
            print(f'[ERROR] get_removal_from_supply: {e}')
            return pd.DataFrame()

    def get_removal_from_stock(self, date_from: str, date_to: str, limit: int = 500) -> pd.DataFrame:
        """Вывоз/утилизация со стока FBO (v1/removal/from-stock/list) – бета"""
        try:
            all_rows = []
            last_id = ''
            payload = {'date_from': date_from, 'date_to': date_to, 'limit': limit, 'last_id': last_id}
            while True:
                resp = requests.post(
                    f'{self.base_url}/v1/removal/from-stock/list',
                    headers=self.headers,
                    json=payload
                )
                if resp.status_code != 200:
                    print(f'[WARN] get_removal_from_stock статус {resp.status_code}')
                    break
                data = resp.json()
                rows = data.get('returns_summary_report_rows', [])
                all_rows.extend(rows)
                if not data.get('last_id') or len(rows) < limit:
                    break
                last_id = data['last_id']
                payload['last_id'] = last_id
                time.sleep(0.3)
            return pd.DataFrame(all_rows)
        except Exception as e:
            print(f'[ERROR] get_removal_from_stock: {e}')
            return pd.DataFrame()

    # ------------------------------------------------------------------
    # 5. ФИНАНСЫ
    # ------------------------------------------------------------------

    def get_cash_flow_statement(self, date_from: str, date_to: str) -> pd.DataFrame:
        """Отчёт о движении денежных средств (v1/finance/cash-flow-statement) – может быть устаревшим"""
        try:
            if 'T' not in date_from:
                date_from = f"{date_from}T00:00:00Z"
            if 'T' not in date_to:
                date_to = f"{date_to}T23:59:59Z"
            resp = requests.post(
                f'{self.base_url}/v1/finance/cash-flow-statement',
                headers=self.headers,
                json={'date_from': date_from, 'date_to': date_to}
            )
            if resp.status_code != 200:
                print(f'[WARN] get_cash_flow_statement статус {resp.status_code}')
                return pd.DataFrame()
            return pd.DataFrame(resp.json().get('result', {}).get('data', []))
        except Exception as e:
            print(f'[ERROR] get_cash_flow_statement: {e}')
            return pd.DataFrame()

    def get_finance_balance(self, date_from: str, date_to: str) -> dict:
        """Баланс (v1/finance/balance) – бета"""
        try:
            resp = requests.post(
                f'{self.base_url}/v1/finance/balance',
                headers=self.headers,
                json={'date_from': date_from, 'date_to': date_to}
            )
            if resp.status_code != 200:
                print(f'[WARN] get_finance_balance статус {resp.status_code}')
                return {}
            return resp.json()
        except Exception as e:
            print(f'[ERROR] get_finance_balance: {e}')
            return {}

    def get_finance_realization(self, year: int, month: int) -> pd.DataFrame:
        """Отчёт о реализации (v2/finance/realization) – может быть недоступен"""
        try:
            resp = requests.post(
                f'{self.base_url}/v2/finance/realization',
                headers=self.headers,
                json={'year': year, 'month': month}
            )
            if resp.status_code != 200:
                print(f'[WARN] get_finance_realization статус {resp.status_code}')
                return pd.DataFrame()
            return pd.DataFrame(resp.json().get('result', {}).get('rows', []))
        except Exception as e:
            print(f'[ERROR] get_finance_realization: {e}')
            return pd.DataFrame()

    def get_finance_realization_by_posting(self, year: int, month: int) -> pd.DataFrame:
        """Позаказный отчёт о реализации (v1/finance/realization/posting) – рабочий метод"""
        try:
            resp = requests.post(
                f'{self.base_url}/v1/finance/realization/posting',
                headers=self.headers,
                json={'year': year, 'month': month}
            )
            if resp.status_code != 200:
                print(f'[WARN] get_finance_realization_by_posting статус {resp.status_code}')
                return pd.DataFrame()
            return pd.DataFrame(resp.json().get('rows', []))
        except Exception as e:
            print(f'[ERROR] get_finance_realization_by_posting: {e}')
            return pd.DataFrame()

    def get_transactions(self, date_from: str, date_to: str, page: int = 1, page_size: int = 1000) -> pd.DataFrame:
        """Список транзакций (v3/finance/transaction/list) – устаревает, но работает"""
        try:
            if 'T' not in date_from:
                date_from = f"{date_from}T00:00:00Z"
            if 'T' not in date_to:
                date_to = f"{date_to}T23:59:59Z"
            resp = requests.post(
                f'{self.base_url}/v3/finance/transaction/list',
                headers=self.headers,
                json={
                    'filter': {'date': {'from': date_from, 'to': date_to}},
                    'page': page,
                    'page_size': page_size
                }
            )
            if resp.status_code != 200:
                print(f'[WARN] get_transactions статус {resp.status_code}')
                return pd.DataFrame()
            return pd.DataFrame(resp.json().get('result', {}).get('operations', []))
        except Exception as e:
            print(f'[ERROR] get_transactions: {e}')
            return pd.DataFrame()

    def get_accrual_types(self) -> pd.DataFrame:
        """Справочник начислений (v1/finance/accrual/types) – бета"""
        try:
            resp = requests.post(
                f'{self.base_url}/v1/finance/accrual/types',
                headers=self.headers,
                json={}
            )
            if resp.status_code != 200:
                print(f'[WARN] get_accrual_types статус {resp.status_code}')
                return pd.DataFrame()
            return pd.DataFrame(resp.json().get('accrual_types', []))
        except Exception as e:
            print(f'[ERROR] get_accrual_types: {e}')
            return pd.DataFrame()

    def get_accrual_by_day(self, date: str, last_id: str = '') -> pd.DataFrame:
        """Начисления за день (v1/finance/accrual/by-day) – бета"""
        try:
            payload = {'date': date, 'last_id': last_id}
            resp = requests.post(
                f'{self.base_url}/v1/finance/accrual/by-day',
                headers=self.headers,
                json=payload
            )
            if resp.status_code != 200:
                print(f'[WARN] get_accrual_by_day статус {resp.status_code}')
                return pd.DataFrame()
            return pd.DataFrame(resp.json().get('accruals', []))
        except Exception as e:
            print(f'[ERROR] get_accrual_by_day: {e}')
            return pd.DataFrame()

    # ------------------------------------------------------------------
    # 6. АКЦИИ (Ozon и продавца)
    # ------------------------------------------------------------------

    def get_ozon_actions(self) -> pd.DataFrame:
        """Список акций Ozon (v1/actions) – GET"""
        try:
            resp = requests.get(f'{self.base_url}/v1/actions', headers=self.headers)
            if resp.status_code != 200:
                print(f'[WARN] get_ozon_actions статус {resp.status_code}')
                return pd.DataFrame()
            return pd.DataFrame(resp.json().get('result', []))
        except Exception as e:
            print(f'[ERROR] get_ozon_actions: {e}')
            return pd.DataFrame()

    # ---- Акции продавца ----

    def get_seller_actions(self, limit: int = 100, offset: int = 0, status: str = None) -> pd.DataFrame:
        """Список своих акций (v1/seller-actions/list)"""
        try:
            payload = {'limit': limit, 'offset': offset}
            if status:
                payload['status'] = [status]
            resp = requests.post(
                f'{self.base_url}/v1/seller-actions/list',
                headers=self.headers,
                json=payload
            )
            if resp.status_code != 200:
                print(f'[WARN] get_seller_actions статус {resp.status_code}')
                return pd.DataFrame()
            return pd.DataFrame(resp.json().get('actions', []))
        except Exception as e:
            print(f'[ERROR] get_seller_actions: {e}')
            return pd.DataFrame()

    def create_discount_action(self, date_start: str, date_end: str, min_percent: float, title: str = '') -> int:
        """Создать акцию «Скидка» (v1/seller-actions/create/discount)"""
        try:
            payload = {'date_start': date_start, 'date_end': date_end, 'min_action_percent': min_percent}
            if title:
                payload['title'] = title
            resp = requests.post(
                f'{self.base_url}/v1/seller-actions/create/discount',
                headers=self.headers,
                json=payload
            )
            return resp.json().get('action_id', 0)
        except Exception as e:
            print(f'[ERROR] create_discount_action: {e}')
            return 0

    def create_discount_with_condition(self, date_start: str, date_end: str,
                                       discount_type: str, discount_value: float,
                                       min_order_amount: float, title: str = '') -> int:
        """Скидка от суммы заказа (v1/seller-actions/create/discount-with-condition)"""
        try:
            payload = {
                'date_start': date_start,
                'date_end': date_end,
                'discount_type': discount_type,
                'discount_value': discount_value,
                'min_order_amount': min_order_amount
            }
            if title:
                payload['title'] = title
            resp = requests.post(
                f'{self.base_url}/v1/seller-actions/create/discount-with-condition',
                headers=self.headers,
                json=payload
            )
            return resp.json().get('action_id', 0)
        except Exception as e:
            print(f'[ERROR] create_discount_with_condition: {e}')
            return 0

    def create_installment_action(self, date_start: str, title: str = '') -> int:
        """Беспроцентная рассрочка (v1/seller-actions/create/installment)"""
        try:
            payload = {'date_start': date_start}
            if title:
                payload['title'] = title
            resp = requests.post(
                f'{self.base_url}/v1/seller-actions/create/installment',
                headers=self.headers,
                json=payload
            )
            return resp.json().get('action_id', 0)
        except Exception as e:
            print(f'[ERROR] create_installment_action: {e}')
            return 0

    def create_multi_level_discount(self, date_start: str, date_end: str,
                                    discount_type: str, levels: List[dict], title: str = '') -> int:
        """Многоуровневая скидка (v1/seller-actions/create/multi-level-discount)"""
        try:
            payload = {
                'date_start': date_start,
                'date_end': date_end,
                'discount_type': discount_type,
                'discount_levels': levels
            }
            if title:
                payload['title'] = title
            resp = requests.post(
                f'{self.base_url}/v1/seller-actions/create/multi-level-discount',
                headers=self.headers,
                json=payload
            )
            return resp.json().get('action_id', 0)
        except Exception as e:
            print(f'[ERROR] create_multi_level_discount: {e}')
            return 0

    def create_voucher_action(self, date_start: str, date_end: str,
                              discount_type: str, discount_value: float,
                              budget: int, title: str = '', user_ids: List[int] = None) -> int:
        """Скидка по промокоду (v1/seller-actions/create/voucher)"""
        try:
            payload = {
                'date_start': date_start,
                'date_end': date_end,
                'discount_type': discount_type,
                'discount_value': discount_value,
                'budget': budget,
                'voucher_parameters': {'type': 'ONE', 'count_codes': 100, 'is_private': False}
            }
            if title:
                payload['title'] = title
            if user_ids:
                payload['user_ids'] = user_ids
            resp = requests.post(
                f'{self.base_url}/v1/seller-actions/create/voucher',
                headers=self.headers,
                json=payload
            )
            return resp.json().get('action_id', 0)
        except Exception as e:
            print(f'[ERROR] create_voucher_action: {e}')
            return 0

    def add_products_to_action(self, action_id: int, products: List[dict]) -> bool:
        """Добавить товары в акцию (v1/seller-actions/products/add)"""
        try:
            payload = {'action_id': action_id, 'products': products}
            resp = requests.post(
                f'{self.base_url}/v1/seller-actions/products/add',
                headers=self.headers,
                json=payload
            )
            return resp.status_code == 200
        except Exception:
            return False

    def remove_products_from_action(self, action_id: int, skus: List[int]) -> bool:
        """Удалить товары из акции (v1/seller-actions/products/delete)"""
        try:
            payload = {'action_id': action_id, 'skus': skus}
            resp = requests.post(
                f'{self.base_url}/v1/seller-actions/products/delete',
                headers=self.headers,
                json=payload
            )
            return resp.status_code == 200
        except Exception:
            return False

    def get_action_candidates(self, action_id: int, limit: int = 100) -> pd.DataFrame:
        """Товары, доступные для добавления в акцию (v1/seller-actions/products/candidates)"""
        try:
            all_products = []
            cursor = 0
            while True:
                resp = requests.post(
                    f'{self.base_url}/v1/seller-actions/products/candidates',
                    headers=self.headers,
                    json={'action_id': action_id, 'cursor': cursor, 'limit': limit}
                )
                if resp.status_code != 200:
                    print(f'[WARN] get_action_candidates статус {resp.status_code}')
                    break
                data = resp.json()
                items = data.get('products', [])
                all_products.extend(items)
                if not data.get('has_next') or not data.get('cursor'):
                    break
                cursor = data['cursor']
                time.sleep(0.3)
            return pd.DataFrame(all_products)
        except Exception as e:
            print(f'[ERROR] get_action_candidates: {e}')
            return pd.DataFrame()

    def get_action_products(self, action_id: int, limit: int = 100) -> pd.DataFrame:
        """Товары, уже участвующие в акции (v1/seller-actions/products/list)"""
        try:
            all_products = []
            cursor = 0
            while True:
                resp = requests.post(
                    f'{self.base_url}/v1/seller-actions/products/list',
                    headers=self.headers,
                    json={'action_id': action_id, 'cursor': cursor, 'limit': limit}
                )
                if resp.status_code != 200:
                    print(f'[WARN] get_action_products статус {resp.status_code}')
                    break
                data = resp.json()
                items = data.get('products', [])
                all_products.extend(items)
                if not data.get('has_next') or not data.get('cursor'):
                    break
                cursor = data['cursor']
                time.sleep(0.3)
            return pd.DataFrame(all_products)
        except Exception as e:
            print(f'[ERROR] get_action_products: {e}')
            return pd.DataFrame()

    def archive_action(self, action_id: int) -> bool:
        """Перенести акцию в архив (v1/seller-actions/archive)"""
        try:
            resp = requests.post(
                f'{self.base_url}/v1/seller-actions/archive',
                headers=self.headers,
                json={'action_id': action_id}
            )
            return resp.status_code == 200
        except Exception:
            return False

    def toggle_action_activity(self, action_id: int, turn_on: bool) -> bool:
        """Включить/выключить акцию (v1/seller-actions/change-activity)"""
        try:
            resp = requests.post(
                f'{self.base_url}/v1/seller-actions/change-activity',
                headers=self.headers,
                json={'action_id': action_id, 'is_turn_on': turn_on}
            )
            return resp.status_code == 200
        except Exception:
            return False

    def get_voucher_file(self, action_id: int) -> str:
        """Получить ссылку на CSV с промокодами (v1/seller-actions/voucher/get)"""
        try:
            resp = requests.post(
                f'{self.base_url}/v1/seller-actions/voucher/get',
                headers=self.headers,
                json={'action_id': action_id}
            )
            if resp.status_code != 200:
                print(f'[WARN] get_voucher_file статус {resp.status_code}')
                return ''
            return resp.json().get('file', '')
        except Exception as e:
            print(f'[ERROR] get_voucher_file: {e}')
            return ''

    # ---- Автодобавление в акции Ozon ----

    def get_auto_add_products(self, action_id: int, auto_add_date: str, limit: int = 100) -> pd.DataFrame:
        """Товары в автодобавлении (v1/actions/auto-add/products/list)"""
        try:
            all_products = []
            offset = 0
            while True:
                resp = requests.post(
                    f'{self.base_url}/v1/actions/auto-add/products/list',
                    headers=self.headers,
                    json={
                        'action_id': action_id,
                        'auto_add_date': auto_add_date,
                        'limit': limit,
                        'offset': offset
                    }
                )
                if resp.status_code != 200:
                    print(f'[WARN] get_auto_add_products статус {resp.status_code}')
                    break
                data = resp.json()
                items = data.get('products', [])
                all_products.extend(items)
                if len(items) < limit:
                    break
                offset += limit
                time.sleep(0.3)
            return pd.DataFrame(all_products)
        except Exception as e:
            print(f'[ERROR] get_auto_add_products: {e}')
            return pd.DataFrame()

    def update_auto_add_products(self, action_id: int, auto_add_date: str, products: List[dict]) -> dict:
        """Обновить автодобавление (v1/actions/auto-add/products/update)"""
        try:
            payload = {
                'action_id': action_id,
                'auto_add_date': auto_add_date,
                'to_update': products
            }
            resp = requests.post(
                f'{self.base_url}/v1/actions/auto-add/products/update',
                headers=self.headers,
                json=payload
            )
            return resp.json()
        except Exception as e:
            print(f'[ERROR] update_auto_add_products: {e}')
            return {}

    # ------------------------------------------------------------------
    # 7. СКЛАД И ОСТАТКИ
    # ------------------------------------------------------------------

    def get_stocks(self) -> pd.DataFrame:
        """Базовые остатки (v4/product/info/stocks)"""
        try:
            resp = requests.post(
                f'{self.base_url}/v4/product/info/stocks',
                headers=self.headers,
                json={'filter': {'visibility': 'ALL'}, 'limit': 1000}
            )
            if resp.status_code != 200:
                print(f'[WARN] get_stocks статус {resp.status_code}')
                return pd.DataFrame()
            return pd.DataFrame(resp.json().get('items', []))
        except Exception as e:
            print(f'[ERROR] get_stocks: {e}')
            return pd.DataFrame()

    def get_stock_analytics(self, skus: List[int] = None) -> pd.DataFrame:
        """Детальная аналитика остатков (v1/analytics/stocks)"""
        try:
            payload = {'skus': skus or []}
            resp = requests.post(
                f'{self.base_url}/v1/analytics/stocks',
                headers=self.headers,
                json=payload
            )
            if resp.status_code != 200:
                print(f'[WARN] get_stock_analytics статус {resp.status_code}')
                return pd.DataFrame()
            return pd.DataFrame(resp.json().get('items', []))
        except Exception as e:
            print(f'[ERROR] get_stock_analytics: {e}')
            return pd.DataFrame()

    def get_warehouse_list(self, limit: int = 200) -> pd.DataFrame:
        """Список складов (v2/warehouse/list)"""
        try:
            all_wh = []
            cursor = ''
            payload = {'limit': limit, 'cursor': cursor}
            while True:
                resp = requests.post(
                    f'{self.base_url}/v2/warehouse/list',
                    headers=self.headers,
                    json=payload
                )
                if resp.status_code != 200:
                    print(f'[WARN] get_warehouse_list статус {resp.status_code}')
                    break
                data = resp.json()
                warehouses = data.get('warehouses', [])
                all_wh.extend(warehouses)
                if not data.get('has_next') or not data.get('cursor'):
                    break
                payload['cursor'] = data['cursor']
                time.sleep(0.3)
            return pd.DataFrame(all_wh)
        except Exception as e:
            print(f'[ERROR] get_warehouse_list: {e}')
            return pd.DataFrame()

    def get_supply_orders(self, states: List[str] = None) -> pd.DataFrame:
        """Заявки на поставку FBO (v3/supply-order/list)"""
        try:
            filter_obj = {}
            if states:
                filter_obj['states'] = states
            all_ids = []
            last_id = ''
            payload = {'filter': filter_obj, 'limit': 100, 'last_id': last_id}
            while True:
                resp = requests.post(
                    f'{self.base_url}/v3/supply-order/list',
                    headers=self.headers,
                    json=payload
                )
                if resp.status_code != 200:
                    print(f'[WARN] get_supply_orders статус {resp.status_code}')
                    break
                data = resp.json()
                ids = data.get('order_ids', [])
                all_ids.extend(ids)
                if not data.get('last_id'):
                    break
                payload['last_id'] = data['last_id']
                time.sleep(0.3)
            return pd.DataFrame(all_ids, columns=['order_id'])
        except Exception as e:
            print(f'[ERROR] get_supply_orders: {e}')
            return pd.DataFrame()

    # ------------------------------------------------------------------
    # 8. ОТЗЫВЫ И РЕЙТИНГИ
    # ------------------------------------------------------------------

    def get_reviews(self, status: str = 'ALL', limit: int = 100, last_id: str = '',
                    date_from: str = None, date_to: str = None) -> pd.DataFrame:
        """Список отзывов (v2/review/list) – требуется подписка Premium Pro или Управление отзывами"""
        try:
            all_reviews = []
            payload = {'limit': limit, 'last_id': last_id, 'sort_dir': 'ASC'}
            filters = {}
            if status and status != 'ALL':
                filters['status'] = status
            if date_from:
                filters['published_from'] = date_from
            if date_to:
                filters['published_to'] = date_to
            if filters:
                payload['filters'] = filters

            while True:
                resp = requests.post(
                    f'{self.base_url}/v2/review/list',
                    headers=self.headers,
                    json=payload
                )
                if resp.status_code != 200:
                    # Если 403 – просто выходим, т.к. это ожидаемо при отсутствии подписки
                    if resp.status_code == 403:
                        print('[WARN] Отзывы недоступны (нет подписки)')
                    else:
                        print(f'[WARN] get_reviews статус {resp.status_code}')
                    break
                data = resp.json()
                items = data.get('reviews', [])
                all_reviews.extend(items)
                if not data.get('has_next') or not data.get('last_id'):
                    break
                payload['last_id'] = data['last_id']
                time.sleep(0.3)
            return pd.DataFrame(all_reviews)
        except Exception as e:
            print(f'[ERROR] get_reviews: {e}')
            return pd.DataFrame()

    def get_review_info(self, review_id: str) -> dict:
        """Информация об отзыве (v2/review/info)"""
        try:
            resp = requests.post(
                f'{self.base_url}/v2/review/info',
                headers=self.headers,
                json={'review_id': review_id}
            )
            if resp.status_code != 200:
                print(f'[WARN] get_review_info статус {resp.status_code}')
                return {}
            return resp.json()
        except Exception as e:
            print(f'[ERROR] get_review_info: {e}')
            return {}

    def get_review_counts(self) -> dict:
        """Количество отзывов по статусам (v2/review/count)"""
        try:
            resp = requests.post(
                f'{self.base_url}/v2/review/count',
                headers=self.headers,
                json={}
            )
            if resp.status_code != 200:
                print(f'[WARN] get_review_counts статус {resp.status_code}')
                return {}
            return resp.json()
        except Exception as e:
            print(f'[ERROR] get_review_counts: {e}')
            return {}

    def change_review_status(self, review_ids: List[str], status: str) -> bool:
        """Изменить статус отзывов (v2/review/change-status)"""
        try:
            payload = {'review_ids': review_ids, 'status': status}
            resp = requests.post(
                f'{self.base_url}/v2/review/change-status',
                headers=self.headers,
                json=payload
            )
            return resp.status_code == 200
        except Exception:
            return False

    def create_review_comment(self, review_id: str, text: str,
                              mark_processed: bool = True,
                              parent_comment_id: str = None) -> str:
        """Оставить комментарий на отзыв (v1/review/comment/create)"""
        try:
            payload = {
                'review_id': review_id,
                'text': text,
                'mark_review_as_processed': mark_processed
            }
            if parent_comment_id:
                payload['parent_comment_id'] = parent_comment_id
            resp = requests.post(
                f'{self.base_url}/v1/review/comment/create',
                headers=self.headers,
                json=payload
            )
            if resp.status_code != 200:
                print(f'[WARN] create_review_comment статус {resp.status_code}')
                return ''
            return resp.json().get('comment_id', '')
        except Exception as e:
            print(f'[ERROR] create_review_comment: {e}')
            return ''

    def get_rating_summary(self) -> dict:
        """Текущие рейтинги продавца (v1/rating/summary)"""
        try:
            resp = requests.post(
                f'{self.base_url}/v1/rating/summary',
                headers=self.headers,
                json={}
            )
            if resp.status_code != 200:
                print(f'[WARN] get_rating_summary статус {resp.status_code}')
                return {}
            return resp.json()
        except Exception as e:
            print(f'[ERROR] get_rating_summary: {e}')
            return {}

    def get_rating_history(self, date_from: str, date_to: str,
                           ratings: List[str], with_premium_scores: bool = False) -> dict:
        """История рейтингов (v1/rating/history)"""
        try:
            payload = {
                'date_from': date_from,
                'date_to': date_to,
                'ratings': ratings,
                'with_premium_scores': with_premium_scores
            }
            resp = requests.post(
                f'{self.base_url}/v1/rating/history',
                headers=self.headers,
                json=payload
            )
            if resp.status_code != 200:
                print(f'[WARN] get_rating_history статус {resp.status_code}')
                return {}
            return resp.json()
        except Exception as e:
            print(f'[ERROR] get_rating_history: {e}')
            return {}

    def get_fbs_error_index(self) -> dict:
        """Индекс ошибок FBS/rFBS (v1/rating/index/fbs/info)"""
        try:
            resp = requests.post(
                f'{self.base_url}/v1/rating/index/fbs/info',
                headers=self.headers,
                json={}
            )
            if resp.status_code != 200:
                print(f'[WARN] get_fbs_error_index статус {resp.status_code}')
                return {}
            return resp.json()
        except Exception as e:
            print(f'[ERROR] get_fbs_error_index: {e}')
            return {}

    def get_fbs_error_postings(self, date_from: str, date_to: str, limit: int = 1000) -> pd.DataFrame:
        """Отправления, влияющие на индекс ошибок (v1/rating/index/fbs/posting/list)"""
        try:
            all_errors = []
            cursor = ''
            payload = {'filter': {'date_from': date_from, 'date_to': date_to}, 'limit': limit, 'cursor': cursor}
            while True:
                resp = requests.post(
                    f'{self.base_url}/v1/rating/index/fbs/posting/list',
                    headers=self.headers,
                    json=payload
                )
                if resp.status_code != 200:
                    print(f'[WARN] get_fbs_error_postings статус {resp.status_code}')
                    break
                data = resp.json()
                items = data.get('errors', [])
                all_errors.extend(items)
                if not data.get('has_next') or not data.get('cursor'):
                    break
                payload['cursor'] = data['cursor']
                time.sleep(0.3)
            return pd.DataFrame(all_errors)
        except Exception as e:
            print(f'[ERROR] get_fbs_error_postings: {e}')
            return pd.DataFrame()

    # ------------------------------------------------------------------
    # 9. АСИНХРОННЫЕ ОТЧЁТЫ
    # ------------------------------------------------------------------

    def create_product_report(self, visibility: str = 'ALL', offer_ids: List[str] = None,
                              skus: List[int] = None) -> str:
        """Запустить отчёт по товарам (v1/report/products/create)"""
        try:
            payload = {
                'visibility': visibility,
                'offer_id': offer_ids or [],
                'sku': skus or [],
                'language': 'DEFAULT'
            }
            resp = requests.post(
                f'{self.base_url}/v1/report/products/create',
                headers=self.headers,
                json=payload
            )
            if resp.status_code != 200:
                print(f'[WARN] create_product_report статус {resp.status_code}')
                return ''
            return resp.json().get('result', {}).get('code', '')
        except Exception as e:
            print(f'[ERROR] create_product_report: {e}')
            return ''

    def create_returns_report(self, date_from: str, date_to: str,
                              delivery_schema: str = None, status: str = None) -> str:
        """Отчёт по возвратам (v2/report/returns/create)"""
        try:
            payload = {
                'filter': {'date_from': date_from, 'date_to': date_to},
                'language': 'DEFAULT'
            }
            if delivery_schema:
                payload['filter']['delivery_schema'] = delivery_schema
            if status:
                payload['filter']['status'] = status
            resp = requests.post(
                f'{self.base_url}/v2/report/returns/create',
                headers=self.headers,
                json=payload
            )
            if resp.status_code != 200:
                print(f'[WARN] create_returns_report статус {resp.status_code}')
                return ''
            return resp.json().get('result', {}).get('code', '')
        except Exception as e:
            print(f'[ERROR] create_returns_report: {e}')
            return ''

    def create_postings_report(self, date_from: str, date_to: str,
                               delivery_schema: List[str] = None) -> str:
        """Отчёт по отправлениям (v1/report/postings/create)"""
        try:
            payload = {
                'filter': {'processed_at_from': date_from, 'processed_at_to': date_to},
                'language': 'DEFAULT'
            }
            if delivery_schema:
                payload['filter']['delivery_schema'] = delivery_schema
            resp = requests.post(
                f'{self.base_url}/v1/report/postings/create',
                headers=self.headers,
                json=payload
            )
            if resp.status_code != 200:
                print(f'[WARN] create_postings_report статус {resp.status_code}')
                return ''
            return resp.json().get('result', {}).get('code', '')
        except Exception as e:
            print(f'[ERROR] create_postings_report: {e}')
            return ''

    def get_report_info(self, code: str) -> dict:
        """Информация о готовом отчёте (v1/report/info)"""
        try:
            resp = requests.post(
                f'{self.base_url}/v1/report/info',
                headers=self.headers,
                json={'code': code}
            )
            if resp.status_code != 200:
                print(f'[WARN] get_report_info статус {resp.status_code}')
                return {}
            return resp.json().get('result', {})
        except Exception as e:
            print(f'[ERROR] get_report_info: {e}')
            return {}

    def get_report_list(self, page: int = 1, page_size: int = 100, report_type: str = 'ALL') -> pd.DataFrame:
        """Список созданных отчётов (v1/report/list)"""
        try:
            payload = {'page': page, 'page_size': page_size, 'report_type': report_type}
            resp = requests.post(
                f'{self.base_url}/v1/report/list',
                headers=self.headers,
                json=payload
            )
            if resp.status_code != 200:
                print(f'[WARN] get_report_list статус {resp.status_code}')
                return pd.DataFrame()
            return pd.DataFrame(resp.json().get('result', {}).get('reports', []))
        except Exception as e:
            print(f'[ERROR] get_report_list: {e}')
            return pd.DataFrame()

    # ------------------------------------------------------------------
    # 10. ЧАТЫ (PREMIUM)
    # ------------------------------------------------------------------

    def send_chat_message(self, chat_id: str, text: str) -> bool:
        """Отправить сообщение в чат (v1/chat/send/message) – Premium"""
        try:
            payload = {'chat_id': chat_id, 'text': text}
            resp = requests.post(
                f'{self.base_url}/v1/chat/send/message',
                headers=self.headers,
                json=payload
            )
            return resp.status_code == 200
        except Exception:
            return False

    def start_chat(self, posting_number: str) -> str:
        """Создать новый чат (v1/chat/start) – Premium"""
        try:
            resp = requests.post(
                f'{self.base_url}/v1/chat/start',
                headers=self.headers,
                json={'posting_number': posting_number}
            )
            if resp.status_code != 200:
                print(f'[WARN] start_chat статус {resp.status_code}')
                return ''
            return resp.json().get('result', {}).get('chat_id', '')
        except Exception as e:
            print(f'[ERROR] start_chat: {e}')
            return ''

    def mark_messages_read(self, chat_id: str, from_message_id: int = None) -> int:
        """Отметить сообщения как прочитанные (v2/chat/read) – Premium"""
        try:
            payload = {'chat_id': chat_id}
            if from_message_id:
                payload['from_message_id'] = from_message_id
            resp = requests.post(
                f'{self.base_url}/v2/chat/read',
                headers=self.headers,
                json=payload
            )
            if resp.status_code != 200:
                print(f'[WARN] mark_messages_read статус {resp.status_code}')
                return 0
            return resp.json().get('unread_count', 0)
        except Exception as e:
            print(f'[ERROR] mark_messages_read: {e}')
            return 0

    # ------------------------------------------------------------------
    # 11. ПУШ-УВЕДОМЛЕНИЯ
    # ------------------------------------------------------------------

    def set_notification_url(self, url: str, types: List[str]) -> bool:
        """Подключить URL для уведомлений (v1/notification/set)"""
        try:
            payload = {'url': url, 'types': types}
            resp = requests.post(
                f'{self.base_url}/v1/notification/set',
                headers=self.headers,
                json=payload
            )
            return resp.status_code == 200
        except Exception:
            return False

    def update_notification_url(self, url_id: int, url: str = None, types: List[str] = None) -> bool:
        """Обновить URL (v1/notification/update)"""
        try:
            payload = {'id': url_id}
            if url:
                payload['url'] = url
            if types:
                payload['types'] = types
            resp = requests.post(
                f'{self.base_url}/v1/notification/update',
                headers=self.headers,
                json=payload
            )
            return resp.status_code == 200
        except Exception:
            return False

    def delete_notification_url(self, url_id: int) -> bool:
        """Удалить URL (v1/notification/delete)"""
        try:
            resp = requests.post(
                f'{self.base_url}/v1/notification/delete',
                headers=self.headers,
                json={'id': url_id}
            )
            return resp.status_code == 200
        except Exception:
            return False

    def check_notification_url(self, url: str) -> dict:
        """Проверить URL (v1/notification/check)"""
        try:
            resp = requests.post(
                f'{self.base_url}/v1/notification/check',
                headers=self.headers,
                json={'url': url}
            )
            if resp.status_code != 200:
                print(f'[WARN] check_notification_url статус {resp.status_code}')
                return {}
            return resp.json()
        except Exception as e:
            print(f'[ERROR] check_notification_url: {e}')
            return {}

    def enable_notification(self, url_id: int, enabled: bool) -> bool:
        """Включить/выключить уведомления (v1/notification/enable)"""
        try:
            resp = requests.post(
                f'{self.base_url}/v1/notification/enable',
                headers=self.headers,
                json={'id': url_id, 'enabled': enabled}
            )
            return resp.status_code == 200
        except Exception:
            return False

    def get_notification_list(self) -> pd.DataFrame:
        """Список подключённых URL (v1/notification/list)"""
        try:
            resp = requests.post(
                f'{self.base_url}/v1/notification/list',
                headers=self.headers,
                json={}
            )
            if resp.status_code != 200:
                print(f'[WARN] get_notification_list статус {resp.status_code}')
                return pd.DataFrame()
            return pd.DataFrame(resp.json().get('urls', []))
        except Exception as e:
            print(f'[ERROR] get_notification_list: {e}')
            return pd.DataFrame()

    def get_notification_types(self) -> pd.DataFrame:
        """Типы уведомлений (v1/notification/push-type/list)"""
        try:
            resp = requests.post(
                f'{self.base_url}/v1/notification/push-type/list',
                headers=self.headers,
                json={}
            )
            if resp.status_code != 200:
                print(f'[WARN] get_notification_types статус {resp.status_code}')
                return pd.DataFrame()
            return pd.DataFrame(resp.json().get('types', []))
        except Exception as e:
            print(f'[ERROR] get_notification_types: {e}')
            return pd.DataFrame()

    # ------------------------------------------------------------------
    # 12. СКИДКА ОТ КОЛИЧЕСТВА (БЕТА)
    # ------------------------------------------------------------------

    def set_stairway_discount(self, sku: int, enabled: bool, steps: List[dict] = None) -> bool:
        """Установить скидку от количества (v1/product/stairway-discount/by-quantity/set)"""
        try:
            stairway = {'enabled': enabled}
            if steps:
                stairway['stairway'] = {'steps': steps}
            payload = {'stairways': [{'sku': sku, **stairway}], 'suppress_warnings': True}
            resp = requests.post(
                f'{self.base_url}/v1/product/stairway-discount/by-quantity/set',
                headers=self.headers,
                json=payload
            )
            return resp.status_code == 200
        except Exception:
            return False

    def get_stairway_discount(self, skus: List[int]) -> pd.DataFrame:
        """Получить скидку от количества (v1/product/stairway-discount/by-quantity/get)"""
        try:
            payload = {'skus': skus[:5000]}
            resp = requests.post(
                f'{self.base_url}/v1/product/stairway-discount/by-quantity/get',
                headers=self.headers,
                json=payload
            )
            if resp.status_code != 200:
                print(f'[WARN] get_stairway_discount статус {resp.status_code}')
                return pd.DataFrame()
            return pd.DataFrame(resp.json().get('stairways', []))
        except Exception as e:
            print(f'[ERROR] get_stairway_discount: {e}')
            return pd.DataFrame()

    # ------------------------------------------------------------------
    # 13. КАТЕГОРИИ И ХАРАКТЕРИСТИКИ
    # ------------------------------------------------------------------

    def get_category_tree(self, language: str = 'DEFAULT') -> pd.DataFrame:
        """Дерево категорий (v1/description-category/tree)"""
        try:
            resp = requests.post(
                f'{self.base_url}/v1/description-category/tree',
                headers=self.headers,
                json={'language': language}
            )
            if resp.status_code != 200:
                print(f'[WARN] get_category_tree статус {resp.status_code}')
                return pd.DataFrame()
            return pd.DataFrame(resp.json().get('result', []))
        except Exception as e:
            print(f'[ERROR] get_category_tree: {e}')
            return pd.DataFrame()

    def get_category_attributes(self, category_id: int, type_id: int, language: str = 'DEFAULT') -> pd.DataFrame:
        """Характеристики категории (v1/description-category/attribute)"""
        try:
            payload = {
                'description_category_id': category_id,
                'type_id': type_id,
                'language': language
            }
            resp = requests.post(
                f'{self.base_url}/v1/description-category/attribute',
                headers=self.headers,
                json=payload
            )
            if resp.status_code != 200:
                print(f'[WARN] get_category_attributes статус {resp.status_code}')
                return pd.DataFrame()
            return pd.DataFrame(resp.json().get('result', []))
        except Exception as e:
            print(f'[ERROR] get_category_attributes: {e}')
            return pd.DataFrame()

    def get_dependent_attributes(self, category_id: int, type_id: int) -> pd.DataFrame:
        """Зависимые характеристики (v1/description-category/dependent-attributes) – бета"""
        try:
            payload = {'description_category_id': category_id, 'type_id': type_id}
            resp = requests.post(
                f'{self.base_url}/v1/description-category/dependent-attributes',
                headers=self.headers,
                json=payload
            )
            if resp.status_code != 200:
                print(f'[WARN] get_dependent_attributes статус {resp.status_code}')
                return pd.DataFrame()
            return pd.DataFrame(resp.json().get('result', []))
        except Exception as e:
            print(f'[ERROR] get_dependent_attributes: {e}')
            return pd.DataFrame()

    def get_dependent_attribute_values(self, parent_attr_id: int, child_attr_id: int,
                                       category_id: int, type_id: int,
                                       limit: int = 100, cursor: str = '') -> pd.DataFrame:
        """Значения дочерней характеристики (v1/description-category/dependent-attributes/values) – бета"""
        try:
            payload = {
                'parent_attribute_id': parent_attr_id,
                'child_attribute_id': child_attr_id,
                'description_category_id': category_id,
                'type_id': type_id,
                'limit': limit,
                'cursor': cursor
            }
            resp = requests.post(
                f'{self.base_url}/v1/description-category/dependent-attributes/values',
                headers=self.headers,
                json=payload
            )
            if resp.status_code != 200:
                print(f'[WARN] get_dependent_attribute_values статус {resp.status_code}')
                return pd.DataFrame()
            return pd.DataFrame(resp.json().get('result', []))
        except Exception as e:
            print(f'[ERROR] get_dependent_attribute_values: {e}')
            return pd.DataFrame()

    # ------------------------------------------------------------------
    # 14. PREMIUM-АНАЛИТИКА (поисковые запросы, детали цен)
    # ------------------------------------------------------------------

    def get_product_queries(self, date_from: str, date_to: str, skus: List[int],
                            page: int = 0, page_size: int = 1000) -> pd.DataFrame:
        """Запросы моих товаров (v1/analytics/product-queries) – Premium"""
        try:
            payload = {
                'date_from': date_from,
                'date_to': date_to,
                'skus': skus,
                'page': page,
                'page_size': page_size,
                'sort_by': 'BY_SEARCHES',
                'sort_dir': 'DESCENDING'
            }
            resp = requests.post(
                f'{self.base_url}/v1/analytics/product-queries',
                headers=self.headers,
                json=payload
            )
            if resp.status_code != 200:
                print(f'[WARN] get_product_queries статус {resp.status_code}')
                return pd.DataFrame()
            return pd.DataFrame(resp.json().get('items', []))
        except Exception as e:
            print(f'[ERROR] get_product_queries: {e}')
            return pd.DataFrame()

    def get_product_queries_details(self, date_from: str, date_to: str, skus: List[int],
                                    limit_by_sku: int = 15, page: int = 0, page_size: int = 100) -> pd.DataFrame:
        """Детализация запросов по товару (v1/analytics/product-queries/details) – Premium"""
        try:
            payload = {
                'date_from': date_from,
                'date_to': date_to,
                'skus': skus,
                'limit_by_sku': limit_by_sku,
                'page': page,
                'page_size': page_size,
                'sort_by': 'BY_SEARCHES',
                'sort_dir': 'DESCENDING'
            }
            resp = requests.post(
                f'{self.base_url}/v1/analytics/product-queries/details',
                headers=self.headers,
                json=payload
            )
            if resp.status_code != 200:
                print(f'[WARN] get_product_queries_details статус {resp.status_code}')
                return pd.DataFrame()
            return pd.DataFrame(resp.json().get('queries', []))
        except Exception as e:
            print(f'[ERROR] get_product_queries_details: {e}')
            return pd.DataFrame()

    def get_search_queries_by_text(self, text: str, limit: int = 50, offset: int = 0) -> pd.DataFrame:
        """Поиск по тексту запросов (v1/search-queries/text) – Premium Pro"""
        try:
            payload = {
                'text': text,
                'limit': str(limit),
                'offset': str(offset),
                'sort_by': 'CLIENT_COUNT',
                'sort_dir': 'DESC'
            }
            resp = requests.post(
                f'{self.base_url}/v1/search-queries/text',
                headers=self.headers,
                json=payload
            )
            if resp.status_code != 200:
                print(f'[WARN] get_search_queries_by_text статус {resp.status_code}')
                return pd.DataFrame()
            return pd.DataFrame(resp.json().get('search_queries', []))
        except Exception as e:
            print(f'[ERROR] get_search_queries_by_text: {e}')
            return pd.DataFrame()

    def get_top_search_queries(self, limit: int = 50, offset: int = 0) -> pd.DataFrame:
        """Топ популярных запросов (v1/search-queries/top) – Premium Pro"""
        try:
            payload = {'limit': str(limit), 'offset': str(offset)}
            resp = requests.post(
                f'{self.base_url}/v1/search-queries/top',
                headers=self.headers,
                json=payload
            )
            if resp.status_code != 200:
                print(f'[WARN] get_top_search_queries статус {resp.status_code}')
                return pd.DataFrame()
            return pd.DataFrame(resp.json().get('search_queries', []))
        except Exception as e:
            print(f'[ERROR] get_top_search_queries: {e}')
            return pd.DataFrame()

    def get_product_prices_details(self, skus: List[int]) -> pd.DataFrame:
        """Детальная информация о ценах (v1/product/prices/details) – Premium Pro"""
        try:
            payload = {'skus': skus[:1000]}
            resp = requests.post(
                f'{self.base_url}/v1/product/prices/details',
                headers=self.headers,
                json=payload
            )
            if resp.status_code != 200:
                print(f'[WARN] get_product_prices_details статус {resp.status_code}')
                return pd.DataFrame()
            return pd.DataFrame(resp.json().get('prices', []))
        except Exception as e:
            print(f'[ERROR] get_product_prices_details: {e}')
            return pd.DataFrame()

    def get_finance_realization_by_day(self, day: int, month: int, year: int) -> pd.DataFrame:
        """Отчёт о реализации за день (v1/finance/realization/by-day) – Premium"""
        try:
            payload = {'day': day, 'month': month, 'year': year}
            resp = requests.post(
                f'{self.base_url}/v1/finance/realization/by-day',
                headers=self.headers,
                json=payload
            )
            if resp.status_code != 200:
                print(f'[WARN] get_finance_realization_by_day статус {resp.status_code}')
                return pd.DataFrame()
            return pd.DataFrame(resp.json().get('rows', []))
        except Exception as e:
            print(f'[ERROR] get_finance_realization_by_day: {e}')
            return pd.DataFrame()

    # ------------------------------------------------------------------
    # 15. МАССОВЫЙ ЭКСПОРТ (export_all)
    # ------------------------------------------------------------------

    def export_all(self, output_dir: str = 'assets/exports', days: int = 30,
                   with_premium: bool = False, modules: List[str] = None):
        """
        Полная выгрузка всех данных.
        :param output_dir: папка для сохранения
        :param days: период в днях для аналитики
        :param with_premium: использовать ли Premium-методы
        :param modules: список модулей для выгрузки (по умолчанию все)
        """
        import os
        os.makedirs(output_dir, exist_ok=True)

        date_to = datetime.now().strftime('%Y-%m-%d')
        date_from = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        if modules is None:
            modules = ['products', 'sales', 'finance', 'returns', 'reviews',
                       'ratings', 'stocks', 'actions', 'analytics']

        print(f'Начало выгрузки данных за период {date_from} – {date_to}')

        products = pd.DataFrame()
        # 1. Товары
        if 'products' in modules:
            print('1. Выгрузка товаров...')
            products = self.get_products()
            if not products.empty:
                products.to_csv(f'{output_dir}/products.csv', index=False)
                # детали по первым 100 товарам
                offer_ids = products['offer_id'].head(100).tolist()
                details = self.get_product_details(offer_ids)
                if not details.empty:
                    details.to_csv(f'{output_dir}/product_details.csv', index=False)
            else:
                print('   Товары не получены')

        # 2. Продажи (FBO)
        if 'sales' in modules:
            print('2. Выгрузка продаж (FBO)...')
            sales = self.get_postings_fbo(date_from, date_to)
            if not sales.empty:
                sales.to_csv(f'{output_dir}/sales_fbo.csv', index=False)
            else:
                # Попробуем FBS
                print('   Продажи FBO не найдены, пробуем FBS...')
                sales_fbs = self.get_postings_fbs(date_from, date_to)
                if not sales_fbs.empty:
                    sales_fbs.to_csv(f'{output_dir}/sales_fbs.csv', index=False)
                else:
                    print('   Продажи не найдены ни по FBO, ни по FBS')

        # 3. Финансы – используем рабочий метод get_finance_realization_by_posting
        if 'finance' in modules:
            print('3. Выгрузка финансов...')
            today = datetime.now()
            last_month = today.replace(day=1) - timedelta(days=1)
            # Используем позаказный отчёт о реализации (работает стабильно)
            realization = self.get_finance_realization_by_posting(last_month.year, last_month.month)
            if not realization.empty:
                realization.to_csv(f'{output_dir}/finance_realization.csv', index=False)
            else:
                print('   Финансовый отчёт по реализации пуст (возможно, нет данных за этот месяц)')

            # Транзакции (за период)
            trans = self.get_transactions(date_from, date_to, page=1, page_size=100)
            if not trans.empty:
                trans.to_csv(f'{output_dir}/transactions.csv', index=False)
            else:
                print('   Транзакции не получены')

        # 4. Возвраты
        if 'returns' in modules:
            print('4. Выгрузка возвратов...')
            returns = self.get_returns(date_from, date_to)
            if not returns.empty:
                returns.to_csv(f'{output_dir}/returns.csv', index=False)
            else:
                print('   Возвратов не найдено')

            giveouts = self.get_return_giveouts()
            if not giveouts.empty:
                giveouts.to_csv(f'{output_dir}/return_giveouts.csv', index=False)

            cancellations = self.get_cancellations(state='ALL')
            if not cancellations.empty:
                cancellations.to_csv(f'{output_dir}/cancellations.csv', index=False)

        # 5. Отзывы и рейтинги
        if 'reviews' in modules:
            print('5. Выгрузка отзывов и рейтингов...')
            # Отзывы (может потребоваться подписка)
            reviews = self.get_reviews(status='ALL', date_from=f"{date_from}T00:00:00Z", date_to=f"{date_to}T23:59:59Z")
            if not reviews.empty:
                reviews.to_csv(f'{output_dir}/reviews.csv', index=False)
            else:
                print('   Отзывы не получены (возможно, нет подписки)')

            counts = self.get_review_counts()
            if counts:
                with open(f'{output_dir}/review_counts.json', 'w', encoding='utf-8') as f:
                    json.dump(counts, f, ensure_ascii=False, indent=2)

            rating_summary = self.get_rating_summary()
            if rating_summary:
                with open(f'{output_dir}/rating_summary.json', 'w', encoding='utf-8') as f:
                    json.dump(rating_summary, f, ensure_ascii=False, indent=2)

        # 6. Остатки
        if 'stocks' in modules:
            print('6. Выгрузка остатков...')
            stocks = self.get_stocks()
            if not stocks.empty:
                stocks.to_csv(f'{output_dir}/stocks.csv', index=False)
            else:
                print('   Остатки не получены')

            stock_analytics = self.get_stock_analytics()
            if not stock_analytics.empty:
                stock_analytics.to_csv(f'{output_dir}/stock_analytics.csv', index=False)

        # 7. Акции
        if 'actions' in modules:
            print('7. Выгрузка акций...')
            ozon_actions = self.get_ozon_actions()
            if not ozon_actions.empty:
                ozon_actions.to_csv(f'{output_dir}/ozon_actions.csv', index=False)

            seller_actions = self.get_seller_actions(limit=100)
            if not seller_actions.empty:
                seller_actions.to_csv(f'{output_dir}/seller_actions.csv', index=False)

        # 8. Premium-аналитика (если включено)
        if with_premium and 'analytics' in modules:
            print('8. Выгрузка Premium-аналитики...')
            # берём первые 100 SKU из товаров
            skus = products['sku'].head(100).tolist() if not products.empty else []
            if skus:
                try:
                    product_queries = self.get_product_queries(f"{date_from}T00:00:00Z", f"{date_to}T23:59:59Z", skus)
                    if not product_queries.empty:
                        product_queries.to_csv(f'{output_dir}/product_queries.csv', index=False)
                except Exception as e:
                    print(f'  Premium-метод product_queries: {e}')

        print(f'Выгрузка завершена! Файлы сохранены в {output_dir}/')

# ----------------------------------------------------------------------
#  ТОЧКА ВХОДА (для автономного запуска)
# ----------------------------------------------------------------------

if __name__ == '__main__':
    # Загрузка конфигурации
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        print('[ERROR] Файл config.json не найден. Создайте его на основе config_template.json')
        exit(1)

    exporter = OzonAPIExporter(
        client_id=config['ozon_api']['client_id'],
        api_key=config['ozon_api']['api_key'],
        base_url=config['ozon_api']['base_url']
    )

    # Выполняем полную выгрузку
    exporter.export_all(
        output_dir='assets/exports',
        days=config['export_settings'].get('days', 30),
        with_premium=config['export_settings'].get('with_premium', False)
    )