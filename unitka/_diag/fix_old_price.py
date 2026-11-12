from pathlib import Path

path = Path(r"C:\Users\sergu\Desktop\проект\unitka\auto_repricer.py")
content = path.read_text(encoding="utf-8")

old_payload = '        payload = [{"offer_id": t["offer_id"], "price": str(t["new"])}]'
new_payload = '''        old_price = str(round(t["new"] * 1.2, 2)) # Зачеркнутая цена на 20% выше
        payload = [{"offer_id": t["offer_id"], "price": str(t["new"]), "old_price": old_price}]'''

if old_payload in content:
    content = content.replace(old_payload, new_payload)
    path.write_text(content, encoding="utf-8")
    print("УСПЕХ: В репрайсер добавлена передача old_price (чтобы Ozon не ругался)")
else:
    print("ОШИБКА: Не нашел строку payload. Возможно, файл изменился.")