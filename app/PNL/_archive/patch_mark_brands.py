"""Патч mark_brands.py — добавляет два правила:
1. Все SKU из monthly_realization_rows → is_own=1 (это твои товары).
2. SKU с is_own=1, но brand=None → brand='VIVA - HOME TEXTILE'.
"""

src = open("mark_brands.py", encoding="utf-8").read()

# Добавляем после существующего UPDATE по бренду
OLD = '''    placeholders = ",".join("?" * len(OWN_BRANDS))
    conn.execute(
        f"UPDATE products SET is_own = 1 WHERE brand IN ({placeholders})",
        OWN_BRANDS,
    )
    conn.commit()
'''

NEW = '''    placeholders = ",".join("?" * len(OWN_BRANDS))
    conn.execute(
        f"UPDATE products SET is_own = 1 WHERE brand IN ({placeholders})",
        OWN_BRANDS,
    )
    conn.commit()

    # ── ПРАВИЛО 2: все SKU из отчёта реализации → свои ──
    conn.execute("""
        UPDATE products
        SET is_own = 1
        WHERE sku IN (
            SELECT DISTINCT sku FROM monthly_realization_rows
            WHERE sku IS NOT NULL
        )
    """)
    conn.commit()

    # ── ПРАВИЛО 3: SKU со is_own=1 и brand=NULL → ставим VIVA ──
    conn.execute("""
        UPDATE products
        SET brand = 'VIVA - HOME TEXTILE'
        WHERE brand IS NULL AND is_own = 1
    """)
    conn.commit()
'''

if OLD in src:
    src = src.replace(OLD, NEW, 1)
    print("[OK] mark_brands.py дополнен правилами 2 и 3")
else:
    print("[?] Не нашёл блок UPDATE по бренду")

open("mark_brands.py", "w", encoding="utf-8").write(src)
print("[OK] сохранён")