# Карта хранилищ Claude (WSL + Windows) — для поиска/извлечения сессий

## Claude Code (CLI и сессии из Desktop)

WSL (`~/.claude/`):
- `projects/<project-slug>/<session-uuid>.jsonl` — транскрипт сессии; подкаталог `<uuid>/subagents/agent-*.jsonl` — субагенты.
- `<project-slug>` = путь проекта с `/` → `-` (напр. `-home-sg-robot-dog`).
- `sessions/<pid>.json` — дескриптор живой сессии: `{pid, sessionId, cwd, startedAt, version, entrypoint (cli|claude-desktop), hostSessionId: "local_<uuid>", name, status}`.
- `session-env/<uuid>/` — окружение сессии.
- `remote/` — демон моста: `run/<hash>/remote-server.log`, `rpc.sock`, `ccd-cli/<version>` (бинарники демона).
- `.claude.json` (в домашнем каталоге, не в подпапке) — глобальный конфиг: `replBridgePlaceholders: {"cse_…": {pid, procStart, createdAt}}`; кэш артефактов (accountUuid/orgUuid).
- `backups/.claude.json.backup.<ms>` — бэкапы конфига (в них сохраняются старые cse_ ID).

Windows (`C:\Users\<u>\.claude\`): то же самое; плюс `projects\ssh-<uuid>\<uuid>.jsonl` — копии сессий, запускавшихся по SSH (в т.ч. в WSL), и `projects\C--Users-…-…\` для нативных Windows-проектов.

## Записи моста (bridge) и что такое cse_

- В jsonl локальной сессии: `{"type":"bridge-session","sessionId":"<uuid>","bridgeSessionId":"cse_…","ownerAccountUuid":…,"ownerOrganizationUuid":…}` — связка локальной сессии с облачной.
- `cse_` = ID на стороне claude.ai: у Desktop-сессий — «cowork» (URL `claude.ai/cowork/<cse_>`), поток событий `/v1/code/sessions/<cse_>/events/stream` (backend «ccr»). Формат: `cse_` + 24 символа; время из ID не декодируется (не ULID), не тратить время.
- Другой источник связки: `~/.claude.json` → `replBridgePlaceholders{cse_ → pid}` → `sessions/<pid>.json` → sessionId.

## Claude Desktop (MSIX)

Установка: `C:\Program Files\WindowsApps\Claude_<version>_x64__<family>\app\claude.exe` (Electron; в 2026 — Chrome 152 / V8 формат v17). Найти: `powershell.exe Get-AppxPackage *Claude* | Select InstallLocation`.

Данные: `C:\Users\<u>\AppData\Local\Packages\Claude_<family>\LocalCache\Roaming\Claude\`:

- `claude-code-sessions\<accountUuid>\<orgUuid>\local_<uuid>.json` — реестр сессий Desktop: `{sessionId:"local_…", cliSessionId:"<uuid>", cwd, title, model, lastActivityAt, permissionMode}`; префикс `deleted_` — удалённые. Связка Desktop↔CLI: `local_*.json.cliSessionId` ↔ `sessions/<pid>.json.hostSessionId`.
- `IndexedDB\https_claude.ai_0.indexeddb.leveldb` — БД веб-приложения: хранилища `claude-conversation-store` (запись на сессию: `conversationUuid:"cowork:<cse_>", accountUuid, orgUuid, lastOpenedAt, conversationUpdatedAt, approxBytes, messageCount`), `keyval-store`, `frame-db-cache/outbox`, `frame-mcp-cache`.
- `IndexedDB\https_claude.ai_0.indexeddb.blob\…` — крупные значения (V8 serialization; см. ниже).
- `Local Storage\leveldb`, `Session Storage\` — состояние UI: `pinnedOrder`, read-state по `cse_`, снапшоты чата, диалоговые флаги.
- `Cache\Cache_Data\data_N` + `f_*` — Chromium Simple Cache; ключи включают полные URL (`…/v1/code/sessions/<cse_>/events/stream?from_sequence_num=…`); тела бывают сжаты. Полный парсер не обязателен — ключи и фрагменты ищутся `rg -a`.
- `logs\` — `claude.ai-web.log`, `main.log`, `remote-control.log`, `ssh.log`, `cowork_vm_node.log` (ротированные `*1.log` — старые, там оседают старые cse_). Аналогичные логи бывают и в `AppData\Local\Claude\logs\`.
- Прочее: `claude-code-vm\<ver>\claude` (встроенный CLI для VM), `ssh-cli-cache\*.zst` (CLI для SSH-хостов), `config.json` (кэши oauth), `remote-control-state.json`, `ccd-ids.json`, `cowork-enabled-cli-ops.json`, `git-worktrees.json`.

## Примеры команд поиска

```
# точный ID по всем сторонам (ОБЯЗАТЕЛЬНО -a, иначе бинарь пропускается)
rg -a -uu -l '<ID>' /home/sg/.claude /home/sg/.claude.json /mnt/c/Users/<u>/.claude \
  /mnt/c/Users/<u>/AppData/Local/Packages/Claude_*/LocalCache/Roaming/Claude 2>/dev/null

# все cse_ ID в каталоге (уникальные)
rg -a -uu -o 'cse_[A-Za-z0-9]{20,}' '<dir>' 2>/dev/null | sort -u
```

## Формат V8 serialization (значения IndexedDB)

- Заголовок: `0xFF` + varint версии: `ff 0f` = v15 (node), `ff 11` = v17 (Chromium 152).
- Теги: `0x22` (`"`) one-byte string + varint len; `0x63` (`c`) two-byte string + varint len (UTF-16LE); `0x49` (`I`) int32 + varint; `0x6f` (`o`) object.
- node v26.7 поддерживает только v13–15 (проверено перебором версии в заголовке: d,e,f — ok; остальные — «invalid or unsupported version»).
- Для v16+ нужен рантайм с совпадающим V8 (Electron самого приложения в режиме `ELECTRON_RUN_AS_NODE=1`).
- Без совместимого рантайма возможен грубый fallback: извлечение строк по тегам (0x22/0x63 + varint длина) — даёт текст без структуры.
