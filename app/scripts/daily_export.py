#!/usr/bin/env python3
"""
Daily Export Script
Автоматическая ежедневная выгрузка ключевых метрик
"""

import json
from datetime import datetime, timedelta
from ozon_api_export import OzonAPIExporter

def main():
    # Загрузка конфигурации
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    exporter = OzonAPIExporter(
        client_id=config['ozon_api']['client_id'],
        api_key=config['ozon_api']['api_key']
    )
    
    # Вчерашние данные
    date_yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    date_today = datetime.now().strftime('%Y-%m-%d')
    
    print(f'Ежедневная выгрузка за {date_yesterday}...')
    
    # Ключевые метрики
    sales = exporter.get_sales_report(date_yesterday, date_today)
    advertising = exporter.get_advertising_campaigns()
    stocks = exporter.get_stocks()
    
    # Сохранение
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    sales.to_csv(f'assets/exports/daily_sales_{timestamp}.csv', index=False)
    advertising.to_csv(f'assets/exports/daily_advertising_{timestamp}.csv', index=False)
    stocks.to_csv(f'assets/exports/daily_stocks_{timestamp}.csv', index=False)
    
    print('Ежедневная выгрузка завершена!')

if __name__ == '__main__':
    main()