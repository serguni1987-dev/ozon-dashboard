# Читаем файл, убираем BOM
with open("sheets_sync.py", "rb") as f:
    raw = f.read()
if raw.startswith(b"\xef\xbb\xbf"):
    raw = raw[3:]
src = raw.decode("utf-8")

# Ищем все битые print(" <LF> [...]
# Они выглядят так:  print("\n[Лист ...")
# где \n это реальный перенос строки

broken_count = 0
new_lines = []
lines = src.split("\n")
i = 0
while i < len(lines):
    line = lines[i]
    # Если строка заканчивается на print(" и следующая начинается с [ — склеиваем
    if line.rstrip().endswith('print("') and i + 1 < len(lines) and lines[i+1].startswith("["):
        merged = line.rstrip()[:-1] + "\\n" + lines[i+1]
        new_lines.append(merged)
        broken_count += 1
        i += 2
    else:
        new_lines.append(line)
        i += 1

src = "\n".join(new_lines)

# Сохраняем без BOM
with open("sheets_sync.py", "wb") as f:
    f.write(src.encode("utf-8"))

print(f"[OK] Исправлено битых print: {broken_count}")
