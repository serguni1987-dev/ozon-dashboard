"""unitka/init_db.py — создание пустой базы у нового продавца.

    py -m unitka.init_db           создать недостающие таблицы и индексы в app\\ozon.db
    py -m unitka.init_db --check   только показать, каких таблиц не хватает
    py -m unitka.init_db --dump    пересобрать unitka\\schema.sql из рабочей базы (делает разработчик)

Схема лежит в unitka\\schema.sql. Все команды — CREATE ... IF NOT EXISTS: существующие
таблицы и данные не трогаются, запуск на рабочей базе безопасен.
"""
from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path

from . import config

SCHEMA = Path(__file__).resolve().parent / "schema.sql"


def dump(db_path: Path = config.DB_PATH, out: Path = SCHEMA) -> int:
    con = sqlite3.connect(str(db_path))
    rows = con.execute(
        "SELECT type, name, sql FROM sqlite_master "
        "WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY type DESC, name"
    ).fetchall()
    con.close()
    parts = ["-- Схема базы «Пульт Ozon». Файл собран командой: py -m unitka.init_db --dump", ""]
    for _type, _name, sql in rows:
        sql = re.sub(r"^CREATE TABLE (?!IF NOT EXISTS)", "CREATE TABLE IF NOT EXISTS ", sql.strip(), flags=re.I)
        sql = re.sub(r"^CREATE (UNIQUE )?INDEX (?!IF NOT EXISTS)", r"CREATE \1INDEX IF NOT EXISTS ", sql, flags=re.I)
        parts.append(sql + ";\n")
    out.write_text("\n".join(parts), encoding="utf-8", newline="\n")
    return len(rows)


def schema_tables() -> list[str]:
    text = SCHEMA.read_text(encoding="utf-8")
    return re.findall(r'CREATE TABLE IF NOT EXISTS\s+["`\[]?([A-Za-z0-9_]+)', text)


def missing(db_path: Path = config.DB_PATH) -> list[str]:
    if not Path(db_path).exists():
        return schema_tables()
    con = sqlite3.connect(str(db_path))
    have = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    con.close()
    return [t for t in schema_tables() if t not in have]


def statements() -> list[str]:
    """Команды из schema.sql по одной (разделитель — «;» в конце команды)."""
    out, buf = [], ""
    for line in SCHEMA.read_text(encoding="utf-8").splitlines():
        if not buf and (not line.strip() or line.lstrip().startswith("--")):
            continue
        buf += line + "\n"
        if sqlite3.complete_statement(buf):
            out.append(buf.strip())
            buf = ""
    return out


def ensure(con) -> list[str]:
    """Выполняет schema.sql на открытом соединении, команда за командой. Не падает:
    если команда не подошла к уже существующей базе (например, индекс на колонку,
    которой в старой таблице нет), она пропускается и возвращается в списке ошибок."""
    errors = []
    for sql in statements():
        try:
            con.execute(sql)
        except sqlite3.Error as exc:
            errors.append(f"{sql.splitlines()[0][:80]} — {exc}")
    con.commit()
    return errors


def apply(db_path: Path = config.DB_PATH) -> tuple[list[str], list[str]]:
    """Создаёт недостающие таблицы. Возвращает (созданные таблицы, пропущенные команды)."""
    before = missing(db_path)
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    errors = ensure(con)
    con.close()
    return before, errors


def main() -> None:
    ap = argparse.ArgumentParser(description="Создание и проверка схемы базы")
    ap.add_argument("--check", action="store_true", help="только показать недостающие таблицы")
    ap.add_argument("--dump", action="store_true", help="пересобрать schema.sql из рабочей базы")
    args = ap.parse_args()
    if args.dump:
        print(f"schema.sql: {dump()} объектов из {config.DB_PATH}")
        return
    if args.check:
        m = missing()
        print("Все таблицы на месте." if not m else "Не хватает таблиц: " + ", ".join(m))
        return
    created, errors = apply()
    print(f"База: {config.DB_PATH}")
    print("Схема в порядке, новых таблиц нет." if not created else f"Создано таблиц: {len(created)} ({', '.join(created)})")
    for e in errors:
        print(f"  пропущено: {e}")


if __name__ == "__main__":
    main()
