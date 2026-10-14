# Артефакты системного анализа

Единый источник истины для контрактов API, карточек методов, моделей данных и диаграмм.
ТЗ и экранные формы ведутся в Confluence и ссылаются сюда **на конкретный тег / коммит**.

| Документ | О чём |
|---|---|
| [PROCESS.md](PROCESS.md) | Процесс работы аналитика: этапы, роли, статусы, версионирование, лучшие практики |
| [PRACTICE.md](PRACTICE.md) | Практика по шагам: пять правил актуальной документации на учебной системе |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Как вносить изменения: ветка → проверка → PR → релиз |
| [registry/METHODS.md](registry/METHODS.md) | Реестр всех методов со статусами (генерируется) |
| [GLOSSARY.md](GLOSSARY.md) | Единый глоссарий |
| [adr/](adr/) | Архитектурные решения |

## Структура

```
.
├── PROCESS.md · CONTRIBUTING.md · GLOSSARY.md
├── .spectral.yaml                 # правила стиля API (исполняемый регламент)
├── .github/
│   ├── workflows/ci.yml           # проверки на каждый PR
│   ├── workflows/release.yml      # публикация по тегу версии: Pages + Confluence
│   ├── workflows/drift.yml        # ночная сверка, при расхождении — Issue
│   ├── pull_request_template.md   # чек-лист PR
│   └── CODEOWNERS                 # кто обязан одобрять
├── scripts/
│   ├── check.sh                   # все проверки локально
│   ├── build_registry.py          # реестр методов + проверка связности
│   ├── check_version_bump.py      # контракт изменён → версия поднята?
│   ├── drift.sh                   # ночная сверка: документация против стенда
│   ├── check_drift_erd.py         # ERD против реальной БД
│   └── publish_confluence.py      # копии страниц в Confluence с версией в шапке
├── stand/                         # учебный стенд в Docker (сервис + БД) — замена тестового стенда банка
├── docs/confluence-review.md      # владелец и дата пересмотра для страниц ТЗ
├── templates/                     # шаблоны: копировать, не править на месте
│   ├── method-card.md · openapi.yaml · erd.dbml · sequence.puml
│   ├── integration-passport.md · adr.md · CHANGELOG.md
│   └── word/                      # .docx-шаблоны ТЗ и экранных форм для Confluence / СЭД
├── adr/
│   └── ADR-0001-docs-as-code.md
├── registry/
│   └── METHODS.md                 # генерируется, руками не редактировать
└── systems/
    └── <system>/
        ├── README.md · CHANGELOG.md
        ├── api/openapi.yaml       # контракт — источник истины
        ├── methods/API-NNN-*.md   # карточки методов
        ├── erd/*.dbml             # модель данных
        ├── diagrams/*.puml        # sequence / state
        └── integrations/IP-*.md   # интеграционные паспорта
```

## Быстрый старт

```bash
pip install pyyaml
./scripts/check.sh
```

`systems/example-system/` — заполненный пример. Скопируйте его под свою систему.
