# Как вносить изменения

Короткая инструкция для аналитика. Процесс целиком — в [PROCESS.md](PROCESS.md).

## Один раз: подготовка

1. Установить Git, VS Code (расширения: *YAML*, *PlantUML*, *DBML Language*, *Markdown Preview Mermaid*), Node.js 18+ и Python 3.
2. `pip install pyyaml`
3. Клонировать репозиторий: `git clone <url>`

## Каждый раз: цикл изменения

```bash
# 1. Свежий main и новая ветка под задачу
git checkout main && git pull
git checkout -b sa/PRJ-123-client-accounts

# 2. Правки
#    новая система  → скопировать структуру systems/example-system/
#    новый метод    → скопировать templates/method-card.md в systems/<sys>/methods/API-NNN-<slug>.md
#    контракт       → systems/<sys>/api/openapi.yaml (+ info.version, + CHANGELOG.md)
#    модель данных  → systems/<sys>/erd/*.dbml

# 3. Проверка — она же пересоберёт registry/METHODS.md
./scripts/check.sh

# 4. Коммит и push
git add .
git commit -m "PRJ-123: API-002 getClientAccounts — активные счета клиента"
git push -u origin sa/PRJ-123-client-accounts
```

5. Открыть Pull Request, заполнить чек-лист из шаблона PR. Статус в карточках — `review`.
6. Отвечать на замечания коммитами в ту же ветку. Обсуждения закрывает тот, кто их открыл.
7. После одобрений PR вливается в `main`. Статус карточек → `approved` (можно в том же PR перед слиянием).

## Правила коммитов

- Формат: `<JIRA>: <что сделано>` — `PRJ-123: API-002 добавлено поле balance`.
- Один коммит — одно логическое изменение. Не смешивайте контракт двух разных задач.

## Релиз (после выхода в прод)

```bash
git checkout main && git pull
# статус карточек → released, CHANGELOG: «Не выпущено» → [X.Y.Z] — дата
git commit -am "example-system: релиз API 1.1.0"
git tag -a example-system-api-v1.1.0 -m "API 1.1.0: getClientAccounts"
git push && git push --tags
```

После тега обновите ссылки в ТЗ / Confluence на этот тег.

## Частые вопросы

| Вопрос | Ответ |
|---|---|
| CI ругается «registry/METHODS.md устарел» | Запустить `python3 scripts/build_registry.py` и закоммитить файл |
| Конфликт в `registry/METHODS.md` при слиянии | Принять любую версию и перезапустить скрипт — файл генерируемый |
| Spectral ругается на правило, а у нас исключение | Обсудить с ведущим аналитиком; исключение оформляется в `.spectral.yaml` с комментарием «почему» |
| Нужно приложить схему от контрагента (PDF) | Не в этот репозиторий, если документ конфиденциальный. В паспорте `IP-*` — название, версия и где хранится |
| Как посмотреть ERD картинкой | Вставить DBML на dbdiagram.io (без конфиденциальных пояснений) или открыть в VS Code с расширением DBML |
| Хочу правку прямо в Apidog | Можно для экспериментов, но в `main` попадает только то, что пришло через PR в `openapi.yaml` |
