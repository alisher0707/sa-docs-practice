#!/usr/bin/env bash
# Локальная проверка перед коммитом — те же проверки, что в CI.
#   ./scripts/check.sh
# Нужны: Node.js 18+ (npx), Python 3 + PyYAML. Java + plantuml.jar — опционально.
set -uo pipefail
cd "$(dirname "$0")/.."

FAIL=0
step() { printf '\n\033[1m▶ %s\033[0m\n' "$1"; }
fail() { printf '\033[31m✗ %s\033[0m\n' "$1"; FAIL=1; }
ok()   { printf '\033[32m✓ %s\033[0m\n' "$1"; }

step "OpenAPI: правила стиля (Spectral)"
specs=$(ls systems/*/api/*.y*ml 2>/dev/null)
if [ -n "$specs" ]; then
  if npx --yes @stoplight/spectral-cli lint $specs --ruleset .spectral.yaml --fail-severity=error; then
    ok "Контракты соответствуют правилам"
  else
    fail "Spectral нашёл ошибки"
  fi
else
  ok "Контрактов нет — пропуск"
fi

step "DBML: синтаксис моделей данных"
for f in systems/*/erd/*.dbml; do
  [ -e "$f" ] || continue
  if npx --yes -p @dbml/cli dbml2sql "$f" --postgres > /dev/null; then
    ok "$f"
  else
    fail "$f"
  fi
done

step "Карточки методов и реестр"
if [ "${1:-}" = "--ci" ]; then
  python3 scripts/build_registry.py --check || fail "Реестр / карточки"
else
  python3 scripts/build_registry.py || fail "Реестр / карточки"
fi

step "Версия контракта поднята (сравнение с origin/main)"
if [ "$(git rev-parse --abbrev-ref HEAD 2>/dev/null)" != "main" ] && git rev-parse --verify -q origin/main > /dev/null; then
  python3 scripts/check_version_bump.py origin/main || fail "Версия контракта"
else
  echo "Вы в main или нет origin/main — пропуск"
fi

step "PlantUML: синтаксис диаграмм (если установлен)"
if command -v plantuml > /dev/null; then
  if plantuml -checkonly systems/*/diagrams/*.puml; then ok "Диаграммы"; else fail "PlantUML"; fi
else
  echo "plantuml не установлен — пропуск (проверится в CI)"
fi

step "Секреты и реальные данные (грубая проверка)"
if grep -rInE '(BEGIN (RSA |EC )?PRIVATE KEY|password\s*[:=]\s*\S{4,}|\b(860|986|989|418|510|522|540)[0-9]{10,13}\b)' \
     --include='*.yaml' --include='*.yml' --include='*.md' --include='*.dbml' --include='*.puml' systems templates; then
  fail "Похоже на секрет или номер карты — проверьте строки выше"
else
  ok "Подозрительных строк не найдено"
fi

echo
if [ $FAIL -eq 0 ]; then ok "Все проверки пройдены"; else fail "Есть ошибки — исправьте перед PR"; fi
exit $FAIL
