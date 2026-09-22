# Удаляем все BOM из файла (не только в начале)
with open("sheets_sync.py", "rb") as f:
    data = f.read()

# BOM в UTF-8 = b"\xef\xbb\xbf"
# Убираем в начале (если есть)
if data.startswith(b"\xef\xbb\xbf"):
    data = data[3:]

# Убираем все остальные вхождения
data = data.replace(b"\xef\xbb\xbf", b"")

with open("sheets_sync.py", "wb") as f:
    f.write(data)

print("[OK] Все BOM удалены")
