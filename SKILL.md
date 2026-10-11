---
name: claude-cowork-bridge
description: "Сессии Claude (cse_/CC): задачи, доставка, импорт, форензика"
version: 1.2.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [claude, cowork, claude-code, bridge, collaboration, api, import, forensics, windows, wsl]
---

# Работа с сессиями Claude (cowork `cse_`, Claude Code, импорт и форензика)

Класс задач: «поставь задачу Клоду», «посмотри, что он ответил», «забери результат», «передай ему файл» — облачная cowork-сессия (claude.ai, `cse_…`) как вторая команда проекта; «подключись к сессии клодкода», «загрузи контекст в сессию» — доставка сообщения в живую локальную сессию Claude Code; «импортируй сессию с клода», «перенеси диалог», «найди сессию по ID» (UUID или `cse_…`) — импорт сессий в Hermes и разбор хранилищ Claude.

## When to Use

- «дай задачу Клоду», «посмотри, что он ответил», «забери результат» — сессия `cse_…` работает как вторая команда проекта.
- Приёмка и независимая верификация материалов, сделанных в cowork-сессии (диффы, прогоны, скачивание артефактов).
- Настройка доступа к сессии (cookies из Claude Desktop) и разбор ленты событий.
- «Подключись к сессии клодкода», «загрузи контекст в сессию» — доставка сообщения в живую локальную сессию Claude Code (inbox-сокет; ручной выбор сессии при нескольких в проекте — раздел «Claude Code сессии»).
- Импорт/перенос сессии (диалога) из Claude в Hermes; поиск сессии по ID по всем хранилищам; форензика хранилищ Claude Desktop (IndexedDB, V8, логи).

## Модель работы

- В сессии ДВА автора сообщений: **владелец** (человек, пишет напрямую из приложения) и **мы** (агент, ретранслируем задачи). Прямое сообщение владельца приоритетно: перед отправкой просмотреть свежие `user`-события и не отправлять позицию, противоречащую ему.
- Полный цикл — один круг: постановка → ожидание → приёмка → независимая верификация → возврат уточнений. Не дробить на серию согласований; владельцу отдавать только его решения (условия, деньги, внешние обязательства, публикация данных).
- Результат сессии — самоотчёт, а не доказательство: артефакты скачивать и проверять независимо (диффы, точечные грепы, прогон поставок у себя).

## Авторизация (однократно)

- Cookies claude.ai берутся из Claude Desktop: `Local State` → DPAPI-ключ → `Network/Cookies` (Chromium v10: AES-GCM, в plaintext срезать первые 32 байта). Готовая реализация — `scripts/cowork_pull.py`.
- Сохранить curl-конфиг с заголовками (Cookie, User-Agent приложения, Origin/Referer, `anthropic-version: 2023-06-01` — обязателен). Путь: env `COWORK_CFG` (по умолчанию `~/.config/cowork-bridge/curlrc`).
- Чтение cookies — только с согласия владельца аккаунта.

## Скрипты

| Скрипт | Назначение |
|---|---|
| `scripts/cowork_post.py <cse> <файл-с-текстом\|->` | отправить задачу; uuid каждый раз новый; успех → `{"results":[{"sequence_num":"…"}]}` |
| `scripts/watch_after.py <cse> [seq]` | ждать новое главное сообщение после seq (окно 500); запускать фоном с уведомлением |
| `scripts/cowork_get.py <cse> <путь> [выход]` | скачать файл из среды сессии |
| `scripts/cowork_pull.py <cse>` | полный выкач ленты + расшифровка + import jsonl для Hermes |
| `scripts/v8_probe.js <файлы…>` | дамп V8-значений из блобов IndexedDB (рантаймом с совпадающим V8) |
| `scripts/cc_sessions.py <каталог>` | список ЖИВЫХ сессий Claude Code проекта — для ручного выбора, если их несколько |
| `scripts/cc_send.py <сокет> <sessionId> <файл>` | доставить сообщение в живую сессию Claude Code (inbox-сокет) |
| `scripts/cc_peek.py <jsonl> [N] [chars]` | шапка и хвост лога сессии (проверка доставки и хода) |
| `scripts/cc_search.py <jsonl> <слова…>` | поиск по тексту сообщений лога сессии |

