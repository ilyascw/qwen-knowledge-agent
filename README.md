# Qwen Knowledge Agent

Инженерный эксперимент по встраиванию готового agent CLI в Python-сервис.
Qwen Code запускается как subprocess, общается с приложением через
`stream-json` и получает доступ к внешним системам через MCP.

Из этих блоков собран однопользовательский Telegram-агент с контекстом диалога,
долговременной памятью и read-only поиском по Jira и Confluence.

## Демо

<p align="center">
  <img src="assets/demo.gif" width="420" alt="Qwen Knowledge Agent: память и поиск задач Jira в Telegram">
</p>

На записи агент запоминает пользовательский контекст, продолжает диалог между
отдельными subprocess-запусками и находит назначенные пользователю задачи Jira.
Smoke-test выполнен на относительно компактной модели
`qwen3.6-35b-a3b`.

## Идея

Agent CLI уже содержит цикл общения с моделью, tool calling, MCP, permissions,
сессии и обработку ошибок. Python-приложение использует этот runtime через
процессную границу:

```text
argv:       пользовательский запрос и параметры запуска
stdout:     stream-json с сообщениями, tool calls и final result
stderr:     диагностика ядра и MCP
exit code:  результат выполнения процесса
```

Такой подход сокращает путь от идеи до работающего прототипа. Для следующего
агента можно заменить Telegram, системные инструкции и набор MCP-tools, сохранив
интеграционный слой вокруг Qwen Code.

Здесь эта гипотеза проверена на Qwen Code `0.13.1`. Зафиксированная версия
показывает, что подход работает и на уже не новом агентном ядре.

## Что получилось

```text
┌──────────────┐
│   Telegram   │
└──────┬───────┘
       │ update
       ▼
┌──────────────────────┐
│ aiogram + Python     │  auth, typing, timeout, logs
└──────────┬───────────┘
           │ spawn / resume
           ▼
┌──────────────────────┐
│ Qwen Code subprocess │  agent loop, stream-json
└──────┬────────┬──────┘
       │ MCP    │ MCP
       ▼        ▼
┌───────────┐  ┌──────────────┐
│ Atlassian │  │ SQLite memory│
│ read-only │  │ read / write │
└───────────┘  └──────────────┘
       │        │
       └────┬───┘
            │ result event
            ▼
      Telegram reply
```

Один процесс Python принимает Telegram updates и последовательно обслуживает
одного владельца. Каждый запрос выполняет отдельный headless Qwen-процесс.
Контекст текущего диалога восстанавливается штатным механизмом Qwen sessions.

Retrieval остаётся агентным: модель формулирует JQL/CQL-запросы, выбирает
релевантные артефакты и читает их через MCP. Предварительная индексация
корпоративных данных не требуется.

## Qwen Code как subprocess

Первое сообщение запускается со стабильным session ID:

```text
qwen --prompt <message> \
     --output-format stream-json \
     --approval-mode default \
     --model <model-from-env> \
     --session-id <uuid>
```

Следующие сообщения используют `--resume <uuid>`. Qwen загружает JSONL
transcript и продолжает диалог в новом процессе. Стабильный приватный workspace
сохраняет project hash, по которому Qwen `0.13.1` находит сессию.

Команда `/new` удаляет transcript активной сессии и создаёт новый session ID.
Именованные записи SQLite сохраняются.

### Обработка stdout и stderr

`stdout` читается построчно во время работы процесса. Из потока извлекаются
tool calls и финальное событие `result`:

```text
request=8f21c912 qwen_started session=7c90b15e resumed=true
request=8f21c912 tool_call name=mcp__atlassian__jira_search
request=8f21c912 qwen_waiting elapsed_s=20
request=8f21c912 tool_call name=mcp__atlassian__jira_get_issue
request=8f21c912 qwen_completed duration_ms=18432
```

`stderr` вычитывается параллельно, чтобы pipe buffer не блокировал subprocess.
Runner контролирует общий timeout, exit code, permission errors и наличие
финального текста. Heartbeat показывает в логах состояние длинных LLM-вызовов.

Логи содержат имена tools и технические идентификаторы. Тексты сообщений,
аргументы вызовов и содержимое документов исключены из логирования.

## Два уровня памяти

| Уровень | Хранилище | Назначение | Сброс |
| --- | --- | --- | --- |
| Контекст диалога | Qwen JSONL session | уточняющие вопросы и связный разговор | `/new` |
| Долговременная память | SQLite | устойчивые факты и предпочтения | `forget(key)` |

SQLite-интерфейс состоит из трёх MCP-tools:

```text
recall_memory(query)
remember(key, content)
forget(key)
```

Модель сохраняет факт по явной просьбе пользователя или при обнаружении
устойчивого персонального контекста. Промпт запрещает записывать credentials и
другие секреты. Удаление выполняется по явной команде пользователя.

## Jira и Confluence

`mcp-atlassian` предоставляет пять операций:

```text
jira_search
jira_get_issue
confluence_search
confluence_get_page
confluence_get_page_children
```

Граница read-only закреплена двумя настройками: сервер стартует с
`--read-only`, а Qwen получает точный allowlist из этих пяти tools.
Create/update/delete tools отсутствуют в registry агента.

