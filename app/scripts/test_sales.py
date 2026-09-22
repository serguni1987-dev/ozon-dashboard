from ozon_api_export import OzonAPIExporter
import json

with open('../config.json', 'r') as f:
    config = json.load(f)

exporter = OzonAPIExporter(config['ozon_api']['client_id'], config['ozon_api']['api_key'])

# Период, в котором точно есть заказ (по скриншоту – 27 августа)
sales = exporter.get_postings_fbo('2026-08-27', '2026-08-27')
print(f'Найдено заказов: {len(sales)}')
if not sales.empty:
    print(sales[['posting_number', 'order_number', 'status', 'created_at']].head())
else:
    print('Заказов не найдено. Проверьте настройки API.')