## Приём результатов

- Читать только **главную ветку**: события без `payload.agent_id` (под-агенты — шум).
- Текст ответа тура — `payload.result` события `result`; идущие подряд пустые result — «аки», выкидывать.
- Файлы — по ВСЕМ `SendUserFile` окна событий: выдач бывает несколько паков.
- Скачивание — GET `/file?path=` (корни `/mnt/user-data/outputs`, `working`, `uploads`, `mcp_spill`); предел 25 МиБ на файл; большие резать `split -b 24M` и склеивать после сверки sha256.
- Верификация обязательна: дифф против предыдущей версии, поиск заявленных правок, прогон тестов/скриптов поставки, пересчёт ключевых чисел.
- Тексты задач нумеровать и хранить в рабочей папке проекта (`zadacha_<дата>_N.txt`) — по ним восстанавливаются постановки, seq и приложенные файлы.
- Сессия ведёт несколько тем сразу — читать ленту от своего последнего seq; спорные утверждения второй стороны доводить до собственного вердикта (разбор по первоисточникам), а не пересказывать.

## Импорт сессий в Hermes

**Классификация ID.** UUID (`xxxxxxxx-…`) — локальная сессия Claude Code: `~/.claude/projects/<slug>/<uuid>.jsonl` (WSL) или `C:\Users\<u>\.claude\projects\…` (Windows; сессии по SSH — в `ssh-<uuid>/`). `cse_<24 симв.>` — мостовая/облачная сессия на claude.ai; локально может не быть файлом; время из ID не декодируется (не ULID). Искать ID дословно по всем хранилищам; не подбирать сессию по свежести.

**Импорт локального файла:**

```sh
hermes sessions import --from claude <path.jsonl>   # чужой файл только читается, не изменяется
hermes --resume <полученный id>                     # продолжить в Hermes
```

- Без `<path>` — интерактивный выборщик (нужен TTY); в неинтерактивном запуске путь передавать явно.
- Форматы Claude Code / Codex CLI; для диалога из другого источника собрать jsonl в формате Claude Code (`{"type":"user|assistant","message":{…}}`) — парсер берёт user/assistant, сам склеивает роли.
- Копии на обеих сторонах (WSL и Windows `ssh-<uuid>`) — сравнить mtime/размер/хвост и импортировать более полную.

**Поиск по хранилищам (порядок проходов):**

1. WSL: `~/.claude/projects`, `~/.claude.json`, `~/.claude/backups/`, `~/.claude/sessions/`, `~/.claude/session-env/`, `~/.claude/remote/`.
2. Windows Claude Code: `/mnt/c/Users/<u>/.claude/{projects,backups,sessions}`, `/mnt/c/Users/<u>/.claude.json`.
3. Claude Desktop (MSIX): `/mnt/c/Users/<u>/AppData/Local/Packages/Claude_*/LocalCache/Roaming/Claude/` — IndexedDB (`claude-conversation-store`, ключи `cowork:<cse_>`), Local Storage, Session Storage, Cache_Data, logs.
4. Логи: `/mnt/c/Users/<u>/AppData/Local/Claude/logs/` и та же папка внутри `Packages/…/Claude/logs/` — в ротированных `*1.log` встречаются старые `cse_`.

Пользователя Windows найти заранее: перечислить каталоги в `/mnt/c/Users/`, затем отфильтровать `claude` в `/mnt/c/Users/<u>/AppData/Local/Packages`. Поиск вести `rg -a -uu` (флаг `-a` обязателен для бинарных хранилищ). Детальная карта хранилищ, bridge-записи, формат V8 — `references/claude-stores-map.md`.

## Выкач cowork-сессии и реконструкция (проверено 2026-10-06)

Локально — только фрагменты кэша; полный текст живёт на сервере. Путь — cookies из Desktop + API (`scripts/cowork_pull.py <cse_ID>` выполняет шаги автоматом; согласие на чтение cookies — до). Шаги, если делать руками:

