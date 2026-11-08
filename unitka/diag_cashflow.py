import json
import sys
from .ozon_client import OzonClient

def main(date_from, date_to):
    client = OzonClient()
    payload = {
        "date": {
            "from": date_from + 'T00:00:00.000Z',
            "to": date_to + 'T23:59:59.999Z'
        },
        "page": 1,
        "page_size": 10,
        "with_details": True
    }
    print("Отправляем запрос с параметрами:")
    print(json.dumps(payload, indent=2))
    print("\nОтвет от API:")
    resp = client._post('/v1/finance/cash-flow-statement/list', payload)
    if resp:
        print(json.dumps(resp, indent=2, ensure_ascii=False))
    else:
        print("Ответ пустой или ошибка.")

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Использование: python -m unitka.diag_cashflow YYYY-MM-DD YYYY-MM-DD")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])