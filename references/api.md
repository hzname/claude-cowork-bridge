# API cowork-сессии (claude.ai) — шпаргалка

Базовый хост: `https://claude.ai`.
Заголовки: Cookie (claude.ai), `anthropic-version: 2023-06-01` (обязателен), User-Agent приложения Desktop, Origin/Referer `https://claude.ai`.

## Эндпоинты

| Метод/путь | Назначение |
|---|---|
| `GET /v1/code/sessions/<cse>` | мета сессии |
| `GET /v1/code/sessions/<cse>/events?limit=≤500[&cursor=…]` | лента событий, newest-first; `cursor` из `next_cursor` |
| `POST /v1/code/sessions/<cse>/events` | отправка сообщения |
| `GET /v1/code/sessions/<cse>/file?path=<url-encoded>` | скачивание файла, ответ `{"content":"<base64>"}` |

Тело отправки:
```json
{"events":[{"event_type":"user","payload":{"type":"user","uuid":"<новый>","message":{"role":"user","content":"текст"},"client_platform":"desktop_app"}}]}
```
Ответ: `{"results":[{"sequence_num":"…"}]}`. Повтор с тем же uuid отсекается как дубликат.

## События

- `event_type`: user / assistant / result / system / tool_progress / rate_limit_event / control_request / control_response / env_manager_log / active_goal / autocompact_state.
- `sequence_num` — растёт, сравнивать **численно**.
- `payload.agent_id` — событие под-агента (sidechain); для переписки исключать.
- Текст ответа тура — `payload.result` у события `result`.
- Выдача файлов — `tool_use` c `name == SendUserFile`, пути в `input.files` (обычно `/mnt/user-data/outputs/…`).
- `rate_limit_event.rate_limit_info`: окна five_hour / seven_day, `utilization`, `status`.

## Файловая система среды сессии

- Корни для `GET /file?path=`: `/mnt/user-data/outputs`, `/mnt/user-data/working`, `/mnt/user-data/uploads`, `/mnt/user-data/mcp_spill` (проверены); файлы самого воркспейса (`/tmp/claude-0/…/scratchpad/…`) недоступны по API.
- Вложения владельца из интерфейса Desktop попадают в `/root/.claude/uploads/<session-uuid>/<файл>` и доступны сессии сразу.
- Предел одного файла — 25 МиБ (`session_file_too_large`); больше — частями (`split -b 24M`) с манифестами sha256.

## Лимиты выдачи

- `limit` ≤ 500 (при 1000 — 400 «must be … less than or equal to 500»).
- `cursor` — строка-seq; `before=` игнорируется.