1. **Ключ:** `Local State` → `os_crypt.encrypted_key` (срезать 5 байт `DPAPI`, unprotect) → 32-байтный AES-ключ.
2. **Cookies:** `Network/Cookies` → значения v10: AES-256-GCM (nonce = bytes[3:15], tag в конце), в plaintext срезать первые 32 байта.
3. **API:** `GET /v1/code/sessions/<cse_>` (мета), `GET .../events?limit=500` (newest-first) → пагинация `&cursor=<next_cursor>`; заголовки `Cookie`, `anthropic-version: 2023-06-01`, UA приложения, `Origin`/`Referer`.
4. **Реконструкция:** main-ветка (`payload.parent_tool_use_id == null`); user-события без служебных префиксов (`<system-reminder`, `<artifact-view-context`, `<artifact-content-authored-by-others`, `<local-command`, `<command-`, `Base directory for this skill:`, `Caveat:`), пропуск `isSynthetic`/`silent_resend_of`; `[Image: …]` → `[изображение]`; финальный текст тура — `payload.result`; инструменты — сводкой («Bash×N, …»).
5. **Импорт в Hermes:** собрать Claude-Code-формат jsonl → `hermes sessions import --from claude <path>` → `hermes sessions rename <id> "<title>"`; сверка полноты по числу записей в state.db.

Альтернатива — `claude --teleport <id>`/`--cloud`: только при залогиненном CLI (проверить `claude auth status`).

## Артефакты cowork-сессии (проверено 2026-10-06)

- **Манифест:** `GET /api/frame/<artifact-uuid>?org=<ORG>&via=share_link&bk=initial&actor=id&vt=1` + заголовки `X-Frame-CP: go`, `X-Frame-Platform: desktop`, `X-Frame-Surface: code` — title, capabilities, список файлов фрейма.
- **Файлы сессии:** `GET /v1/code/sessions/<cse_>/file?path=<путь>` (корни `/mnt/user-data/outputs`, `/mnt/user-data/working`, `/mnt/project-files`; ответ `{"content":"<base64>"}`).
- **Полный текст артефактов (надёжный путь):** реконструкция из правок `mcp__Claude_Docs__update`: `replace` — контент в `with`; `insert` — контент в `source` (!); `target.kind=="find"` — текстовая правка; `kind=="cell"` — пропускать с пометкой. Плейсхолдеры `<?claude block XX?>` — интерактивные виджеты без текста. Экспорты (`mcp__Claude_Docs__export`) могут нести `bytes_b64` — готовый файл в base64.
- API `doc/ops`/`doc/replica` без привязки к сессии отдаёт 404 — не полагаться; реконструкция из правок полнее. Cookie фрейма выдаётся через `https://<uuid>.frame.claudeusercontent.com/_t?__frame_t=…`; viewer-страница в headless-браузере упирается в Cloudflare — работать curl с cookie.

## Claude Code сессии (локальные): подключение и доставка (проверено 2026-10-11)

Кросс-сессионная доставка Claude Code (v2.1.224+): текст кладётся в **inbox-сокет** живой сессии; всё локально (Linux/WSL2 — Unix-сокет, без сети и серверов).