Ответы по корпоративным данным содержат ссылки на прочитанные Jira issues и
Confluence pages. При недостатке подтверждений агент сообщает об этом явно.

## Telegram

Бот работает через long polling и принимает сообщения только от
`TELEGRAM_USER_ID`. Во время LLM-вызова отображается typing indicator. Ответы
длиннее лимита Telegram делятся на несколько сообщений.

Доступные команды:

| Команда | Действие |
| --- | --- |
| `/start` | кратко показывает возможности агента |
| `/new` | начинает чистую Qwen-сессию, сохраняя SQLite memory |

## Расширяемость ядра

Qwen Code `0.13.1` уже предоставляет стандартные интерфейсы для развития
прототипа:

| Интерфейс | Возможное применение |
| --- | --- |
| MCP tools | новые внешние системы и действия |
| Skills | переиспользуемые доменные workflows |
| Task / subagents | специализированные исполнители и параллельные ветки |
| Hooks | проверки и реакции на lifecycle events |
| Extensions | пакеты с tools, skills, subagents и настройками |
| Tool permissions | отдельные allow/deny-политики для сценариев |

Текущая реализация использует MCP и tool permissions. Остальные интерфейсы
остаются доступными для следующих итераций.

Специализация knowledge-агента описана в
[`agent/QWEN.md`](agent/QWEN.md).

## Границы выполнения

| Слой | Политика |
| --- | --- |
| Telegram | один пользователь из `TELEGRAM_USER_ID` |
| Qwen tools | 5 Atlassian tools + 3 memory tools |
| Files, shell, web | deny rules |
| Atlassian | `--read-only` и `--enabled-tools` |
| Sessions | transcript хранится в приватном volume; `/new` удаляет активный |
| Privacy | telemetry и checkpointing отключены |
| Docker | non-root, read-only root filesystem, `cap_drop: ALL` |
| Persistence | `/data`: SQLite, Qwen runtime и workspace |

Контейнер получает единственную постоянную writable-точку `/data`. Root
filesystem доступен только для чтения.

## Стек

| Задача | Решение |
| --- | --- |
| Agent runtime | Qwen Code 0.13.1 |
| Управление процессом | Python 3.11, `asyncio.subprocess` |
| Telegram transport | aiogram 3 |
| Интеграции | MCP, `mcp-atlassian`, FastMCP |
| Состояние | Qwen sessions, SQLite |
| Конфигурация | Pydantic Settings, `SecretStr`, environment |
| Качество | pytest, strict mypy, Ruff |
| Запуск | Docker Compose |

Модель, OpenAI-compatible endpoint, credentials, timeouts и пути задаются через
environment variables.

## Запуск

Требования: Docker и Telegram bot token от BotFather.

```bash
cp .env.example .env
# заполнить Telegram, LLM и Atlassian credentials
docker compose up --build -d
docker compose logs -f agent
```

Основные переменные:

```dotenv
TELEGRAM_BOT_TOKEN=
TELEGRAM_USER_ID=

QWEN_API_KEY=
QWEN_API_BASE_URL=
QWEN_MODEL=

JIRA_URL=
JIRA_USERNAME=
JIRA_API_TOKEN=
CONFLUENCE_URL=
CONFLUENCE_USERNAME=
CONFLUENCE_API_TOKEN=
```

Pydantic валидирует конфигурацию при старте. `SecretStr` защищает токены от
случайного вывода, а сгенерированный Qwen config содержит только ссылки на
environment variables.

Можно подключить общий env-файл:

```bash
SHARED_ENV_FILE=../eval/.env docker compose up --build -d
```

Остановка с сохранением состояния:

```bash
docker compose down
```

Полное удаление memory и session data:

```bash
docker compose down -v
```

## Проверки

```bash
uv sync --group dev
make check
```

`make check` запускает:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
```

28 тестов покрывают:

- CRUD и поиск SQLite memory;
- lifecycle Qwen-сессии и выбор `--session-id` / `--resume`;
- сохранение memory при `/new`;
- Pydantic settings;
- tool allowlist и read-only Atlassian config;
- отсутствие credentials в сгенерированном Qwen config;
- разбор JSON/JSONL event stream;
- извлечение финального ответа;
- Telegram-specific разбиение сообщений.

GitHub Actions выполняет тот же quality gate на push и pull request.

Реальный smoke-test охватывает Telegram, Qwen subprocess, session resume,
SQLite memory, Jira и Confluence. Следующая итерация качества — закрытый набор
вопросов с ожидаемыми источниками:

| Метрика | Что измеряет |
| --- | --- |
| Source recall | найден ли ожидаемый Jira/Confluence-артефакт |
| Citation validity | подтверждает ли прочитанная ссылка ответ |
| Groundedness | опираются ли утверждения на найденные данные |
| Tool-denial rate | стабильность permissions и MCP-конфигурации |
| Latency p50/p95 | длительность полного Telegram round trip |

## Текущая граница прототипа

- один пользователь;
- последовательная обработка запросов;
- отдельный Qwen subprocess на сообщение;
- lexical search по небольшой таблице памяти;
- Telegram long polling.

Весь контур воспроизводится одной командой `docker compose up --build -d`.
