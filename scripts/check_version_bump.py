#!/usr/bin/env python3
"""
Проверка «не забыли поднять версию контракта».

  python3 scripts/check_version_bump.py [base_ref]     # по умолчанию origin/main

Для каждого systems/*/api/*.yaml сравнивает текущую версию файла с версией в base_ref:
  - контракт изменился, а info.version та же          → ОШИБКА
  - info.version стала меньше                          → ОШИБКА
  - info.version не по SemVer (X.Y.Z)                  → ОШИБКА
  - контракт изменился, а CHANGELOG.md системы — нет  → предупреждение
Новый контракт (его нет в base_ref) проверяется только на формат версии.
Зависимость: PyYAML.
"""
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def at_base(ref, path):
    r = git("show", f"{ref}:{path}")
    return r.stdout if r.returncode == 0 else None


def semver(v):
    m = SEMVER.match(str(v or ""))
    return tuple(map(int, m.groups())) if m else None


def without_version(doc):
    doc = dict(doc or {})
    info = dict(doc.get("info") or {})
    info.pop("version", None)
    doc["info"] = info
    return doc


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else "origin/main"
    if git("rev-parse", "--verify", base).returncode != 0:
        print(f"ERROR базовая ветка '{base}' не найдена (сделайте git fetch)")
        return 1

    changed_files = set(git("diff", "--name-only", base).stdout.split())
    errors, warnings = [], []

    for spec in sorted(ROOT.glob("systems/*/api/*.y*ml")):
        rel = spec.relative_to(ROOT).as_posix()
        head_doc = yaml.safe_load(spec.read_text(encoding="utf-8")) or {}
        head_v = (head_doc.get("info") or {}).get("version")
        if semver(head_v) is None:
            errors.append(f"{rel}: info.version '{head_v}' не по SemVer (нужно X.Y.Z)")
            continue

        base_text = at_base(base, rel)
        if base_text is None:
            print(f"OK    {rel}: новый контракт, версия {head_v}")
            continue

        base_doc = yaml.safe_load(base_text) or {}
        base_v = (base_doc.get("info") or {}).get("version")
        if without_version(base_doc) == without_version(head_doc):
            continue  # контракт по смыслу не менялся

        if semver(base_v) and semver(head_v) <= semver(base_v):
            if head_v == base_v:
                errors.append(f"{rel}: контракт изменён, а версия осталась {head_v} — поднимите info.version по SemVer")
            else:
                errors.append(f"{rel}: версия уменьшилась {base_v} → {head_v}")
            continue

        changelog = f"{spec.parent.parent.relative_to(ROOT).as_posix()}/CHANGELOG.md"
        if changelog not in changed_files:
            warnings.append(f"{rel}: версия {base_v} → {head_v}, но {changelog} не обновлён")
        print(f"OK    {rel}: {base_v} → {head_v}")

    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