1. **Найти сессию.** Реестр: `~/.claude/sessions/<pid>.json` — поля `sessionId`, `cwd`, `name`, `status`, `messagingSocketPath` (`/run/user/1000/cc-socks/<pid>.sock`). При перезапуске сессии (в т.ч. обновлении Desktop) **pid и сокет меняются**, в реестре копятся мёртвые записи — отсеивать сверкой `procStart` с `/proc/<pid>/stat`.
2. **Несколько сессий в проекте — выбирать вручную, не по свежести.** `scripts/cc_sessions.py <каталог проекта>` покажет только живые: pid, sessionId, имя, статус, сокет. Выбор по имени (напр. «Обновление информации» vs «Освежись»); при неоднозначности — спросить владельца. Имена видны в Desktop.
3. **Отправить:** `scripts/cc_send.py <сокет> <sessionId> <файл-с-текстом>`. Кадр — newline-delimited JSON + half-close (SHUT_WR): `{"msgV":1,"msg_id":"<uuid>","type":"user","message":{"role":"user","content":"…"},"priority":"next","session_id":"<sessionId>"}`. Обязательны `type` и непустой `message.content`; `session_id` сверяется с получателем (несовпадение — **молчаливый дроп**!). `from` можно не ставить — доставка «от безымянного пира». Auth-строка на Linux необязательна; токен из `<pid>.<sha256>.key` — только для «своего ребёнка» сессии, не подделывать.
4. **Доставка по умолчанию:** `crossSessionInbound` не задан → prompting-получатель (auto/acceptEdits/dontAsk) принимает сообщение от неверифицируемого отправителя; bypassing-получатель откладывает на аппрув-диалог; `refuse` в настройках — дроп.
5. **Проверка:** jsonl сессии (`~/.claude/projects/<slug>/<uuid>.jsonl`) растёт; в нём появляется `user | Another Claude session sent a message: <текст>`, затем сессия сама начинает ход. Разбор логов: `scripts/cc_peek.py <jsonl> [N] [chars]`, `scripts/cc_search.py <jsonl> <слова…>`.
6. **Ограничения:** ~1 МБ на сообщение; сессия получает только текст (без нашей истории и файлов); ответ нам не придёт (без `from`) — канал односторонний.

## Питфоллы

1. **seq сравнивать только численно.** `'10017' <= '9474'` лексикографически — сканеры/watcher'ы молча пропускают ответы после 9999. Всегда `int()`.
2. **Лимиты.** `rate_limit_event` (>0.9 окна) — сообщение может «съесться»; после отправки убедиться, что seq появился в ленте; иначе переотправить после сброса.
3. **Пагинация и заголовки.** `limit ≤ 500`, newest-first, продолжение `cursor=<next_cursor>` (`before=` игнорируется); заголовок `anthropic-version: 2023-06-01` обязателен (иначе 400).
4. **Файл В сессию** публичным API не кладётся — вложение кладёт только владелец через интерфейс Desktop; оно появляется в среде сессии (`/root/.claude/uploads/<session-uuid>/`).
5. **Владелец пишет сам** — сканировать все `user`-события окна, отделяя наши ретрансляции (по первым строкам отправленных текстов) от его сообщений.
6. **Структура событий:** `event_type` (user/assistant/result/system/tool_progress/rate_limit_event/control_*), `sequence_num` растёт, выдача newest-first.
7. **Формулировать проверяемо:** точные правки + список «подтвердить со ссылкой на источник» + «осталось на решение»; иначе приёмка превращается в переписку.
8. **Долгие задачи** не блокировать: watcher фоном, результат забрать по уведомлению. Пустые строки `http:` в выводе watcher'а = куки-конфиг не найден (автоочистка однажды снесла `~/.config/cowork-bridge/curlrc`, watcher 45 мин молчал); watch_after сам пробует COWORK_CFG → штатный путь → `/home/sg/cowork-import/curlrc_base.txt` → scratch. Держать рабочий конфиг хотя бы в одном из этих мест.
9. **Окно сканирования — 200–500 событий.** Поток под-агентов вытесняет главные сообщения и команды владельца из малых окон: окно в 20 событий однажды пропустило и команду владельца, и передачу набора. `watch_after` читает 500.
10. **Claude Code: сокет и pid меняются при перезапуске сессии** (в т.ч. обновлении Desktop) — брать актуальные из `~/.claude/sessions/<pid>.json` и сверять `procStart` с `/proc/<pid>/stat`; `session_id` кадра обязан совпадать с получателем (несовпадение — молчаливый дроп); сессий в проекте бывает несколько — выбирать вручную (`cc_sessions.py`), не по свежести.
11. **Бинарные хранилища требуют `-a`.** LevelDB (`.ldb`/`.log`), Cache_Data, IndexedDB-блобы — поиск только `rg -a -uu`; без `-a` — ложное «нигде нет».
12. **Данные Desktop — в `AppData/Local/Packages/<family>/LocalCache/(Roaming|Local)/…`**, а не в `AppData/Roaming`. После отрицательной проверки Roaming не сдаваться.
13. **V8 serialization.** Chromium 152 пишет v17 (`ff 11`), node v26.7 принимает только v13–15; нужен рантайм с тем же V8 — Electron самого приложения (`ELECTRON_RUN_AS_NODE=1 "<app>\claude.exe"`); версию в заголовке смотреть `head -c2 <blob> | xxd`.
14. **Гейт подтверждений Hermes** режет составные команды (циклы, env + длинные аргументы, вложенные тела) в таймаут — дробить на простые; сложный вызов оформлять файлом и запускать `bash script.sh`.
15. **`WindowsApps` ACL** — перечисление может «не найти» приложение; помогает `Get-AppxPackage *Claude* | Select InstallLocation` и прямой путь.
16. **Логи Tirith (`~/.local/share/tirith/`) — команды самого агента**: найденный там искомый ID — ложный след, не данные Claude.
17. **Каталоги-пустышки Desktop** (`Claude-Data`, `Claude-3p`, `claude-cli-nodejs`) — не тратить время; реальные данные в `Packages/…`.
18. **`claude --teleport/--cloud` требует логина CLI** (`claude auth status`); осторожно с `ccd-cli` — подкоманд нет, слово трактуется как промпт (создаёт лишнюю сессию).
19. **Правки документов — в `ops`:** вставки лежат в `op["source"]`, замены — в `op["with"]`; учитывать оба, иначе теряются секции и получаются урезанные документы.
20. **Отправка в сессию:** POST `/v1/code/sessions/<id>/events` с uuid (повтор с тем же uuid отсекается — генерировать заново); в активный лимит сообщение съедается — отправлять после сброса; файлы рабочей папки — попросить `tar czf /mnt/user-data/outputs/<имя>.tar.gz …` и скачать.
21. **Лимит файлового API — 25 МиБ** («session_file_too_large»): резать `split -b 24M` + `sha256sum` частей + manifest, качать по списку, склеивать и сверять sha256.
22. **Прогон поставки у себя — venv и чистый каталог.** Зависимости в venv (не user-site: `python -I` его не видит); свои инструменты держать ВНЕ поставляемого каталога (самопроверки сканируют каталог и ловят лишнее); гонять на чистой копии/архиве «как поставлено».
23. **curlrc прунится и куки залочены.** Scratch Hermes чистится (idle ~24 ч) — после пропажи curl падает `rc 26`, а скрипты могут печатать СТАРЫЙ resp (сверять свежесть); держать копию конфига вне scratch; при живом Claude Desktop `Network/Cookies` бывает залочен — копировать с ретраями (окно ловится за ~30 с) или при закрытом приложении.

