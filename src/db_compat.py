"""
src/db_compat.py
Funciones de compatibilidad SQL entre
SQLite y PostgreSQL. No importar directamente
— usar via src.db que lo carga automáticamente.
"""
import re

def adapt_sql(sql: str, is_postgres: bool) -> str:
    """
    Adapta SQL de SQLite a PostgreSQL o viceversa.
    Solo se llama cuando is_postgres=True.
    """
    if not is_postgres:
        return sql

    # datetime('now') → NOW()
    sql = re.sub(
        r"datetime\('now'\)",
        "NOW()",
        sql, flags=re.IGNORECASE
    )
    # datetime('now', '+Xd') → NOW() + INTERVAL
    sql = re.sub(
        r"datetime\('now',\s*'([+-]\d+)\s*(\w+)'\)",
        lambda m: f"NOW() + INTERVAL '{m.group(1)} {m.group(2)}'",
        sql, flags=re.IGNORECASE
    )
    # DATE('now', '-X days/months') → (CURRENT_DATE + INTERVAL '-X days')
    sql = re.sub(
        r"DATE\('now',\s*'([^']+)'\)",
        lambda m: f"(CURRENT_DATE + INTERVAL '{m.group(1)}')",
        sql, flags=re.IGNORECASE
    )
    # DATE('now') → CURRENT_DATE
    sql = re.sub(
        r"DATE\('now'\)",
        "CURRENT_DATE",
        sql, flags=re.IGNORECASE
    )
    # DATE(column_name) → (column_name)::date  — cast timestamp → date
    # Must run after 'now' forms above so only plain identifiers remain
    sql = re.sub(
        r'\bDATE\((\w+)\)',
        r'(\1)::date',
        sql, flags=re.IGNORECASE
    )
    # AUTOINCREMENT → eliminar (PostgreSQL usa
    # SERIAL que no necesita la palabra)
    sql = re.sub(
        r'\bAUTOINCREMENT\b', '',
        sql, flags=re.IGNORECASE
    )
    # INTEGER PRIMARY KEY → SERIAL PRIMARY KEY
    # (solo en CREATE TABLE)
    if 'CREATE TABLE' in sql.upper():
        sql = re.sub(
            r'INTEGER PRIMARY KEY',
            'SERIAL PRIMARY KEY',
            sql, flags=re.IGNORECASE
        )
    # ? placeholders → %s (PostgreSQL usa %s)
    # Solo sustituir ? que sean parámetros
    # (no los que estén dentro de strings)
    sql = _replace_placeholders(sql)

    return sql

def _replace_placeholders(sql: str) -> str:
    """
    Reemplaza ? por %s para PostgreSQL.
    Ignora ? dentro de strings SQL.
    """
    result = []
    in_string = False
    string_char = None
    for char in sql:
        if char in ("'", '"') and not in_string:
            in_string = True
            string_char = char
            result.append(char)
        elif char == string_char and in_string:
            in_string = False
            string_char = None
            result.append(char)
        elif char == '?' and not in_string:
            result.append('%s')
        else:
            result.append(char)
    return ''.join(result)

def adapt_params(params, is_postgres: bool):
    """
    Adapta parámetros de query.
    SQLite acepta cualquier tipo.
    PostgreSQL necesita None en lugar de
    tipos Python específicos en algunos casos.
    """
    if not is_postgres or params is None:
        return params
    if isinstance(params, (list, tuple)):
        return tuple(params)
    return params
