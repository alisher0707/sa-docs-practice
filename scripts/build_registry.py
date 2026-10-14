#!/usr/bin/env python3
"""
Сборка реестра методов и проверка связности артефактов.

  python3 scripts/build_registry.py          # проверить и перезаписать registry/METHODS.md
  python3 scripts/build_registry.py --check  # только проверить (для CI): код выхода 1,
                                             # если есть ошибки или реестр устарел

Что проверяется:
  - front matter карточки заполнен, статус из допустимого списка;
  - id совпадает с префиксом имени файла, system — с именем папки;
  - id уникален в пределах системы;
  - operation_id существует в api/*.yaml этой системы;
  - (предупреждение) у каждой операции контракта есть карточка.
Зависимость: PyYAML (pip install pyyaml).
"""
import re
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SYSTEMS = ROOT / "systems"
OUT = ROOT / "registry" / "METHODS.md"

REQUIRED = ["id", "title", "system", "operation_id", "status", "contract_version", "direction", "owner", "updated"]
STATUSES = {
    "draft": "⚪ draft",
    "review": "🟡 review",
    "approved": "🔵 approved",
    "released": "🟢 released",
    "deprecated": "⚫ deprecated",
}
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}


def front_matter(path: Path):
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not m:
        return None
    return yaml.safe_load(m.group(1)) or {}


def operations(system_dir: Path):
    """operationId -> (METHOD, path, deprecated) по всем api/*.yaml системы."""
    ops = {}
    for spec in sorted((system_dir / "api").glob("*.y*ml")):
        doc = yaml.safe_load(spec.read_text(encoding="utf-8")) or {}
        for p, item in (doc.get("paths") or {}).items():
            for method, op in (item or {}).items():
                if method in HTTP_METHODS and isinstance(op, dict) and op.get("operationId"):
                    ops[op["operationId"]] = (method.upper(), p, bool(op.get("deprecated")))
    return ops


def main(check_only: bool) -> int:
    errors, warnings, rows = [], [], []

    for system_dir in sorted(d for d in SYSTEMS.iterdir() if d.is_dir()):
        ops = operations(system_dir)
        seen_ids, covered_ops = {}, set()

        for card in sorted((system_dir / "methods").glob("*.md")):
            rel = card.relative_to(ROOT)
            fm = front_matter(card)
            if fm is None:
                errors.append(f"{rel}: нет front matter (блок --- в начале файла)")
                continue

            missing = [k for k in REQUIRED if not fm.get(k) or str(fm.get(k)).startswith("<")]
            if missing:
                errors.append(f"{rel}: не заполнены поля {', '.join(missing)}")

            cid = str(fm.get("id", ""))
            if cid and not card.name.startswith(cid + "-"):
                errors.append(f"{rel}: имя файла должно начинаться с '{cid}-'")
            if cid in seen_ids:
                errors.append(f"{rel}: id {cid} уже используется в {seen_ids[cid]}")
            seen_ids[cid] = rel

            if fm.get("system") != system_dir.name:
                errors.append(f"{rel}: system='{fm.get('system')}', а папка '{system_dir.name}'")

            status = fm.get("status")
            if status not in STATUSES:
                errors.append(f"{rel}: недопустимый status '{status}' (допустимо: {', '.join(STATUSES)})")

            op_id = fm.get("operation_id")
            op = ops.get(op_id)
            if op_id and op is None:
                errors.append(f"{rel}: operation_id '{op_id}' не найден в {system_dir.name}/api/*.yaml")
            if op:
                covered_ops.add(op_id)
                if op[2] and status != "deprecated":
                    warnings.append(f"{rel}: операция помечена deprecated в контракте, а status='{status}'")

            consumers = fm.get("consumers") or []
            rows.append({
                "system": system_dir.name,
                "id": cid,
                "link": "../" + card.relative_to(ROOT).as_posix(),
                "title": fm.get("title", ""),
                "op": f"`{op[0]} {op[1]}`" if op else "—",
                "op_id": f"`{op_id}`" if op_id else "—",
                "status": STATUSES.get(status, str(status)),
                "version": fm.get("contract_version", ""),
                "direction": fm.get("direction", ""),
                "consumers": ", ".join(map(str, consumers)) if isinstance(consumers, list) else str(consumers),
                "owner": fm.get("owner", ""),
                "updated": str(fm.get("updated", "")),
            })

        for op_id in sorted(set(ops) - covered_ops):
            warnings.append(f"{system_dir.name}: у операции '{op_id}' нет карточки метода")

    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")

    content = render(rows)
    if check_only:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if strip_date(current) != strip_date(content):
            print("ERROR registry/METHODS.md устарел — запустите: python3 scripts/build_registry.py")
            errors.append("stale registry")
    elif not errors:
        OUT.parent.mkdir(exist_ok=True)
        OUT.write_text(content, encoding="utf-8")
        print(f"OK    {OUT.relative_to(ROOT)}: {len(rows)} методов")

    return 1 if errors else 0


def strip_date(text: str) -> str:
    return re.sub(r"Сгенерировано: \d{4}-\d{2}-\d{2}", "", text)


def render(rows) -> str:
    out = [
        "# Реестр методов",
        "",
        "> Файл генерируется `scripts/build_registry.py` из front matter карточек. **Не редактируйте вручную.**",
        f"> Сгенерировано: {date.today().isoformat()}",
        "",
    ]
    counts = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    out.append("**Итого:** " + (" · ".join(f"{k}: {v}" for k, v in counts.items()) or "методов пока нет"))
    out.append("")

    for system in sorted({r["system"] for r in rows}):
        out += [
            f"## {system}",
            "",
            "| ID | Метод | Операция | operationId | Статус | Версия | Направление | Потребители | Владелец | Обновлено |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for r in (x for x in rows if x["system"] == system):
            out.append(
                f"| [{r['id']}]({r['link']}) | {r['title']} | {r['op']} | {r['op_id']} | {r['status']} | "
                f"{r['version']} | {r['direction']} | {r['consumers']} | {r['owner']} | {r['updated']} |"
            )
        out.append("")
    return "\n".join(out)


if __name__ == "__main__":
    sys.exit(main("--check" in sys.argv))
