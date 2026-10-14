# Практика на ноутбуке: пять правил актуальной документации

Тренируемся на учебной системе `example-system` (данные синтетические). Потом переносим в банк.

| Правило | Где тренируем |
|---|---|
| 1. Каждый факт — в одном месте | Этапы 2–3: контракт и ERD только в git |
| 2. Изменение = задача + документация | Этап 4: Pull Request с чек-листом |
| 3. Робот проверяет каждое изменение | Этапы 1, 3, 4: `check.sh` и GitHub Actions |
| 4. Справочник сверяется с системой | Этап 5: стенд в Docker и ночная сверка |
| 5. Владелец и дата пересмотра | Этап 7: Confluence |

Всё запускается в Терминале из папки репозитория.

## Этап 0. Инструменты

```bash
git --version && node -v && python3 --version && docker --version
pip3 install --user pyyaml markdown schemathesis
```

## Этап 1. Локальная проверка

```bash
./scripts/check.sh
```
Ожидаемо: «Все проверки пройдены».

## Этап 2. Репозиторий на GitHub

1. github.com → New repository → `sa-docs-practice`, **Private**, без README.
2. В Терминале:
```bash
git init -b main
git add .
git commit -m "Начальная структура документации"
git remote add origin https://github.com/<ваш-логин>/sa-docs-practice.git
git push -u origin main
```
3. В `.github/CODEOWNERS` заменить `@your-login` на свой логин, закоммитить.

## Этап 3. Защита main и робот

GitHub → репозиторий → Settings → Branches → Add rule → `main`:
- Require a pull request before merging (Approvals: 0 — свой PR одобрить нельзя)
- Require status checks to pass → выбрать `checks`
- Do not allow bypassing the above settings

Проверка: `git push` прямо в `main` должен быть отклонён.

## Этап 4. Изменение через Pull Request

```bash
git checkout -b sa/PRJ-1-middle-name
```
1. В `systems/example-system/api/openapi.yaml` в схему `ClientInfo` добавить поле
   `middleName: { type: string, description: Отчество руководителя }`. **Версию не трогать.**
2. `git commit -am "PRJ-1: отчество руководителя" && git push -u origin sa/PRJ-1-middle-name`
3. Открыть Pull Request → проверка красная: «контракт изменён, а версия осталась».
4. Поднять `info.version` до `1.2.0`, добавить строку в `CHANGELOG.md`, закоммитить, запушить → зелёная.
5. Merge.

## Этап 5. Стенд и ночная сверка

```bash
./scripts/drift.sh
```
Поднимает в Docker сервис и базу (`stand/`), сверяет их с контрактом и ERD.
Ожидаемо: «Документация совпадает с системой».

Имитируем «разработчик поменял систему, а документацию — нет»:
1. В `stand/app/server.py` добавить в ответ клиента `"phone": "+998901234567"`.
2. В `stand/db/init.sql` добавить в таблицу `partner` колонку `phone varchar(16)`.
3. ```bash
   docker compose -f stand/docker-compose.yml down -v
   ./scripts/drift.sh
   ```
   Ожидаемо: два расхождения — недокументированное поле в API (утечка ПДн!) и лишняя колонка в БД.
4. Вернуть как было: `git checkout stand/`.

На GitHub: Actions → `drift` → Run workflow. При расхождении робот сам создаёт Issue с отчётом.

## Этап 6. Релиз и публикация

1. Settings → Pages → Source: **GitHub Actions**.
2. Для Confluence: Settings → Secrets and variables → Actions → New repository secret:

| Секрет | Значение |
|---|---|
| `CONFLUENCE_URL` | `https://<сайт>.atlassian.net/wiki` |
| `CONFLUENCE_DEPLOYMENT` | `cloud` |
| `CONFLUENCE_SPACE` | ключ учебного пространства, например `SAP` |
| `CONFLUENCE_USER` | email учётной записи Atlassian |
| `CONFLUENCE_TOKEN` | API-токен: id.atlassian.com → Security → API tokens |

3. Поставить метку версии:
```bash
git checkout main && git pull
git tag -a example-system-api-v1.2.0 -m "API 1.2.0: отчество руководителя"
git push --tags
```
Ожидаемо: сайт документации на Pages и страницы в Confluence с «Версия example-system-api-v1.2.0» в шапке.

Проверить без отправки: `python3 scripts/publish_confluence.py --dry-run` → `public/confluence/`.

## Этап 7. Пересмотр ТЗ в Confluence

По инструкции [docs/confluence-review.md](docs/confluence-review.md): шапка с владельцем и датой, отчёт по просроченным страницам.

## Этап 8. Перенос в банк

| Что | Практика | Банк |
|---|---|---|
| Репозиторий | личный | новый в организации банка |
| CODEOWNERS | ваш логин | команды банка |
| Approvals в защите main | 0 | по матрице из PROCESS.md |
| Confluence | `cloud`, email + API-токен | `dc`, токен (PAT) технической учётки |
| Стенд для сверки | `stand/` в Docker | тестовый стенд: `SKIP_STAND=1`, `API_URL`, `PSQL` |
| Инструменты (npm, pip, Docker-образы) | из интернета | из внутреннего Nexus / Artifactory |
| Сайт документации | GitHub Pages | Pages, если разрешены, иначе только Confluence |
