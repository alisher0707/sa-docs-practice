#!/usr/bin/env bash
# «Ночная сверка»: документация в git против реального стенда.
#   ./scripts/drift.sh            # поднять стенд (если не запущен), сверить API и ERD
#   ./scripts/drift.sh --down     # то же, а потом остановить стенд
# Нужны: Docker, Node.js 18+, Python 3 + schemathesis (pip install schemathesis).
# В банке вместо stand/ — адрес тестового стенда и доступ к тестовой БД (переменные ниже).
set -uo pipefail
cd "$(dirname "$0")/.."

COMPOSE="docker compose -f stand/docker-compose.yml"
API_URL="${API_URL:-http://localhost:8080}"
API_KEY="${API_KEY:-demo-key}"
PSQL="${PSQL:-$COMPOSE exec -T db psql -U postgres}"
SPEC="systems/example-system/api/openapi.yaml"
ERD="systems/example-system/erd/client.dbml"

FAIL=0
step() { printf '\n\033[1m▶ %s\033[0m\n' "$1"; }

if [ -z "${SKIP_STAND:-}" ]; then
  step "Стенд: запуск"
  $COMPOSE up -d --build --wait || { echo "Стенд не поднялся"; exit 2; }
fi

step "API: стенд отвечает так, как написано в контракте (Schemathesis)"
if schemathesis run "$SPEC" --url "$API_URL" -H "X-API-Key: $API_KEY" \
     --checks not_a_server_error,status_code_conformance,content_type_conformance,response_schema_conformance,response_headers_conformance \
     --max-examples 30 --no-color; then
  echo "OK    API совпадает с контрактом"
else
  echo "ERROR API разошёлся с контрактом — см. отчёт выше"
  FAIL=1
fi

step "ERD: база стенда совпадает с моделью данных"
python3 scripts/check_drift_erd.py "$ERD" --psql "$PSQL" --db app || FAIL=1

[ "${1:-}" = "--down" ] && $COMPOSE down -v

echo
if [ $FAIL -eq 0 ]; then echo "✓ Документация совпадает с системой"; else echo "✗ Есть расхождения — документация или система требуют исправления"; fi
exit $FAIL
