#!/usr/bin/env python3
"""
Сверка модели данных: ERD в git (DBML, «как согласовано») против реальной БД стенда («как сделано»).

  python3 scripts/check_drift_erd.py systems/example-system/erd/client.dbml \
      --psql "docker compose -f stand/docker-compose.yml exec -T db psql -U postgres" --db app

Как работает:
  1. DBML превращается в SQL (dbml2sql) и разворачивается во временной БД erd_expected
     на том же сервере PostgreSQL — так типы сравниваются один к одному.
  2. Из обеих БД берётся список таблиц и колонок (тип, NOT NULL).
  3. Любое расхождение — ошибка, код выхода 1.

--psql — команда запуска psql без имени БД. По умолчанию просто «psql» (локальный клиент;
параметры подключения — через PGHOST/PGPORT/PGUSER/PGPASSWORD).
"""
import argparse
import shlex
import subprocess
import sys

QUERY = """
SELECT c.table_name || '.' || c.column_name || ' ' ||
       CASE WHEN c.data_type = 'USER-DEFINED' THEN c.udt_name
            WHEN c.character_maximum_length IS NOT NULL THEN c.data_type || '(' || c.character_maximum_length || ')'
            ELSE c.data_type END ||
       CASE WHEN c.is_nullable = 'NO' THEN ' not null' ELSE '' END
FROM information_schema.columns c
JOIN information_schema.tables t
  ON t.table_schema = c.table_schema AND t.table_name = c.table_name AND t.table_type = 'BASE TABLE'
WHERE c.table_schema = 'public'
ORDER BY 1;
"""
SCRATCH = "erd_expected"


def run(cmd, stdin=None):
    r = subprocess.run(cmd, input=stdin, capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(r.stdout + r.stderr)
        raise SystemExit(f"ERROR команда завершилась с ошибкой: {' '.join(cmd[:4])} …")
    return r.stdout


def psql(base, db, sql=None, stdin=None):
    cmd = base + ["-v", "ON_ERROR_STOP=1", "-X", "-q", "-At", "-d", db]
    if sql:
        cmd += ["-c", sql]
    return run(cmd, stdin)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dbml")
    ap.add_argument("--psql", default="psql")
    ap.add_argument("--db", default="app", help="БД стенда")
    ap.add_argument("--dbml2sql", default="npx --yes -p @dbml/cli@3 dbml2sql")
    a = ap.parse_args()
    base = shlex.split(a.psql)

    expected_sql = run(shlex.split(a.dbml2sql) + [a.dbml, "--postgres"])

    psql(base, "postgres", f"DROP DATABASE IF EXISTS {SCRATCH}")
    psql(base, "postgres", f"CREATE DATABASE {SCRATCH}")
    try:
        psql(base, SCRATCH, stdin=expected_sql)
        expected = set(psql(base, SCRATCH, QUERY).split("\n")) - {""}
    finally:
        psql(base, "postgres", f"DROP DATABASE IF EXISTS {SCRATCH}")
    actual = set(psql(base, a.db, QUERY).split("\n")) - {""}

    only_doc = sorted(expected - actual)
    only_db = sorted(actual - expected)
    if not only_doc and not only_db:
        print(f"OK    {a.dbml}: модель данных совпадает с БД стенда ({len(actual)} колонок)")
        return 0

    print(f"ERROR {a.dbml}: модель данных разошлась с БД стенда")
    for line in only_db:
        print(f"  + в БД есть, в ERD нет:   {line}")
    for line in only_doc:
        print(f"  - в ERD есть, в БД нет:   {line}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