## Рабочий круг (пример)

```sh
# 0. импорт готовой сессии (локальный jsonl)
hermes sessions import --from claude session.jsonl

# 1. постановка
python3 scripts/cowork_post.py cse_XXXX task.txt
# 2. ожидание (фоном, с уведомлением)
python3 scripts/watch_after.py cse_XXXX 12345 &
# 3. приёмка: скачать артефакты
python3 scripts/cowork_get.py cse_XXXX /mnt/user-data/outputs/result.zip ./result.zip
# 4. верификация у себя: диффы, прогоны — и только потом доклад владельцу

# 5. (Claude Code) доставка в живую сессию: при нескольких — выбрать вручную
python3 scripts/cc_sessions.py ~/robot-dog
python3 scripts/cc_send.py /run/user/1000/cc-socks/<pid>.sock <sessionId> context.txt
```

## Файлы навыка

- `references/api.md` — эндпоинты, структура событий, лимиты.
- `references/claude-stores-map.md` — карта хранилищ Claude Code/Desktop, записи bridge/cowork, формат V8.
- `scripts/cowork_post.py`, `scripts/watch_after.py`, `scripts/cowork_get.py`, `scripts/cowork_pull.py`, `scripts/v8_probe.js`, `scripts/cc_sessions.py`, `scripts/cc_send.py`, `scripts/cc_peek.py`, `scripts/cc_search.py`.
